# prayertimes-data

Official prayer times for Turkish districts, published monthly from the
Diyanet İşleri Başkanlığı Awqat Salah API.

Kaynak: Diyanet İşleri Başkanlığı

- `districts.json` — district list (`id`, `name`, `stateId`, `state`, `lat`, `lon`)
- `turkey.bin.gz` — every district's times in one compact file (about 0.5 MB) for the app; layout in `scripts/pack.py`
- `d/{id}.json` — `days` maps `YYYY-MM-DD` to `"imsak güneş öğle ikindi akşam yatsı"`

District coordinates in `scripts/coordinates.json` are district centres from
Wikidata (CC0); province centres are reference points fitted to Diyanet's
published times. Districts added by Diyanet later are listed without
coordinates until they are added there.
