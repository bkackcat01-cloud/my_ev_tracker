import streamlit as st
import pandas as pd
import plotly.express as px
import os

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
# MINIMAL CSS
# =========================
st.markdown("""
<style>
section[data-testid="stSidebar"] {
    background-color: #fafafa;
}
h1, h2, h3 {
    font-weight: 600;
}
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
    "Date", "Provider", "Location",
    "Type", "kWh", "Total Cost",
    "Cost_per_kWh", "Month"
]

if os.path.isfile(RAWDATA):
    df = pd.read_csv(RAWDATA)
    df["Date"] = pd.to_datetime(df["Date"])
else:
    df = pd.DataFrame(columns=EXPECTED_COLUMNS)

if not df.empty:
    df["Month"] = df["Date"].dt.to_period("M").astype(str)
    df["Day"] = df["Date"].dt.day_name()

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
tab_log, tab_overview, tab_insights, tab_data = st.tabs([
    "➕ Log Session",
    "📊 Overview",
    "📈 Insights",
    "🗂 Data"
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
            provider = (
                other_provider.strip()
                if selected_provider == "Other"
                else selected_provider
            )

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

                if os.path.isfile(RAWDATA):
                    new_row.to_csv(RAWDATA, mode="a", header=False, index=False)
                else:
                    new_row.to_csv(RAWDATA, index=False)

                st.success("Charging session saved")
                st.rerun()

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
# TAB 3 — INSIGHTS (YOUR REQUESTED GRAPHS)
# =========================
with tab_insights:

    if df.empty:
        st.info("No data available yet.")
    else:
        col1, col2 = st.columns(2)

        # --- Session Duration Proxy ---
        with col1:
            fig_kwh = px.histogram(
                df,
                x="kWh",
                nbins=20,
                title="Charging Session Size (kWh)"
            )
            st.plotly_chart(fig_kwh, use_container_width=True)

        daily_df = df.groupby(df["Date"].dt.date)["Total Cost"].sum().reset_index()

            fig_daily = px.bar(
                daily_df,
                x="Date",
                y="Total Cost",
                title="Daily Spending"
            )
            st.plotly_chart(fig_daily, use_container_width=True)

            fig_type = px.pie(
                df,
                names="Type",
                hole=0.5,
                title="AC vs DC"
            )
            st.plotly_chart(fig_type, use_container_width=True)

        # --- AC vs DC Cost Comparison ---
        with col2:
            type_cost = (
                df.groupby("Type")["Cost_per_kWh"]
                .mean()
                .reset_index()
            )

            fig_type_cost = px.bar(
                type_cost,
                x="Type",
                y="Cost_per_kWh",
                title="Average Cost per kWh: AC vs DC"
            )
            st.plotly_chart(fig_type_cost, use_container_width=True)

        st.divider()

        # --- Heatmap: Charging Behavior by Day ---
        day_order = [
            "Monday", "Tuesday", "Wednesday",
            "Thursday", "Friday", "Saturday", "Sunday"
        ]

        heatmap_df = (
            df.groupby("Day")["Total Cost"]
            .sum()
            .reindex(day_order)
            .reset_index()
        )

        fig_heatmap = px.imshow(
            heatmap_df[["Total Cost"]].T,
            x=heatmap_df["Day"],
            aspect="auto",
            title="Charging Spend by Day of Week"
        )

        st.plotly_chart(fig_heatmap, use_container_width=True)

# =========================
# TAB 4 — DATA
# =========================
with tab_data:

    if df.empty:
        st.info("No data available yet.")
    else:
        edited_df = st.data_editor(
            df.sort_values("Date", ascending=False),
            num_rows="dynamic"
        )

        if st.button("Save Changes"):
            edited_df.to_csv(RAWDATA, index=False)
            st.success("Data saved successfully")
            st.rerun()

