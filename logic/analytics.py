"""
Lightweight visitor counter: active-now, unique visitors, and total visits.

How "unique" is determined: Streamlit gives each browser tab a session that
resets on every page reload, so counting sessions alone would call every
reload a "new" visitor. To do better without adding a login system, this
sets a long-lived browser cookie (fb_visitor_id) the first time someone
shows up and reuses it on later visits - so "unique" really means "unique
browser cookie", which undercounts a person who clears cookies or uses a
different browser/device, and overcounts a household that shares one
browser. That's the best available without real accounts.

How "active now" is determined: there's no continuous heartbeat (this app
doesn't auto-refresh), so a visitor counts as "active" if they've been seen
- page load or any interaction - within the last ACTIVE_WINDOW_MINUTES.
This will undercount someone who has the tab open but hasn't clicked
anything in a while.

Storage caveat: this uses a local SQLite file (analytics.db), kept separate
from foodbank_app.db for the same reason temp_listings.db is separate - so
rebuilding the main database never touches it. BUT if this app is deployed
on Streamlit Community Cloud specifically: local files there are not
guaranteed to survive a reboot or redeploy, so these counts (and the
temporary-food-bank listings, which have the same limitation) can reset
unexpectedly on that platform. Fine for a rough personal-project counter;
not something to build a real metric on.
"""
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "analytics.db"

ACTIVE_WINDOW_MINUTES = 5

_SCHEMA = """
CREATE TABLE IF NOT EXISTS visitors (
    visitor_id TEXT PRIMARY KEY,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    visit_count INTEGER NOT NULL DEFAULT 1
);
"""


def _ensure_schema(db_path: Path = DB_PATH) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute(_SCHEMA)
    conn.commit()
    conn.close()


def record_visit(visitor_id: str, db_path: Path = DB_PATH) -> None:
    """Call once per session (not once per rerun/interaction) - the caller
    is responsible for only calling this the first time in a given session,
    e.g. by gating it behind a st.session_state flag."""
    _ensure_schema(db_path)
    now = datetime.utcnow().isoformat()
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO visitors (visitor_id, first_seen, last_seen, visit_count) "
        "VALUES (?, ?, ?, 1) "
        "ON CONFLICT(visitor_id) DO UPDATE SET "
        "last_seen = excluded.last_seen, visit_count = visit_count + 1",
        (visitor_id, now, now),
    )
    conn.commit()
    conn.close()


def get_stats(active_window_minutes: int = ACTIVE_WINDOW_MINUTES, db_path: Path = DB_PATH) -> Dict:
    """Returns {"active": ..., "unique": ..., "total_visits": ...}."""
    _ensure_schema(db_path)
    cutoff = (datetime.utcnow() - timedelta(minutes=active_window_minutes)).isoformat()
    conn = sqlite3.connect(db_path)
    active = conn.execute(
        "SELECT COUNT(*) FROM visitors WHERE last_seen >= ?", (cutoff,)
    ).fetchone()[0]
    unique = conn.execute("SELECT COUNT(*) FROM visitors").fetchone()[0]
    total_visits = conn.execute("SELECT COALESCE(SUM(visit_count), 0) FROM visitors").fetchone()[0]
    conn.close()
    return {"active": active, "unique": unique, "total_visits": total_visits}


if __name__ == "__main__":
    record_visit("test-visitor-1")
    record_visit("test-visitor-2")
    record_visit("test-visitor-1")  # same visitor, second visit
    print(get_stats())
