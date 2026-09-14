"""The 2016 Istanbul unified Hijri calendar rule that Diyanet follows, used to build the app's month-start table.

A month starts the day after an evening on which, at sunset somewhere on Earth before 00:00 UTC, the moon is at
least 5 degrees high (topocentric) and 8 degrees from the sun (geocentric); or, after 00:00 UTC, the same holds on
the American mainland and conjunction came before dawn in Wellington.

Requires: pip install astronomy-engine
"""
import datetime as dt

import astronomy as A

ALT_MIN = 5.0
ELONG_MIN = 8.0
LAT_STEP = 5
LON_STEP = 5
LAT_LIMIT = 60
REFINE_STARTS = 60
REFINE_MARGIN = 3.0
MIN_STEP = 0.1
WELLINGTON = A.Observer(-41.29, 174.78, 0)

# Coarse outlines of mainland North and South America as (lat, lon) vertices
NORTH_AMERICA = [(70, -165), (72, -125), (70, -95), (74, -80), (60, -64), (52, -56), (45, -61), (41, -70),
                 (35, -75), (30, -81), (25, -80), (30, -84), (29, -95), (22, -97), (19, -96), (21, -87),
                 (15, -83), (9, -78), (7, -78), (8, -83), (13, -88), (16, -95), (20, -105), (23, -110),
                 (31, -113), (32, -117), (38, -123), (48, -125), (55, -131), (59, -139), (60, -147),
                 (57, -157), (54, -164), (60, -165), (66, -168)]
SOUTH_AMERICA = [(12, -72), (11, -62), (5, -52), (-5, -35), (-13, -38), (-23, -42), (-34, -53), (-39, -57),
                 (-42, -63), (-52, -68), (-55, -67), (-54, -72), (-46, -75), (-37, -73), (-18, -70),
                 (-14, -76), (-5, -81), (1, -80), (7, -78), (9, -76)]


def inside(polygon, lat, lon):
    hit = False
    for (y1, x1), (y2, x2) in zip(polygon, polygon[1:] + polygon[:1]):
        if (y1 > lat) != (y2 > lat) and lon < x1 + (lat - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


def in_americas(lat, lon):
    return inside(NORTH_AMERICA, lat, lon) or inside(SOUTH_AMERICA, lat, lon)


def t_of(d: dt.datetime):
    return A.Time.Make(d.year, d.month, d.day, d.hour, d.minute, d.second)


def to_dt(t):
    return t.Utc().replace(tzinfo=None)


def criteria_at(obs, t):
    eq = A.Equator(A.Body.Moon, t, obs, True, True)
    hor = A.Horizon(t, obs, eq.ra, eq.dec, A.Refraction.Airless)
    elong = A.AngleFromSun(A.Body.Moon, t)
    return hor.altitude >= ALT_MIN and elong >= ELONG_MIN


def score(evening, conjunction, midnight, nz_ok, lat, lon):
    """min(altitude - 5, elongation - 8) at local sunset, or None where the sunset does not count."""
    if not -89 < lat < 89:
        return None
    lon = (lon + 180) % 360 - 180
    obs = A.Observer(lat, lon, 0)
    local_noon = dt.datetime.combine(evening, dt.time(12)) - dt.timedelta(hours=lon / 15)
    s = A.SearchRiseSet(A.Body.Sun, obs, A.Direction.Set, t_of(local_noon), 1)
    if s is None:
        return None
    sunset = to_dt(s)
    if sunset <= conjunction:
        return None
    if sunset >= midnight and not (nz_ok and in_americas(lat, lon)):
        return None
    eq = A.Equator(A.Body.Moon, s, obs, True, True)
    alt = A.Horizon(s, obs, eq.ra, eq.dec, A.Refraction.Airless).altitude
    return min(alt - ALT_MIN, A.AngleFromSun(A.Body.Moon, s) - ELONG_MIN)


def evening_qualifies(evening: dt.date, conjunction: dt.datetime):
    """Does the month start on evening + 1 day? Coarse grid, then a narrowing search near the best points."""
    midnight = dt.datetime.combine(evening + dt.timedelta(days=1), dt.time())
    nz_dawn = A.SearchAltitude(A.Body.Sun, WELLINGTON, A.Direction.Rise,
                               t_of(midnight - dt.timedelta(hours=12)), 1, -18)
    nz_ok = nz_dawn is not None and conjunction < to_dt(nz_dawn)
    scored = []
    for lat in range(-LAT_LIMIT, LAT_LIMIT + 1, LAT_STEP):
        for lon in range(-180, 180, LON_STEP):
            v = score(evening, conjunction, midnight, nz_ok, lat, lon)
            if v is not None:
                if v >= 0:
                    return True
                scored.append((v, lat, lon))
    scored.sort(reverse=True)
    for v, lat, lon in scored[:REFINE_STARTS]:
        if v < -REFINE_MARGIN:
            break
        step = LAT_STEP / 2
        while step >= MIN_STEP:
            improved = False
            for dlat, dlon in ((step, 0), (-step, 0), (0, step), (0, -step), (step, step), (step, -step), (-step, step), (-step, -step)):
                w = score(evening, conjunction, midnight, nz_ok, lat + dlat, lon + dlon)
                if w is not None and w > v:
                    v, lat, lon, improved = w, lat + dlat, lon + dlon, True
                    if v >= 0:
                        return True
            if not improved:
                step /= 2
    return False


def month_starts(from_date: dt.date, to_date: dt.date):
    t = t_of(dt.datetime.combine(from_date, dt.time()))
    result = []
    while True:
        c = A.SearchMoonPhase(0, t, 40)
        conj = to_dt(c)
        if conj.date() > to_date:
            return result
        evening = conj.date() - dt.timedelta(days=1)
        while not evening_qualifies(evening, conj):
            evening += dt.timedelta(days=1)
        result.append((conj, evening + dt.timedelta(days=1)))
        t = c.AddDays(20)

