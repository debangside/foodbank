"""
Load food bank / pantry locations from data/food_banks.csv into the SQLite
database.

Required columns: name, lat, lon. Everything else in the CSV (address,
hours, state, phone, website, source, etc.) is carried through as-is - this
stays flexible since the nationwide file (merged from OpenStreetMap plus
the original hand-compiled Union County list) has more metadata columns
than the original single-county file did.
"""
import sqlite3
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "foodbank_app.db"
CSV_PATH = BASE_DIR / "data" / "food_banks.csv"


def load_food_banks(csv_path: Path = CSV_PATH, db_path: Path = DB_PATH) -> int:
    if not csv_path.exists():
        raise FileNotFoundError(
            f"Could not find {csv_path}. Expected a CSV with at least: name, lat, lon"
        )

    df = pd.read_csv(csv_path)
    df.columns = [c.strip().lower() for c in df.columns]

    required = {"name", "lat", "lon"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"food_banks.csv is missing required columns: {missing}")

    before = len(df)
    df = df.dropna(subset=["lat", "lon"])
    dropped = before - len(df)
    if dropped:
        print(f"Warning: dropped {dropped} row(s) missing lat/lon")

    conn = sqlite3.connect(db_path)
    df.to_sql("food_banks", conn, if_exists="replace", index=False)
    conn.close()

    print(f"Loaded {len(df)} food bank rows into {db_path.name}::food_banks")
    return len(df)


if __name__ == "__main__":
    load_food_banks()
