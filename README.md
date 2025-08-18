### **Rocky: Training Tracker - Project Plan & User Guide**

**Author:** Gemini & Parker Conroy
**Date:** August 17, 2025
**Version:** 2.7 (Rocky Edition)

---

### **1. Product Vision & Requirements (PRD)**

#### **1.1. Purpose and Vision**

"Rocky" is a high-performance training tracker designed for dedicated runners. The application provides a centralized, intelligent platform to analyze historical workout data, track performance against a future training plan, and receive AI-powered insights to optimize training and stay motivated.

#### **1.2. Core Features**

* **(FR-1) Historical Performance Analysis:**
    * **Bulk Data Ingestion:** Users can upload their entire workout history via multiple `.csv`, `.gpx`, and `.fit` files.
    * **Performance Management Chart (PMC):** The app calculates and displays a complete PMC, showing the interplay of Fitness (CTL), Fatigue (ATL), and Form (TSB) over time.

* **(FR-2) Training Plan Tracking:**
    * **Plan Ingestion:** Parses detailed training plan CSVs to understand future workout load.
    * **Training Readiness:** Calculates the user's projected form (TSB) for the first workout of the plan, providing immediate feedback on whether they are starting fresh, fatigued, or in an optimal state.
    * **Projected Fitness:** Displays a chart forecasting the user's fitness (CTL) progression based on the uploaded plan.

* **(FR-3) Health Metrics & AI Analysis:**
    * **LTHR Estimation:** Ingests a workout CSV to provide an estimated Lactate Threshold Heart Rate (LTHR), a key metric for calculating training stress.
    * **AI-Powered Coaching:** Uses the Gemini API to provide detailed, contextual analysis of the user's fitness, fatigue, form, and adherence to their plan.

---

### **2. Software & System Requirements (SRD)**

#### **2.1. System Architecture**

* **Frontend:** A web interface built using **Streamlit**, with UI components separated into `ui_components.py`.
* **Backend / Core Logic:** A Python engine (`app.py`, `parsers.py`) containing all business logic.
* **Data Storage:** A local **SQLite** database file (`training.db`) managed by `database.py`.

#### **2.2. Technology Stack**

* **Language:** Python 3.9+
* **Framework:** Streamlit
* **Data Manipulation:** Pandas
* **File Parsing:** `gpxpy`, `python-fitparse`
* **Database:** `sqlite3`
* **Visualization:** Plotly
* **AI Integration:** Google Gemini API (`gemini-2.5-flash-lite`)

---

### **3. User Instructions**

#### **3.1. Setup and Installation**

**Step 1: Create a Virtual Environment (Recommended)**

```bash
# For macOS/Linux
python3 -m venv venv
source venv/bin/activate

# For Windows
python -m venv venv
venv\Scripts\activate
```

**Step 2: Install Dependencies**

```bash
pip install -r requirements.txt
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

1.  **Estimate LTHR**: Go to the **Health Metrics** tab. Upload your `Workouts - Workouts.csv` or `Workouts - Heart Rate v pace.csv` file to get an estimated LTHR.
2.  **Configure**: Update the **VDOT / LTHR** value in the sidebar with your new estimate.
3.  **Process History**: Go to the **Performance Analysis** tab. Upload all your workout history files (`Workouts - Workouts.csv`, `.gpx`, `.fit`) to build your historical performance chart.
4.  **Upload Plan**: Go to the **Training Plan** tab and upload your training plan CSV. This will display your upcoming schedule, your readiness for the plan, and your projected fitness.
5.  **Get AI Coaching**: Click the "Generate Training Analysis" button for AI-powered feedback.
