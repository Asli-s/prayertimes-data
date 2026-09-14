"""Builds Türkiye's Hijri month starts as the app's bundled table (about 3 minutes on 24 cores).

Run from this folder, then copy hijri_month_starts.txt to the app's app/src/main/resources/.
"""
import datetime as dt
import multiprocessing as mp

import hijri_rule as H

# Anchor: Diyanet's 1 Ramazan 1447
ANCHOR_MONTH = 1447 * 12 + 8
ANCHOR_START = dt.date(2026, 2, 19)
FIRST = (1438, 1)
LAST = (1525, 12)


def starts_for_year(year):
    return H.month_starts(dt.date(year, 1, 1), dt.date(year, 12, 31))


if __name__ == "__main__":
    with mp.Pool() as pool:
        results = pool.map(starts_for_year, range(2016, 2103))
    starts = sorted({s for year in results for _, s in year})
    index = starts.index(ANCHOR_START)
    labelled = {}
    for i, s in enumerate(starts):
        m = ANCHOR_MONTH + (i - index)
        labelled[(m // 12, m % 12 + 1)] = s
    first = labelled[FIRST]
    months = [labelled[(y, mo)] for y in range(FIRST[0], LAST[0] + 1) for mo in range(1, 13)]
    months.append(labelled[(LAST[0] + 1, 1)])
    lengths = "".join("9" if (b - a).days == 29 else "0" if (b - a).days == 30 else "?" for a, b in zip(months, months[1:]))
    assert set(lengths) <= {"9", "0"}, lengths
    with open("hijri_month_starts.txt", "w", encoding="utf-8", newline="\n") as f:
        f.write("# Hijri month starts in Türkiye's calendar (2016 İstanbul unified Hijri calendar rule), generated.\n")
        f.write("# First line: first Hijri year, month and its Gregorian start. Second line: one character per month,\n")
        f.write("# 9 for a 29-day month and 0 for a 30-day month.\n")
        f.write(f"{FIRST[0]} {FIRST[1]} {first.isoformat()}\n{lengths}\n")
    print("months", len(lengths), "first", first)
