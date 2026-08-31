"""
Union County Food Bank Finder - Streamlit UI

Ties the logic layer (geocode, nearest_foodbank, routing, transit,
temp_listings) into a simple form: enter a zip code, pick driving or
transit, and see the nearest food bank plus a route to get there. The
"donate" framing reuses the exact same lookup as "receive" - finding a food
bank near you is the same query either way, just different copy on screen.
A third option lets anyone post a short-lived, ad-hoc food drop-off (extra
event food, a few boxes of produce, etc.) that nearby users can find and
claim meals from.

Run with:
    streamlit run app.py
"""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

LOGIC_DIR = Path(__file__).resolve().parent.parent / "logic"
sys.path.insert(0, str(LOGIC_DIR))

from geocode import geocode  # noqa: E402
from nearest_foodbank import find_nearest_foodbanks  # noqa: E402
from routing import get_driving_route  # noqa: E402
from transit import find_transit_option  # noqa: E402
from temp_listings import create_listing, find_nearby_listings, claim_meals, delete_listing  # noqa: E402

st.set_page_config(page_title="Union County Food Bank Finder", page_icon="🥫")

# Soft pastel background with a handful of low-opacity food emoji scattered
# behind the content - subtle "food app" vibe without getting in the way of
# readability. Sits behind everything (z-index -1, pointer-events: none) so
# it never blocks clicks or covers text.
st.markdown(
    """
    <style>
    .stApp { background: linear-gradient(135deg, #fff6e9 0%, #ffe9f0 30%, #eaf6f0 65%, #eaf0ff 100%); }
    </style>
    <div id="food-bg-decor" style="position:fixed; inset:0; z-index:-1; pointer-events:none; overflow:hidden;">
        <span style="position:absolute; top:4%; left:6%; font-size:44px; opacity:0.12; transform:rotate(-12deg);">🍎</span>
        <span style="position:absolute; top:8%; right:8%; font-size:52px; opacity:0.10; transform:rotate(15deg);">🥑</span>
        <span style="position:absolute; top:35%; left:2%; font-size:36px; opacity:0.10; transform:rotate(8deg);">🥕</span>
        <span style="position:absolute; top:60%; right:4%; font-size:48px; opacity:0.12; transform:rotate(-10deg);">🍊</span>
        <span style="position:absolute; bottom:6%; left:10%; font-size:40px; opacity:0.10; transform:rotate(20deg);">🍞</span>
        <span style="position:absolute; bottom:10%; right:14%; font-size:44px; opacity:0.12; transform:rotate(-18deg);">🍇</span>
        <span style="position:absolute; top:20%; left:45%; font-size:32px; opacity:0.08; transform:rotate(5deg);">🥦</span>
        <span style="position:absolute; bottom:30%; left:30%; font-size:30px; opacity:0.08; transform:rotate(-6deg);">🍒</span>
    </div>
    """,
    unsafe_allow_html=True,
)

# Dark mode toggle, top left. Streamlit's built-in theme is set server-side
# (config.toml), so a user-facing toggle has to work by injecting CSS that
# overrides the default light theme's colors when switched on.
top_left, _ = st.columns([1, 5])
with top_left:
    dark_mode = st.toggle("Dark mode", key="dark_mode")

if dark_mode:
    st.markdown(
        """
        <style>
        .stApp { background: linear-gradient(135deg, #1a1625 0%, #14202b 35%, #10231f 70%, #171225 100%); color: #fafafa; }
        #food-bg-decor { opacity: 0.5; }
        [data-testid="stHeader"] { background-color: rgba(0,0,0,0); }
        h1, h2, h3, h4, h5, h6, p, label, span, li { color: #fafafa !important; }
        [data-testid="stMetricValue"], [data-testid="stMetricLabel"] { color: #fafafa !important; }
        .stTextInput input, .stTextArea textarea, .stNumberInput input {
            background-color: #262730; color: #fafafa; border-color: #4a4a4a;
        }
        .stButton button {
            background-color: #262730; color: #fafafa; border-color: #4a4a4a;
        }
        [data-testid="stWidgetLabel"] p { color: #fafafa !important; }
        div[role="radiogroup"] label { color: #fafafa !important; }
        .stAlert { background-color: #262730; }
        </style>
        """,
        unsafe_allow_html=True,
    )

st.title("Union County Food Bank Finder")
st.caption(
    "Data: USDA Food Access Research Atlas, NJ Transit GTFS, and public food "
    "pantry directories for Union County, NJ."
)

role = st.radio(
    "I want to...",
    ["Find food near me", "Find where to donate or volunteer", "Set up a temporary food bank"],
)

# --- Temporary food bank: post an ad-hoc drop-off -----------------------
if role == "Set up a temporary food bank":
    st.subheader("Set up a temporary food bank")
    st.caption(
        "For one-off giveaways - leftover event food, extra produce boxes, etc. "
        "Posted here so nearby neighbors can find it and pick some up before it's gone."
    )

    with st.form("post_listing"):
        name = st.text_input("What should we call this?", placeholder="e.g. Extra produce boxes")
        address = st.text_input("Pickup address or zip code")
        meal_type = st.text_input("Type of food", placeholder="e.g. Sandwiches, canned goods, produce")
        meals_total = st.number_input("Number of meals/servings available", min_value=1, step=1, value=10)
        notes = st.text_area("Notes (optional)", placeholder="e.g. Available until 6pm, ring the doorbell")
        post_submitted = st.form_submit_button("Post food bank")

    if post_submitted:
        if not name.strip() or not address.strip():
            st.error("Please fill in a name and an address.")
            st.stop()

        with st.spinner("Looking up that address..."):
            try:
                lat, lon = geocode(address.strip())
            except Exception as e:
                st.error(f"Couldn't find that address: {e}")
                st.stop()

        listing = create_listing(
            name=name.strip(),
            address=address.strip(),
            lat=lat,
            lon=lon,
            meal_type=meal_type.strip(),
            meals_total=int(meals_total),
            notes=notes.strip(),
        )
        st.success(
            f"Posted! {int(meals_total)} servings of {meal_type.strip() or 'food'} at {address.strip()}."
        )
        st.warning("Save this removal code now - you'll need it to take the listing down later. It won't be shown again.")
        st.code(listing["manage_key"])
        st.map(pd.DataFrame([{"lat": lat, "lon": lon}]))

    st.divider()
    st.subheader("Remove a listing")
    st.caption(
        "Already gave everything away, or need to take a listing down early? "
        "Enter the removal code you were given when you posted it."
    )
    with st.form("remove_listing"):
        remove_key = st.text_input("Removal code")
        remove_submitted = st.form_submit_button("Remove listing")

    if remove_submitted:
        if not remove_key.strip():
            st.error("Please enter a removal code.")
        elif delete_listing(remove_key.strip()):
            st.success("Listing removed.")
        else:
            st.error("No listing found with that removal code.")

# --- Find food / donate: existing lookup flow ---------------------------
else:
    zip_code = st.text_input("Enter your zip code", placeholder="e.g. 07060")
    mode = st.radio("How are you getting there?", ["Driving", "Public transit"])
    submitted = st.button("Find nearest food bank")

    if submitted:
        if not zip_code.strip():
            st.error("Please enter a zip code.")
            st.stop()

        with st.spinner("Looking up your location..."):
            try:
                lat, lon = geocode(zip_code.strip())
            except Exception as e:
                st.error(f"Couldn't find that zip code: {e}")
                st.stop()

        candidates = find_nearest_foodbanks(lat, lon, n=3)
        if not candidates:
            st.error("No food banks found in the database.")
            st.stop()

        nearest = candidates[0]

        # OSM coverage is uneven by region - if even the "nearest" result is
        # implausibly far, say so rather than presenting it as a real option.
        FAR_AWAY_MILES = 50
        if nearest["distance_miles"] > FAR_AWAY_MILES:
            st.warning(
                f"⚠️ The closest entry in our data is {nearest['distance_miles']} miles away. "
                "Our food bank data comes from OpenStreetMap and a hand-checked Union County, NJ "
                "list, so coverage is uneven by region - this result may not reflect what's actually "
                "nearby. Consider checking Feeding America's locator directly for this area."
            )

        heading = "Nearest food bank" if role == "Find food near me" else "Nearest place to donate or volunteer"
        st.subheader(f"{heading}: {nearest['name']}")

        col1, col2, col3 = st.columns(3)
        col1.metric("Straight-line distance", f"{nearest['distance_miles']} mi")
        col2.write(f"**Address**\n\n{nearest['address']}")
        col3.write(f"**Hours**\n\n{nearest['hours']}")

        if mode == "Driving":
            with st.spinner("Calculating driving route..."):
                try:
                    route = get_driving_route(lat, lon, nearest["lat"], nearest["lon"])
                    st.success(
                        f"🚗 About {route['distance_miles']} miles, "
                        f"~{route['duration_minutes']} minutes driving."
                    )
                except Exception as e:
                    st.warning(f"Couldn't calculate a driving route: {e}")
        else:
            with st.spinner("Finding transit options..."):
                try:
                    transit = find_transit_option(lat, lon, nearest["lat"], nearest["lon"])
                    if transit["found"]:
                        routes = ", ".join(
                            f"Route {r['route_short_name']}" for r in transit["direct_routes"]
                        )
                        st.success(
                            f"🚌 Walk to **{transit['origin_stop']['stop_name']}** "
                            f"({transit['origin_stop']['distance_miles']} mi away), take {routes}, "
                            f"get off near **{transit['dest_stop']['stop_name']}** "
                            f"({transit['dest_stop']['distance_miles']} mi from your destination)."
                        )
                    else:
                        st.warning(
                            "No direct (no-transfer) transit route found between the nearest "
                            "stops. A transfer may be needed - check NJ Transit's own trip "
                            "planner for a full itinerary."
                        )
                except Exception as e:
                    st.warning(f"Couldn't look up transit options: {e}")

        st.subheader("Map")
        map_data = pd.DataFrame(
            [{"lat": lat, "lon": lon}] + [{"lat": c["lat"], "lon": c["lon"]} for c in candidates]
        )
        st.map(map_data)
        st.caption("First point is your location; the others are the nearest food banks below.")

        if len(candidates) > 1:
            st.subheader("Other nearby options")
            for c in candidates[1:]:
                st.write(f"- **{c['name']}** ({c['distance_miles']} mi) - {c['address']}")

        # Nearby temporary food banks that neighbors have posted.
        if role == "Find food near me":
            nearby_listings = find_nearby_listings(lat, lon, n=5)
            if nearby_listings:
                st.subheader("Nearby temporary food banks")
                st.caption("Ad-hoc drop-offs posted by neighbors - first come, first served.")
                for listing in nearby_listings:
                    st.write(
                        f"**{listing['name']}** - {listing['meal_type'] or 'food'} "
                        f"({listing['meals_remaining']} of {listing['meals_total']} left) - "
                        f"{listing['distance_miles']} mi - {listing['address']}"
                    )
                    if listing["notes"]:
                        st.caption(listing["notes"])

                    with st.form(f"claim_{listing['id']}"):
                        claim_n = st.number_input(
                            "How many are you picking up?",
                            min_value=1,
                            max_value=int(listing["meals_remaining"]),
                            value=1,
                            step=1,
                            key=f"claim_input_{listing['id']}",
                        )
                        claim_btn = st.form_submit_button("Mark as picked up")

                    if claim_btn:
                        new_remaining = claim_meals(listing["id"], int(claim_n))
                        st.success(f"Marked {int(claim_n)} picked up - {new_remaining} left.")
                        st.rerun()
