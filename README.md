### **Rocky: Training Tracker - Project Plan & User Guide**

**Author:** Gemini & Parker Conroy
**Date:** August 20, 2025
**Version:** 4.2

### **1. Features**

"Rocky" is a high-performance training tracker that provides a centralized platform to analyze historical workout data, track performance against a future training plan, and receive AI-powered insights.

* **Historical Performance Analysis**:
    * **Bulk Data Ingestion**: Upload your entire workout history from multiple `.csv`, `.gpx`, and `.fit` files.
    * **Performance Management Chart (PMC)**: Visualize the interplay of your Fitness (CTL), Fatigue (ATL), and Form (TSB) over time.

* **Training Plan Tracking**:
    * **Plan Ingestion**: Parse detailed training plan CSVs to forecast future workout load.
    * **Plan Adherence Assessment**: Get an immediate, data-driven assessment of your current fitness (CTL), fatigue (ATL), and form (TSB) compared to your plan's projections.
    * **Projected Fitness**: View a chart forecasting your fitness (CTL) progression based on your uploaded plan.
    * **Long-Range Visualizations**: See your entire training block at a glance with a weekly stacked bar chart of mileage by intensity and a full calendar view of all upcoming workouts.

* **Weather-Aware Coaching**:
    * **Weekly Forecast**: See a 7-day weather forecast for Austin, TX.
    * **Pace Adjustments**: Get specific, weather-adjusted pace targets for your next run. The app now shows a pace range based on the day's high and low temperatures.
    * **AI-Powered Weekly Outlook**: Receive actionable advice for your upcoming week that considers your current fatigue (ATL) and the weather forecast to help you adjust training intensity and stay on track.

* **Health Metrics & Diagnostics**:
    * **LTHR Estimation**: Estimate your Lactate Threshold Heart Rate (LTHR) by uploading a workout CSV.
    * **Stateless Persistence**: Your VDOT and LTHR settings are saved automatically between sessions without requiring a login.
    * **App Health Check**: A dedicated "Tests" tab to run diagnostic checks on the application's core components.

### **2. System Architecture**

The application is built with a modular and maintainable structure.

* **`app.py` (Core Logic)**: The main application file that handles state management, core calculations, and orchestrates the different components.
* **`ui_components.py` (Frontend)**: Contains the rendering logic for each of the application's tabs.
* **`utils.py` (Shared Functions)**: A utility module for shared calculation functions (like weather adjustments and pace estimations) to prevent circular dependencies.
* **`database.py` (Data Storage)**: Manages a local **SQLite** database (`training.db`) with support for a single, persistent user profile.
* **`parsers.py` (Data Ingestion)**: Contains the functions for parsing various file types (`.csv`, `.gpx`, `.fit`).
* **`tests.py` (Testing)**: Provides unit tests for the application's core functionality.

### **3. User Instructions**

#### **3.1. Setup and Installation**

**Step 1: Create and Activate a Virtual Environment with uv**
```bash
# Create the virtual environment
uv venv

# Activate the environment
# For macOS/Linux
source .venv/bin/activate
# For Windows
.venv\Scripts\activate
```

**Step 2: Install Dependencies with uv**
```bash
uv pip install -r requirements.txt
```

**Step 3: Set Up Gemini API Key**
1.  Obtain a Gemini API key from the [Google AI Studio](https://aistudio.google.com/app/apikey).
2.  In your project folder, create a new directory named `.streamlit`.
3.  Inside `.streamlit`, create a file named `secrets.toml`.
4.  Add your API key to the `secrets.toml` file:
    ```toml
    GEMINI_API_KEY = "YOUR_API_KEY_HERE"
    ```

#### **3.2. How to Run the Application**
```bash
streamlit run app.py
```

#### **3.3. How to Use the Application**
1.  **Estimate LTHR & VDOT**: Go to the **Health Metrics** tab and upload your `Workouts - Workouts.csv` or `Workouts - Heart Rate v pace.csv` file to get an estimated LTHR.
2.  **Configure**: Update the **VDOT Score** and **LTHR** values in the sidebar. These settings will be saved automatically for your next session.
3.  **Process History**: Go to the **Performance Analysis** tab and upload all your workout history files to build your historical performance chart.
4.  **Upload Plan**: Go to the **Training Plan** tab and upload your training plan CSV. This will display your plan adherence, upcoming schedule, and projected fitness.
5.  **Get Weather Advice**: Navigate to the **Weather** tab to see the forecast and AI-powered pace adjustments for your next run. Click the "Get AI Weather & Fatigue Analysis" button for a strategic overview of the week.
6.  **Get AI Coaching**: In the **Training Plan** tab, click the "Generate Training Analysis" button for AI-powered feedback on your overall progress.
7.  **Run Diagnostics**: If you encounter issues, use the **Tests** tab to check the application's health.
