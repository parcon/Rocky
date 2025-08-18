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

# --- Initialize Session State ---
if 'pmc_data' not in st.session_state:
    st.session_state.pmc_data = pd.DataFrame()
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

def get_ai_analysis(df):
    """Generates AI-powered training commentary using the Gemini API."""
    if not model: return "AI analysis is disabled."
    if df.empty: return "Not enough data for analysis."

    try:
        today = datetime.now().date()
        past_week_df = df[df['metric_date'].dt.date >= (today - timedelta(days=7))]
        next_week_df = df[(df['metric_date'].dt.date > today) & (df['metric_date'].dt.date <= (today + timedelta(days=7)))]

        prompt = f"""
        You are an expert running coach providing a detailed analysis based on the Performance Management Chart (PMC) model.

        **Key Metrics:**
        - **CTL (Fitness):** Chronic Training Load, your long-term fitness. A rising CTL is good.
        - **ATL (Fatigue):** Acute Training Load, your short-term fatigue. A high ATL means you're tired.
        - **TSB (Form):** Training Stress Balance (CTL - ATL). Positive TSB means you are fresh (good form). Negative TSB means you are fatigued.

        **Data from the last 7 days:**
        {past_week_df[['metric_date', 'planned_tss', 'actual_tss', 'ctl', 'atl', 'tsb']].to_string()}

        **Planned workouts for the next 7 days:**
        {next_week_df[['metric_date', 'planned_tss']].to_string()}

        **Your Task:**
        Based on all the data provided, provide a brief analysis covering:
        1.  **Fitness Trend (CTL):** How has the runner's fitness changed over the last week?
        2.  **Current Fatigue (ATL & TSB):** How tired is the runner right now, and what is their current form?
        3.  **Adherence & Advice:** How well did they follow the plan last week, and what should they be mindful of for the upcoming week's training?
        """
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"An error occurred while generating AI analysis: {e}"

# --- Main Application ---
def main():
    st.title("🥊 Rocky: It Ain't About How Hard Ya Hit...")
    database.init_db()

    # --- Sidebar Configuration ---
    st.sidebar.header("⚙️ Configuration")
    vdot_lthr = st.sidebar.number_input("VDOT / LTHR (used for TSS calculation)", min_value=100, max_value=220, value=175)
    st.sidebar.info("This value is used as your LTHR to calculate TSS. Estimate it in the 'Health Metrics' tab.")

    # --- Load Initial Data ---
    if st.session_state.pmc_data.empty:
        all_metrics_df = database.get_all_metrics()
        st.session_state.pmc_data = calculate_pmc(all_metrics_df)

    # --- Main App Tabs ---
    tab1, tab2, tab3 = st.tabs(["📊 Performance Analysis", "📅 Training Plan", "❤️ Health Metrics"])

    with tab1:
        ui_components.render_performance_analysis_tab(vdot_lthr)

    with tab2:
        ui_components.render_training_plan_tab(get_ai_analysis)

    with tab3:
        ui_components.render_health_metrics_tab()

if __name__ == "__main__":
    main()
