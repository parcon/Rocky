# database.py
# Version 3.4
# Handles all database interactions, including stateless user persistence and robust schema migrations.

import sqlite3
import pandas as pd
from datetime import date

DATABASE_FILE = "data/training.db"

def table_exists(cursor, table_name):
    """Checks if a table exists in the database."""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    return cursor.fetchone() is not None

def init_db():
    """Initializes the database and creates/updates tables with robust migration."""
    with sqlite3.connect(DATABASE_FILE) as conn:
        cursor = conn.cursor()

        # --- Settings Table for Persistence ---
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                user_id INTEGER NOT NULL,
                setting_name TEXT NOT NULL,
                setting_value TEXT,
                PRIMARY KEY (user_id, setting_name)
            )
        """)

        # --- Create Tables if they don't exist ---
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workouts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
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
                user_id INTEGER NOT NULL,
                metric_date TEXT NOT NULL,
                planned_tss REAL DEFAULT 0,
                actual_tss REAL DEFAULT 0,
                total_miles REAL DEFAULT 0,
                PRIMARY KEY (user_id, metric_date)
            )
        """)

        # --- Schema Migration: Check for old tables and migrate if they exist ---
        if table_exists(cursor, "workouts_old"):
             cursor.execute("DROP TABLE workouts_old")
        if table_exists(cursor, "daily_metrics_old"):
             cursor.execute("DROP TABLE daily_metrics_old")

        cursor.execute("PRAGMA table_info(workouts)")
        workouts_cols = [info[1] for info in cursor.fetchall()]
        if 'user_id' not in workouts_cols:
            cursor.execute("ALTER TABLE workouts RENAME TO workouts_old")
            cursor.execute("""
                CREATE TABLE workouts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, workout_date TEXT NOT NULL,
                    source_type TEXT NOT NULL, distance_miles REAL, duration_seconds INTEGER,
                    avg_heart_rate INTEGER, tss REAL NOT NULL, unique_id TEXT UNIQUE
                )
            """)
            cursor.execute("""
                INSERT INTO workouts (id, user_id, workout_date, source_type, distance_miles, duration_seconds, avg_heart_rate, tss, unique_id)
                SELECT id, 1, workout_date, source_type, distance_miles, duration_seconds, avg_heart_rate, tss, unique_id FROM workouts_old
            """)
            cursor.execute("DROP TABLE workouts_old")

        cursor.execute("PRAGMA table_info(daily_metrics)")
        metrics_cols = [info[1] for info in cursor.fetchall()]
        if 'user_id' not in metrics_cols:
            cursor.execute("ALTER TABLE daily_metrics RENAME TO daily_metrics_old")
            cursor.execute("""
                CREATE TABLE daily_metrics (
                    user_id INTEGER NOT NULL, metric_date TEXT NOT NULL, planned_tss REAL DEFAULT 0,
                    actual_tss REAL DEFAULT 0, total_miles REAL DEFAULT 0, PRIMARY KEY (user_id, metric_date)
                )
            """)
            cursor.execute("""
                INSERT INTO daily_metrics (user_id, metric_date, planned_tss, actual_tss, total_miles)
                SELECT 1, metric_date, planned_tss, actual_tss, total_miles FROM daily_metrics_old
            """)
            cursor.execute("DROP TABLE daily_metrics_old")
        
        conn.commit()

# --- Settings Functions ---
def get_setting(user_id, setting_name):
    """Retrieves a specific setting for a user."""
    with sqlite3.connect(DATABASE_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT setting_value FROM settings WHERE user_id = ? AND setting_name = ?", (user_id, setting_name))
        result = cursor.fetchone()
        return result[0] if result else None

def set_setting(user_id, setting_name, setting_value):
    """Saves or updates a specific setting for a user."""
    with sqlite3.connect(DATABASE_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO settings (user_id, setting_name, setting_value)
            VALUES (?, ?, ?)
        """, (user_id, setting_name, str(setting_value)))
        conn.commit()

# --- Data Functions (now user-aware) ---
def add_workout(user_id, workout_data):
    """Adds a single workout record for a specific user."""
    with sqlite3.connect(DATABASE_FILE) as conn:
        cursor = conn.cursor()
        unique_id = f"{user_id}-{workout_data['workout_date']}-{workout_data.get('duration_seconds', 0)}-{workout_data.get('distance_miles', 0)}"
        cursor.execute("""
            INSERT OR IGNORE INTO workouts (user_id, workout_date, source_type, distance_miles, duration_seconds, avg_heart_rate, tss, unique_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id, workout_data['workout_date'], workout_data['source_type'],
            workout_data.get('distance_miles'), workout_data.get('duration_seconds'),
            workout_data.get('avg_heart_rate'), workout_data['tss'], unique_id
        ))
        if cursor.rowcount > 0:
            workout_date_str = workout_data['workout_date']
            cursor.execute("INSERT OR IGNORE INTO daily_metrics (user_id, metric_date) VALUES (?, ?)", (user_id, workout_date_str))
            cursor.execute("""
                UPDATE daily_metrics SET actual_tss = actual_tss + ?, total_miles = total_miles + ?
                WHERE user_id = ? AND metric_date = ?
            """, (workout_data['tss'], workout_data.get('distance_miles', 0), user_id, workout_date_str))
        conn.commit()

def update_planned_tss(user_id, date_str, tss):
    """Updates the planned_tss for a specific date for a user."""
    with sqlite3.connect(DATABASE_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO daily_metrics (user_id, metric_date) VALUES (?, ?)", (user_id, date_str))
        cursor.execute("UPDATE daily_metrics SET planned_tss = ? WHERE user_id = ? AND metric_date = ?", (tss, user_id, date_str))
        conn.commit()

def get_all_metrics(user_id):
    """Retrieves all data from the daily_metrics table for a user."""
    with sqlite3.connect(DATABASE_FILE) as conn:
        return pd.read_sql_query("SELECT metric_date, planned_tss, actual_tss FROM daily_metrics WHERE user_id = ? ORDER BY metric_date", conn, params=(user_id,))

def get_miles_for_period(user_id, start_date, end_date):
    """Calculates the sum of miles run in a given date range for a user."""
    with sqlite3.connect(DATABASE_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(total_miles) FROM daily_metrics WHERE user_id = ? AND metric_date BETWEEN ? AND ?",
                       (user_id, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
        result = cursor.fetchone()[0]
        return result if result else 0
