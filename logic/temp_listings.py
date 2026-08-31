"""
Lets anyone post a short-lived, ad-hoc food drop-off - "20 sandwiches at the
community center until 6pm" - and lets nearby users find it and mark off how
many they picked up.

Stored in its own database file (temp_listings.db), separate from
foodbank_app.db. scripts/build_db.py wipes and rebuilds foodbank_app.db from
source data every time it runs (that's fine for food banks/tracts/GTFS,
which all come from files), but live user-submitted listings must never be
destroyed by that rebuild, so they live in their own file instead.
"""
import secrets
import sqlite3
from pathlib import Path
from typing import Dict, List

from nearest_foodbank import haversine_miles

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "temp_listings.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS temp_listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    address TEXT NOT NULL,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    meal_type TEXT,
    meals_total INTEGER NOT NULL,
    meals_remaining INTEGER NOT NULL,
    notes TEXT,
    manage_key TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def _ensure_schema(db_path: Path = DB_PATH) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute(_SCHEMA)
    # Anyone who created a listing.db before manage_key existed gets it
    # added here rather than needing to delete and recreate the file.
    try:
        conn.execute("ALTER TABLE temp_listings ADD COLUMN manage_key TEXT")
    except sqlite3.OperationalError:
        pass  # column already exists
    conn.commit()
    conn.close()


def create_listing(
    name: str,
    address: str,
    lat: float,
    lon: float,
    meal_type: str,
    meals_total: int,
    notes: str = "",
    db_path: Path = DB_PATH,
) -> Dict:
    """Create a listing and return {"id": ..., "manage_key": ...}. The
    manage_key is a random code shown to the poster once, at creation time -
    it's the only thing that can later remove the listing, so a stranger
    can't cancel someone else's post just by guessing a sequential id."""
    if meals_total <= 0:
        raise ValueError("meals_total must be a positive number")
    _ensure_schema(db_path)
    manage_key = secrets.token_hex(4)  # 8 hex chars, easy to type/copy
    conn = sqlite3.connect(db_path)
    cur = conn.execute(
        "INSERT INTO temp_listings "
        "(name, address, lat, lon, meal_type, meals_total, meals_remaining, notes, manage_key) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (name, address, lat, lon, meal_type, meals_total, meals_total, notes, manage_key),
    )
    conn.commit()
    listing_id = cur.lastrowid
    conn.close()
    return {"id": listing_id, "manage_key": manage_key}


def find_nearby_listings(lat: float, lon: float, n: int = 5, db_path: Path = DB_PATH) -> List[Dict]:
    """Active listings (meals_remaining > 0), nearest first."""
    _ensure_schema(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM temp_listings WHERE meals_remaining > 0").fetchall()
    conn.close()

    results = []
    for row in rows:
        d = haversine_miles(lat, lon, row["lat"], row["lon"])
        results.append({**dict(row), "distance_miles": round(d, 2)})
    results.sort(key=lambda r: r["distance_miles"])
    return results[:n]


def delete_listing(manage_key: str, db_path: Path = DB_PATH) -> bool:
    """Remove a listing using the removal code its creator was given, not
    the raw row id - so only someone who has that code (the poster, or
    someone they shared it with) can take a listing down, not just anyone
    who guesses or increments a listing number. Returns True if a row was
    actually deleted."""
    _ensure_schema(db_path)
    conn = sqlite3.connect(db_path)
    cur = conn.execute("DELETE FROM temp_listings WHERE manage_key = ?", (manage_key.strip(),))
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    return deleted


def claim_meals(listing_id: int, meals_wanted: int, db_path: Path = DB_PATH) -> int:
    """Deduct meals_wanted from a listing. Clamps to whatever's actually left
    (rather than erroring) so two people claiming at nearly the same time
    can't push the count negative. Returns the new remaining count."""
    if meals_wanted <= 0:
        raise ValueError("meals_wanted must be a positive number")
    _ensure_schema(db_path)
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT meals_remaining FROM temp_listings WHERE id = ?", (listing_id,)
    ).fetchone()
    if row is None:
        conn.close()
        raise ValueError(f"No listing with id {listing_id}")
    remaining = row[0]
    taken = min(meals_wanted, remaining)
    new_remaining = remaining - taken
    conn.execute(
        "UPDATE temp_listings SET meals_remaining = ? WHERE id = ?",
        (new_remaining, listing_id),
    )
    conn.commit()
    conn.close()
    return new_remaining


if __name__ == "__main__":
    created = create_listing("Test drop", "123 Main St, Elizabeth, NJ", 40.6640, -74.2107, "Sandwiches", 20)
    print("Created listing", created)
    print(find_nearby_listings(40.6640, -74.2107))
    print("After claiming 5:", claim_meals(created["id"], 5))
    print("Removed:", delete_listing(created["manage_key"]))
