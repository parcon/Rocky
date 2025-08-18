import pandas as pd
import gpxpy
import fitparse
from datetime import datetime
import database
import os

# --- Configuration for Planned TSS Estimation ---
# These factors are simplified multipliers. A more complex model could use pace.
# (TSS per mile or per minute for different zones)
INTENSITY_FACTORS = {
    'E_Pace_Miles': 8,    # Lower TSS per mile for easy pace
    'M_Pace_Miles': 12,   # Medium TSS for marathon pace
    'T_Pace_Miles': 18,   # Higher TSS for threshold pace
    'I_Pace_Miles': 25,   # Very high TSS for interval pace
    'R_Pace_Miles': 30,   # Max TSS for repetition pace
    'E_Pace_Time_min': 0.8 # TSS per minute for time-based easy runs
}

def parse_and_store_plan(file):
    """Parses the new training plan format and stores planned TSS."""
    df = pd.read_csv(file)
    df['Date'] = pd.to_datetime(df['Date'])
    
    # Define the columns needed for TSS calculation
    tss_cols = ['E_Pace_Miles', 'M_Pace_Miles', 'T_Pace_Miles', 'I_Pace_Miles', 'R_Pace_Miles', 'E_Pace_Time_min']
    
    # Ensure all required columns exist, convert them to numeric, and fill any missing values with 0
    for col in tss_cols:
        if col not in df.columns:
            df[col] = 0
        # Force column to be numeric, coercing errors to NaN, then fill NaN with 0
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # Calculate planned TSS for each day
    df['planned_tss'] = (
        df['E_Pace_Miles'] * INTENSITY_FACTORS['E_Pace_Miles'] +
        df['M_Pace_Miles'] * INTENSITY_FACTORS['M_Pace_Miles'] +
        df['T_Pace_Miles'] * INTENSITY_FACTORS['T_Pace_Miles'] +
        df['I_Pace_Miles'] * INTENSITY_FACTORS['I_Pace_Miles'] +
        df['R_Pace_Miles'] * INTENSITY_FACTORS['R_Pace_Miles'] +
        df['E_Pace_Time_min'] * INTENSITY_FACTORS['E_Pace_Time_min']
    )

    for _, row in df.iterrows():
        date_str = row['Date'].strftime('%Y-%m-%d')
        database.update_planned_tss(date_str, row['planned_tss'])
    
    return df

def parse_and_store_workout(file_path, lthr):
    """Routes the file to the correct parser based on extension."""
    filename = os.path.basename(file_path).lower()
    if filename.endswith('.gpx'):
        workout_data = parse_gpx(file_path, lthr)
    elif filename.endswith('.fit'):
        workout_data = parse_fit(file_path, lthr)
    elif filename.endswith('.csv'):
        # Assuming CSV is in the "Workouts - Workouts.csv" format
        parse_historical_csv(file_path, lthr)
        workout_data = None # This function handles its own DB writes
    else:
        raise ValueError(f"Unsupported file type: {filename}")

    if workout_data:
        database.add_workout(workout_data)

def parse_historical_csv(file_path, lthr):
    """Parses historical workout data from a CSV file (e.g., Apple Health export)."""
    df = pd.read_csv(file_path)
    # Standardize column names if they vary
    df.rename(columns={'Distance': 'Distance_miles', 'Heart Rate': 'avg_heart_rate', 'Total Time': 'duration_str'}, inplace=True, errors='ignore')
    
    for _, row in df.iterrows():
        try:
            # Skip non-running activities for this model
            if 'Running' not in row['Type']:
                continue

            workout_date = pd.to_datetime(row['Date']).strftime('%Y-%m-%d')
            duration_seconds = time_str_to_seconds(row['duration_str'])
            avg_hr = pd.to_numeric(row.get('avg_heart_rate'), errors='coerce')
            distance = pd.to_numeric(row.get('Distance_miles'), errors='coerce')
            
            if pd.isna(avg_hr):
                # Estimate TSS based on duration if HR is missing (50 TSS/hr)
                tss = (duration_seconds / 3600) * 50
            else:
                tss = calculate_hrtss(avg_hr, duration_seconds, lthr)

            workout_data = {
                'workout_date': workout_date,
                'source_type': 'csv',
                'distance_miles': distance,
                'duration_seconds': duration_seconds,
                'avg_heart_rate': avg_hr,
                'tss': tss
            }
            database.add_workout(workout_data)
        except (KeyError, ValueError) as e:
            # Skip rows that are missing critical data or have formatting issues
            # st.warning(f"Skipping row in {os.path.basename(file_path)} due to error: {e}")
            continue

def parse_gpx(file_path, lthr):
    """Parses a GPX file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as gpx_file:
            gpx = gpxpy.parse(gpx_file)
    except Exception as e:
        # Fallback for encoding errors
        with open(file_path, 'r') as gpx_file:
            gpx = gpxpy.parse(gpx_file)

    
    start_time = gpx.get_time_bounds().start_time.replace(tzinfo=None)
    duration = gpx.get_duration()
    distance_meters = gpx.length_3d()
    distance_miles = distance_meters * 0.000621371
    
    # GPX often lacks HR. Estimate TSS based on duration (50 TSS/hr).
    tss = (duration / 3600) * 50

    return {
        'workout_date': start_time.strftime('%Y-%m-%d'),
        'source_type': 'gpx',
        'distance_miles': distance_miles,
        'duration_seconds': duration,
        'avg_heart_rate': None,
        'tss': tss
    }

def parse_fit(file_path, lthr):
    """Parses a FIT file."""
    fitfile = fitparse.FitFile(file_path)
    
    hr_data, start_time, total_distance, total_duration = [], None, 0, 0

    for record in fitfile.get_messages('record'):
        if record.get_value('heart_rate'):
            hr_data.append(record.get_value('heart_rate'))

    for record in fitfile.get_messages('session'):
        start_time = record.get_value('start_time').replace(tzinfo=None)
        total_distance = record.get_value('total_distance') # In meters
        total_duration = record.get_value('total_timer_time')

    if not total_duration or not start_time:
        return None 

    if hr_data:
        avg_hr = sum(hr_data) / len(hr_data)
        tss = calculate_hrtss(avg_hr, total_duration, lthr)
    else:
        # Estimate TSS if no HR data
        avg_hr = None
        tss = (total_duration / 3600) * 50


    distance_miles = total_distance * 0.000621371 if total_distance else 0
    
    return {
        'workout_date': start_time.strftime('%Y-%m-%d'),
        'source_type': 'fit',
        'distance_miles': distance_miles,
        'duration_seconds': total_duration,
        'avg_heart_rate': avg_hr,
        'tss': tss
    }

def calculate_hrtss(avg_hr, duration_seconds, lthr):
    """Calculates Heart Rate Training Stress Score (hrTSS)."""
    if not avg_hr or not lthr or lthr == 0 or not duration_seconds: return 0
    intensity_factor = avg_hr / lthr
    return (duration_seconds * avg_hr * intensity_factor) / (lthr * 36)

def time_str_to_seconds(time_str):
    """Converts time string like '1:24:30' or '1h24m30s' to seconds."""
    if not isinstance(time_str, str): return 0
    
    # Handle H:M:S format
    if ':' in time_str:
        parts = list(map(int, time_str.split(':')))
        if len(parts) == 3: # H:M:S
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        elif len(parts) == 2: # M:S
            return parts[0] * 60 + parts[1]
        else:
            return 0

    # Handle XhYmZs format
    h, m, s = 0, 0, 0
    if 'h' in time_str:
        parts = time_str.split('h')
        h = int(parts[0])
        time_str = parts[1]
    if 'm' in time_str:
        parts = time_str.split('m')
        m = int(parts[0])
        time_str = parts[1]
    if 's' in time_str:
        s = int(time_str.replace('s', ''))
    return h * 3600 + m * 60 + s
