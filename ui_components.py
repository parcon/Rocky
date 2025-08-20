# ui_components.py
# Version 4.1
# Adds an AI-powered weekly outlook to the weather tab.

import streamlit as st
import pandas as pd
import database
import parsers
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os
import re
# --- Import utility functions from the utils.py file ---
from utils import (
    calculate_dew_point,
    adjust_pace_for_weather,
    get_pace_from_vdot
)

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

# --- Helper Functions specific to UI ---
def seconds_to_pace_str(seconds):
    """Converts seconds to a m:ss pace string."""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}:{secs:02d}"

def get_weather_icon(condition):
    """Returns an emoji icon based on the weather condition string."""
    condition = condition.lower()
    if 'sun' in condition: return '☀️'
    if 'cloud' in condition: return '☁️'
    if 'rain' in condition or 'storm' in condition: return '🌧️'
    return '🌡️'

def get_target_paces_from_description(description):
    """Extracts pace types (E, M, T, I, R) from a workout description string."""
    if not isinstance(description, str): return []
    paces = re.findall(r'\b([EMTIR])\b', description.upper())
    return sorted(set(paces), key=paces.index)

def calculate_projected_pmc(plan_df, initial_ctl=0, initial_atl=0):
    """Calculates a projected PMC based on a training plan DataFrame."""
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
        ctls.append(current_ctl)
        atls.append(current_atl)
        last_ctl, last_atl = current_ctl, current_atl
        
    proj_df['ctl'], proj_df['atl'] = ctls, atls
    proj_df['tsb'] = proj_df['ctl'] - proj_df['atl']
    return proj_df

def create_weekly_miles_chart(plan_df):
    """Creates a stacked bar chart of weekly miles by intensity from a plan DataFrame."""
    if plan_df.empty:
        return go.Figure()

    df = plan_df.copy()
    df['Date'] = pd.to_datetime(df['Date'])
    
    pace_cols = ['E_Pace_Miles', 'M_Pace_Miles', 'T_Pace_Miles', 'I_Pace_Miles', 'R_Pace_Miles']
    
    for col in pace_cols:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    df['week_start'] = df['Date'].dt.to_period('W').apply(lambda w: w.start_time).dt.date
    weekly_summary = df.groupby('week_start')[pace_cols].sum().reset_index()

    fig = go.Figure()
    
    colors = {'E_Pace_Miles': '#1f77b4', 'M_Pace_Miles': '#ff7f0e', 'T_Pace_Miles': '#2ca02c', 
              'I_Pace_Miles': '#d62728', 'R_Pace_Miles': '#9467bd'}
    labels = {'E_Pace_Miles': 'Easy', 'M_Pace_Miles': 'Marathon', 'T_Pace_Miles': 'Threshold', 
              'I_Pace_Miles': 'Interval', 'R_Pace_Miles': 'Repetition'}

    for col in pace_cols:
        fig.add_trace(go.Bar(
            x=weekly_summary['week_start'],
            y=weekly_summary[col],
            name=labels[col],
            marker_color=colors[col]
        ))

    fig.update_layout(
        title_text="Projected Weekly Mileage by Intensity",
        xaxis_title="Week",
        yaxis_title="Total Miles",
        barmode='stack',
        legend_title_text="Intensity"
    )
    return fig

# --- Tab Rendering Functions ---
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

        st.subheader("Plan Adherence Assessment")
        if not st.session_state.pmc_data.empty and not st.session_state.plan_df.empty:
            today = datetime.now().date()
            
            # Get current actual metrics from historical data
            actual_metrics_today = st.session_state.pmc_data[st.session_state.pmc_data['metric_date'].dt.date <= today]
            current_ctl, current_atl, current_tsb = (actual_metrics_today.iloc[-1][['ctl', 'atl', 'tsb']] if not actual_metrics_today.empty else (0, 0, 0))

            # Get planned metrics for today
            plan_start_date = st.session_state.plan_df['Date'].min()
            historical_before_plan = st.session_state.pmc_data[st.session_state.pmc_data['metric_date'] < plan_start_date]
            initial_ctl, initial_atl = (historical_before_plan.iloc[-1][['ctl', 'atl']] if not historical_before_plan.empty else (0, 0))

            plan_up_to_today = st.session_state.plan_df[st.session_state.plan_df['Date'].dt.date <= today]
            projected_to_today = calculate_projected_pmc(plan_up_to_today, initial_ctl, initial_atl)
            
            if not projected_to_today.empty:
                latest_planned = projected_to_today.iloc[-1]
                planned_ctl, planned_atl, planned_tsb = latest_planned['ctl'], latest_planned['atl'], latest_planned['tsb']
                delta_ctl, delta_atl, delta_tsb = current_ctl - planned_ctl, current_atl - planned_atl, current_tsb - planned_tsb
            else:
                planned_ctl, planned_atl, planned_tsb = 0, 0, 0
                delta_ctl, delta_atl, delta_tsb = 0, 0, 0

            col1, col2, col3 = st.columns(3)
            col1.metric("CTL (Fitness)", f"{current_ctl:.1f}", f"{delta_ctl:.1f} vs. Plan ({planned_ctl:.1f})")
            col2.metric("ATL (Fatigue)", f"{current_atl:.1f}", f"{delta_atl:.1f} vs. Plan ({planned_atl:.1f})", delta_color="inverse")
            col3.metric("TSB (Form)", f"{current_tsb:.1f}", f"{delta_tsb:.1f} vs. Plan ({planned_tsb:.1f})")

            if abs(delta_ctl) < 3:
                st.success("✅ **On Track:** Your current fitness is closely aligned with the plan.")
            elif delta_ctl > 3:
                st.info("📈 **Ahead of Plan:** You've accumulated more fitness than planned. Ensure you're recovering well.")
            else:
                st.warning("📉 **Behind Plan:** You've accumulated less fitness than planned. Check your recent workout consistency.")
        else:
            st.info("Upload a training plan and process historical data to see your adherence assessment.")

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

        st.subheader("Long-Range Plan Overview")
        if not st.session_state.plan_df.empty:
            weekly_miles_fig = create_weekly_miles_chart(st.session_state.plan_df)
            st.plotly_chart(weekly_miles_fig, use_container_width=True)
            
            st.write("**Training Plan Calendar**")
            plan_df_display = st.session_state.plan_df.copy()
            plan_df_display['Date'] = pd.to_datetime(plan_df_display['Date']).dt.strftime('%a, %b %d')
            st.dataframe(plan_df_display[['Date', 'Workout_Category', 'Original_Description', 'Total_Miles', 'planned_tss']], use_container_width=True)
        else:
            st.info("Upload a training plan to see the long-range overview.")

def render_weather_tab(tab, vdot, user_id, get_ai_analysis_func):
    with tab:
        st.header("Weather-Adjusted Pace Guide")

        if st.session_state.plan_df.empty:
            st.warning("Upload a training plan on the 'Training Plan' tab to get weather-based advice.")
            return

        plan_df = st.session_state.plan_df.copy()
        plan_df['Date'] = pd.to_datetime(plan_df['Date'])
        
        today = datetime.now().date()
        future_plan_display = plan_df[plan_df['Date'].dt.date >= today].head(3)

        if future_plan_display.empty:
            st.info("No upcoming runs found in your training plan.")
            return
            
        st.markdown("---")

        for index, next_run in future_plan_display.iterrows():
            next_run_date = next_run['Date'].date()
            
            weather_forecast = MOCK_WEATHER_DATA[0] # Default
            for forecast in MOCK_WEATHER_DATA:
                try:
                    forecast_date = datetime.strptime(f"{forecast['date']} {datetime.now().year}", "%b %d %Y").date()
                    if forecast_date == next_run_date:
                        weather_forecast = forecast
                        break
                except ValueError:
                    continue

            dew_point_low = calculate_dew_point(weather_forecast['low'], weather_forecast['humidity'])
            dew_point_high = calculate_dew_point(weather_forecast['high'], weather_forecast['humidity'])
            target_paces = get_target_paces_from_description(next_run['Original_Description'])

            col1, col2, col3, col4 = st.columns([1, 1.5, 3, 2])

            with col1:
                st.markdown(f"**{next_run_date.strftime('%a, %b %d')}**")
            
            with col2:
                st.markdown(f"{get_weather_icon(weather_forecast['condition'])} {weather_forecast['low']}°F - {weather_forecast['high']}°F")
            
            with col3:
                st.markdown(f"**{next_run['Original_Description']}** ({next_run['Total_Miles']} mi)")

            with col4:
                if not target_paces:
                    st.caption("No pace targets")
                else:
                    pace_strings = []
                    for pace_type in target_paces:
                        base_pace = get_pace_from_vdot(vdot, pace_type)
                        adjusted_pace_low = adjust_pace_for_weather(base_pace, dew_point_low)
                        adjusted_pace_high = adjust_pace_for_weather(base_pace, dew_point_high)
                        
                        pace_str_low = seconds_to_pace_str(adjusted_pace_low)
                        pace_str_high = seconds_to_pace_str(adjusted_pace_high)
                        base_pace_str = seconds_to_pace_str(base_pace)

                        if pace_str_low == pace_str_high:
                            pace_strings.append(f"{pace_type}: {pace_str_high} ({base_pace_str})")
                        else:
                            pace_strings.append(f"{pace_type}: {pace_str_low} - {pace_str_high} ({base_pace_str})")
                    
                    st.markdown(" / ".join(pace_strings))
            
            st.markdown("---")

        st.subheader("🤖 AI-Powered Weekly Outlook")
        if st.button("Get AI Weather & Fatigue Analysis"):
            with st.spinner("Analyzing your upcoming week..."):
                current_atl = 0
                if not st.session_state.pmc_data.empty:
                    today_metric = st.session_state.pmc_data[st.session_state.pmc_data['metric_date'].dt.date <= today]
                    if not today_metric.empty:
                        current_atl = today_metric.iloc[-1]['atl']
                
                end_of_week = today + timedelta(days=(6 - today.weekday()))
                runs_this_week_df = plan_df[(plan_df['Date'].dt.date >= today) & (plan_df['Date'].dt.date <= end_of_week)]
                
                weekly_weather_forecast = []
                for day_offset in range((end_of_week - today).days + 1):
                    target_date = today + timedelta(days=day_offset)
                    for forecast in MOCK_WEATHER_DATA:
                        try:
                            forecast_date = datetime.strptime(f"{forecast['date']} {datetime.now().year}", "%b %d %Y").date()
                            if forecast_date == target_date:
                                weekly_weather_forecast.append(forecast)
                                break
                        except ValueError:
                            continue

                ai_input_data = {
                    'atl': current_atl,
                    'runs': runs_this_week_df[['Date', 'Original_Description', 'Total_Miles']],
                    'weather': weekly_weather_forecast
                }
                analysis = get_ai_analysis_func(ai_input_data, context="weather_weekly")
                st.markdown(analysis)

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
            # Import tests locally to prevent circular dependency
            import tests
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

                st.subheader("Weather Model")
                result, message = tests.test_weather_adjustments()
                if result: st.success("✅ PASSED: Weather adjustment model is working correctly.")
                else: st.error(f"❌ FAILED: {message}")
