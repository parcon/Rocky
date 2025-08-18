### **Project Plan: Intelligent Running Performance Tracker**

**Author:** Gemini
**Date:** August 17, 2025
**Version:** 1.0 (Combined)

---

### **1. Introduction & Vision**

#### **1.1. Purpose and Vision**

This document provides a complete specification for the "Intelligent Running Performance Tracker." It merges the product vision with the technical blueprint, serving as a single source of truth for all stakeholders. The application's purpose is to provide runners with a centralized, intelligent platform to import workout data, visualize performance against a training plan, and receive AI-powered insights to keep them on track and optimize their training.

#### **1.2. Scope**

The initial version of the application will support data ingestion from local files (`.gpx`, `.fit`, `.csv`), calculate core performance metrics (TSS, CTL, ATL, TSB), visualize planned vs. actual performance, and provide AI-powered commentary via the Gemini API. The system will use a local SQLite database, architected for a seamless future migration to a cloud database like Firebase Firestore.

#### **1.3. User Personas**

* **The Dedicated Amateur:** A runner serious about training for a specific goal (e.g., a marathon). They follow a structured plan and want to know if they are "on track" and what they should be mindful of.

* **The Data-Driven Athlete:** A runner comfortable with training metrics who wants a powerful tool to analyze their performance, including detailed CTL, ATL, and TSB data.

---

### **2. Features & Functional Requirements**

#### **2.1. Data Ingestion**

* **Feature:** The application will import both planned training schedules and completed workout data from multiple sources.

* **Requirements:**

    * **(FR-1) Training Plan Ingestion:** The system shall allow users to upload a training plan in CSV format.

        * **(FR-1.1) CSV Parsing:** The system must parse the CSV, expecting columns: `Date`, `Workout_Description`, `Total_Miles`.

        * **(FR-1.2) Planned TSS Estimation:** The system must parse the `Workout_Description` string (e.g., "4E+8M+1T+1E") to estimate a `planned_tss`. This requires a user-configurable mapping of workout types (e.g., E, M, T, I, R) to intensity factors or paces to derive a total TSS for the planned workout.

    * **(FR-2) Workout Data Ingestion:** The system shall allow users to upload completed workout files.

        * **(FR-2.1) GPX File Parsing:** The system will use the `gpxpy` library to parse `.gpx` files and extract time series data for distance, duration, and elevation.

        * **(FR-2.2) FIT File Parsing:** The system will use the `python-fitparse` library to parse `.fit` files and extract detailed workout data, including heart rate.

#### **2.2. Core Metrics & Calculations**

* **Feature:** The application will calculate key performance indicators to model a runner's fitness, fatigue, and form over time.

* **Requirements:**

    * **(FR-3) Core Metric Calculation:** The system must calculate performance metrics based on TSS.

        * **(FR-3.1) Actual TSS Calculation:** The system will calculate TSS for completed workouts. The primary method will be Heart Rate TSS (hrTSS), requiring the user to input their lactate threshold heart rate.

        * **(FR-3.2) PMC Calculation:** The system will iterate through all dates from the start of the plan to the present, calculating the daily CTL (42-day average), ATL (7-day average), and TSB (`CTL - ATL`) based on the `actual_tss` and `planned_tss` values.

#### **2.3. Data Visualization & Adherence**

* **Feature:** The application will provide a clear, interactive visualization comparing the user's planned training load against their actual performance.

* **Requirements:**

    * **(FR-4) Data Visualization:** The system must provide clear visualizations of the user's data.

        * **(FR-4.1) Performance Management Chart:** A `Plotly` chart will display `CTL`, `ATL`, `TSB`, and `actual_tss` over time. It will also overlay the *modeled* TSB derived from the `planned_tss` values to provide an immediate visual reference for adherence.

#### **2.4. AI-Powered Analysis**

* **Feature:** The application will leverage the Gemini API to provide users with personalized, forward-looking commentary on their training.

* **Requirements:**

    * **(FR-5) AI Commentary:** The system must provide AI-powered analysis.

        * **(FR-5.1) Gemini API Integration:** The system will construct a prompt containing the user's recent `daily_metrics` data and upcoming planned workouts. This prompt will be sent to the Gemini API.

        * **(FR-5.2) Display Commentary:** The natural language response from the Gemini API will be displayed clearly to the user in the Streamlit interface.

---

### **3. System Architecture & Design**

#### **3.1. System Architecture**

The application will use a modular, three-tier architecture:

```
+------------------+      +-------------------+      +--------------------------+      +-----------------+
|                  |      |                   |      |                          |      |                 |
|  Streamlit       +----->|   Backend /       +----->|  Data Abstraction Layer  +----->|  SQLite DB      |
|  Frontend (UI)   |      |   Core Logic      |      |  (DAL)                   |      |  (training.db)  |
|                  |      |                   |      |                          |      |                 |
+------------------+      +-------------------+      +--------------------------+      +-----------------+

```

* **Frontend:** A web interface built using **Streamlit** for all user interactions.

* **Backend / Core Logic:** A Python engine containing all business logic (parsing, calculations, API calls).

* **Data Abstraction Layer (DAL):** An intermediary module that handles all database communications, allowing for easy database backend swapping in the future.

* **Data Storage:** A local **SQLite** database file (`training.db`).

#### **3.2. Data Model & Schema (SQLite)**

The database will consist of two primary tables:

**Table 1: `workouts`**
| Column Name | Data Type | Description |
| :--- | :--- | :--- |
| `id` | INTEGER | Primary Key, Auto-incrementing |
| `workout_date` | TEXT | Date of the workout (ISO 8601: YYYY-MM-DD) |
| `source_type` | TEXT | 'gpx', 'fit', or 'manual' |
| `distance_meters` | REAL | Total distance in meters |
| `duration_seconds` | INTEGER | Total duration in seconds |
| `avg_heart_rate` | INTEGER | Average heart rate in BPM |
| `tss` | REAL | Calculated Training Stress Score |

**Table 2: `daily_metrics`**
| Column Name | Data Type | Description |
| :--- | :--- | :--- |
| `metric_date` | TEXT | The specific date (Primary Key, ISO 8601) |
| `planned_tss` | REAL | Estimated TSS from the training plan |
| `actual_tss` | REAL | Sum of TSS from all workouts on this date |
| `ctl` | REAL | Chronic Training Load for this date |
| `atl` | REAL | Acute Training Load for this date |
| `tsb` | REAL | Training Stress Balance for this date |

---

### **4. Non-Functional Requirements**

| **ID** | **Requirement** | **Description** |
| :--- | :--- | :--- |
| **NFR-1** | **Performance** | The main chart should load in < 3 seconds for an 18-week plan. File parsing should complete within 5 seconds for typical file sizes. |
| **NFR-2** | **Scalability** | The DAL is designed to allow future migration from SQLite to a cloud NoSQL database (e.g., Firestore) to support multiple users. |
| **NFR-3** | **Usability** | The UI must be simple and intuitive, with key actions achievable in a minimal number of clicks. |
| **NFR-4** | **Reliability** | The system must include robust error handling for file parsing and API calls, providing clear feedback to the user. |

---

### **5. Technology Stack**

* **Language:** Python 3.9+

* **Frontend Framework:** Streamlit

* **Data Manipulation:** Pandas, NumPy

* **File Parsing:** `gpxpy`, `python-fitparse`

* **Database:** `sqlite3` (standard library)

* **Visualization:** Plotly

* **API Clients:** `google-api-python-client`, `google-generativeai`

---

### **6. Success Metrics**

* **User Engagement:** Number of weekly active users.

* **Feature Adoption:** Percentage of users who upload a training plan and use the Gemini analysis feature.

* **User Satisfaction:** Qualitative feedback on the accuracy of the planned TSS model and the usefulness of the AI-generated commentary.
