"""
Load one or more GTFS feeds into the SQLite database. Each transit agency's
feed lives in its own subfolder under data/gtfs/, e.g.:

    data/gtfs/
      nj_transit/
        stops.txt
        routes.txt
        trips.txt
        stop_times.txt
        calendar_dates.txt
      mta_nyc/
        stops.txt
        ...

All feeds get merged into shared tables (gtfs_stops, gtfs_routes, etc.), each
row tagged with a feed_id column so you can tell which agency it came from.
IDs (stop_id, trip_id, route_id, service_id, agency_id) are prefixed with
the feed folder's name - e.g. stop_id "1001" in nj_transit becomes
"nj_transit::1001" - because different agencies commonly reuse the same raw
numeric IDs, and without prefixing, loading a second agency's feed could
silently collide with the first agency's stops or trips.

Caveat worth knowing: this assumes each feed's core files share the same
column layout (true for the required GTFS columns, not guaranteed for every
optional column some agencies add). This has only been tested with one real
feed (NJ Transit) plus synthetic multi-feed data - if a second real agency's
feed has a very different optional-column set, the append step may need a
small tweak.
"""
import sqlite3
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "foodbank_app.db"
GTFS_DIR = BASE_DIR / "data" / "gtfs"

EXPECTED_FILES = ["stops.txt", "routes.txt", "trips.txt", "stop_times.txt"]

# Only these core files are loaded. shapes.txt (route-line polyline geometry)
# is never used by this app and can be huge, so it's left out. Everything
# else some agencies ship (frequencies.txt, transfers.txt, fare files, etc.)
# is also irrelevant here - allowlisting keeps a new file type in some
# agency's feed from silently becoming a new table instead of just being
# ignored.
ALLOWED_FILES = {
    "agency.txt",
    "calendar.txt",
    "calendar_dates.txt",
    "routes.txt",
    "stops.txt",
    "trips.txt",
    "stop_times.txt",
}

# Files -> columns that are IDs referencing other GTFS files. These get
# prefixed with the feed name so multiple agencies can share these tables
# without their raw IDs colliding.
ID_COLUMNS = {
    "stops.txt": ["stop_id"],
    "routes.txt": ["route_id", "agency_id"],
    "trips.txt": ["trip_id", "route_id", "service_id"],
    "stop_times.txt": ["trip_id", "stop_id"],
    "calendar.txt": ["service_id"],
    "calendar_dates.txt": ["service_id"],
    "agency.txt": ["agency_id"],
}


def _prefix_ids(df: pd.DataFrame, filename: str, feed_id: str) -> pd.DataFrame:
    for col in ID_COLUMNS.get(filename, []):
        if col in df.columns:
            df[col] = df[col].apply(lambda v: f"{feed_id}::{v}" if pd.notna(v) else v)
    return df


def load_gtfs(gtfs_dir: Path = GTFS_DIR, db_path: Path = DB_PATH) -> dict:
    if not gtfs_dir.exists():
        raise FileNotFoundError(f"Could not find {gtfs_dir}.")

    feed_dirs = [d for d in sorted(gtfs_dir.iterdir()) if d.is_dir()]
    if not feed_dirs:
        raise FileNotFoundError(
            f"No feed subfolders found in {gtfs_dir}. Each transit agency's GTFS "
            f"files should live in its own subfolder, e.g. data/gtfs/nj_transit/*.txt "
            f"instead of loose .txt files directly in data/gtfs/."
        )

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    counts = {}
    tables_seen = set()

    for feed_dir in feed_dirs:
        feed_id = feed_dir.name
        txt_files = [f for f in sorted(feed_dir.glob("*.txt")) if f.name in ALLOWED_FILES]
        if not txt_files:
            print(f"[{feed_id}] Warning: no .txt files found, skipping")
            continue

        missing = [f for f in EXPECTED_FILES if not (feed_dir / f).exists()]
        if missing:
            print(f"[{feed_id}] Warning: missing {missing} (some lookups may not work)")

        for txt_file in txt_files:
            table_name = f"gtfs_{txt_file.stem}"
            df = pd.read_csv(txt_file, dtype=str, low_memory=False)
            df = _prefix_ids(df, txt_file.name, feed_id)
            df["feed_id"] = feed_id

            if_exists = "replace" if table_name not in tables_seen else "append"
            if if_exists == "append":
                # Different agencies' GTFS files don't always share the same
                # optional columns (e.g. some routes.txt have network_id,
                # others don't). A plain append crashes if this feed's
                # dataframe has a column the table doesn't have yet, so widen
                # the table first for any new columns.
                existing_cols = {
                    row[1] for row in cur.execute(f"PRAGMA table_info({table_name})").fetchall()
                }
                new_cols = [c for c in df.columns if c not in existing_cols]
                for col in new_cols:
                    cur.execute(f'ALTER TABLE {table_name} ADD COLUMN "{col}" TEXT')
                if new_cols:
                    conn.commit()
            df.to_sql(table_name, conn, if_exists=if_exists, index=False)
            tables_seen.add(table_name)
            counts[f"{feed_id}/{table_name}"] = len(df)
            print(f"[{feed_id}] Loaded {len(df)} rows into {table_name}")

    if not counts:
        raise FileNotFoundError(f"No usable GTFS data found under {gtfs_dir}.")

    for stmt in [
        "CREATE INDEX IF NOT EXISTS idx_stop_times_stop_id ON gtfs_stop_times(stop_id)",
        "CREATE INDEX IF NOT EXISTS idx_stop_times_trip_id ON gtfs_stop_times(trip_id)",
        "CREATE INDEX IF NOT EXISTS idx_trips_route_id ON gtfs_trips(route_id)",
        "CREATE INDEX IF NOT EXISTS idx_stops_feed_id ON gtfs_stops(feed_id)",
    ]:
        try:
            cur.execute(stmt)
        except sqlite3.OperationalError as e:
            print(f"Skipped an index (table/column not present yet): {e}")
    conn.commit()
    conn.close()

    return counts


if __name__ == "__main__":
    load_gtfs()
