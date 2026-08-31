"""
Turn a zip code or address into (lat, lon) using Nominatim, OpenStreetMap's
free geocoder (no API key needed). Results are cached in the geocode_cache
table so repeat lookups don't hit the API again - both to be a good citizen
of a free public service and because Nominatim's usage policy asks for a
maximum of 1 request/second.

NOTE: this needs real internet access to test. It could not be verified
from the sandbox this was built in - run the __main__ block below on your
own machine to confirm it works before wiring it into the app.
"""
import sqlite3
import time
from pathlib import Path
from typing import Optional, Tuple

import requests

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "foodbank_app.db"

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
# Nominatim's usage policy asks that requests identify the application -
# update the contact info if you plan to use this beyond a class project.
USER_AGENT = "union-county-foodbank-app/1.0 (student project)"


def _cache_get(query: str, db_path: Path) -> Optional[Tuple[float, float]]:
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT lat, lon FROM geocode_cache WHERE query = ?", (query,)
    ).fetchone()
    conn.close()
    return row


def _cache_put(query: str, lat: float, lon: float, db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT OR REPLACE INTO geocode_cache (query, lat, lon, fetched_at) "
        "VALUES (?, ?, ?, datetime('now'))",
        (query, lat, lon),
    )
    conn.commit()
    conn.close()


def geocode(query: str, db_path: Path = DB_PATH, country_bias: str = "us") -> Tuple[float, float]:
    """
    Geocode a zip code or address string to (lat, lon).
    Raises ValueError if nothing is found.
    """
    cached = _cache_get(query, db_path)
    if cached:
        return cached

    resp = requests.get(
        NOMINATIM_URL,
        params={"q": query, "format": "json", "countrycodes": country_bias, "limit": 1},
        headers={"User-Agent": USER_AGENT},
        timeout=10,
    )
    resp.raise_for_status()
    results = resp.json()
    if not results:
        raise ValueError(f"Could not geocode '{query}' - check the zip code/address is valid")

    lat, lon = float(results[0]["lat"]), float(results[0]["lon"])
    _cache_put(query, lat, lon, db_path)
    time.sleep(1)  # respect Nominatim's 1 request/second usage policy
    return lat, lon


if __name__ == "__main__":
    import sys

    q = sys.argv[1] if len(sys.argv) > 1 else "07060"  # Plainfield, NJ zip as a default test
    print(f"Geocoding '{q}'...")
    print(geocode(q))
