"""
A simplified transit lookup: finds the GTFS stop nearest to a location, and
any route whose trips serve both the origin and destination stops directly.

This is NOT full multi-transfer trip planning - that needs a real router
like OpenTripPlanner, which is out of scope for this project's timeline
(see the project notes on why). This is a "here's a reasonable transit
option" heuristic: nearest stop to the origin, nearest stop to the
destination, and any single route that connects them without a transfer.
If no direct route is found, that's a real limitation worth surfacing to
the user rather than pretending no transit option exists.

This only needs the local database - no internet required - so it can be
(and was) fully tested against the real GTFS data already loaded.

Since GTFS data may only be loaded for specific states/agencies (see
load_gtfs.py), a location far from any loaded feed would otherwise return
a technically-nearest-but-absurd result (e.g. a "nearby" stop 300 miles
away). MAX_REASONABLE_STOP_DISTANCE_MILES guards against that - beyond this
distance, we report transit as unavailable rather than a nonsense route.
"""
import sqlite3
from pathlib import Path
from typing import Dict, Optional

from nearest_foodbank import haversine_miles

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "foodbank_app.db"

# Beyond this distance, a "nearest stop" isn't a real transit option - it
# just means no feed is loaded for this area yet.
MAX_REASONABLE_STOP_DISTANCE_MILES = 3.0

# Coarse lat/lon box (degrees) used to pre-filter candidate stops in SQL
# before ranking them with exact haversine distance. ~0.15 degrees is roughly
# 10 miles, comfortably wider than MAX_REASONABLE_STOP_DISTANCE_MILES, so it
# never excludes a stop that would otherwise have been the real answer.
STOP_BBOX_DEGREES = 0.15


def _nearest_stop(lat: float, lon: float, db_path: Path) -> Optional[Dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # With nationwide stop data, a full-table scan for every lookup is slow.
    # Pre-filter to a small bounding box with SQL and only haversine-rank
    # that much smaller candidate set. If the box happens to be empty (e.g.
    # sparse feed coverage near this point), fall back to a full scan so
    # correctness never depends on the box being big enough.
    box = STOP_BBOX_DEGREES
    rows = conn.execute(
        "SELECT stop_id, stop_name, stop_lat, stop_lon FROM gtfs_stops "
        "WHERE CAST(stop_lat AS REAL) BETWEEN ? AND ? "
        "AND CAST(stop_lon AS REAL) BETWEEN ? AND ?",
        (lat - box, lat + box, lon - box, lon + box),
    ).fetchall()
    if not rows:
        rows = conn.execute("SELECT stop_id, stop_name, stop_lat, stop_lon FROM gtfs_stops").fetchall()
    conn.close()

    best, best_dist = None, None
    for row in rows:
        d = haversine_miles(lat, lon, float(row["stop_lat"]), float(row["stop_lon"]))
        if best_dist is None or d < best_dist:
            best_dist = d
            best = dict(row)
            best["distance_miles"] = round(d, 2)
    return best


def find_transit_option(
    origin_lat: float, origin_lon: float, dest_lat: float, dest_lon: float, db_path: Path = DB_PATH
) -> Dict:
    origin_stop = _nearest_stop(origin_lat, origin_lon, db_path)
    dest_stop = _nearest_stop(dest_lat, dest_lon, db_path)

    if not origin_stop or not dest_stop:
        return {"found": False, "reason": "No transit stops loaded in the database at all"}

    too_far = (
        origin_stop["distance_miles"] > MAX_REASONABLE_STOP_DISTANCE_MILES
        or dest_stop["distance_miles"] > MAX_REASONABLE_STOP_DISTANCE_MILES
    )
    if too_far:
        return {
            "found": False,
            "reason": (
                "Transit data isn't available in this area yet - the nearest loaded stop "
                f"is {max(origin_stop['distance_miles'], dest_stop['distance_miles'])} mi away, "
                "which means no transit feed covers this location (only specific states/"
                "agencies are loaded - see data/gtfs/)."
            ),
        }

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Routes whose trips visit the origin stop BEFORE the destination stop
    # (same trip, same direction) - a same-route, no-transfer option.
    query = """
        SELECT DISTINCT t.route_id, r.route_short_name, r.route_long_name
        FROM gtfs_stop_times st1
        JOIN gtfs_stop_times st2 ON st1.trip_id = st2.trip_id
        JOIN gtfs_trips t ON st1.trip_id = t.trip_id
        JOIN gtfs_routes r ON t.route_id = r.route_id
        WHERE st1.stop_id = ? AND st2.stop_id = ?
          AND CAST(st1.stop_sequence AS INTEGER) < CAST(st2.stop_sequence AS INTEGER)
        LIMIT 5
    """
    matches = conn.execute(query, (origin_stop["stop_id"], dest_stop["stop_id"])).fetchall()
    conn.close()

    return {
        "found": len(matches) > 0,
        "origin_stop": origin_stop,
        "dest_stop": dest_stop,
        "direct_routes": [dict(m) for m in matches],
        "note": "Direct same-route match only (no transfers). A real trip planner "
                "(e.g. OpenTripPlanner) would also find multi-transfer options when "
                "no direct route exists.",
    }


if __name__ == "__main__":
    # downtown Elizabeth, NJ -> downtown Plainfield, NJ
    result = find_transit_option(40.6640, -74.2107, 40.6337, -74.4079)
    print(f"Origin stop:  {result['origin_stop']['stop_name']} ({result['origin_stop']['distance_miles']} mi away)")
    print(f"Dest stop:    {result['dest_stop']['stop_name']} ({result['dest_stop']['distance_miles']} mi away)")
    print(f"Direct route found: {result['found']}")
    for r in result["direct_routes"]:
        print(f"  Route {r['route_short_name']}: {r['route_long_name']}")
