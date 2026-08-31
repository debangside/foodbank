"""
Coverage score v1: ranks Union County tracts by need, using only the
demographic fields already in the tracts table.

This does NOT yet factor in distance to the nearest food bank, which was
part of the original plan - that needs each tract's centroid coordinates,
and the USDA Atlas doesn't include those. Adding it would mean pulling
Census TIGER/Line tract boundary shapefiles and using geopandas to compute
centroids - a reasonable v2 upgrade if you have time left, but out of
scope for this first pass.

v1 scoring: normalize poverty_rate (0-60 points) and add a flat bonus if
the tract is flagged low-income-low-access by USDA (0-40 points), for a
0-100 "need score" per tract. This is a deliberately simple, explainable
model - worth defending as a starting point, not the final word.
"""
import sqlite3
from pathlib import Path
from typing import Dict, List

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "foodbank_app.db"


def compute_coverage_scores(db_path: Path = DB_PATH) -> List[Dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = [
        dict(r)
        for r in conn.execute(
            "SELECT geoid, county, poverty_rate, lila_1_10, lila_half_10, lila_vehicle FROM tracts"
        ).fetchall()
    ]
    conn.close()

    poverty_values = [r["poverty_rate"] for r in rows if r["poverty_rate"] is not None]
    max_poverty = max(poverty_values) if poverty_values else 1

    for r in rows:
        poverty_component = (r["poverty_rate"] or 0) / max_poverty * 60  # up to 60 points
        is_lila = bool(int(r["lila_1_10"] or 0)) or bool(int(r["lila_half_10"] or 0))
        lila_component = 40 if is_lila else 0  # up to 40 points
        r["need_score"] = round(poverty_component + lila_component, 1)
        r["is_lila"] = is_lila

    rows.sort(key=lambda r: r["need_score"], reverse=True)

    conn = sqlite3.connect(db_path)
    conn.executemany(
        "UPDATE tracts SET coverage_score = ? WHERE geoid = ?",
        [(r["need_score"], r["geoid"]) for r in rows],
    )
    conn.commit()
    conn.close()

    return rows


if __name__ == "__main__":
    scores = compute_coverage_scores()
    print(f"Scored {len(scores)} tracts. Top 10 highest-need in Union County:\n")
    for r in scores[:10]:
        flag = "LILA" if r["is_lila"] else "    "
        print(f"  {r['geoid']}  need={r['need_score']:>5}  poverty={r['poverty_rate']:>5}%  {flag}")
