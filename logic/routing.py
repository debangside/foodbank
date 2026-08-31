"""
Point-to-point routing, free tools only:
  - Driving directions via OSRM's public demo server (no API key needed).
  - Walking directions via OpenRouteService (free tier, needs a free API
    key from openrouteservice.org - sign up, then either pass api_key= or
    set the ORS_API_KEY environment variable).

NOTE: both need real internet access to test, and could not be verified
from the sandbox this was built in - run the __main__ block on your own
machine to confirm they work before wiring them into the app.
"""
import os
from typing import Dict, Optional

import requests

OSRM_URL = "https://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}"
ORS_URL = "https://api.openrouteservice.org/v2/directions/foot-walking"


def get_driving_route(origin_lat: float, origin_lon: float, dest_lat: float, dest_lon: float) -> Dict:
    """Driving distance/duration between two points, via OSRM's free public server."""
    url = OSRM_URL.format(lon1=origin_lon, lat1=origin_lat, lon2=dest_lon, lat2=dest_lat)
    resp = requests.get(url, params={"overview": "false"}, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != "Ok":
        raise ValueError(f"OSRM could not find a route: {data.get('message', data.get('code'))}")

    route = data["routes"][0]
    return {
        "mode": "driving",
        "distance_miles": round(route["distance"] / 1609.34, 2),
        "duration_minutes": round(route["duration"] / 60, 1),
    }


def get_walking_route(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    api_key: Optional[str] = None,
) -> Dict:
    """Walking distance/duration between two points, via OpenRouteService's free tier."""
    api_key = api_key or os.environ.get("ORS_API_KEY")
    if not api_key:
        raise ValueError(
            "OpenRouteService needs a free API key - sign up at openrouteservice.org, "
            "then either pass api_key= or set the ORS_API_KEY environment variable."
        )

    resp = requests.get(
        ORS_URL,
        params={
            "api_key": api_key,
            "start": f"{origin_lon},{origin_lat}",
            "end": f"{dest_lon},{dest_lat}",
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    summary = data["features"][0]["properties"]["summary"]
    return {
        "mode": "walking",
        "distance_miles": round(summary["distance"] / 1609.34, 2),
        "duration_minutes": round(summary["duration"] / 60, 1),
    }


if __name__ == "__main__":
    # test with two real Union County points: downtown Elizabeth -> downtown Plainfield
    ORIGIN = (40.6640, -74.2107)
    DEST = (40.6337, -74.4079)

    print("Driving:", get_driving_route(*ORIGIN, *DEST))

    try:
        print("Walking:", get_walking_route(*ORIGIN, *DEST))
    except ValueError as e:
        print("Walking: skipped -", e)
