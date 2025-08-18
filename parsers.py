import pandas as pd
import gpxpy
import fitparse
from datetime import datetime
import database
import os

# --- Configuration for Planned TSS Estimation ---
INTENSITY_FACTORS = {
    'E_Pace_Miles': 8, 'M_Pace_Miles': 12, 'T_Pace_Miles': 18,
    'I_Pace_Miles': 25, 'R_Pace_Miles': 30, 'E_Pace_Time_min': 0.8
}

def parse_and_store_plan(file):
    """Parses the new training plan format and stores planned TSS."""
    df = pd.read_csv(file)
    df['Date'] = pd.to_datetime(df['Date'])
    
    tss_cols = ['E_Pace_Miles', 'M_Pace_Miles', 'T_Pace_Miles', 'I_Pace_Miles', 'R_Pace_Miles', 'E_Pace_Time_min']
    
    for col in tss_cols:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

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

def estimate_lthr_from_csv(file):
    """Estimates LTHR from a health metrics CSV file object."""
    df = pd.read_csv(file)
    
    # --- Flexible Column Naming ---
    if 'Heart Rate' in df.columns:
        hr_col = 'Heart Rate'
    elif 'HR' in df.columns:
        hr_col = 'HR'
    else:
        raise ValueError("CSV must contain either an 'HR' or 'Heart Rate' column.")

    if 'running time' in df.columns:
        duration_col = 'running time'
    elif 'Total Time' in df.columns:
        duration_col = 'Total Time'
    else:
        raise ValueError("CSV must contain a duration column named 'running time' or 'Total Time'.")

    df['HR_numeric'] = pd.to_numeric(df[hr_col], errors='coerce')
    df.dropna(subset=['HR_numeric', duration_col], inplace=True)

    df['duration_minutes'] = df[duration_col].apply(lambda x: time_str_to_seconds(str(x)) / 60)
    
    hard_efforts = df[(df['duration_minutes'] >= 20) & (df['duration_minutes'] <= 75)]
    
    if len(hard_efforts) < 1:
        raise ValueError("No suitable runs found (20-75 minutes long) to estimate LTHR.")

    top_efforts = hard_efforts.nlargest(5, 'HR_numeric')
    estimated_lthr = int(top_efforts['HR_numeric'].mean())
    
    return estimated_lthr


def parse_and_store_workout(file_obj, lthr, file_extension):
    """Routes the file object to the correct parser based on its extension."""
    if file_extension == '.gpx':
        workout_data = parse_gpx(file_obj, lthr)
    elif file_extension == '.fit':
        workout_data = parse_fit(file_obj, lthr)
    elif file_extension == '.csv':
        parse_historical_csv(file_obj, lthr)
        workout_data = None
    else:
        raise ValueError(f"Unsupported file type: {file_extension}")

    if workout_data:
        database.add_workout(workout_data)

def parse_historical_csv(file_obj, lthr):
    """Parses historical workout data from a CSV file object."""
    df = pd.read_csv(file_obj)
    df.rename(columns={'Distance': 'Distance_miles', 'Heart Rate': 'avg_heart_rate', 'Total Time': 'duration_str'}, inplace=True, errors='ignore')
    
    for _, row in df.iterrows():
        try:
            if 'Running' not in row.get('Type', ''): continue

            workout_date = pd.to_datetime(row['Date']).strftime('%Y-%m-%d')
            duration_seconds = time_str_to_seconds(row['duration_str'])
            avg_hr = pd.to_numeric(row.get('avg_heart_rate'), errors='coerce')
            distance = pd.to_numeric(row.get('Distance_miles'), errors='coerce')
            
            tss = calculate_hrtss(avg_hr, duration_seconds, lthr) if pd.notna(avg_hr) else (duration_seconds / 3600) * 50

            workout_data = {
                'workout_date': workout_date, 'source_type': 'csv', 'distance_miles': distance,
                'duration_seconds': duration_seconds, 'avg_heart_rate': avg_hr, 'tss': tss
            }
            database.add_workout(workout_data)
        except (KeyError, ValueError):
            continue

def parse_gpx(file_obj, lthr):
    """Parses a GPX file object."""
    gpx = gpxpy.parse(file_obj.read())
    
    start_time = gpx.get_time_bounds().start_time.replace(tzinfo=None)
    duration = gpx.get_duration()
    distance_miles = gpx.length_3d() * 0.000621371
    tss = (duration / 3600) * 50

    return {
        'workout_date': start_time.strftime('%Y-%m-%d'), 'source_type': 'gpx', 'distance_miles': distance_miles,
        'duration_seconds': duration, 'avg_heart_rate': None, 'tss': tss
    }

def parse_fit(file_obj, lthr):
    """Parses a FIT file object."""
    fitfile = fitparse.FitFile(file_obj)
    hr_data, start_time, total_distance, total_duration = [], None, 0, 0

    for record in fitfile.get_messages('record'):
        if record.get_value('heart_rate'):
            hr_data.append(record.get_value('heart_rate'))

    for record in fitfile.get_messages('session'):
        start_time = record.get_value('start_time').replace(tzinfo=None)
        total_distance = record.get_value('total_distance')
        total_duration = record.get_value('total_timer_time')

    if not total_duration or not start_time: return None 

    avg_hr = sum(hr_data) / len(hr_data) if hr_data else None
    tss = calculate_hrtss(avg_hr, total_duration, lthr) if avg_hr else (total_duration / 3600) * 50
    distance_miles = total_distance * 0.000621371 if total_distance else 0
    
    return {
        'workout_date': start_time.strftime('%Y-%m-%d'), 'source_type': 'fit', 'distance_miles': distance_miles,
        'duration_seconds': total_duration, 'avg_heart_rate': avg_hr, 'tss': tss
    }

def calculate_hrtss(avg_hr, duration_seconds, lthr):
    """Calculates Heart Rate Training Stress Score (hrTSS)."""
    if not all([avg_hr, lthr, duration_seconds]): return 0
    intensity_factor = avg_hr / lthr
    return (duration_seconds * avg_hr * intensity_factor) / (lthr * 36)

def time_str_to_seconds(time_str):
    """Converts complex time strings like '1:24:30' or '1h24m30s' to seconds."""
    if not isinstance(time_str, str):
        return 0
    
    # Handle H:M:S format first, as it's less ambiguous
    if ':' in time_str and 'h' not in time_str.lower():
        try:
            parts = list(map(int, time_str.split(':')))
            if len(parts) == 3:
                return parts[0] * 3600 + parts[1] * 60 + parts[2]
            elif len(parts) == 2:
                return parts[0] * 60 + parts[1]
            return 0
        except ValueError:
             # Fallback for formats that contain ':' but aren't purely numeric
             pass

    # Handle Xh Ym Zs format and mixed formats
    h, m, s = 0, 0, 0
    # Replace common delimiters to handle mixed cases like '1h:30m'
    time_str_processed = time_str.lower().replace(':', ' ').replace('h', 'h ').replace('m', 'm ').replace('s', 's ')
    parts = time_str_processed.split()
    
    try:
        for part in parts:
            if part.endswith('h'):
                h = int(part[:-1])
            elif part.endswith('m'):
                m = int(part[:-1])
            elif part.endswith('s'):
                s = int(part[:-1])
    except (ValueError, IndexError):
        return 0 # Return 0 if parsing fails

    return h * 3600 + m * 60 + s
