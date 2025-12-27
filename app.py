import streamlit as st
import pandas as pd
import plotly.express as px
import os

# --- Configuration ---
FILE_NAME = 'ev_charging_log_my.csv'
CURRENCY = "MYR"

st.set_page_config(page_title="Malaysia EV Tracker", page_icon="⚡", layout="wide")
st.title("🇲🇾 Malaysia EV Charging Tracker")

# --- 1. INSTANT INPUT SECTION ---
st.subheader("📝 Record New Session")

providers = [
    "Gentari", "JomCharge", "chargEV", "Shell Recharge (ParkEasy)", 
    "TNB Electron", "ChargeSini", "Tesla Supercharger", "DC Handal", "Home", "Other"
]

col_p1, col_p2 = st.columns([1, 2])
with col_p1:
    selected_provider = st.selectbox("Select Provider", providers)

with col_p2:
    other_name = ""
    if selected_provider == "Other":
        other_name = st.text_input("✍️ Specify Provider Name", placeholder="e.g. JusEV")

# --- 2. DATA DETAILS (Inside Form) ---
with st.form("charging_form", clear_on_submit=True):
    col1, col2, col3 = st.columns(3)
    
    with col1:
        date_val = st.date_input("Date")
        location = st.text_input("Location", placeholder="e.g. Pavilion Bukit Jalil")
    
    with col2:
        output_type = st.radio("Output Type", ["AC", "DC"], horizontal=True)
        kwh_val = st.number_input("Energy (kWh)", min_value=0.1, step=0.1)
        
    with col3:
        total_cost = st.number_input(f"Total Cost ({CURRENCY})", min_value=0.0, step=0.01)

    submitted = st.form_submit_button("💾 Save Session Data")

    if submitted:
        final_provider = other_name if selected_provider == "Other" else selected_provider
        
        if selected_provider == "Other" and not other_name.strip():
            st.error("Please enter a provider name in the 'Specify' box.")
        else:
            cost_per_kwh = total_cost / kwh_val if kwh_val > 0 else 0
            
            new_data = pd.DataFrame([{
                "Date": pd.to_datetime(date_val),
                "Provider": final_provider,
                "Location": location,
                "Type": output_type,
                "kWh": kwh_val,
                "Total Cost": total_cost,
                "Cost_per_kWh": round(cost_per_kwh, 3)
            }])

            if not os.path.isfile(FILE_NAME):
                new_data.to_csv(FILE_NAME, index=False)
            else:
                new_data.to_csv(FILE_NAME, mode='a', header=False, index=False)
            st.success(f"Successfully recorded session for {final_provider}!")

# --- 3. ANALYTICS SECTION ---
if os.path.isfile(FILE_NAME):
    df = pd.read_csv(FILE_NAME)
    df['Date'] = pd.to_datetime(df['Date'])
    df['Location'] = df['Location'].astype(str)  # 确保 Location 是字符串

    # --- Month Selector ---
    df['Month'] = df['Date'].dt.to_period('M').astype(str)
    months = sorted(df['Month'].unique(), reverse=True)
    selected_month = st.selectbox("📅 Select Month", options=["All"] + months, index=0)
    if selected_month != "All":
        df = df[df['Month'] == selected_month]

    if df.empty:
        st.warning("⚠️ No data for the selected month.")
        st.stop()

    # --- Key Metrics ---
    st.divider()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Spent", f"{CURRENCY} {df['Total Cost'].sum():.2f}")
    m2.metric("Avg Price/kWh", f"{CURRENCY} {df['Cost_per_kWh'].mean():.2f}")
    m3.metric("Total Energy", f"{df['kWh'].sum():.1f} kWh")
    m4.metric("Sessions", len(df))

    # --- GRAPHS ---
    col_a, col_b = st.columns(2)

    with col_a:
        daily_df = df.groupby(df['Date'].dt.date)['Total Cost'].sum().reset_index()
        fig_daily = px.bar(daily_df, x='Date', y='Total Cost', 
                           title=f"Spending per Day ({CURRENCY})", 
                           color_discrete_sequence=['#00CC96'])
        st.plotly_chart(fig_daily, use_container_width=True)

        fig_provider = px.pie(df, names='Provider', values='Total Cost', 
                              title="Spending by Provider", hole=0.4)
        st.plotly_chart(fig_provider, use_container_width=True)

    with col_b:
        fig_type = px.pie(df, names='Type', title="Charging Type Frequency (AC vs DC)", 
                          color_discrete_map={'AC':'#636EFA', 'DC':'#EF553B'})
        st.plotly_chart(fig_type, use_container_width=True)

        fig_scatter = px.scatter(df, x="kWh", y="Total Cost", color="Provider", size="Cost_per_kWh", 
                                 title="Cost vs Energy (Size = Price per kWh)", 
                                 labels={'Total Cost': f'Total Cost ({CURRENCY})'},
                                 hover_data=['Location'])
        st.plotly_chart(fig_scatter, use_container_width=True)

    # --- Top 5 Locations ---
    st.divider()
    st.subheader("📍 Top 5 Locations by Total Cost")
    top_locations = df[df['Location'].notna()].groupby("Location")["Total Cost"].sum().sort_values(ascending=False).head(5).reset_index()
    fig_top_locations = px.bar(
        top_locations,
        x="Location",
        y="Total Cost",
        title=f"Top 5 Locations by Total Cost ({CURRENCY})",
        color="Total Cost",
        color_continuous_scale='Viridis',
        text="Total Cost"
    )
    fig_top_locations.update_traces(texttemplate='%{text:.2f}', textposition='outside')
    st.plotly_chart(fig_top_locations, use_container_width=True)

    # --- Raw Data with Edit Option ---
    with st.expander("📂 View & Edit Raw Data Log"):
        edited_df = st.data_editor(df.sort_values(by="Date", ascending=False), num_rows="dynamic")
        st.markdown("### ⚡ Save Edited Data")
        if st.button("💾 Save Changes"):
            edited_df.to_csv(FILE_NAME, index=False)
            st.success("✅ Changes saved successfully!")

else:
    st.info("Awaiting data... Log a session above to see the analysis!")
