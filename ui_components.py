# ui_components.py
# Version 3.4
# Contains functions for rendering the different tabs in the Streamlit UI.
# Fixes plot display issue with st.rerun().

import streamlit as st
import pandas as pd
import database
import parsers
import tests
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os
import re

# Mock weather data for Austin, TX as a fallback
MOCK_WEATHER_DATA = [
    {'day': 'Tue', 'date': 'Aug 19', 'condition': 'Mostly Cloudy', 'high': 98, 'low': 76, 'humidity': 60},
    {'day': 'Wed', 'date': 'Aug 20', 'condition': 'Scattered T-Storms', 'high': 96, 'low': 77, 'humidity': 59},
    {'day': 'Thu', 'date': 'Aug 21', 'condition': 'Partly Cloudy', 'high': 93, 'low': 76, 'humidity': 64},
    {'day': 'Fri', 'date': 'Aug 22', 'condition': 'Partly Cloudy', 'high': 93, 'low': 74, 'humidity': 58},
    {'day': 'Sat', 'date': 'Aug 23', 'condition': 'Mostly Sunny', 'high': 94, 'low': 73, 'humidity': 54},
    {'day': 'Sun', 'date': 'Aug 24', 'condition': 'Sunny', 'high': 94, 'low': 74, 'humidity': 55},
    {'day': 'Mon', 'date': 'Aug 25', 'condition': 'Partly Cloudy', 'high': 92, 'low': 76, 'humidity': 60},
]

def get_weather_icon(condition):
    """Returns an emoji icon for a given weather condition."""
    condition = condition.lower()
    if 'sun' in condition: return '☀️'
    if 'cloud' in condition: return '☁️'
    if 'rain' in condition or 'storm' in condition: return '🌧️'
    return '🌡️'

def calculate_projected_pmc(plan_df, initial_ctl=0, initial_atl=0):
    if plan_df.empty: return pd.DataFrame()
    proj_df = plan_df[['Date', 'planned_tss']].copy()
    proj_df.rename(columns={'Date': 'metric_date'}, inplace=True)
    proj_df['metric_date'] = pd.to_datetime(proj_df['metric_date'])
    proj_df = proj_df.sort_values('metric_date')
    ctl_alpha, atl_alpha = 2 / 43.0, 2 / 8.0
    last_ctl, last_atl = initial_ctl, initial_atl
    ctls, atls = [], []
    for tss in proj_df['planned_tss']:
        current_ctl = (tss * ctl_alpha) + (last_ctl * (1 - ctl_alpha))
        current_atl = (tss * atl_alpha) + (last_atl * (1 - atl_alpha))
        ctls.append(current_ctl); atls.append(current_atl)
        last_ctl, last_atl = current_ctl, current_atl
    proj_df['ctl'], proj_df['atl'] = ctls, atls
    proj_df['tsb'] = proj_df['ctl'] - proj_df['atl']
    return proj_df

def render_performance_analysis_tab(tab, lthr, user_id):
    with tab:
        st.header("Historical Performance Analysis")
        st.write("Upload your workout history files to see long-term fitness trends.")
        st.subheader("1. Upload Workout History")
        uploaded_files = st.file_uploader("Upload Workout History Files", type=['csv', 'gpx', 'fit'], accept_multiple_files=True, key="perf_uploader")
        if uploaded_files:
            st.subheader("2. Process Data")
            if st.button("Process Uploaded Files"):
                with st.spinner(f"Processing {len(uploaded_files)} files..."):
                    errors = []
                    for i, file in enumerate(uploaded_files):
                        try:
                            file_extension = os.path.splitext(file.name)[1].lower()
                            parsers.parse_and_store_workout(user_id, file, lthr, file_extension)
                        except Exception as e:
                            errors.append(f"Failed to process {file.name}: {e}")
                    
                    st.success("Processing complete.")
                    if errors:
                        st.error("Some files failed:\n\n" + "\n".join(str(e) for e in errors))
                
                # FIX: Force a rerun to reload data and update the plot
                st.rerun()

        st.subheader("3. View Your Performance Chart")
        if not st.session_state.pmc_data.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=st.session_state.pmc_data['metric_date'], y=st.session_state.pmc_data['ctl'], mode='lines', name='CTL (Fitness)'))
            fig.add_trace(go.Scatter(x=st.session_state.pmc_data['metric_date'], y=st.session_state.pmc_data['atl'], mode='lines', name='ATL (Fatigue)'))
            fig.add_trace(go.Scatter(x=st.session_state.pmc_data['metric_date'], y=st.session_state.pmc_data['tsb'], mode='lines', name='TSB (Form)'))
            fig.add_trace(go.Bar(x=st.session_state.pmc_data['metric_date'], y=st.session_state.pmc_data['actual_tss'], name='Actual TSS'))
            fig.update_layout(title="Fitness, Fatigue, and Form Over Time")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Upload and process your historical data to view the performance chart.")

def render_training_plan_tab(tab, get_ai_analysis_func, user_id):
    with tab:
        st.header("Training Plan Tracker")
        plan_file = st.file_uploader("Upload Training Plan (CSV)", type=['csv'], key="plan_uploader")
        if plan_file:
            try:
                st.session_state.plan_df = parsers.parse_and_store_plan(user_id, plan_file)
                st.success("Training plan processed successfully!")
            except Exception as e:
                st.error(f"Error processing plan: {e}")
                st.session_state.plan_df = pd.DataFrame()
        st.subheader("Current Status")
        col1, col2 = st.columns(2)
        today = datetime.now().date()
        start_of_week = today - timedelta(days=today.weekday())
        weekly_miles = database.get_miles_for_period(user_id, start_of_week, today)
        col1.metric("Miles Run This Week", f"{weekly_miles:.2f} mi")
        current_atl, current_ctl = 0, 0
        if not st.session_state.pmc_data.empty:
            today_metric = st.session_state.pmc_data[st.session_state.pmc_data['metric_date'].dt.date <= today]
            if not today_metric.empty:
                latest_data = today_metric.iloc[-1]
                current_atl, current_ctl = latest_data['atl'], latest_data['ctl']
        col2.metric("Current ATL (Fatigue)", f"{current_atl:.1f}")
        if not st.session_state.plan_df.empty and not st.session_state.pmc_data.empty:
            st.subheader("Training Readiness")
            first_workout = st.session_state.plan_df[st.session_state.plan_df['planned_tss'] > 0].iloc[0]
            first_workout_tss, first_workout_date = first_workout['planned_tss'], pd.to_datetime(first_workout['Date']).date()
            ctl_alpha, atl_alpha = 2 / 43.0, 2 / 8.0
            projected_ctl = (first_workout_tss * ctl_alpha) + (current_ctl * (1 - ctl_alpha))
            projected_atl = (first_workout_tss * atl_alpha) + (current_atl * (1 - atl_alpha))
            projected_tsb = projected_ctl - projected_atl
            col1, col2 = st.columns(2)
            col1.metric("Current CTL (Fitness)", f"{current_ctl:.1f}")
            col2.metric(f"Projected TSB after first workout ({first_workout_date.strftime('%b %d')})", f"{projected_tsb:.1f}")
            if projected_tsb > 5: st.success(f"**Fresh and ready.** Projected form of {projected_tsb:.1f} is optimal.")
            elif -10 <= projected_tsb <= 5: st.info(f"**Good training zone.** Projected form of {projected_tsb:.1f} is solid.")
            elif -25 <= projected_tsb < -10: st.warning(f"**Slightly fatigued.** Projected form of {projected_tsb:.1f} suggests some fatigue.")
            else: st.error(f"**High risk of overreaching.** Projected form of {projected_tsb:.1f} is very low.")
        st.subheader("🤖 AI-Powered Training Analysis")
        if st.button("Generate Training Analysis"):
            with st.spinner("Analyzing your performance..."):
                combined_df = st.session_state.pmc_data.copy()
                if not st.session_state.plan_df.empty:
                    plan_tss_df = st.session_state.plan_df[['Date', 'planned_tss']].rename(columns={'Date': 'metric_date'})
                    plan_tss_df['metric_date'] = pd.to_datetime(plan_tss_df['metric_date'])
                    combined_df = pd.merge(combined_df, plan_tss_df, on='metric_date', how='outer', suffixes=('_hist', '_plan'))
                    combined_df['planned_tss'] = combined_df['planned_tss_hist'].fillna(combined_df['planned_tss_plan'])
                    combined_df.drop(columns=['planned_tss_hist', 'planned_tss_plan'], inplace=True)
                    combined_df.sort_values('metric_date', inplace=True)
                analysis = get_ai_analysis_func(combined_df, context="training")
                st.markdown(analysis)
        st.subheader("Projected Fitness (CTL)")
        if not st.session_state.plan_df.empty and not st.session_state.pmc_data.empty:
            initial_ctl, initial_atl = st.session_state.pmc_data.iloc[-1]['ctl'], st.session_state.pmc_data.iloc[-1]['atl']
            projected_data = calculate_projected_pmc(st.session_state.plan_df, initial_ctl, initial_atl)
            fig_proj = go.Figure()
            fig_proj.add_trace(go.Scatter(x=st.session_state.pmc_data['metric_date'], y=st.session_state.pmc_data['ctl'], mode='lines', name='Historical CTL'))
            fig_proj.add_trace(go.Scatter(x=projected_data['metric_date'], y=projected_data['ctl'], mode='lines', name='Projected CTL', line=dict(dash='dash')))
            fig_proj.update_layout(title="Historical vs. Projected Fitness (CTL)")
            st.plotly_chart(fig_proj, use_container_width=True)
        else:
            st.info("Upload a training plan and process historical data to see your projected fitness.")
        st.subheader("Upcoming Workouts")
        if not st.session_state.plan_df.empty:
            plan_df_display = st.session_state.plan_df.copy()
            plan_df_display['Date'] = pd.to_datetime(plan_df_display['Date'])
            future_plan = plan_df_display[plan_df_display['Date'].dt.date >= today].copy()
            future_plan['Date'] = future_plan['Date'].dt.strftime('%a, %b %d')
            st.dataframe(future_plan[['Date', 'Workout_Category', 'Original_Description', 'Total_Miles']].head(14), use_container_width=True)
        else:
            st.info("Upload a training plan to see your upcoming schedule.")

def render_weather_tab(tab, vdot, user_id):
    with tab:
        st.header("Weather-Adjusted Pace Guide")
        
        if st.session_state.plan_df.empty:
            st.warning("Upload a training plan on the 'Training Plan' tab to get weather-based advice.")
            return

        plan_df = st.session_state.plan_df.copy()
        plan_df['Date'] = pd.to_datetime(plan_df['Date'])
        
        today = datetime.now().date()
        future_plan = plan_df[plan_df['Date'].dt.date >= today]
        
        if future_plan.empty:
            st.info("No upcoming runs found in your training plan.")
            return
            
        next_run = future_plan.iloc[0]
        next_run_date = next_run['Date'].date()
        
        weather_forecast = MOCK_WEATHER_DATA[0]
        for forecast in MOCK_WEATHER_DATA:
            if datetime.strptime(f"{forecast['date']} 2025", "%b %d %Y").date() == next_run_date:
                weather_forecast = forecast
                break
        
        st.subheader(f"Next Run: {next_run_date.strftime('%A, %b %d')}")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"#### {get_weather_icon(weather_forecast['condition'])} {weather_forecast['high']}°F")
            st.caption(f"Low: {weather_forecast['low']}°F | Humidity: {weather_forecast['humidity']}%")
        with col2:
            st.markdown(f"#### {next_run['Original_Description']}")
            st.caption(f"{next_run['Total_Miles']} miles")

        st.markdown("---")
        
        target_paces = get_target_paces_from_description(next_run['Original_Description'])
        
        st.subheader("Pace Targets & Adjustments")
        cols = st.columns(len(target_paces))
        
        for i, pace_type in enumerate(target_paces):
            with cols[i]:
                st.markdown(f"##### {pace_type}")
                base_pace_seconds = get_pace_from_vdot(vdot, pace_type)
                adjusted_pace_seconds = adjust_pace_for_weather(base_pace_seconds, weather_forecast['high'], weather_forecast['humidity'])
                delta_str = f"+{int(adjusted_pace_seconds - base_pace_seconds)}s"
                
                st.metric(label="Target Pace", value=seconds_to_pace_str(base_pace_seconds))
                st.metric(label="Adjusted Pace", value=seconds_to_pace_str(adjusted_pace_seconds), delta=delta_str, delta_color="inverse")

def render_health_metrics_tab(tab):
    with tab:
        st.header("Health Metrics & LTHR Estimation")
        st.write("Upload your workout data file to estimate your Lactate Threshold Heart Rate (LTHR).")
        st.info("This feature works best with `Workouts - Workouts.csv` or `Workouts - Heart Rate v pace.csv`.")
        health_file = st.file_uploader("Upload Health Data CSV", type=['csv'], key="health_uploader")
        if health_file:
            try:
                estimated_lthr = parsers.estimate_lthr_from_csv(health_file)
                st.success(f"**Estimated LTHR: {estimated_lthr} bpm**")
                st.info("Based on the average heart rate of your top 5 hardest runs (by HR) between 20 and 75 minutes.")
                st.markdown("---")
                st.write("You can now update the **LTHR** value in the sidebar with this estimate.")
            except Exception as e:
                st.error(f"Could not process file: {e}")

def render_tests_tab(tab):
    with tab:
        st.header("✅ App Health Check")
        st.write("Run these tests to confirm all key features of the application are working correctly.")
        if st.button("Run All Tests"):
            with st.spinner("Running tests..."):
                st.subheader("Database Connection")
                result, message = tests.test_database_connection()
                if result: st.success("✅ PASSED: Database initialized successfully.")
                else: st.error(f"❌ FAILED: {message}")
                st.subheader("File Parsers")
                result, message = tests.test_parsers()
                if result: st.success("✅ PASSED: All file parsers are working correctly.")
                else: st.error(f"❌ FAILED: {message}")
                st.subheader("PMC Model")
                result, message = tests.test_pmc_calculation()
                if result: st.success("✅ PASSED: PMC calculation model is working correctly.")
                else: st.error(f"❌ FAILED: {message}")
