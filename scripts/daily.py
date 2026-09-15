"""Fetches Diyanet's verse, hadith and prayer of the day.

The API only serves today's content, so every day is kept in a growing archive
(one JSON file per year, committed to the `archive` branch) and the last few
days are published for the app as daily/content.json.

Usage: daily.py ARCHIVE_DIR SITE_DIR
"""

import datetime as dt
import json
import os
import sys

from fetch import Api

FIELDS = ("verse", "verseSource", "hadith", "hadithSource", "pray", "praySource")
PUBLISHED_DAYS = 7
# Türkiye has stayed on UTC+3 all year since 2016
TURKEY = dt.timezone(dt.timedelta(hours=3))


def content_date(day_of_year, today):
    """The date nearest to today with Diyanet's day-of-year, so runs around New Year pick the right year."""
    candidates = [dt.date(year, 1, 1) + dt.timedelta(days=day_of_year - 1)
                  for year in (today.year - 1, today.year, today.year + 1)]
    return min(candidates, key=lambda day: abs(day - today))


def load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")


def main():
    archive_dir, site_dir = sys.argv[1], sys.argv[2]

    api = Api(os.environ["AWQAT_USERNAME"], os.environ["AWQAT_PASSWORD"])
    api.login()
    raw = api.get("/api/DailyContent")

    entry = {k: (raw.get(k) or "").strip() for k in FIELDS}
    if not entry["hadith"] or not entry["verse"]:
        sys.exit("Incomplete daily content: " + json.dumps(raw, ensure_ascii=False))

    today = dt.datetime.now(TURKEY).date()
    day = content_date(int(raw["dayOfYear"]), today)
    entry["dayOfYear"] = int(raw["dayOfYear"])
    print(f"{day} (day {entry['dayOfYear']}, run on {today}):", entry["hadithSource"])

    year_path = os.path.join(archive_dir, "daily-content", f"{day.year}.json")
    year = load(year_path)
    if year.get(day.isoformat()) != entry:
        year[day.isoformat()] = entry
        save(year_path, year)

    # Built from the archive rather than the previously published file, so a lost gh-pages heals itself
    recent = {}
    for offset in range(PUBLISHED_DAYS):
        d = today - dt.timedelta(days=offset)
        stored = load(os.path.join(archive_dir, "daily-content", f"{d.year}.json")).get(d.isoformat())
        if stored:
            recent[d.isoformat()] = {k: stored[k] for k in FIELDS}
    save(os.path.join(site_dir, "daily", "content.json"), {"days": recent})


if __name__ == "__main__":
    main()
