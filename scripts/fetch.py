"""Fetches official Diyanet prayer times for every Turkish district and writes
one JSON file per district into the output directory.

Credentials come from the AWQAT_USERNAME / AWQAT_PASSWORD environment variables.
Existing files in the output directory are merged, so days from earlier runs
survive a failed month.
"""

import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

import pack

API = "https://awqatsalah.diyanet.gov.tr"
TURKEY_ID = 2
MONTHS_AHEAD = 13
KEEP_PAST_DAYS = 31
REQUEST_GAP_SECONDS = 0.3


class Api:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.token = None

    def login(self):
        body = self._send("POST", "/Auth/Login",
                          {"email": self.username, "password": self.password}, auth=False)
        self.token = body["data"]["accessToken"]

    def get(self, path):
        return self._call("GET", path, None)

    def post(self, path, payload):
        return self._call("POST", path, payload)

    def _call(self, method, path, payload):
        for attempt in range(4):
            try:
                body = self._send(method, path, payload)
                return body.get("data")
            except urllib.error.HTTPError as e:
                if e.code == 401:
                    self.login()
                elif e.code in (429, 500, 502, 503, 504):
                    time.sleep(5 * (attempt + 1))
                else:
                    raise
            except urllib.error.URLError:
                time.sleep(5 * (attempt + 1))
        return self._send(method, path, payload).get("data")

    def _send(self, method, path, payload, auth=True):
        time.sleep(REQUEST_GAP_SECONDS)
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if auth:
            headers["Authorization"] = "Bearer " + self.token
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(API + path, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.load(resp)


def parse_date(text):
    text = text.strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", text)
    if m:
        return dt.date(int(m[1]), int(m[2]), int(m[3]))
    m = re.match(r"(\d{2})\.(\d{2})\.(\d{4})", text)
    if m:
        return dt.date(int(m[3]), int(m[2]), int(m[1]))
    raise ValueError("Unrecognised date: " + text)


def add_months(day, months):
    y, m = divmod(day.month - 1 + months, 12)
    return dt.date(day.year + y, m + 1, 1)


def load_existing(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f).get("days", {})
    except (FileNotFoundError, ValueError):
        return {}


def fetch_calendar(api, out_dir, today):
    """Diyanet's religious days, and from them the first day of each Hijri month in Diyanet's calendar,
    which can differ by a day from other Hijri calendars."""
    folder = os.path.join(out_dir, "calendar")
    os.makedirs(folder, exist_ok=True)
    # The API only serves the current and next year, so older years build up here as time passes
    for year in range(today.year, today.year + 2):
        path = os.path.join(folder, f"religious-days-{year}.json")
        data = api.get(f"/api/IslamicReligiousDay/ByYear?year={year}") or []
        if not data and os.path.exists(path):
            continue
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)

    months = {}
    for name in sorted(os.listdir(folder)):
        if not name.startswith("religious-days-"):
            continue
        with open(os.path.join(folder, name), encoding="utf-8") as f:
            for day in json.load(f):
                if day["hijriDay"] == 1:
                    months[f"{day['hijriYear']}-{day['hijriMonth']:02d}"] = day["gregorianDate"][:10]
    with open(os.path.join(folder, "months.json"), "w", encoding="utf-8") as f:
        json.dump(dict(sorted(months.items())), f, separators=(",", ":"))
    print(f"Calendar: {len(months)} Hijri month starts")


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "site"
    os.makedirs(os.path.join(out_dir, "d"), exist_ok=True)

    api = Api(os.environ["AWQAT_USERNAME"], os.environ["AWQAT_PASSWORD"])
    api.login()

    today = dt.date.today()
    start = today.replace(day=1)
    end = add_months(start, MONTHS_AHEAD) - dt.timedelta(days=1)
    oldest_kept = (today - dt.timedelta(days=KEEP_PAST_DAYS)).isoformat()

    try:
        print("Quota:", json.dumps(api.get("/api/Quota/My"), ensure_ascii=False))
    except Exception as e:
        print("Quota check failed:", e)
    try:
        fetch_calendar(api, out_dir, today)
    except Exception as e:
        # Prayer times matter more; publish them even when the calendar fails
        print("FAILED calendar:", e)
        if os.environ.get("CALENDAR_ONLY") == "true":
            sys.exit(1)
    if os.environ.get("CALENDAR_ONLY") == "true":
        return

    with open(os.path.join(os.path.dirname(__file__), "coordinates.json"), encoding="utf-8") as f:
        coordinates = json.load(f)

    districts = []
    failures = []
    for state in api.get(f"/api/Place/States/{TURKEY_ID}"):
        for city in api.get(f"/api/Place/Cities/{state['id']}"):
            district = {"id": city["id"], "name": city["name"],
                        "stateId": state["id"], "state": state["name"]}
            if str(city["id"]) in coordinates:
                district["lat"], district["lon"] = coordinates[str(city["id"])]
            else:
                print("No coordinates for", city["id"], city["name"])
            districts.append(district)

    limit = int(os.environ.get("DISTRICT_LIMIT") or 0)
    if limit:
        districts = districts[:limit]

    days_by_id = {}
    for i, district in enumerate(districts, 1):
        path = os.path.join(out_dir, "d", f"{district['id']}.json")
        days = {k: v for k, v in load_existing(path).items() if k >= oldest_kept}
        try:
            rows = api.post("/api/PrayerTime/DateRange", {
                "cityId": district["id"],
                "startDate": start.isoformat() + "T00:00:00",
                "endDate": end.isoformat() + "T00:00:00",
            }) or []
            for row in rows:
                day = parse_date(row["gregorianDateShortIso8601"]).isoformat()
                days[day] = " ".join(row[k] for k in
                                     ("fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha"))
        except Exception as e:
            failures.append(f"{district['id']} {district['name']}: {e}")
        days_by_id[district["id"]] = days
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"id": district["id"], "days": dict(sorted(days.items()))},
                      f, ensure_ascii=False, separators=(",", ":"))
        if i % 100 == 0:
            print(f"{i}/{len(districts)} districts")

    with open(os.path.join(out_dir, "districts.json"), "w", encoding="utf-8") as f:
        json.dump({"updated": today.isoformat(), "districts": districts},
                  f, ensure_ascii=False, separators=(",", ":"))

    with open(os.path.join(out_dir, "turkey.bin.gz"), "wb") as f:
        packed = pack.pack(districts, days_by_id)
        if pack.unpack(packed) != {d["id"]: days_by_id[d["id"]] for d in districts}:
            sys.exit("turkey.bin.gz does not read back identically")
        f.write(packed)

    print(f"{len(districts)} districts, {len(failures)} failed")
    for line in failures:
        print("FAILED", line)
    # A handful of failures is tolerable because old days are kept; many means something broke.
    if len(failures) > len(districts) // 20:
        sys.exit(1)


if __name__ == "__main__":
    main()
