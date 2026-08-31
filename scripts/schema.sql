-- Base schema for the food bank app's data layer.
--
-- food_banks and tracts tables are NOT created here - they're created
-- automatically by load_food_banks.py and load_tracts.py (via pandas
-- to_sql), so their columns always match whatever is actually in your
-- source CSVs. See those scripts for the expected input format.
--
-- GTFS tables (gtfs_stops, gtfs_routes, gtfs_trips, gtfs_stop_times,
-- gtfs_calendar, ...) are likewise created automatically by load_gtfs.py,
-- one per .txt file found in data/gtfs/.

-- Cache of geocoded addresses/zip codes, to avoid repeat calls to the
-- Nominatim geocoding API. Populated later by the live app (logic layer),
-- not by these data-loading scripts.
CREATE TABLE IF NOT EXISTS geocode_cache (
    query      TEXT PRIMARY KEY,   -- the zip code or address that was geocoded
    lat        REAL,
    lon        REAL,
    fetched_at TEXT                -- ISO timestamp, so you can expire old entries later
);
