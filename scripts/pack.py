"""Packs every district's prayer times into one small gzip file for the app.

Layout (big-endian), gzip-compressed:
  "PTD1"
  int32   first date of the file, as days since 1970-01-01
  uint16  number of districts
  per district:
    int32   Diyanet district id
    int32   latitude  x 10000, or INT32_MIN when unknown
    int32   longitude x 10000, or INT32_MIN when unknown
    uint16  index of the district's first day, counted from the file's first date
    uint16  number of days that follow, including missing ones inside the range
    when that number is not 0:
      first day: 6 x uint16 minutes after Turkish local midnight (İmsak, Güneş, Öğle, İkindi, Akşam, Yatsı)
      each later day: 6 x int8 change in minutes from the last day that had times,
                      all six -128 when the day is missing

Times change by a minute or two a day, so the deltas compress to well under 1 KB per district.

Run directly to rebuild turkey.bin.gz from a published site folder: python scripts/pack.py site
"""

import datetime as dt
import gzip
import json
import os
import struct
import sys

MAGIC = b"PTD1"
EPOCH = dt.date(1970, 1, 1)
UNKNOWN_COORD = -2**31
MISSING_DELTA = -128


def to_minutes(line):
    return [int(t[:2]) * 60 + int(t[3:5]) for t in line.split()]


def pack(districts, days_by_id):
    """districts: dicts with id and optional lat/lon; days_by_id: id -> {"YYYY-MM-DD": "HH:MM x6"}."""
    all_dates = sorted({d for days in days_by_id.values() for d in days})
    if not all_dates:
        raise ValueError("No days to pack")
    first = dt.date.fromisoformat(all_dates[0])

    out = bytearray(MAGIC)
    out += struct.pack(">iH", (first - EPOCH).days, len(districts))
    for district in districts:
        lat = round(district["lat"] * 10000) if "lat" in district else UNKNOWN_COORD
        lon = round(district["lon"] * 10000) if "lon" in district else UNKNOWN_COORD
        out += struct.pack(">iii", district["id"], lat, lon)
        days = days_by_id.get(district["id"], {})
        if not days:
            out += struct.pack(">HH", 0, 0)
            continue
        start = dt.date.fromisoformat(min(days))
        length = (dt.date.fromisoformat(max(days)) - start).days + 1
        out += struct.pack(">HH", (start - first).days, length)
        previous = to_minutes(days[start.isoformat()])
        out += struct.pack(">6H", *previous)
        for i in range(1, length):
            line = days.get((start + dt.timedelta(days=i)).isoformat())
            if line is None:
                out += struct.pack(">6b", *[MISSING_DELTA] * 6)
                continue
            minutes = to_minutes(line)
            deltas = [m - p for m, p in zip(minutes, previous)]
            if any(not -127 <= d <= 127 for d in deltas):
                raise ValueError(f"District {district['id']}: jump of more than 127 minutes after {start + dt.timedelta(days=i - 1)}")
            out += struct.pack(">6b", *deltas)
            previous = minutes
    # mtime=0 keeps the output byte-identical when the data is
    return gzip.compress(bytes(out), compresslevel=9, mtime=0)


def unpack(data):
    """Inverse of pack: id -> {"YYYY-MM-DD": "HH:MM x6"}."""
    raw = gzip.decompress(data)
    if raw[:4] != MAGIC:
        raise ValueError("Not a PTD1 file")
    first_day, district_count = struct.unpack_from(">iH", raw, 4)
    pos = 10
    result = {}
    for _ in range(district_count):
        district_id, _lat, _lon, start_index, length = struct.unpack_from(">iiiHH", raw, pos)
        pos += 16
        days = {}
        if length:
            start = EPOCH + dt.timedelta(days=first_day + start_index)
            current = list(struct.unpack_from(">6H", raw, pos))
            pos += 12
            days[start.isoformat()] = current
            for i in range(1, length):
                deltas = struct.unpack_from(">6b", raw, pos)
                pos += 6
                if deltas[0] == MISSING_DELTA:
                    continue
                current = [c + d for c, d in zip(current, deltas)]
                days[(start + dt.timedelta(days=i)).isoformat()] = current
        result[district_id] = {k: " ".join(f"{m // 60:02d}:{m % 60:02d}" for m in v) for k, v in days.items()}
    return result


def main():
    site = sys.argv[1] if len(sys.argv) > 1 else "site"
    with open(os.path.join(site, "districts.json"), encoding="utf-8") as f:
        districts = json.load(f)["districts"]
    days_by_id = {}
    for district in districts:
        with open(os.path.join(site, "d", f"{district['id']}.json"), encoding="utf-8") as f:
            days_by_id[district["id"]] = json.load(f)["days"]
    data = pack(districts, days_by_id)
    if unpack(data) != {d["id"]: days_by_id[d["id"]] for d in districts}:
        raise SystemExit("turkey.bin.gz does not read back identically")
    with open(os.path.join(site, "turkey.bin.gz"), "wb") as f:
        f.write(data)
    print(f"turkey.bin.gz: {len(data)} bytes for {len(districts)} districts")


if __name__ == "__main__":
    main()
