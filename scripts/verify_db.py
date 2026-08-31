"""
Sanity-check foodbank_app.db after running build_db.py.

Run this any time you want to confirm your real data loaded correctly
before moving on to the logic layer:

    python verify_db.py

It checks that expected tables exist, that row counts look sane, that
coordinates fall within a reasonable US bounding box (a good way to
catch garbage geocodes, like 0,0 or a swapped lat/lon), and runs a couple of
referential-integrity checks between GTFS tables. Prints PASS/WARN/FAIL per
check, plus a few sample rows so you can eyeball the actual data. Tables
that haven't been loaded yet (e.g. you haven't added the GTFS feed) show up
as WARN, not FAIL, so this is safe to run at any stage of data collection.
"""
import datetime
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "foodbank_app.db"

# Rough bounding box for the continental US + AK/HI - food banks and GTFS
# stops can now come from any state, so this replaced the old NJ-only box.
# Anything outside this is almost certainly a bad geocode.
US_BOUNDS = {"lat": (18.0, 72.0), "lon": (-179.0, -65.0)}

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"


def _report(status, msg):
    print(f"[{status}] {msg}")


def table_exists(cur, name):
    return (
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone()
        is not None
    )


def check_food_banks(cur):
    print("\n--- food_banks ---")
    if not table_exists(cur, "food_banks"):
        _report(FAIL, "food_banks table does not exist - run load_food_banks.py")
        return

    count = cur.execute("SELECT COUNT(*) FROM food_banks").fetchone()[0]
    if count == 0:
        _report(FAIL, "food_banks table is empty")
        return
    _report(PASS, f"{count} rows loaded")

    null_coords = cur.execute(
        "SELECT COUNT(*) FROM food_banks WHERE lat IS NULL OR lon IS NULL"
    ).fetchone()[0]
    _report(WARN if null_coords else PASS,
            f"{null_coords} row(s) missing lat/lon" if null_coords else "no missing coordinates")

    out_of_bounds = cur.execute(
        "SELECT name, lat, lon FROM food_banks WHERE "
        "lat NOT BETWEEN ? AND ? OR lon NOT BETWEEN ? AND ?",
        (*US_BOUNDS["lat"], *US_BOUNDS["lon"]),
    ).fetchall()
    if out_of_bounds:
        _report(FAIL, f"{len(out_of_bounds)} row(s) outside the US bounding box (likely bad geocode):")
        for row in out_of_bounds[:10]:
            print("   ", row)
        if len(out_of_bounds) > 10:
            print(f"    ... and {len(out_of_bounds) - 10} more")
    else:
        _report(PASS, "all coordinates fall within the US bounding box")

    dupes = cur.execute(
        "SELECT lat, lon, COUNT(*) c FROM food_banks GROUP BY lat, lon HAVING c > 1"
    ).fetchall()
    if dupes:
        _report(WARN, f"{len(dupes)} coordinate pair(s) shared by more than one food bank "
                      "(fine for a first pass, but those pins will stack on the map)")

    print("Sample rows:")
    for row in cur.execute("SELECT name, lat, lon FROM food_banks LIMIT 5"):
        print("   ", row)


def check_tracts(cur):
    print("\n--- tracts ---")
    if not table_exists(cur, "tracts"):
        _report(WARN, "tracts table does not exist yet - run load_tracts.py once you have usda_atlas.csv")
        return

    count = cur.execute("SELECT COUNT(*) FROM tracts").fetchone()[0]
    if count == 0:
        _report(FAIL, "tracts table is empty")
        return
    _report(PASS, f"{count} rows loaded")

    # No longer assumes a single county - tracts may be scoped to one county,
    # one state, several states, or nationwide (see load_tracts.py's
    # fips_prefix argument). These checks work at any scope instead.
    distinct_states = cur.execute("SELECT COUNT(DISTINCT state) FROM tracts").fetchone()[0]
    _report(PASS, f"covers {distinct_states} distinct state value(s)")

    bad_geoid = cur.execute(
        "SELECT COUNT(*) FROM tracts WHERE geoid IS NULL OR LENGTH(geoid) != 11"
    ).fetchone()[0]
    _report(
        WARN if bad_geoid else PASS,
        f"{bad_geoid} row(s) have a malformed geoid (expected 11 digits)"
        if bad_geoid else "all geoids are well-formed (11 digits)",
    )

    bad_poverty = cur.execute(
        "SELECT COUNT(*) FROM tracts WHERE poverty_rate IS NOT NULL "
        "AND (poverty_rate < 0 OR poverty_rate > 100)"
    ).fetchone()[0]
    _report(WARN if bad_poverty else PASS,
            f"{bad_poverty} row(s) have a poverty_rate outside 0-100" if bad_poverty else "poverty_rate values look sane")

    print("Sample rows:")
    for row in cur.execute("SELECT geoid, county, poverty_rate, lila_1_10 FROM tracts LIMIT 5"):
        print("   ", row)


def check_gtfs(cur):
    print("\n--- GTFS tables ---")
    expected = ["gtfs_stops", "gtfs_routes", "gtfs_trips", "gtfs_stop_times", "gtfs_calendar"]
    missing = [t for t in expected if not table_exists(cur, t)]
    if missing:
        _report(WARN, f"missing GTFS tables (run load_gtfs.py once you have a feed): {missing}")

    present = [t for t in expected if table_exists(cur, t)]
    for t in present:
        count = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        _report(PASS if count > 0 else FAIL, f"{t}: {count} rows")

    if table_exists(cur, "gtfs_stops"):
        has_feed_id = cur.execute("PRAGMA table_info(gtfs_stops)").fetchall()
        if any(col[1] == "feed_id" for col in has_feed_id):
            print("Feeds loaded (by stop count):")
            for feed_id, n in cur.execute(
                "SELECT feed_id, COUNT(*) FROM gtfs_stops GROUP BY feed_id ORDER BY feed_id"
            ).fetchall():
                print(f"    {feed_id}: {n} stops")

        bad_stops = cur.execute(
            "SELECT COUNT(*) FROM gtfs_stops WHERE "
            "CAST(stop_lat AS REAL) NOT BETWEEN ? AND ? OR CAST(stop_lon AS REAL) NOT BETWEEN ? AND ?",
            (*US_BOUNDS["lat"], *US_BOUNDS["lon"]),
        ).fetchone()[0]
        if bad_stops:
            _report(WARN, f"{bad_stops} GTFS stop(s) fall outside the US bounding box (check for a bad feed)")
        else:
            _report(PASS, "all GTFS stops fall within the US bounding box")

    if table_exists(cur, "gtfs_stop_times") and table_exists(cur, "gtfs_trips"):
        orphan_trips = cur.execute(
            "SELECT COUNT(*) FROM gtfs_stop_times st "
            "LEFT JOIN gtfs_trips t ON st.trip_id = t.trip_id "
            "WHERE t.trip_id IS NULL"
        ).fetchone()[0]
        _report(FAIL if orphan_trips else PASS,
                f"{orphan_trips} stop_times row(s) reference a trip_id not in gtfs_trips" if orphan_trips
                else "every stop_time references a valid trip")

    if table_exists(cur, "gtfs_stop_times") and table_exists(cur, "gtfs_stops"):
        orphan_stops = cur.execute(
            "SELECT COUNT(*) FROM gtfs_stop_times st "
            "LEFT JOIN gtfs_stops s ON st.stop_id = s.stop_id "
            "WHERE s.stop_id IS NULL"
        ).fetchone()[0]
        _report(FAIL if orphan_stops else PASS,
                f"{orphan_stops} stop_times row(s) reference a stop_id not in gtfs_stops" if orphan_stops
                else "every stop_time references a valid stop")

    if table_exists(cur, "gtfs_calendar"):
        print("Service date range(s):")
        for row in cur.execute("SELECT service_id, start_date, end_date FROM gtfs_calendar LIMIT 5"):
            print("   ", row)
        today = datetime.date.today().strftime("%Y%m%d")
        expired = cur.execute("SELECT COUNT(*) FROM gtfs_calendar WHERE end_date < ?", (today,)).fetchone()[0]
        total = cur.execute("SELECT COUNT(*) FROM gtfs_calendar").fetchone()[0]
        if total and expired == total:
            _report(FAIL, "every service in gtfs_calendar has already expired - download a fresher feed")
        elif expired:
            _report(WARN, f"{expired} of {total} service(s) in gtfs_calendar have expired")


def check_geocode_cache(cur):
    print("\n--- geocode_cache ---")
    if not table_exists(cur, "geocode_cache"):
        _report(FAIL, "geocode_cache table missing - re-run schema.sql")
        return
    count = cur.execute("SELECT COUNT(*) FROM geocode_cache").fetchone()[0]
    _report(PASS, f"table exists ({count} cached entries - 0 is normal before the app has run)")


def main():
    if not DB_PATH.exists():
        print(f"[FAIL] {DB_PATH} does not exist yet - run build_db.py first")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    check_food_banks(cur)
    check_tracts(cur)
    check_gtfs(cur)
    check_geocode_cache(cur)

    conn.close()
    print("\nDone. Fix any FAIL lines before moving on to the logic layer; WARN lines are worth a look but not blocking.")


if __name__ == "__main__":
    main()
