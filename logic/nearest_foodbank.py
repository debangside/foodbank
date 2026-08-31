"""
Given a location, find the nearest food banks by straight-line (haversine)
distance. With only a couple dozen food banks in the dataset, a plain sort
is plenty fast - no need for a spatial index (like a BallTree) at this
scale. If the food bank list ever grows into the thousands, that would be
the first thing to swap in.
"""
import math
import sqlite3
from pathlib import Path
from typing import Dict, List

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "foodbank_app.db"

EARTH_RADIUS_MILES = 3958.8


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two lat/lon points, in miles."""
    lat1, lon1, lat2, lon2 = map(math.radians, (lat1, lon1, lat2, lon2))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * math.asin(math.sqrt(a))


def find_nearest_foodbanks(lat: float, lon: float, n: int = 3, db_path: Path = DB_PATH) -> List[Dict]:
    """Return the n closest food banks to (lat, lon), nearest first."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    # SELECT * rather than a fixed column list - food_banks now carries extra
    # metadata (state, phone, website, source) beyond the original five
    # columns, and this stays correct regardless of which columns exist.
    rows = conn.execute("SELECT * FROM food_banks").fetchall()
    conn.close()

    results = []
    for row in rows:
        d = haversine_miles(lat, lon, row["lat"], row["lon"])
        results.append({**dict(row), "distance_miles": round(d, 2)})

    results.sort(key=lambda r: r["distance_miles"])
    return results[:n]


if __name__ == "__main__":
    # manual smoke test: a point near downtown Elizabeth, NJ
    print("Nearest food banks to downtown Elizabeth, NJ (40.6640, -74.2107):\n")
    for fb in find_nearest_foodbanks(40.6640, -74.2107, n=5):
        print(f"  {fb['distance_miles']:>5} mi - {fb['name']} ({fb['address']})")
