"""
Ties the logic layer together for the "receiver" flow: given a zip code (or
address) and a transport mode, find the nearest food bank and a route to it.

This is a deterministic pipeline, not an LLM agent - the task itself
(zip code in, food bank + route out) doesn't need an LLM to decide what to
do next, since the steps are always the same. If you want to add the
free-text / natural-language front end discussed earlier, this is the
function an LLM tool-calling loop would ultimately call - it doesn't
change what happens underneath.

NOTE: this calls geocode() and (for driving mode) get_driving_route(),
both of which need real internet access - it could not be run end-to-end
from the sandbox this was built in. nearest_foodbank and transit were
fully tested locally against the real database.
"""
import json
from pathlib import Path

from geocode import geocode
from nearest_foodbank import find_nearest_foodbanks
from routing import get_driving_route
from transit import find_transit_option


def find_help(zip_or_address: str, mode: str = "driving", n_candidates: int = 3) -> dict:
    """
    mode: "driving" or "transit"
    """
    if mode not in ("driving", "transit"):
        raise ValueError("mode must be 'driving' or 'transit'")

    lat, lon = geocode(zip_or_address)
    candidates = find_nearest_foodbanks(lat, lon, n=n_candidates)

    if not candidates:
        return {"error": "No food banks found in the database"}

    nearest = candidates[0]

    if mode == "driving":
        route = get_driving_route(lat, lon, nearest["lat"], nearest["lon"])
    else:
        route = find_transit_option(lat, lon, nearest["lat"], nearest["lon"])

    return {
        "origin": {"query": zip_or_address, "lat": lat, "lon": lon},
        "mode": mode,
        "nearest_food_bank": nearest,
        "other_candidates": candidates[1:],
        "route": route,
    }


if __name__ == "__main__":
    result = find_help("07060", mode="driving")  # Plainfield, NJ zip
    print(json.dumps(result, indent=2, default=str))
