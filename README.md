# Food bank app — data layer

Scripts that build `foodbank_app.db` (SQLite) from three source files. Tested
end-to-end against synthetic sample data — all scripts run cleanly and
produce the expected tables.

## Setup

Place your three source files here, in a `data/` folder next to `scripts/`:

```
foodbank_app/
  data/
    food_banks.csv      <- columns: name, address, lat, lon, hours
    usda_atlas.csv       <- full USDA Food Access Research Atlas CSV
    gtfs/                <- unzipped GTFS feed (stops.txt, routes.txt,
                             trips.txt, stop_times.txt, calendar.txt, ...)
  scripts/
    schema.sql
    load_food_banks.py
    load_gtfs.py
    load_tracts.py
    build_db.py
```

Where to get each file:
- `food_banks.csv` — compile by hand from the Union County Resource Guide
  and foodpantries.org/co/nj-union (name, address, then geocode each
  address to get lat/lon).
- `usda_atlas.csv` — download from
  https://www.ers.usda.gov/data-products/food-access-research-atlas
  (the national file is fine — `load_tracts.py` filters it to Union County,
  FIPS prefix `34039`, automatically).
- `gtfs/` — download the NJ Transit feed from mobilitydatabase.org (no
  login needed to download) and unzip it into this folder.

## Build the database

```
cd scripts
pip install pandas
python build_db.py
```

This creates `foodbank_app.db` one level up, with tables: `food_banks`,
`tracts`, `geocode_cache`, and one `gtfs_*` table per GTFS file (e.g.
`gtfs_stops`, `gtfs_routes`, `gtfs_stop_times`).

Re-run `python build_db.py` any time to rebuild from scratch — it deletes
and recreates the database file each time, so it's always safe to re-run.

## Notes

- `load_tracts.py` is tolerant of minor USDA column-naming differences
  between Atlas releases (see `COLUMN_CANDIDATES` in that file) — if it
  errors out looking for a column, open the CSV and add the actual column
  name to the relevant list.
- `coverage_score` in the `tracts` table is left blank on purpose — that
  gets computed in the next layer (logic layer), once food bank coordinates
  and tract centroids are both loaded, as distance-to-nearest-food-bank
  combined with poverty rate and vehicle access.
- `geocode_cache` is created empty — it's used later by the live app to
  avoid repeat calls to the Nominatim geocoding API.
