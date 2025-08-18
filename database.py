import sqlite3
import pandas as pd
from datetime import date

DATABASE_FILE = "data/training.db"

def _add_total_miles_column_if_not_exists(cursor):
    """Checks for the total_miles column and adds it if it doesn't exist."""
    cursor.execute("PRAGMA table_info(daily_metrics)")
    columns = [info[1] for info in cursor.fetchall()]
    if 'total_miles' not in columns:
        cursor.execute("ALTER TABLE daily_metrics ADD COLUMN total_miles REAL DEFAULT 0")

def init_db():
    """Initializes the database and creates/updates tables."""
    with sqlite3.connect(DATABASE_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workouts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workout_date TEXT NOT NULL,
                source_type TEXT NOT NULL,
                distance_miles REAL,
                duration_seconds INTEGER,
                avg_heart_rate INTEGER,
                tss REAL NOT NULL,
                unique_id TEXT UNIQUE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_metrics (
                metric_date TEXT PRIMARY KEY,
                planned_tss REAL DEFAULT 0,
                actual_tss REAL DEFAULT 0
            )
        """)
        
        # --- Schema Migration ---
        _add_total_miles_column_if_not_exists(cursor)

        conn.commit()

def add_workout(workout_data):
    """Adds a single workout record and updates daily_metrics."""
    with sqlite3.connect(DATABASE_FILE) as conn:
        cursor = conn.cursor()
        
        # Use a unique ID to prevent duplicate entries
        unique_id = f"{workout_data['workout_date']}-{workout_data.get('duration_seconds', 0)}-{workout_data.get('distance_miles', 0)}"

        cursor.execute("""
            INSERT OR IGNORE INTO workouts (workout_date, source_type, distance_miles, duration_seconds, avg_heart_rate, tss, unique_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            workout_data['workout_date'],
            workout_data['source_type'],
            workout_data.get('distance_miles'),
            workout_data.get('duration_seconds'),
            workout_data.get('avg_heart_rate'),
            workout_data['tss'],
            unique_id
        ))

        # Check if insert was successful before updating daily metrics
        if cursor.rowcount > 0:
            workout_date_str = workout_data['workout_date']
            cursor.execute("INSERT OR IGNORE INTO daily_metrics (metric_date) VALUES (?)", (workout_date_str,))
            
            cursor.execute("""
                UPDATE daily_metrics
                SET actual_tss = actual_tss + ?,
                    total_miles = total_miles + ?
                WHERE metric_date = ?
            """, (workout_data['tss'], workout_data.get('distance_miles', 0), workout_date_str))

        conn.commit()

def update_planned_tss(date_str, tss):
    """Updates the planned_tss for a specific date."""
    with sqlite3.connect(DATABASE_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO daily_metrics (metric_date) VALUES (?)", (date_str,))
        cursor.execute("UPDATE daily_metrics SET planned_tss = ? WHERE metric_date = ?", (tss, date_str))
        conn.commit()

def get_all_metrics():
    """Retrieves all data from the daily_metrics table."""
    with sqlite3.connect(DATABASE_FILE) as conn:
        df = pd.read_sql_query("SELECT metric_date, planned_tss, actual_tss FROM daily_metrics ORDER BY metric_date", conn)
        return df

def get_miles_for_period(start_date, end_date):
    """Calculates the sum of miles run in a given date range."""
    with sqlite3.connect(DATABASE_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT SUM(total_miles) FROM daily_metrics
            WHERE metric_date BETWEEN ? AND ?
        """, (start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
        result = cursor.fetchone()[0]
        return result if result else 0
