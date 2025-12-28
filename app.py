import streamlit as st
import pandas as pd
import plotly.express as px
import pydeck as pdk
import os
import time
from geopy.geocoders import Nominatim

# =========================
# CONFIG
# =========================
RAWDATA = "ev_charging_log_my.csv"
CURRENCY = "MYR"

EXPECTED_COLUMNS = [
    "Date","Provider","Location","Type","kWh",
    "Total Cost","Cost_per_kWh","Month"
]

st.set_page_config(page_title="Malaysia EV Charging Tracker", page_icon="⚡", layout="wide")
px.defaults.template = "simple_white"

# =========================
# ENSURE CSV EXISTS WITH HEADERS
# =========================
if not os.path.isfile(RAWDATA) or os.path.getsize(RAWDATA) == 0:
    pd.DataFrame(columns=EXPECTED_COLUMNS).to_csv(RAWDATA, index=False)

# =========================
# LOAD DATA SAFELY
# =========================
@st.cache_data
def load_data():
    df = pd.read_csv(RAWDATA)
    if not df.empty:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df["Month"] = df["Date"].dt.to_period("M").astype(str)
        weekdays_order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
        df["Day"] = pd.Categorical(df["Date"].dt.day_name(), categories=weekdays_order, ordered=True)
    return df

df = load_data()

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
    "➕ Log Session", "📊 Overview", "📈 Insights", "📍 Locations", "🗂 Data"
])

# =========================
# TAB 1 — LOG SESSION
# =========================
with tab_log:
    providers = [
        "Gentari","JomCharge","chargEV","Shell Recharge",
        "TNB Electron","ChargeSini","Tesla Supercharger",
        "DC Handal","Home","Other"
    ]
    col1, col2 = st.columns(2)
    with col1:
        selected_provider = st.selectbox("Provider", providers)
    with col2:
        other_provider = st.text_input("Custom Provider", disabled=(selected_provider != "Other"))

    with st.form("log_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            date_val = st.date_input("Date")
            location = st.text_input("Location")
        with c2:
            output_type = st.radio("Type", ["AC","DC"], horizontal=True)
            kwh_val = st.number_input("Energy (kWh)", min_value=0.1, step=0.1)
        with c3:
            total_cost = st.number_input(f"Total Cost ({CURRENCY})", min_value=0.0, step=0.01)

        submitted = st.form_submit_button("Save Session")
        if submitted:
    provider = other_provider.strip() if selected_provider == "Other" else selected_provider
    if not provider:
        st.error("Please specify provider name.")
    else:
        new_row = pd.DataFrame([{
            "Date": pd.to_datetime(date_val),
            "Provider": provider,
            "Location": location.strip(),
            "Type": output_type,
            "kWh": kwh_val,
            "Total Cost": total_cost,
            "Cost_per_kWh": round(total_cost / kwh_val, 3),
            "Month": str(pd.to_datetime(date_val).to_period("M"))
        }])
        new_row.to_csv(RAWDATA, mode="a", header=False, index=False)
        st.success("Charging session saved")
        st.runtime.scriptrunner.script_request_rerun()

# =========================
# TAB 2 — OVERVIEW
# =========================
with tab_overview:
    if df.empty:
        st.info("No data available yet.")
    else:
        m1,m2,m3,m4 = st.columns(4)
        m1.metric("Total Spent", f"{CURRENCY} {df['Total Cost'].sum():.2f}")
        m2.metric("Avg / kWh", f"{CURRENCY} {df['Cost_per_kWh'].mean():.2f}")
        m3.metric("Energy Used", f"{df['kWh'].sum():.1f} kWh")
        m4.metric("Sessions", len(df))

# =========================
# TAB 3 — INSIGHTS
# =========================
with tab_insights:
    if df.empty:
        st.info("No data available yet.")
    else:
        col1,col2 = st.columns(2)
        with col1:
            daily_df = df.groupby(df["Date"].dt.date)["Total Cost"].sum().reset_index()
            fig_daily = px.bar(daily_df, x="Date", y="Total Cost", title="Daily Spending")
            st.plotly_chart(fig_daily, use_container_width=True)

            fig_type = px.pie(df, names="Type", hole=0.5, title="AC vs DC")
            st.plotly_chart(fig_type, use_container_width=True)

            df_valid = df[df["kWh"]>0].copy()
            df_valid["Duration_Proxy"] = df_valid["Total Cost"]/df_valid["kWh"]
            fig_duration = px.histogram(df_valid, x="Duration_Proxy", nbins=20, title="Session Duration Proxy (Cost per kWh)")
            st.plotly_chart(fig_duration, use_container_width=True)

        with col2:
            fig_scatter = px.scatter(df, x="kWh", y="Total Cost", color="Provider", size="Cost_per_kWh", title="Cost vs Energy", hover_data=["Location"])
            st.plotly_chart(fig_scatter, use_container_width=True)

            ac_dc_df = df.groupby("Type")["Total Cost"].mean().reset_index()
            fig_ac_dc = px.bar(ac_dc_df, x="Type", y="Total Cost", title="Average Cost: AC vs DC", color="Type", color_discrete_map={"AC":"#636EFA","DC":"#EF553B"})
            st.plotly_chart(fig_ac_dc, use_container_width=True)

            heatmap_df = df.groupby(["Day","Type"])["kWh"].sum().reset_index()
            fig_heatmap = px.density_heatmap(heatmap_df, x="Day", y="Type", z="kWh", title="Charging Behavior by Day (kWh)", color_continuous_scale="Viridis")
            st.plotly_chart(fig_heatmap, use_container_width=True)

# =========================
# TAB 4 — LOCATIONS + MAP
# =========================
with tab_locations:
    if df.empty or df["Location"].dropna().empty:
        st.info("No location data available yet.")
    else:
        loc_summary = df[df["Location"].notna() & (df["Location"]!="")].groupby("Location").agg(
            sessions=("Location","count"),
            total_spent=("Total Cost","sum"),
            average_cost=("Cost_per_kWh","mean")
        ).reset_index()

        st.write("### 📍 Top Locations")
        st.dataframe(loc_summary.sort_values("total_spent",ascending=False))

        geolocator = Nominatim(user_agent="ev_tracker_app")
        coords=[]
        for idx,row in loc_summary.iterrows():
            try:
                loc = geolocator.geocode(row["Location"] + ", Malaysia")
                if loc: coords.append((loc.latitude, loc.longitude))
                else: coords.append((None,None))
            except:
                coords.append((None,None))
            time.sleep(1)

        loc_summary["lat"] = [c[0] for c in coords]
        loc_summary["lon"] = [c[1] for c in coords]
        map_df = loc_summary.dropna(subset=["lat","lon"])

        if map_df.empty:
            st.warning("Unable to geocode any location.")
        else:
            map_df["popup"] = map_df.apply(lambda r: f"{r.Location}\nSessions: {r.sessions}\nTotal Cost: {CURRENCY} {r.total_spent:.2f}", axis=1)
            deck = pdk.Deck(
                map_style="mapbox://styles/mapbox/streets-v11",
                initial_view_state=pdk.ViewState(latitude=map_df["lat"].mean(), longitude=map_df["lon"].mean(), zoom=10, pitch=0),
                layers=[pdk.Layer("ScatterplotLayer", data=map_df, get_position=["lon","lat"], get_fill_color=[255,100,90], get_radius=500, pickable=True)],
                tooltip={"text":"{popup}"}
            )
            st.pydeck_chart(deck)

# =========================
# TAB 5 — DATA EDITOR
# =========================
with tab_data:
    if df.empty:
        st.info("No data available yet.")
    else:
        edited_df = st.data_editor(df.sort_values("Date",ascending=False), num_rows="dynamic")
        if st.button("Save Changes"):
            edited_df.to_csv(RAWDATA, index=False)
            st.success("Data saved successfully")
            st.experimental_rerun()
