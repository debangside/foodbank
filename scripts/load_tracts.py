"""
Load USDA Food Access Research Atlas rows into the SQLite database.

Expects the full national Atlas CSV at data/usda_atlas.csv. By default loads
ALL tracts nationwide - pass fips_prefix (or a list of them) to scope it
down to one or more states/counties instead. Keeps a curated set of columns
if present. The Atlas has 100+ columns and its exact naming has shifted
slightly between releases, so this is deliberately tolerant of minor
differences - extend COLUMN_CANDIDATES below if your download uses
different names.
"""
import sqlite3
from pathlib import Path
from typing import List, Optional, Union

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "foodbank_app.db"
CSV_PATH = BASE_DIR / "data" / "usda_atlas.csv"

# Example prefixes if you want to scope down instead of loading nationwide:
# Union County, NJ = state FIPS 34 + county FIPS 039 -> "34039"
# All of New Jersey -> "34"
DEFAULT_FIPS_PREFIX = None  # None = load every tract nationwide

# Each target column maps to a list of possible source column names in the
# Atlas CSV - first match wins.
COLUMN_CANDIDATES = {
    "geoid": ["CensusTract", "GEOID", "geoid"],
    "state": ["State", "state"],
    "county": ["County", "county"],
    "urban": ["Urban", "urban"],
    "population": ["Pop2010", "POP2010", "population"],
    "poverty_rate": ["PovertyRate", "poverty_rate"],
    "median_family_income": ["MedianFamilyIncome", "median_family_income"],
    "low_income_tract": ["LowIncomeTracts", "LILATracts_1And10"],
    "lila_1_10": ["LILATracts_1And10", "LA1and10"],
    "lila_half_10": ["LILATracts_halfAnd10", "LAhalfand10"],
    "lila_vehicle": ["LILATracts_Vehicle", "HUNVFlag"],
}


def _first_matching_column(df: pd.DataFrame, candidates: list) -> Optional[str]:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def load_tracts(
    csv_path: Path = CSV_PATH,
    db_path: Path = DB_PATH,
    fips_prefix: Optional[Union[str, List[str]]] = DEFAULT_FIPS_PREFIX,
) -> int:
    """
    fips_prefix: None (default) loads every tract nationwide. Pass a single
    prefix ("34039") to scope to one county/state, or a list of prefixes
    (["34", "36"]) to load multiple states/counties at once.
    """
    if not csv_path.exists():
        raise FileNotFoundError(
            f"Could not find {csv_path}. Download the Food Access Research "
            "Atlas CSV from https://www.ers.usda.gov/data-products/"
            "food-access-research-atlas and save it there (the national "
            "file is fine - this script can load it nationwide or filter it)."
        )

    df = pd.read_csv(csv_path, dtype={"CensusTract": str}, low_memory=False)

    geoid_col = _first_matching_column(df, COLUMN_CANDIDATES["geoid"])
    if geoid_col is None:
        raise ValueError(
            "Could not find a census tract / GEOID column in the Atlas CSV. "
            f"First 20 columns present: {list(df.columns)[:20]}"
        )

    df[geoid_col] = df[geoid_col].astype(str).str.zfill(11)

    if fips_prefix is None:
        filtered = df.copy()
    else:
        prefixes = [fips_prefix] if isinstance(fips_prefix, str) else list(fips_prefix)
        mask = df[geoid_col].apply(lambda g: any(g.startswith(p) for p in prefixes))
        filtered = df[mask].copy()

    if filtered.empty:
        raise ValueError(
            f"No rows matched fips_prefix={fips_prefix!r}. Double check the "
            "prefix(es) or the source file."
        )

    out = pd.DataFrame()
    out["geoid"] = filtered[geoid_col]
    for target_col, candidates in COLUMN_CANDIDATES.items():
        if target_col == "geoid":
            continue
        src_col = _first_matching_column(filtered, candidates)
        out[target_col] = filtered[src_col] if src_col else None

    # Placeholder - the real coverage score gets computed in the logic layer
    # (distance to nearest food bank + these demographic fields), once food
    # bank coordinates are loaded. Left as NULL here on purpose.
    out["coverage_score"] = None

    conn = sqlite3.connect(db_path)
    out.to_sql("tracts", conn, if_exists="replace", index=False)
    conn.close()

    scope = "nationwide" if fips_prefix is None else f"fips_prefix={fips_prefix!r}"
    print(f"Loaded {len(out)} tract rows ({scope}) into tracts")
    return len(out)


if __name__ == "__main__":
    load_tracts()
