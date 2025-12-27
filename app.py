import streamlit as st
import pandas as pd
import plotly.express as px
import os
import time
from geopy.geocoders import Nominatim
import pydeck as pdk

# =========================
# CONFIG
# =========================
RAWDATA = "rawdata.csv"
CURRENCY = "MYR"

st.set_page_config(
    page_title="Malaysia EV Charging Tracker",
    page_icon="⚡",
    layout="wide"
)

px.defaults.template = "simple_white"

# =========================
# STYLE
# =========================
st.markdown("""
<style>
section[data-testid="stSidebar"] { background-color: #fafafa; }
h1, h2, h3 { font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# =========================
# HEADER
# =========================
st.markdown("""
# Malaysia EV Charging Tracker  
<small style="color:gray">EV charging cost & usage insights</small>
""", unsafe_allow_html=True)

# =========================
# LOAD DATA
# =========================
EXPECTED_COLUMNS = [
    "Date", "Provider", "Location", "Type",
    "kWh", "Total Cost", "Cost_per_kWh",
    "Month", "Latitude", "Longitude"
]

if os.path.isfile(RAWDATA):
    df = pd.read_csv(RAWDATA)
    df["Date"] = pd.to_datetime(df["Date"])
else:
    df = pd.DataFrame(columns=EXPECTED_COLUMNS)

if not df.empty:
    df["Month"] = df["Date"].dt.to_period("M").astype(str)
    weekdays = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    df["Day"] = pd.Categorical(df["Date"].dt.day_name(), categories=weekdays, ordered=True)

# =========================
# FREE AUTO-GEOCODING (CACHED)
# =========================
if not df.empty:
    if "Latitude" not in df.columns:
        df["Latitude"] = None
    if "Longitude" not in df.columns:
        df["Longitude"] = None

    geolocator = Nominatim(user_agent="ev_tracker_app")

    missing_locations = df[
        df["Location"].notna() &
        ((df["Latitude"].isna()) | (df["Longitude"].isna()))
    ]["Location"].unique()

    if len(missing_locations) > 0:
        with st.spinner("📍 Geocoding new locations (free OpenStreetMap)..."):
            for loc in missing_locations:
                try:
                    geo = geolocator.geocode(f"{loc}, Malaysia")
                    if geo:
                        df.loc[df["Location"] == loc, "Latitude"] = geo.latitude
                        df.loc[df["Location"] == loc, "Longitude"] = geo.longitude
                    time.sleep(1)  # Nominatim rate limit
                except Exception:
                    pass
        df.to_csv(RAWDATA, index=False)

# =========================
# SIDEBAR FILTER
# =========================
with st.sidebar:
    st.header("Filters")
    if not df.empty:
        months = sorted(df["Month"].unique(), reverse=True)
        selected_month = st.selectbox("Month", ["All"] + months)
        if selected_month != "All":
            df = df[df["Month"] == selected_month]

# =========================
# TABS
# =========================
tab_log, tab_overview, tab_insights, tab_locations, tab_data = st.tabs([
    "➕ Log Session",
    "📊 Overview",
    "📈 Insights",
    "📍 Locations",
    "🗂 Data"
])

# =========================
# TAB — LOG SESSION
# =========================
with tab_log:
    providers = [
        "Gentari","JomCharge","chargEV","Shell Recharge",
        "TNB Electron","ChargeSini","Tesla Supercharger",
        "DC Handal","Home","Other"
    ]

    col1, col2 = st.columns(2)
    with col1:
        provider = st.selectbox("Provider", providers)
    with col2:
        other_provider = st.text_input("Custom Provider", disabled=(provider != "Other"))

    with st.form("log_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            date_val = st.date_input("Date")
            location = st.text_input("Location")
        with c2:
            charge_type = st.radio("Type", ["AC","DC"], horizontal=True)
            kwh = st.number_input("Energy (kWh)", min_value=0.1, step=0.1)
        with c3:
            cost = st.number_input(f"Total Cost ({CURRENCY})", min_value=0.0, step=0.01)

        if st.form_submit_button("Save Session"):
            final_provider = other_provider.strip() if provider == "Other" else provider
            if not final_provider:
                st.error("Provider name required")
            else:
                new = pd.DataFrame([{
                    "Date": pd.to_datetime(date_val),
                    "Provider": final_provider,
                    "Location": location.strip(),
                    "Type": charge_type,
                    "kWh": kwh,
                    "Total Cost": cost,
                    "Cost_per_kWh": round(cost / kwh, 3),
                    "Month": str(pd.to_datetime(date_val).to_period("M"))
                }])
                new.to_csv(RAWDATA, mode="a", header=not os.path.exists(RAWDATA), index=False)
                st.success("Session saved")
                st.rerun()

# =========================
# TAB — OVERVIEW
# =========================
with tab_overview:
    if df.empty:
        st.info("No data yet.")
    else:
        a,b,c,d = st.columns(4)
        a.metric("Total Spent", f"{CURRENCY} {df['Total Cost'].sum():.2f}")
        b.metric("Avg / kWh", f"{CURRENCY} {df['Cost_per_kWh'].mean():.2f}")
        c.metric("Energy Used", f"{df['kWh'].sum():.1f} kWh")
        d.metric("Sessions", len(df))

# =========================
# TAB — INSIGHTS
# =========================
with tab_insights:
    if df.empty:
        st.info("No data yet.")
    else:
        c1, c2 = st.columns(2)

        with c1:
            daily = df.groupby(df["Date"].dt.date)["Total Cost"].sum().reset_index()
            st.plotly_chart(px.bar(daily, x="Date", y="Total Cost", title="Daily Spending"), True)

            st.plotly_chart(px.pie(df, names="Type", hole=0.5, title="AC vs DC"), True)

            df_valid = df[df["kWh"] > 0]
            df_valid["Duration_Proxy"] = df_valid["Total Cost"] / df_valid["kWh"]
            st.plotly_chart(px.histogram(df_valid, x="Duration_Proxy", title="Session Duration Proxy"), True)

        with c2:
            st.plotly_chart(px.scatter(df, x="kWh", y="Total Cost", color="Provider",
                                        size="Cost_per_kWh", hover_data=["Location"],
                                        title="Cost vs Energy"), True)

            acdc = df.groupby("Type")["Total Cost"].mean().reset_index()
            st.plotly_chart(px.bar(acdc, x="Type", y="Total Cost", title="Avg Cost: AC vs DC"), True)

            heat = df.groupby(["Day","Type"])["kWh"].sum().reset_index()
            st.plotly_chart(px.density_heatmap(heat, x="Day", y="Type", z="kWh",
                                                title="Charging Behavior by Day"), True)

# =========================
# TAB — LOCATIONS (MAP)
# =========================
with tab_locations:
    if df.empty:
        st.info("No location data yet.")
    else:
        loc_stats = (
            df[df["Location"].notna()]
            .groupby("Location")
            .agg(
                Sessions=("Location","count"),
                Total_Cost=("Total Cost","sum"),
                Total_kWh=("kWh","sum"),
                Latitude=("Latitude","first"),
                Longitude=("Longitude","first")
            )
            .reset_index()
            .dropna(subset=["Latitude","Longitude"])
        )

        st.subheader("📍 Charging Sessions Map")

        loc_stats["popup"] = loc_stats.apply(
            lambda r: f"{r.Location}\nSessions: {r.Sessions}\nCost: MYR {r.Total_Cost:.2f}",
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
                    get_position=["Longitude","Latitude"],
                    get_radius="Sessions * 120",
                    get_fill_color=[0, 160, 255],
                    pickable=True
                )
            ],
            tooltip={"text": "{popup}"}
        )

        st.pydeck_chart(deck)

# =========================
# TAB — DATA
# =========================
with tab_data:
    if df.empty:
        st.info("No data yet.")
    else:
        edited = st.data_editor(df.sort_values("Date", ascending=False), num_rows="dynamic")
        if st.button("Save Changes"):
            edited.to_csv(RAWDATA, index=False)
            st.success("Saved")
            st.rerun()
