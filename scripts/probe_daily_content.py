"""Prints what the Awqat Salah daily content endpoints return, to decide how the
app can show a verse, hadith or prayer of the day. Publishes nothing.
"""

import datetime as dt
import json
import os
import urllib.error

from fetch import Api


def show(api, path):
    print("=" * 20, path)
    try:
        print(json.dumps(api.get(path), ensure_ascii=False, indent=1)[:6000])
    except urllib.error.HTTPError as e:
        print("HTTP", e.code, e.read()[:500].decode("utf-8", "replace"))
    except Exception as e:
        print("FAILED:", e)


def main():
    api = Api(os.environ["AWQAT_USERNAME"], os.environ["AWQAT_PASSWORD"])
    api.login()

    today = dt.date.today()
    later = today + dt.timedelta(days=60)

    show(api, "/api/Quota/My")
    show(api, "/api/DailyContent")
    show(api, f"/api/DailyContent/VerseHadithAndPrayer?date={today}")
    show(api, f"/api/DailyContent/VerseHadithAndPrayer?date={today}&language=tr")
    show(api, f"/api/DailyContent/VerseHadithAndPrayer?date={today}&language=en")
    show(api, f"/api/DailyContent/VerseHadithAndPrayer?date={later}&language=tr")
    show(api, f"/api/DailyContent/ReligiousCalendar?date={today}&language=tr")
    show(api, "/api/Quota/My")


if __name__ == "__main__":
    main()
