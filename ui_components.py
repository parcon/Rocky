import streamlit as st
import pandas as pd
import database
import parsers
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os

def calculate_projected_pmc(plan_df, initial_ctl=0, initial_atl=0):
    """Calculates a projected PMC based on a training plan."""
    if plan_df.empty:
        return pd.DataFrame()

    proj_df = plan_df[['Date', 'planned_tss']].copy()
    proj_df.rename(columns={'Date': 'metric_date'}, inplace=True)
    proj_df['metric_date'] = pd.to_datetime(proj_df['metric_date'])
    proj_df = proj_df.sort_values('metric_date')
    
    ctl_alpha = 2 / 43.0
    atl_alpha = 2 / 8.0
    
    last_ctl = initial_ctl
    last_atl = initial_atl
    ctls, atls = [], []

    for tss in proj_df['planned_tss']:
        current_ctl = (tss * ctl_alpha) + (last_ctl * (1 - ctl_alpha))
        current_atl = (tss * atl_alpha) + (last_atl * (1 - atl_alpha))
        ctls.append(current_ctl)
        atls.append(current_atl)
        last_ctl = current_ctl
        last_atl = current_atl
        
    proj_df['ctl'] = ctls
    proj_df['atl'] = atls
    proj_df['tsb'] = proj_df['ctl'] - proj_df['atl']
    return proj_df

def render_performance_analysis_tab(vdot_lthr):
    """Renders the content for the Historical Performance Analysis tab."""
    st.header("Historical Performance Analysis")
    st.write("Upload your workout history files to see long-term fitness trends.")

    st.subheader("1. Upload Workout History")
    st.info("You can upload multiple files at once, including `Workouts - Workouts.csv`, GPX, and FIT files.")
    
    uploaded_files = st.file_uploader(
        "Upload Workout History Files",
        type=['csv', 'gpx', 'fit'],
        accept_multiple_files=True
    )

    if uploaded_files:
        st.subheader("2. Process Data")
        if st.button("Process Uploaded Files"):
            st.info(f"Found {len(uploaded_files)} files. Processing...")
            progress_bar = st.progress(0)
            errors = []
            for i, file in enumerate(uploaded_files):
                try:
                    file_extension = os.path.splitext(file.name)[1].lower()
                    parsers.parse_and_store_workout(file, vdot_lthr, file_extension)
                except Exception as e:
                    errors.append(f"Failed to process {file.name}: {e}")
                progress_bar.progress((i + 1) / len(uploaded_files))
            
            from app import calculate_pmc
            all_metrics_df = database.get_all_metrics()
            st.session_state.pmc_data = calculate_pmc(all_metrics_df)
            st.success("Processing complete. Chart updated.")
            if errors:
                error_message = "Some files failed:\n\n" + "\n".join(str(e) for e in errors)
                st.error(error_message)

    st.subheader("3. View Your Performance Chart")
    if not st.session_state.pmc_data.empty:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=st.session_state.pmc_data['metric_date'], y=st.session_state.pmc_data['ctl'], mode='lines', name='CTL (Fitness)', line=dict(color='blue')))
        fig.add_trace(go.Scatter(x=st.session_state.pmc_data['metric_date'], y=st.session_state.pmc_data['atl'], mode='lines', name='ATL (Fatigue)', line=dict(color='orange')))
        fig.add_trace(go.Scatter(x=st.session_state.pmc_data['metric_date'], y=st.session_state.pmc_data['tsb'], mode='lines', name='TSB (Form)', line=dict(color='green')))
        fig.add_trace(go.Bar(x=st.session_state.pmc_data['metric_date'], y=st.session_state.pmc_data['actual_tss'], name='Actual TSS', marker_color='rgba(255, 0, 0, 0.5)'))
        fig.update_layout(title="Fitness, Fatigue, and Form Over Time", xaxis_title="Date", yaxis_title="Value")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Upload and process your historical data to view the performance chart.")

def render_training_plan_tab(get_ai_analysis_func):
    """Renders the content for the Training Plan Tracker tab."""
    st.header("Training Plan Tracker")
    plan_file = st.file_uploader("Upload Training Plan (CSV)", type=['csv'], key="training_plan_uploader")

    if plan_file:
        try:
            st.session_state.plan_df = parsers.parse_and_store_plan(plan_file)
            st.success("Training plan processed successfully!")
        except Exception as e:
            st.error(f"Error processing plan: {e}")
            st.session_state.plan_df = pd.DataFrame()

    st.subheader("Current Status")
    col1, col2 = st.columns(2)
    today = datetime.now().date()
    start_of_week = today - timedelta(days=today.weekday())
    weekly_miles = database.get_miles_for_period(start_of_week, today)
    col1.metric("Miles Run This Week", f"{weekly_miles:.2f} mi")

    current_atl = 0
    current_ctl = 0
    if not st.session_state.pmc_data.empty:
        today_metric = st.session_state.pmc_data[st.session_state.pmc_data['metric_date'].dt.date <= today]
        if not today_metric.empty:
            latest_data = today_metric.iloc[-1]
            current_atl = latest_data['atl']
            current_ctl = latest_data['ctl']
    col2.metric("Current ATL (Fatigue)", f"{current_atl:.1f}")

    if not st.session_state.plan_df.empty and not st.session_state.pmc_data.empty:
        st.subheader("Training Readiness")
        
        first_workout = st.session_state.plan_df[st.session_state.plan_df['planned_tss'] > 0].iloc[0]
        first_workout_tss = first_workout['planned_tss']
        first_workout_date = pd.to_datetime(first_workout['Date']).date()

        ctl_alpha = 2 / 43.0
        atl_alpha = 2 / 8.0
        
        projected_ctl = (first_workout_tss * ctl_alpha) + (current_ctl * (1 - ctl_alpha))
        projected_atl = (first_workout_tss * atl_alpha) + (current_atl * (1 - atl_alpha))
        projected_tsb = projected_ctl - projected_atl

        col1, col2 = st.columns(2)
        col1.metric("Current CTL (Fitness)", f"{current_ctl:.1f}")
        col2.metric(
            f"Projected TSB after first workout ({first_workout_date.strftime('%b %d')})",
            f"{projected_tsb:.1f}"
        )

        if projected_tsb > 5:
            st.success(f"**You are fresh and ready.** Your projected form of {projected_tsb:.1f} is in the optimal zone for starting a new training block.")
        elif -10 <= projected_tsb <= 5:
            st.info(f"**You are in a good training zone.** Your projected form of {projected_tsb:.1f} indicates you are carrying some fitness but are still ready for the planned workout.")
        elif -25 <= projected_tsb < -10:
            st.warning(f"**You may be slightly fatigued.** Your projected form of {projected_tsb:.1f} suggests you are entering this plan with some residual fatigue. Be mindful of recovery.")
        else:
            st.error(f"**High risk of overreaching.** Your projected form of {projected_tsb:.1f} is very low. Consider an extra rest day before starting the plan to avoid injury.")

    st.subheader("🤖 AI-Powered Training Analysis")
    if st.button("Generate Training Analysis"):
        with st.spinner("Analyzing your performance..."):
            # --- FIX: Combine historical and planned data for the AI ---
            combined_df = st.session_state.pmc_data.copy()
            if not st.session_state.plan_df.empty:
                plan_tss_df = st.session_state.plan_df[['Date', 'planned_tss']].rename(columns={'Date': 'metric_date'})
                plan_tss_df['metric_date'] = pd.to_datetime(plan_tss_df['metric_date'])
                
                # Merge and fill, giving preference to existing planned_tss, then new ones
                combined_df = pd.merge(combined_df, plan_tss_df, on='metric_date', how='outer', suffixes=('_hist', '_plan'))
                combined_df['planned_tss'] = combined_df['planned_tss_hist'].fillna(combined_df['planned_tss_plan'])
                combined_df.drop(columns=['planned_tss_hist', 'planned_tss_plan'], inplace=True)
                combined_df.sort_values('metric_date', inplace=True)

            analysis = get_ai_analysis_func(combined_df)
            st.markdown(analysis)

    # --- CHANGE: Graph from TSB to CTL vs. Expected CTL ---
    st.subheader("Projected Fitness (CTL)")
    if not st.session_state.plan_df.empty and not st.session_state.pmc_data.empty:
        initial_ctl = st.session_state.pmc_data.iloc[-1]['ctl']
        initial_atl = st.session_state.pmc_data.iloc[-1]['atl']
        
        projected_data = calculate_projected_pmc(st.session_state.plan_df, initial_ctl, initial_atl)
        
        fig_proj = go.Figure()
        # Historical CTL
        fig_proj.add_trace(go.Scatter(
            x=st.session_state.pmc_data['metric_date'], 
            y=st.session_state.pmc_data['ctl'], 
            mode='lines', 
            name='Historical CTL', 
            line=dict(color='blue')
        ))
        # Projected CTL
        fig_proj.add_trace(go.Scatter(
            x=projected_data['metric_date'], 
            y=projected_data['ctl'], 
            mode='lines', 
            name='Projected CTL', 
            line=dict(color='purple', dash='dash')
        ))
        
        fig_proj.update_layout(
            title="Historical vs. Projected Fitness (CTL)", 
            xaxis_title="Date", 
            yaxis_title="CTL (Fitness)"
        )
        st.plotly_chart(fig_proj, use_container_width=True)
    else:
        st.info("Upload a training plan and process historical data to see your projected fitness.")

    st.subheader("Upcoming Workouts")
    if not st.session_state.plan_df.empty:
        plan_df_display = st.session_state.plan_df.copy()
        plan_df_display['Date'] = pd.to_datetime(plan_df_display['Date'])
        future_plan = plan_df_display[plan_df_display['Date'].dt.date >= today]
        future_plan['Date'] = future_plan['Date'].dt.strftime('%a, %b %d')
        st.dataframe(future_plan[['Date', 'Workout_Category', 'Original_Description', 'Total_Miles']].head(14), use_container_width=True)
    else:
        st.info("Upload a training plan to see your upcoming schedule.")

def render_health_metrics_tab():
    """Renders the content for the Health Metrics tab."""
    st.header("Health Metrics & LTHR Estimation")
    st.write("Upload your workout data file to estimate your Lactate Threshold Heart Rate (LTHR).")
    st.info("This feature works best with `Workouts - Workouts.csv` or `Workouts - Heart Rate v pace.csv`.")

    health_file = st.file_uploader("Upload Health Data CSV", type=['csv'], key="health_metrics_uploader")

    if health_file:
        try:
            estimated_lthr = parsers.estimate_lthr_from_csv(health_file)
            st.success(f"**Estimated LTHR: {estimated_lthr} bpm**")
            st.info("Based on the average heart rate of your top 5 hardest runs (by HR) between 20 and 75 minutes.")
            st.markdown("---")
            st.write("You can now update the **VDOT / LTHR** value in the sidebar with this estimate.")
        except Exception as e:
            st.error(f"Could not process file: {e}")
