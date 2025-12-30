import streamlit as st
import pandas as pd
import plotly.express as px
import os
from geopy.geocoders import Nominatim
from streamlit_gsheets import GSheetsConnection

# =========================
# CONFIG
# =========================
CURRENCY = "MYR"

st.set_page_config(
    page_title="Malaysia EV Charging Tracker",
    page_icon="⚡",
    layout="wide"
)

# Set Plotly map style
px.set_mapbox_access_token(os.environ.get("MAPBOX_TOKEN", ""))
px.defaults.template = "simple_white"

# =========================
# MINIMAL CSS
# =========================
st.markdown("""
<style>
section[data-testid="stSidebar"] { background-color: #fafafa; }
h1, h2, h3 { font-weight: 600; }
.plotly .mapboxgl-popup { z-index: 1000 !important; }
</style>
""", unsafe_allow_html=True)

# =========================
# HEADER
# =========================
st.markdown("""
# Malaysia EV Charging Tracker
<small style="color:gray">Cloud Edition (Google Sheets)</small>
""", unsafe_allow_html=True)

# =========================
# GOOGLE SHEETS CONNECTION
# =========================
# We use ttl=0 to ensure we always fetch fresh data, or a small number like 5 seconds
conn = st.connection("gsheets", type=GSheetsConnection)

EXPECTED_COLUMNS = ["Date","Provider","Location","Latitude","Longitude","Type","kWh","Total Cost","Cost_per_kWh","Month"]

def load_data():
    try:
        # Read data from the configured Google Sheet
        df = conn.read(worksheet="Sheet1", ttl=0)
        
        # If the sheet is empty (only headers), handle gracefully
        if df.empty:
            return pd.DataFrame(columns=EXPECTED_COLUMNS)

        # 1. Ensure coordinate columns exist
        if "Latitude" not in df.columns: df["Latitude"] = pd.NA
        if "Longitude" not in df.columns: df["Longitude"] = pd.NA
        
        # 2. Process Data Types
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df["Month"] = df["Date"].dt.to_period("M").astype(str)
        df["Day"] = df["Date"].dt.day_name()
        df["Latitude"] = pd.to_numeric(df["Latitude"], errors='coerce')
        df["Longitude"] = pd.to_numeric(df["Longitude"], errors='coerce')
        
        # Ensure numerical columns are actually numbers (Google Sheets can sometimes send strings)
        df["kWh"] = pd.to_numeric(df["kWh"], errors='coerce').fillna(0.0)
        df["Total Cost"] = pd.to_numeric(df["Total Cost"], errors='coerce').fillna(0.0)
        df["Cost_per_kWh"] = pd.to_numeric(df["Cost_per_kWh"], errors='coerce').fillna(0.0)

        # 3. Clean Reindexing
        cols_to_use = EXPECTED_COLUMNS + ["Day"]
        cols_to_use = list(dict.fromkeys(cols_to_use))
        
        # Reindex checks if columns exist and orders them, adds NaN if missing
        df = df.reindex(columns=cols_to_use)
        
        # Filter out rows where Date is NaT (empty rows from sheet)
        df = df.dropna(subset=["Date"])
        
        return df
    except Exception as e:
        st.error(f"Error loading data from Google Sheets: {e}")
        return pd.DataFrame(columns=EXPECTED_COLUMNS)

df = load_data()

# =========================
# GEOCODING FUNCTION
# =========================
def get_coordinates(location_name):
    try:
        geolocator = Nominatim(user_agent="my_ev_tracker_v1")
        search_query = f"{location_name}, Malaysia"
        location = geolocator.geocode(search_query)
        if location:
            return location.latitude, location.longitude
        return None, None
    except:
        return None, None

# =========================
# SIDEBAR FILTER
# =========================
filtered_df = df.copy()
with st.sidebar:
    st.header("Filters")
    if not df.empty and "Month" in df.columns:
        unique_months = df["Month"].dropna().unique().tolist()
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
    "📍 Locations (Map)",
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
        other_provider = st.text_input("Custom Provider", disabled=(selected_provider != "Other"))

    with st.form("log_form", clear_on_submit=True):
        st.write("---")
        c1, c2, c3 = st.columns(3)
        with c1:
            date_val = st.date_input("Date")
            location_name = st.text_input("Location Name")
        with c2:
            output_type = st.radio("Type", ["AC", "DC"], horizontal=True)
            kwh_val = st.number_input("Energy (kWh)", min_value=0.1, step=0.1)
        with c3:
            total_cost = st.number_input(f"Total Cost ({CURRENCY})", min_value=0.0, step=0.01)

        st.write("---")
        st.caption("Coordinates (Leave 0.00 to auto-detect)")
        geo_c1, geo_c2 = st.columns(2)
        with geo_c1:
            lat_val = st.number_input("Latitude", value=0.00, format="%.5f")
        with geo_c2:
            lon_val = st.number_input("Longitude", value=0.00, format="%.5f")

        submitted = st.form_submit_button("Save Session", type="primary")

        if submitted:
            provider = other_provider.strip() if selected_provider == "Other" else selected_provider
            
            if not provider:
                st.error("Please specify provider name.")
            else:
                # --- GEOCODING ---
                final_lat = lat_val
                final_lon = lon_val
                
                if (final_lat == 0.00 or final_lon == 0.00) and location_name.strip():
                    with st.spinner(f"Searching map for '{location_name}'..."):
                        found_lat, found_lon = get_coordinates(location_name)
                        if found_lat:
                            final_lat = found_lat
                            final_lon = found_lon
                            st.toast(f"📍 Found: {final_lat:.4f}, {final_lon:.4f}")
                        else:
                            st.warning("Coordinates not found. Saved without them.")
                            final_lat = pd.NA
                            final_lon = pd.NA
                elif final_lat == 0.00 and final_lon == 0.00:
                    final_lat = pd.NA
                    final_lon = pd.NA

                # --- SAVE TO GOOGLE SHEETS ---
                cost_per_kwh = round(total_cost / kwh_val, 3) if kwh_val > 0 else 0
                month_str = str(pd.to_datetime(date_val).to_period("M"))

                new_data = pd.DataFrame([{
                    "Date": date_val, # Keep as object/date for now, Sheets handles it
                    "Provider": provider,
                    "Location": location_name.strip(),
                    "Latitude": final_lat,
                    "Longitude": final_lon,
                    "Type": output_type,
                    "kWh": kwh_val,
                    "Total Cost": total_cost,
                    "Cost_per_kWh": cost_per_kwh,
                    "Month": month_str
                }])
                
                try:
                    # Append logic: Read full DF (already in memory as `df`), concat, and update
                    # We drop 'Day' because it is a calculated column, we don't save it to Sheets
                    # We also convert Date to string to ensure Sheets doesn't get confused
                    updated_df = pd.concat([df, new_data], ignore_index=True)
                    
                    # Ensure we only write the columns we want to persist
                    save_df = updated_df[EXPECTED_COLUMNS]
                    
                    # Convert dates to string YYYY-MM-DD for consistency in Sheets
                    save_df["Date"] = pd.to_datetime(save_df["Date"]).dt.strftime('%Y-%m-%d')
                    
                    conn.update(worksheet="Sheet1", data=save_df)
                    st.toast("Saved to Google Sheets!", icon="☁️")
                    st.cache_data.clear() # Clear cache to force reload
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to save to Google Sheets: {e}")

# =========================
# TAB 2 — OVERVIEW
# =========================
with tab_overview:
    if filtered_df.empty:
        st.info("No data available.")
    else:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Spent", f"{CURRENCY} {filtered_df['Total Cost'].sum():.2f}")
        avg_cost = filtered_df['Cost_per_kWh'].mean()
        m2.metric("Avg / kWh", f"{CURRENCY} {0.00 if pd.isna(avg_cost) else avg_cost:.2f}")
        m3.metric("Energy Used", f"{filtered_df['kWh'].sum():.1f} kWh")
        m4.metric("Sessions", len(filtered_df))

# =========================
# TAB 3 — INSIGHTS
# =========================
with tab_insights:
    if filtered_df.empty:
        st.info("No data available.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            daily_df = filtered_df.groupby(filtered_df["Date"].dt.date)["Total Cost"].sum().reset_index()
            fig_daily = px.bar(daily_df, x="Date", y="Total Cost", title="Daily Spending")
            st.plotly_chart(fig_daily, use_container_width=True)

            fig_type = px.pie(filtered_df, names="Type", hole=0.5, title="AC vs DC")
            st.plotly_chart(fig_type, use_container_width=True)

        with col2:
            fig_scatter = px.scatter(
                filtered_df, x="kWh", y="Total Cost", color="Provider",
                size="Cost_per_kWh", title="Cost vs Energy",
                hover_data=["Location"]
            )
            st.plotly_chart(fig_scatter, use_container_width=True)

            if "Day" in filtered_df.columns:
                heatmap_df = filtered_df.groupby(["Day","Type"])["kWh"].sum().reset_index()
                day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                fig_heatmap = px.density_heatmap(
                    heatmap_df, x="Day", y="Type", z="kWh",
                    category_orders={"Day": day_order},
                    color_continuous_scale="Viridis",
                    title="Charging Volume by Day"
                )
                fig_heatmap.update_layout(xaxis_title=None, yaxis_title=None)
                st.plotly_chart(fig_heatmap, use_container_width=True)

# =========================
# TAB 4 — LOCATIONS (MAP)
# =========================
with tab_location:
    st.header("Location Analysis")
    map_df = filtered_df.dropna(subset=["Latitude", "Longitude"])
    
    if map_df.empty:
        st.warning("No coordinates found.")
    else:
        location_agg = map_df.groupby(["Location", "Latitude", "Longitude"]).agg(
            Total_Sessions=("Date", "count"),
            Total_Spent=("Total Cost", "sum")
        ).reset_index()

        fig_map = px.scatter_mapbox(
            location_agg,
            lat="Latitude", lon="Longitude",
            size="Total_Sessions", size_max=30,
            color="Total_Spent", color_continuous_scale=px.colors.sequential.Plasma,
            hover_name="Location",
            zoom=10,
            title=f"Charging Locations ({len(location_agg)} sites)"
        )
        fig_map.update_layout(mapbox_style="open-street-map", margin={"r":0,"t":40,"l":0,"b":0})
        st.plotly_chart(fig_map, use_container_width=True)
    
    st.divider()
    # Top Locations Bar Chart
    named_loc_df = filtered_df[filtered_df["Location"].notna() & (filtered_df["Location"].str.strip() != "")]
    if not named_loc_df.empty:
        top_locations = (
            named_loc_df.groupby("Location")["Total Cost"]
            .sum().sort_values(ascending=False)
            .head(5).reset_index()
        )
        fig_loc = px.bar(top_locations, x="Total Cost", y="Location", text="Total Cost", orientation='h')
        fig_loc.update_traces(texttemplate="%{text:.2f}", textposition="outside")
        fig_loc.update_layout(yaxis_title=None)
        st.plotly_chart(fig_loc, use_container_width=True)

# =========================
# TAB 5 — DATA (EDIT)
# =========================
with tab_data:
    st.warning("⚠️ Changes here overwrite the Google Sheet!")
    
    if df.empty:
        st.info("No data.")
    else:
        display_cols = ["Date", "Provider", "Location", "Latitude", "Longitude", "Type", "kWh", "Total Cost", "Month"]
        existing_cols = [c for c in display_cols if c in df.columns]
        
        edited_df = st.data_editor(
            df.sort_values("Date", ascending=False)[existing_cols], 
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "Latitude": st.column_config.NumberColumn(format="%.5f"),
                "Longitude": st.column_config.NumberColumn(format="%.5f"),
            }
        )
        
        if st.button("Save Changes to Google Sheet", type="primary"):
            try:
                # Prepare clean DF for saving
                final_save_df = edited_df[EXPECTED_COLUMNS].copy()
                final_save_df["Date"] = pd.to_datetime(final_save_df["Date"]).dt.strftime('%Y-%m-%d')
                
                conn.update(worksheet="Sheet1", data=final_save_df)
                st.toast("Google Sheet updated!", icon="☁️")
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Error saving: {e}")
