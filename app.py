import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os

RAWDATA = 'rawdata.csv'
CURRENCY = "MYR"

# --- Check if data exists ---
if os.path.isfile(RAWDATA):
    df = pd.read_csv(RAWDATA)
    df['Date'] = pd.to_datetime(df['Date'])
    df['Location'] = df['Location'].astype(str)
    df['Weekday'] = df['Date'].dt.day_name()

    st.subheader("📊 Insights")

    col1, col2 = st.columns(2)

    with col1:
        # --- Daily Spending ---
        daily_df = df.groupby(df["Date"].dt.date)["Total Cost"].sum().reset_index()
        fig_daily = px.bar(
            daily_df,
            x="Date",
            y="Total Cost",
            title="Daily Spending"
        )
        st.plotly_chart(fig_daily, use_container_width=True)

        # --- AC vs DC Pie Chart ---
        fig_type = px.pie(
            df,
            names="Type",
            hole=0.5,
            title="AC vs DC"
        )
        st.plotly_chart(fig_type, use_container_width=True)

        # --- Session Duration Proxy ---
        df['Duration_Proxy'] = df['Total Cost'] / df['kWh']  # assume cost correlates to duration
        fig_duration = px.histogram(
            df,
            x="Duration_Proxy",
            nbins=20,
            title="Session Duration Proxy (Cost per kWh)"
        )
        st.plotly_chart(fig_duration, use_container_width=True)

    with col2:
        # --- Cost vs Energy Scatter ---
        fig_scatter = px.scatter(
            df,
            x="kWh",
            y="Total Cost",
            color="Provider",
            size="Cost_per_kWh",
            title="Cost vs Energy",
            hover_data=["Location"]
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

        # --- AC vs DC Cost Comparison ---
        ac_dc_df = df.groupby("Type")["Total Cost"].mean().reset_index()
        fig_ac_dc = px.bar(
            ac_dc_df,
            x="Type",
            y="Total Cost",
            title="Average Cost: AC vs DC",
            color="Type",
            color_discrete_map={"AC":"#636EFA", "DC":"#EF553B"}
        )
        st.plotly_chart(fig_ac_dc, use_container_width=True)

        # --- Heatmap: Charging Behavior by Weekday ---
        heatmap_df = df.groupby(["Weekday", "Type"])["kWh"].sum().reset_index()
        fig_heatmap = px.density_heatmap(
            heatmap_df,
            x="Weekday",
            y="Type",
            z="kWh",
            title="Charging Behavior by Day (kWh)",
            color_continuous_scale="Viridis"
        )
        st.plotly_chart(fig_heatmap, use_container_width=True)

else:
    st.info("No data yet. Record a session to see insights.")
