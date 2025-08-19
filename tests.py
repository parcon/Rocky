# tests.py
# Version 3.2
# Contains functions to test the core functionality of the application.

import pandas as pd
from io import StringIO
import database
import parsers
from app import calculate_pmc

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
        # Test Plan Parser
        plan_csv = "Date,Total_Miles,E_Pace_Miles\n2025-01-01,5.0,5.0"
        plan_file = StringIO(plan_csv)
        # FIX: Pass the user_id as the first argument
        parsers.parse_and_store_plan(TEST_USER_ID, plan_file)

        # Test Historical Workout CSV Parser
        workout_csv = "Date,Type,Total Time,Distance,Heart Rate\n2025-01-01,Running,0h:30m:00s,3.1,150"
        workout_file = StringIO(workout_csv)
        # FIX: Pass the user_id as the first argument
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
