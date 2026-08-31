"""
Build foodbank_app.db from scratch: applies the base schema, then runs the
three data loaders in order.

Before running, place your source files in ../data/:
    data/food_banks.csv     (name, address, lat, lon, hours)
    data/gtfs/*.txt          (unzipped GTFS feed)
    data/usda_atlas.csv      (USDA Food Access Research Atlas)

Usage:
    python build_db.py
"""
import sqlite3
from pathlib import Path

from load_food_banks import load_food_banks
from load_gtfs import load_gtfs
from load_tracts import load_tracts

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "foodbank_app.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def apply_schema(db_path: Path = DB_PATH, schema_path: Path = SCHEMA_PATH) -> None:
    conn = sqlite3.connect(db_path)
    with open(schema_path) as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()


def _run_step(label, fn):
    """Run one loader; skip it (don't crash the whole build) if its source
    file isn't there yet - useful while you're still collecting the three
    data files one at a time."""
    print(f"\n--- {label} ---")
    try:
        fn()
        return True
    except FileNotFoundError as e:
        print(f"Skipped: {e}")
        return False


def main():
    if DB_PATH.exists():
        print(f"Removing existing {DB_PATH.name} for a clean rebuild")
        DB_PATH.unlink()

    apply_schema()

    results = {
        "food_banks": _run_step("Loading food banks", load_food_banks),
        "gtfs": _run_step("Loading GTFS feed", load_gtfs),
        "tracts": _run_step("Loading USDA Atlas tracts", load_tracts),
    }

    print(f"\nDone. Database at {DB_PATH}")
    skipped = [name for name, ok in results.items() if not ok]
    if skipped:
        print(f"Still missing source data for: {', '.join(skipped)} - add those files and re-run.")
    print("Run verify_db.py now to confirm what actually loaded.")


if __name__ == "__main__":
    main()
