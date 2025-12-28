import streamlit as st
import pandas as pd
import plotly.express as px
import pydeck as pdk
from geopy.geocoders import Nominatim
import time
import os
import pandas as pd

RAWDATA = "rawdata.csv"
EXPECTED_COLUMNS = ["Date","Provider","Location","Type","kWh","Total Cost","Cost_per_kWh","Month"]

if not os.path.isfile(RAWDATA):
    pd.DataFrame(columns=EXPECTED_COLUMNS).to_csv(RAWDATA, index=False)

# =========================
# ENSURE CSV EXISTS
# =========================
CSV_FILE = "ev_charging_log_my.csv"

CSV_COLUMNS = [
    "Date",
    "Provider",
    "Location",
    "Type",
    "kWh",
    "Total Cost",
    "Cost_per_kWh",
    "Latitude",
    "Longitude",
    "Month"
]

if not os.path.isfile(CSV_FILE):
    pd.DataFrame(columns=CSV_COLUMNS).to_csv(CSV_FILE, index=False)


# ===============================
# CONFIG
# ===============================
st.set_page_config(
    page_title="Malaysia EV Charging Dashboard",
    page_icon="⚡",
    layout="wide"
)

FILE_NAME = "ev_charging_log_my.csv"

# ===============================
# LOAD DATA
# ===============================
@st.cache_data
def load_data():
    df = pd.read_csv(FILE_NAME)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    return df

df = load_data()

st.title("⚡ Malaysia EV Charging Analytics")

if df.empty:
    st.error("CSV is empty or missing.")
    st.stop()

# ===============================
# GEO-CODING (FREE OSM)
# ===============================
@st.cache_data(show_spinner=False)
def geocode_locations(locations):
    geolocator = Nominatim(user_agent="ev-charging-dashboard")
    coords = {}

    for loc in locations:
        try:
            geo = geolocator.geocode(f"{loc}, Malaysia", timeout=10)
            coords[loc] = (geo.latitude, geo.longitude) if geo else (None, None)
            time.sleep(0.7)  # safer rate
        except Exception:
            coords[loc] = (None, None)

    return coords

if "Latitude" not in df.columns or "Longitude" not in df.columns:
    st.info("📍 Auto-geocoding locations (OpenStreetMap)")
    loc_map = geocode_locations(df["Location"].dropna().unique())
    df["Latitude"] = df["Location"].map(lambda x: loc_map.get(x, (None, None))[0])
    df["Longitude"] = df["Location"].map(lambda x: loc_map.get(x, (None, None))[1])

# ===============================
# FEATURE ENGINEERING
# ===============================
df["Cost_per_kWh"] = (df["Total Cost"] / df["kWh"]).replace([float("inf")], 0)

# Safe session duration proxy
mean_kwh = df.groupby("Type")["kWh"].transform("mean").replace(0, pd.NA)
df["Session_Duration_Proxy"] = (df["kWh"] / mean_kwh).fillna(0)

# Time features (safe)
df["Hour"] = df["Date"].dt.hour.fillna(-1).astype(int)
df["Day"] = df["Date"].dt.day_name().fillna("Unknown")

# ===============================
# TABS
# ===============================
tab_insights, tab_location = st.tabs(["📊 Insights", "📍 Locations"])

# ===============================
# INSIGHTS TAB
# ===============================
with tab_insights:
    col1, col2 = st.columns(2)

    with col1:
        daily_df = (
            df.groupby(df["Date"].dt.date)["Total Cost"]
            .sum()
            .reset_index(name="Total Cost")
        )

        st.plotly_chart(
            px.bar(daily_df, x="Date", y="Total Cost",
                   title="📅 Daily Charging Spend (MYR)"),
            use_container_width=True
        )

        st.plotly_chart(
            px.pie(df, names="Type", values="Total Cost",
                   hole=0.5, title="🔌 AC vs DC Cost Split"),
            use_container_width=True
        )

    with col2:
        st.plotly_chart(
            px.scatter(
                df,
                x="kWh",
                y="Total Cost",
                color="Provider",
                size="Cost_per_kWh",
                hover_data=["Location"],
                title="💰 Cost vs Energy"
            ),
            use_container_width=True
        )

        st.plotly_chart(
            px.box(
                df,
                x="Type",
                y="Session_Duration_Proxy",
                title="⏱ Session Duration Proxy"
            ),
            use_container_width=True
        )

    heat_df = (
        df[df["Hour"] >= 0]
        .groupby(["Day", "Hour"])
        .size()
        .reset_index(name="Sessions")
    )

    st.plotly_chart(
        px.density_heatmap(
            heat_df,
            x="Hour",
            y="Day",
            z="Sessions",
            color_continuous_scale="Turbo",
            title="🔥 Charging Behavior Heatmap (Day × Hour)"
        ),
        use_container_width=True
    )

# ===============================
# LOCATION TAB — BIG POPUPS
# ===============================
with tab_location:
    loc_stats = (
        df.dropna(subset=["Latitude", "Longitude"])
        .groupby("Location")
        .agg(
            Sessions=("Location", "count"),
            Total_Cost=("Total Cost", "sum"),
            Total_kWh=("kWh", "sum"),
            Latitude=("Latitude", "first"),
            Longitude=("Longitude", "first")
        )
        .reset_index()
    )

    if loc_stats.empty:
        st.warning("No valid geocoded locations.")
    else:
        loc_stats["popup"] = loc_stats.apply(
            lambda r: (
                f"<b>{r.Location}</b><br/>"
                f"🔌 Sessions: {r.Sessions}<br/>"
                f"⚡ Energy: {r.Total_kWh:.1f} kWh<br/>"
                f"💰 Cost: MYR {r.Total_Cost:.2f}"
            ),
            axis=1
        )

        deck = pdk.Deck(
            initial_view_state=pdk.ViewState(
                latitude=loc_stats["Latitude"].mean(),
                longitude=loc_stats["Longitude"].mean(),
                zoom=6
            ),
            layers=[
                pdk.Layer(
                    "ScatterplotLayer",
                    data=loc_stats,
                    get_position=["Longitude", "Latitude"],
                    get_radius="Sessions * 800",
                    radius_min_pixels=15,
                    radius_max_pixels=80,
                    get_fill_color=[0, 140, 255, 180],
                    get_line_color=[255, 255, 255],
                    line_width_min_pixels=2,
                    pickable=True
                )
            ],
            tooltip={
                "html": "{popup}",
                "style": {
                    "backgroundColor": "white",
                    "color": "black",
                    "fontSize": "14px",
                    "padding": "12px",
                    "borderRadius": "10px"
                }
            }
        )

        st.pydeck_chart(deck, use_container_width=True)


