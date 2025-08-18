import streamlit as st
import pandas as pd
import database
import parsers
import plotly.graph_objects as go
from datetime import datetime, timedelta
import google.generativeai as genai
import os

# --- Page Configuration ---
st.set_page_config(
    page_title="Intelligent Running Performance Tracker v2.1",
    page_icon="🏃‍♂️",
    layout="wide"
)

# --- Gemini API Configuration ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.0-pro')
except Exception:
    st.warning("Gemini API key not found or invalid. AI analysis will be disabled.")
    model = None

# --- Helper Functions ---
def calculate_pmc(df):
    """Calculates the Performance Management Chart (CTL, ATL, TSB)."""
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
    if not model:
        return "AI analysis is disabled."
    if df.empty:
        return "Not enough data for analysis."

    try:
        today = datetime.now().date()
        past_week_df = df[df['metric_date'].dt.date >= (today - timedelta(days=7))]
        next_week_df = df[(df['metric_date'].dt.date > today) & (df['metric_date'].dt.date <= (today + timedelta(days=7)))]

        prompt = f"""
        You are an expert running coach. Analyze the following running data and provide actionable advice.
        The user is following a training plan. TSB (Training Stress Balance) indicates form (positive is good, negative is tired).
        CTL (Chronic Training Load) is fitness. ATL (Acute Training Load) is fatigue.

        Data from the last 7 days:
        {past_week_df[['metric_date', 'planned_tss', 'actual_tss', 'ctl', 'atl', 'tsb']].to_string()}

        Planned workouts for the next 7 days:
        {next_week_df[['metric_date', 'planned_tss']].to_string()}

        Based on this data, provide a brief analysis (3-4 sentences) covering:
        1. How well did the runner adhere to the plan last week?
        2. What is their current form (TSB)?
        3. What should they be mindful of for the upcoming week's training?
        """
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"An error occurred while generating AI analysis: {e}"

# --- Main Application ---
st.title("🏃‍♂️ Intelligent Running Performance Tracker")

# --- Database Initialization ---
database.init_db()

# --- Sidebar Configuration ---
st.sidebar.header("⚙️ Configuration")
lthr = st.sidebar.number_input("Lactate Threshold Heart Rate (LTHR)", min_value=100, max_value=220, value=175)
st.sidebar.info("This is used to calculate TSS from workouts with heart rate data.")

# --- Main App Tabs ---
tab1, tab2 = st.tabs(["📊 Performance Analysis", "📅 Training Plan"])

# --- TAB 1: Historical Performance Analysis ---
with tab1:
    st.header("Historical Performance Analysis")
    st.write("Analyze your entire workout history to see long-term fitness trends.")

    st.subheader("1. Select Your Workout Data Folder")
    with st.expander("Click here for instructions on how to get your folder path"):
        st.markdown("""
        **💻 On Windows:**
        1. Open File Explorer and navigate to your folder.
        2. Right-click the folder.
        3. Select **"Copy as path"**.
        
        **🍎 On macOS:**
        1. Open Finder and navigate to your folder.
        2. Right-click the folder.
        3. Hold down the **Option (⌥)** key, and select **"Copy [Folder Name] as Pathname"**.
        
        ---
        
        💡 **Performance Tip:** For best results, use a folder on your local drive, not in a cloud-synced directory (like iCloud, Google Drive, or Dropbox). This will prevent "Operation timed out" errors.
        """)
    
    data_folder = st.text_input("Paste your local workout data folder path here:", placeholder="e.g., /Users/Rocky/Documents/MyRuns")

    st.subheader("2. Process Data")
    if st.button("Process Historical Data"):
        if data_folder and os.path.isdir(data_folder):
            with st.spinner(f"Scanning '{data_folder}' for workout files..."):
                files_found = []
                for root, _, files in os.walk(data_folder):
                    for file in files:
                        if file.lower().endswith(('.gpx', '.fit', '.csv')):
                            files_found.append(os.path.join(root, file))
            
            if not files_found:
                st.warning("No workout files (.gpx, .fit, .csv) found in the specified directory.")
            else:
                st.info(f"Found {len(files_found)} files. Processing now...")
                progress_bar = st.progress(0)
                error_list = []
                for i, file_path in enumerate(files_found):
                    try:
                        parsers.parse_and_store_workout(file_path, lthr)
                    except Exception as e:
                        error_list.append(f"Failed to process {os.path.basename(file_path)}: {e}")
                    progress_bar.progress((i + 1) / len(files_found))
                
                st.success(f"Processing complete.")
                if error_list:
                    st.error("Some files could not be processed:")
                    for err in error_list:
                        st.write(err)
        else:
            st.error("Please provide a valid directory path.")

    # --- Performance Management Chart ---
    st.subheader("3. View Your Performance Chart")
    all_metrics_df = database.get_all_metrics()
    pmc_data = calculate_pmc(all_metrics_df)

    if not pmc_data.empty:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=pmc_data['metric_date'], y=pmc_data['ctl'], mode='lines', name='CTL (Fitness)', line=dict(color='blue')))
        fig.add_trace(go.Scatter(x=pmc_data['metric_date'], y=pmc_data['atl'], mode='lines', name='ATL (Fatigue)', line=dict(color='orange')))
        fig.add_trace(go.Scatter(x=pmc_data['metric_date'], y=pmc_data['tsb'], mode='lines', name='TSB (Form)', line=dict(color='green')))
        fig.add_trace(go.Bar(x=pmc_data['metric_date'], y=pmc_data['actual_tss'], name='Actual TSS', marker_color='rgba(255, 0, 0, 0.5)'))
        fig.update_layout(title="Fitness, Fatigue, and Form Over Time", xaxis_title="Date", yaxis_title="Value")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Process your historical data to view the performance chart.")

# --- TAB 2: Training Plan Tracker ---
with tab2:
    st.header("Training Plan Tracker")
    st.write("Upload your training plan to see upcoming workouts, track key metrics, and get AI-powered advice.")

    plan_file = st.file_uploader("Upload Training Plan (CSV)", type=['csv'], key="training_plan_uploader")

    if plan_file:
        try:
            plan_df = parsers.parse_and_store_plan(plan_file)
            st.success("Training plan processed successfully!")
        except Exception as e:
            st.error(f"Error processing plan: {e}")
            plan_df = pd.DataFrame()
    else:
        plan_df = pd.DataFrame()

    # --- Summary Metrics ---
    st.subheader("Current Status")
    col1, col2 = st.columns(2)
    
    today = datetime.now().date()
    start_of_week = today - timedelta(days=today.weekday())
    
    # Calculate weekly mileage
    weekly_miles = database.get_miles_for_period(start_of_week, today)
    col1.metric("Miles Run This Week", f"{weekly_miles:.2f} mi")

    # Get current ATL
    current_atl = 0
    if not pmc_data.empty:
        today_metric = pmc_data[pmc_data['metric_date'].dt.date == today]
        if not today_metric.empty:
            current_atl = today_metric['atl'].iloc[0]
    col2.metric("Current ATL (Fatigue)", f"{current_atl:.1f}")

    # --- AI-Powered Analysis ---
    st.subheader("🤖 AI-Powered Training Analysis")
    if st.button("Generate Training Analysis"):
        with st.spinner("Analyzing your performance..."):
            # We need to merge actuals with plan for a complete picture
            merged_data_for_ai = pmc_data.copy()
            if not plan_df.empty:
                 plan_tss_df = plan_df[['Date', 'planned_tss']].rename(columns={'Date': 'metric_date'})
                 plan_tss_df['metric_date'] = pd.to_datetime(plan_tss_df['metric_date'])
                 # Update planned_tss in the main df
                 merged_data_for_ai = pd.merge(merged_data_for_ai, plan_tss_df, on='metric_date', how='left')
                 merged_data_for_ai['planned_tss'] = merged_data_for_ai['planned_tss_y'].fillna(merged_data_for_ai['planned_tss_x'])
                 merged_data_for_ai = merged_data_for_ai.drop(columns=['planned_tss_x', 'planned_tss_y'])

            analysis = get_ai_analysis(merged_data_for_ai)
            st.markdown(analysis)

    # --- Upcoming Training Plan Display ---
    st.subheader("Upcoming Workouts")
    if not plan_df.empty:
        plan_df['Date'] = pd.to_datetime(plan_df['Date'])
        future_plan = plan_df[plan_df['Date'].dt.date >= today].copy()
        future_plan['Date'] = future_plan['Date'].dt.strftime('%a, %b %d')
        st.dataframe(future_plan[['Date', 'Workout_Category', 'Original_Description', 'Total_Miles']].head(14), use_container_width=True)
    else:
        st.info("Upload a training plan to see your upcoming schedule.")
