import streamlit as st
import pandas as pd
import plotly.express as px
import os

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
# LOAD DATA (Cache Removed to Fix Update Issue)
# =========================
def load_data():
    try:
        df = pd.read_csv(RAWDATA)
        if not df.empty:
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
            # Create Month column for filtering (YYYY-MM)
            df["Month"] = df["Date"].dt.to_period("M").astype(str)
            df["Day"] = df["Date"].dt.day_name()
        return df
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return pd.DataFrame(columns=EXPECTED_COLUMNS)

# Load the full dataset
df = load_data()

# =========================
# SIDEBAR FILTER (Safe Logic)
# =========================
# We use a separate variable 'filtered_df' for visuals so we don't 
# accidentally delete data when saving in the Data Tab.
filtered_df = df.copy()

with st.sidebar:
    st.header("Filters")
    if not df.empty:
        # Sort months descending
        unique_months = df["Month"].unique().tolist()
        # Handle case where sort fails if mixed types
        try:
            months = sorted(unique_months, reverse=True)
        except:
            months = unique_months
            
        selected_month = st.selectbox("Month", ["All"] + months)
        
        if selected_month != "All":
            filtered_df = df[df["Month"] == selected_month]

# =========================
# TABS
# =========================
tab_log, tab_overview, tab_insights, tab_location, tab_data = st.tabs([
    "➕ Log Session",
    "📊 Overview",
    "📈 Insights",
    "📍 Locations",
    "🗂 Data (Edit)"
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
            # Determine provider name
            provider = other_provider.strip() if selected_provider == "Other" else selected_provider
            
            if not provider:
                st.error("Please specify provider name.")
            else:
                # Calculate derived fields
                cost_per_kwh = round(total_cost / kwh_val, 3) if kwh_val > 0 else 0
                month_str = str(pd.to_datetime(date_val).to_period("M"))

                new_data = {
                    "Date": date_val,
                    "Provider": provider,
                    "Location": location.strip(),
                    "Type": output_type,
                    "kWh": kwh_val,
                    "Total Cost": total_cost,
                    "Cost_per_kWh": cost_per_kwh,
                    "Month": month_str
                }
                
                new_row = pd.DataFrame([new_data])
                
                # Append to CSV
                # header=False because file already exists with headers
                new_row.to_csv(RAWDATA, mode="a", header=False, index=False)
                
                st.success("Charging session saved!")
                st.rerun() # Force a rerun to show new data immediately

# =========================
# TAB 2 — OVERVIEW
# =========================
with tab_overview:
    if filtered_df.empty:
        st.info("No data available for this selection.")
    else:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Spent", f"{CURRENCY} {filtered_df['Total Cost'].sum():.2f}")
        m2.metric("Avg / kWh", f"{CURRENCY} {filtered_df['Cost_per_kWh'].mean():.2f}")
        m3.metric("Energy Used", f"{filtered_df['kWh'].sum():.1f} kWh")
        m4.metric("Sessions", len(filtered_df))

# =========================
# TAB 3 — INSIGHTS
# =========================
with tab_insights:
    if filtered_df.empty:
        st.info("No data available for this selection.")
    else:
        col1, col2 = st.columns(2)

        with col1:
            # Daily Spending
            daily_df = filtered_df.groupby(filtered_df["Date"].dt.date)["Total Cost"].sum().reset_index()
            fig_daily = px.bar(daily_df, x="Date", y="Total Cost", title="Daily Spending")
            st.plotly_chart(fig_daily, use_container_width=True)

            # AC vs DC Pie Chart
            fig_type = px.pie(filtered_df, names="Type", hole=0.5, title="AC vs DC Session Count")
            st.plotly_chart(fig_type, use_container_width=True)

        with col2:
            # Scatter Plot
            fig_scatter = px.scatter(
                filtered_df, x="kWh", y="Total Cost", color="Provider",
                size="Cost_per_kWh", title="Cost vs Energy",
                hover_data=["Location"]
            )
            st.plotly_chart(fig_scatter, use_container_width=True)

            # Heatmap (if Day exists)
            if "Day" in filtered_df.columns:
                heatmap_df = filtered_df.groupby(["Day","Type"])["kWh"].sum().reset_index()
                # Order days correctly
                day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                fig_heatmap = px.density_heatmap(
                    heatmap_df, x="Day", y="Type", z="kWh",
                    category_orders={"Day": day_order},
                    color_continuous_scale="Viridis",
                    title="Charging Volume by Day (kWh)"
                )
                st.plotly_chart(fig_heatmap, use_container_width=True)

# =========================
# TAB 4 — LOCATIONS
# =========================
with tab_location:
    if filtered_df.empty:
        st.info("No data available.")
    else:
        # Filter out empty locations
        loc_df = filtered_df[filtered_df["Location"].notna() & (filtered_df["Location"] != "")]
        
        if loc_df.empty:
            st.info("No location names logged yet.")
        else:
            top_locations = (
                loc_df.groupby("Location")["Total Cost"]
                .sum().sort_values(ascending=False)
                .head(5).reset_index()
            )
            fig_loc = px.bar(top_locations, x="Location", y="Total Cost",
                             text="Total Cost", title="Top 5 Locations by Spending")
            fig_loc.update_traces(texttemplate="%{text:.2f}", textposition="outside")
            st.plotly_chart(fig_loc, use_container_width=True)

# =========================
# TAB 5 — DATA (EDIT FULL DB)
# =========================
with tab_data:
    st.warning("⚠️ Editing data here changes the raw file permanently.")
    
    if df.empty:
        st.info("No data available yet.")
    else:
        # CRITICAL: We pass 'df' (the full dataset) here, NOT 'filtered_df'
        # This prevents accidental deletion of hidden months when saving.
        edited_df = st.data_editor(
            df.sort_values("Date", ascending=False), 
            num_rows="dynamic",
            use_container_width=True
        )
        
        if st.button("Save Changes to CSV"):
            try:
                # Ensure the columns match the expected structure before saving
                final_save_df = edited_df[EXPECTED_COLUMNS]
                final_save_df.to_csv(RAWDATA, index=False)
                st.success("Data saved successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"Error saving data: {e}")
