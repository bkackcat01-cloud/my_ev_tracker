import streamlit as st
import pandas as pd
import plotly.express as px
import os
from datetime import date

# =========================
# CONFIG
# =========================
RAWDATA = "ev_charging_log_my.csv"
CURRENCY = "MYR"

st.set_page_config(
    page_title="Malaysia EV Charging Tracker",
    page_icon="⚡",
    layout="wide"
)

px.defaults.template = "simple_white"

# =========================
# MINIMAL CSS
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
# ENSURE CSV EXISTS
# =========================
EXPECTED_COLUMNS = ["Date","Provider","Location","Type","kWh","Total Cost","Cost_per_kWh","Month"]
if not os.path.isfile(RAWDATA) or os.path.getsize(RAWDATA) == 0:
    pd.DataFrame(columns=EXPECTED_COLUMNS).to_csv(RAWDATA, index=False)

# =========================
# LOAD DATA
# =========================
@st.cache_data
def load_data():
    df = pd.read_csv(RAWDATA)
    if not df.empty:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df["Month"] = df["Date"].dt.to_period("M").astype(str)
        df["Day"] = df["Date"].dt.day_name()
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
tab_log, tab_overview, tab_insights, tab_data, tab_location = st.tabs([
    "➕ Log Session",
    "📊 Overview",
    "📈 Insights",
    "🗂 Data",
    "📍 Locations"
])

# =========================
# TAB 1 — LOG SESSION
# =========================
with tab_log:
    providers = [
        "Gentari", "JomCharge", "chargEV", "Shell Recharge",
        "TNB Electron", "ChargeSini", "Tesla Supercharger",
        "DC Handal", "Home", "Other"
    ]

    col1, col2 = st.columns(2)
    with col1:
        selected_provider = st.selectbox("Provider", providers)
    with col2:
        other_provider = st.text_input(
            "Custom Provider",
            disabled=(selected_provider != "Other")
        )

    with st.form("log_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)

        with c1:
            date_val = st.date_input("Date")
            location = st.text_input("Location")

        with c2:
            output_type = st.radio("Type", ["AC", "DC"], horizontal=True)
            kwh_val = st.number_input("Energy (kWh)", min_value=0.1, step=0.1)

        with c3:
            total_cost = st.number_input(
                f"Total Cost ({CURRENCY})",
                min_value=0.0,
                step=0.01
            )

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
        m1, m2, m3, m4 = st.columns(4)
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
        col1, col2 = st.columns(2)

        with col1:
            # Daily Spending
            daily_df = df.groupby(df["Date"].dt.date)["Total Cost"].sum().reset_index()
            fig_daily = px.bar(daily_df, x="Date", y="Total Cost", title="Daily Spending")
            st.plotly_chart(fig_daily, use_container_width=True)

            # AC vs DC Pie
            fig_type = px.pie(df, names="Type", hole=0.5, title="AC vs DC")
            st.plotly_chart(fig_type, use_container_width=True)

            # Session Duration Proxy
            df['Duration_Proxy'] = df['Total Cost'] / df['kWh']
            fig_duration = px.histogram(df, x="Duration_Proxy", nbins=20, title="Session Duration Proxy (Cost per kWh)")
            st.plotly_chart(fig_duration, use_container_width=True)

        with col2:
            # Cost vs Energy Scatter
            fig_scatter = px.scatter(
                df, x="kWh", y="Total Cost", color="Provider",
                size="Cost_per_kWh", title="Cost vs Energy",
                hover_data=["Location"]
            )
            st.plotly_chart(fig_scatter, use_container_width=True)

            # AC vs DC Cost Comparison
            ac_dc_df = df.groupby("Type")["Total Cost"].mean().reset_index()
            fig_ac_dc = px.bar(
                ac_dc_df, x="Type", y="Total Cost",
                color="Type", color_discrete_map={"AC":"#636EFA","DC":"#EF553B"},
                title="Average Cost: AC vs DC"
            )
            st.plotly_chart(fig_ac_dc, use_container_width=True)

            # Heatmap: Charging Behavior by Weekday
            if "Day" in df.columns:
                heatmap_df = df.groupby(["Day","Type"])["kWh"].sum().reset_index()
                fig_heatmap = px.density_heatmap(
                    heatmap_df, x="Day", y="Type", z="kWh",
                    color_continuous_scale="Viridis",
                    title="Charging Behavior by Day (kWh)"
                )
                st.plotly_chart(fig_heatmap, use_container_width=True)

# =========================
# TAB 4 — LOCATIONS
# =========================
with tab_location:
    if df.empty or df["Location"].dropna().empty:
        st.info("No location data available yet.")
    else:
        top_locations = (
            df[df["Location"].notna() & (df["Location"] != "")]
            .groupby("Location")["Total Cost"]
            .sum().sort_values(ascending=False)
            .head(5).reset_index()
        )
        fig_loc = px.bar(top_locations, x="Location", y="Total Cost",
                         text="Total Cost", title="Top 5 Locations by Spending")
        fig_loc.update_traces(texttemplate="%{text:.2f}", textposition="outside")
        st.plotly_chart(fig_loc, use_container_width=True)

# =========================
# TAB 5 — DATA
# =========================
with tab_data:
    if df.empty:
        st.info("No data available yet.")
    else:
        edited_df = st.data_editor(df.sort_values("Date", ascending=False), num_rows="dynamic")
        if st.button("Save Changes"):
            edited_df.to_csv(RAWDATA, index=False)
            st.success("Data saved successfully")
            st.runtime.scriptrunner.script_request_rerun()
