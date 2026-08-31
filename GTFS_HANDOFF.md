# GTFS Transit Expansion — Session Handoff

Paste this whole file's contents as your first message in the new conversation.

## Project
Nationwide food bank locator app in `foodbank_app/` (SQLite + Python logic layer + Streamlit UI).
Connected folder: `COWORK SHIFT` (the project already lives inside it, at `foodbank_app/` — no
separate "copy into COWORK SHIFT" step is needed, scripts already operate in place).

- 1,710 food banks loaded, nationwide USDA tract data loaded.
- NJ Transit GTFS already loaded and working in the live `foodbank_app.db`
  (`data/gtfs/nj_transit/` has all expected files: agency, calendar_dates, routes, stops, trips,
  stop_times — verified present).
- Now adding 24 state/agency GTFS feeds from zips already uploaded to this Cowork session's
  uploads folder, already inspected/resolved in an earlier session.

## Feed ID → source zip mapping (confirmed, do not re-investigate)
- wego_tn ← google_transit_TN.zip
- abqride_nm ← google_transit_NM.zip
- norta_la ← GTFS_LA.zip (New Orleans, NOT Los Angeles — confirmed via agency.txt)
- cttransit_ct ← googlect_transit_CT.zip (real CT statewide bus feed)
- hartfordline_ct ← hlgtfs_CT.zip (Hartford Line rail, optional/small — drop first if time-constrained)
- metro_stl_mo ← google_transit_MO.zip
- gcrta_oh ← google_transit_GCRTA.zip (SKIP google_transit_OH.zip — confirmed byte-identical duplicate via md5sum)
- valleymetro_az ← googletransit_AZ.zip
- uta_ut ← gtfs_UT.zip
- mcts_wi ← google_transit_WI.zip
- marta_ga ← google_transit_GA.zip
- portland_or ← gtfs_OR.zip
- rtd_co ← google_transit_CO.zip
- mta_md ← mdotmta_gtfs_localbus_MD.zip
- miamidade_fl ← google_transit_FL.zip
- rtc_nv ← google_transit_NV.zip
- kingcounty_wa ← google_transit_WA.zip
- mbta_ma ← MBTA_GTFS_MA.zip (do NOT drop even if time-constrained)
- lametro_ca ← gtfs_bus_CA.zip (LA Metro — largest stop_times file, ~307MB raw; do NOT drop even if time-constrained)
- mtanyct_ny ← gtfs_subway_NY.zip
- mtabus_ny ← gtfs_busco_NY.zip
- septa_bus_pa + septa_rail_pa ← gtfs_public_PA.zip (ZIP OF ZIPS: contains google_bus.zip and
  google_rail.zip inside — unzip a level deeper; septa_rail_pa is the small/optional one, drop
  first if time-constrained)

**Explicitly SKIP** `GTFS_CT.zip` — Amtrak thruway-connections feed (Roadrunner Shuttle, Via Rail,
etc.), not CT local transit — confirmed via agency.txt.

If time runs short, drop `hartfordline_ct` and `septa_rail_pa` first. Never drop `lametro_ca` or
`mbta_ma`.

## Code fixes — STATUS: ALREADY APPLIED (confirmed in the actual project files, not a scratchpad,
## so this should persist regardless of sandbox state — just double check they're still there)
- `scripts/load_gtfs.py`: switched from a shapes.txt-only blocklist to an `ALLOWED_FILES` allowlist
  of `{agency.txt, calendar.txt, calendar_dates.txt, routes.txt, stops.txt, trips.txt, stop_times.txt}`.
  Also added `ALTER TABLE ... ADD COLUMN` widening (via `PRAGMA table_info` diff) before appending a
  feed's dataframe to an existing table, so agencies with extra optional columns (e.g. routes.txt
  `network_id`) don't crash the append.
- `logic/transit.py`: `_nearest_stop()` now pre-filters candidate stops with a SQL bounding box
  (`STOP_BBOX_DEGREES = 0.15`) before exact haversine ranking, with a full-table-scan fallback if
  the box comes back empty (so correctness doesn't depend on box size). Needed because the stops
  table is about to become nationwide-scale.

Known harmless clutter (not a bug, left alone intentionally): `data/gtfs/` has loose duplicate NJ
`.txt` files + a `gtfs.zip` sitting directly in it (outside any feed subfolder), left over from
before the subfolder convention. `load_gtfs.py` only reads subdirectories, so this is inert.

## Critical lesson from a prior incident — DO NOT REPEAT
Extracting all 24 raw zips into /tmp at once filled the sandbox disk and completely wedged the
shell (required a full sandbox reset, which is what caused this handoff in the first place).
Process feeds **ONE AT A TIME**:
1. Extract a single zip to a scratch dir.
2. Filter it down to just one representative weekday's service — use `calendar.txt`'s `monday=1`
   column if present, otherwise the busiest date in `calendar_dates.txt`.
3. Write the filtered result directly into the final `data/gtfs/<feed_id>/` folder.
4. Delete the raw extracted scratch copy before moving to the next zip.

Never hold more than one raw/unfiltered feed in scratch space at a time.

## Remaining steps once the sandbox is healthy
1. Confirm the two code fixes above are still in place (`scripts/load_gtfs.py`, `logic/transit.py`).
2. Process all planned feeds per the mapping above, one at a time, per the disk-safety procedure.
3. Run `python scripts/build_db.py` (rebuilds the full db from food banks + tracts + all GTFS feeds).
4. Run `python scripts/verify_db.py` — confirm no FAIL lines (WARN is fine).
5. The db and `data/gtfs/` feed folders are already inside the connected COWORK SHIFT folder
   (project lives there directly) — no separate copy-out step needed, just confirm the files are
   there and the user can run the Streamlit app locally.

## Why this handoff exists
This session's sandbox (bash tool) has been down the entire time — every call fails with
`useradd: ... No space left on device` at container provisioning, before any command runs.
Confirmed 8/8 identical failures across manual retries, a Claude app restart, and a claimed
"new session" within the same conversation. `status.claude.com` showed no active incident as of
2026-08-30. WSL2 is not installed on the user's machine, ruling out a local WSL disk-full cause.
Working theory: this conversation's backend sandbox/volume is stuck in a bad state, possibly a
carryover from the raw-zip disk-fill incident. Starting a genuinely new, separate conversation is
the next diagnostic step — if bash works there, continue the task in that new conversation using
this handoff for context.

If a fresh conversation *also* fails identically, the issue is account-level and needs Anthropic
support (or a GEP admin, if this is a managed deployment) to resolve — no further self-service
troubleshooting will fix it from either side.

## First thing to do in the new conversation
Grant folder access again when prompted (folder connections are per-conversation) — point it at
`C:\Users\debangsi.de\OneDrive - GEP\Desktop\COWORK SHIFT`. Then ask Claude to verify bash works
(`echo ok`) before resuming the GTFS processing.
