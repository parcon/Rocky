# tests.py
# Version 3.4
# Imports weather functions from the new utils.py to break the circular dependency.

import pandas as pd
from io import StringIO
import database
import parsers
from app import calculate_pmc
from utils import calculate_dew_point, adjust_pace_for_weather # <-- UPDATED IMPORT

# --- Constants ---
TEST_USER_ID = 99 # A dedicated user ID for testing purposes

def test_database_connection():
    """Tests if the database can be initialized and tables created."""
    try:
        database.init_db()
        return True, "Success"
    except Exception as e:
        return False, str(e)

def test_parsers():
    """Tests the core file parsing functions with in-memory file objects."""
    try:
        plan_csv = "Date,Total_Miles,E_Pace_Miles\n2025-01-01,5.0,5.0"
        plan_file = StringIO(plan_csv)
        parsers.parse_and_store_plan(TEST_USER_ID, plan_file)

        workout_csv = "Date,Type,Total Time,Distance,Heart Rate\n2025-01-01,Running,0h:30m:00s,3.1,150"
        workout_file = StringIO(workout_csv)
        parsers.parse_historical_csv(TEST_USER_ID, workout_file, 175)
        
        return True, "Success"
    except Exception as e:
        return False, str(e)

def test_pmc_calculation():
    """Tests the PMC calculation logic."""
    try:
        data = {'metric_date': pd.to_datetime(['2025-01-01', '2025-01-02']),
                'actual_tss': [100, 120]}
        df = pd.DataFrame(data)
        pmc_df = calculate_pmc(df)
        
        if not all(col in pmc_df.columns for col in ['ctl', 'atl', 'tsb']):
            return False, "PMC DataFrame is missing required columns."
        if pmc_df.empty:
            return False, "PMC DataFrame is empty."
            
        return True, "Success"
    except Exception as e:
        return False, str(e)

def test_weather_adjustments():
    """Tests the dew point and pace adjustment calculations."""
    try:
        # Test dew point calculation
        dp = calculate_dew_point(temp_f=75, humidity_pct=80)
        assert 68 < dp < 69, f"Dew point calculation failed. Expected ~68.5, got {dp}"

        # Test pace adjustment below threshold
        no_adjustment = adjust_pace_for_weather(base_pace_seconds=600, dew_point_f=59)
        assert no_adjustment == 600, "Pace should not be adjusted below 60°F dew point."

        # Test pace adjustment above threshold
        adjustment = adjust_pace_for_weather(base_pace_seconds=600, dew_point_f=70)
        # Expected: 600 * (1 + 0.006 * (70 - 60)) = 600 * 1.06 = 636
        assert 635 < adjustment < 637, f"Pace adjustment calculation failed. Expected ~636, got {adjustment}"

        return True, "Success"
    except AssertionError as e:
        return False, str(e)
    except Exception as e:
        return False, f"An unexpected error occurred: {e}"
