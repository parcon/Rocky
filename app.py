# app.py
# Version 3.5
# Main application file for the Rocky Training Tracker.
# Fixes tab rendering logic.

import streamlit as st
import pandas as pd
import database
import parsers
import ui_components
from datetime import datetime, timedelta
import google.generativeai as genai
import os

# --- Page Configuration ---
st.set_page_config(
    page_title="Rocky - Training Tracker",
    page_icon="🥊",
    layout="wide"
)

# --- Constants ---
USER_ID = 1 # Default user for stateless persistence

# --- Initialize Session State ---
if 'plan_df' not in st.session_state:
    st.session_state.plan_df = pd.DataFrame()

# --- Gemini API Configuration ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-2.5-flash-lite')
except Exception:
    st.warning("Gemini API key not found or invalid. AI analysis will be disabled.")
    model = None

# --- Core Logic Functions ---
def calculate_pmc(df):
    """Calculates the Performance Management Chart (CTL, ATL, TSB) from actual workouts."""
    if df.empty:
        return pd.DataFrame()
    
    df['metric_date'] = pd.to_datetime(df['metric_date'])
    df = df.sort_values('metric_date')
    start_date = df['metric_date'].min()
    end_date = max(datetime.now().date(), df['metric_date'].max().date())

    all_dates = pd.date_range(start=start_date, end=end_date)
    df = df.set_index('metric_date').reindex(all_dates).fillna(0).reset_index()
    df = df.rename(columns={'index': 'metric_date'})

    df['ctl'] = df['actual_tss'].ewm(span=42, adjust=False).mean()
    df['atl'] = df['actual_tss'].ewm(span=7, adjust=False).mean()
    df['tsb'] = df['ctl'] - df['atl']
    return df

def get_ai_analysis(df, context="training"):
    """Generates AI-powered training commentary using the Gemini API."""
    if not model: return "AI analysis is disabled."
    if context == "training" and df.empty: return "Not enough data for analysis."

    prompt = ""
    if context == "training":
        today = datetime.now().date()
        past_week_df = df[df['metric_date'].dt.date >= (today - timedelta(days=7))]
        next_week_df = df[(df['metric_date'].dt.date > today) & (df['metric_date'].dt.date <= (today + timedelta(days=7)))]
        prompt = f"""
        You are an expert running coach providing a detailed analysis based on the PMC model.
        - CTL (Fitness): Your long-term fitness.
        - ATL (Fatigue): Your short-term fatigue.
        - TSB (Form): Training Stress Balance (CTL - ATL). Positive is fresh, negative is fatigued.

        **Data from the last 7 days:**
        {past_week_df[['metric_date', 'planned_tss', 'actual_tss', 'ctl', 'atl', 'tsb']].to_string()}

        **Planned workouts for the next 7 days:**
        {next_week_df[['metric_date', 'planned_tss']].to_string()}

        **Your Task:**
        Provide a brief analysis covering: Fitness Trend (CTL), Current Fatigue (ATL & TSB), and Adherence & Advice.
        """
    elif context == "weather":
        prompt = f"""
        You are an expert running coach. Given the weather forecast and a planned workout with different pace targets, provide a short, actionable tip (2-3 sentences) on how to adjust the run.

        **Weather Forecast:**
        - Condition: {df['condition']}
        - High Temperature: {df['high_temp']}°F
        - Humidity: {df['humidity']}%

        **Planned Workout:**
        - Description: {df['workout_desc']}
        - Target Paces: {df['paces']}

        **Your Task:**
        Provide a specific recommendation on how to adjust the target paces due to the weather. For example, "For your Threshold pace portions, consider adding 5-10 seconds per mile. Keep the Easy pace sections truly easy and focus on hydration."
        """

    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"An error occurred while generating AI analysis: {e}"

# --- Main Application ---
def main():
    st.title("🥊 Rocky: It Ain't About How Hard Ya Hit...")
    database.init_db()

    st.sidebar.header("⚙️ Configuration")
    
    initial_lthr = database.get_setting(USER_ID, 'lthr')
    if initial_lthr is None:
        initial_lthr = 175
        database.set_setting(USER_ID, 'lthr', initial_lthr)
    
    initial_vdot = database.get_setting(USER_ID, 'vdot')
    if initial_vdot is None:
        initial_vdot = 50
        database.set_setting(USER_ID, 'vdot', initial_vdot)

    def update_settings():
        database.set_setting(USER_ID, 'lthr', st.session_state.lthr_input)
        database.set_setting(USER_ID, 'vdot', st.session_state.vdot_input)

    vdot = st.sidebar.number_input(
        "VDOT Score", 
        min_value=30, max_value=85, 
        value=int(initial_vdot),
        key='vdot_input',
        on_change=update_settings
    )
    lthr = st.sidebar.number_input(
        "LTHR (Lactate Threshold Heart Rate)", 
        min_value=100, max_value=220, 
        value=int(initial_lthr),
        key='lthr_input',
        on_change=update_settings
    )
    st.sidebar.info("Your VDOT score is used for pace calculations. Your LTHR is used for TSS calculations from heart rate.")

    # --- Single Source of Truth for Data Loading ---
    all_metrics_df = database.get_all_metrics(USER_ID)
    st.session_state.pmc_data = calculate_pmc(all_metrics_df)

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Performance Analysis", "📅 Training Plan", "🌦️ Weather", "❤️ Health Metrics", "✅ Tests"])
    
    with tab1:
        ui_components.render_performance_analysis_tab(lthr, USER_ID)
    with tab2:
        ui_components.render_training_plan_tab(get_ai_analysis, USER_ID)
    with tab3:
        ui_components.render_weather_tab(vdot, USER_ID)
    with tab4:
        ui_components.render_health_metrics_tab()
    with tab5:
        ui_components.render_tests_tab()

if __name__ == "__main__":
    main()
