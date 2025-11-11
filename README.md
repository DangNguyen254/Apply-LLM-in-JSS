# LLM-Powered Job Shop Scheduling (JSSp) Orchestrator

A full-stack, multi-user scheduling application where a Google Gemini LLM acts as a stateful orchestrator to manage, simulate, and solve complex manufacturing scenarios.


*(Add a screenshot of your JavaFX application here, showing the Gantt chart, job list, and chat interface)*

---

## 🤖 Core Concept: The LLM as an Orchestrator

This project is not a simple chatbot. It's a demonstration of an LLM acting as a "stateful orchestrator."

* **The Problem:** Most "AI-powered" apps are simple translators that turn `natural language -> API call`. They are stateless.
* **The Solution:** This system's LLM (Gemini 2.5 Flash) is given a "Tool Belt" of Python functions and a complex system prompt. When given a command like, `"What if a machine breaks?"`, it doesn't just answer—it **creates a multi-step plan**.

**The "What-If" Workflow:**
1.  **LLM calls:** `get_active_scenario()` to get the user's "Live Data" ID (e.g., `Scenario 1`).
2.  **LLM calls:** `create_scenario(base_id=1)` to create a new, temporary `Scenario 2`.
3.  **LLM calls:** `select_scenario(id=2)` to *silently* switch its own context.
4.  **LLM calls:** `modify_machine_group(...)` to "break" the machine in the temporary scenario.
5.  **LLM calls:** `simulate_solve()` to get the KPIs for this temporary state.
6.  **LLM calls:** `select_scenario(id=1)` to switch its context *back* to "Live Data."
7.  **LLM calls:** `delete_scenario(id=2)` to clean up the temporary data.
8.  **LLM responds:** "If that machine broke, your makespan would be X."

When the user says, "Okay, make that real," the LLM knows it is back in the "Live Data" context and re-applies the modification, this time calling the *real* `solve_schedule` tool.

---

## ✨ Key Features

* **LLM Orchestrator:** Uses Google Gemini 2.5 Flash with Tool-Calling to plan and execute complex, multi-step tasks.
* **Multi-Objective Solver:** Employs Google OR-Tools to solve the JSSp, optimizing for a weighted combination of **Job Priority** and **Makespan**.
* **Stateful Multi-User Sessions:** A robust FastAPI backend manages individual user sessions. All operations are isolated and authenticated by a session token.
* **Persistent Multi-Scenario Database:** Uses SQLModel and a SQL Server to store all problem data. Each user has a primary "Live Data" scenario, and all "what-if" simulations are managed as temporary, isolated scenarios.
* **Persistent Schedule Storage:** All solved schedules are saved as versioned records in the database, linked to their parent scenario. This creates a persistent, robust audit trail of solutions.
* **Rich Client Dashboard:** A JavaFX desktop application provides a clean user interface for interaction.
* **Dynamic Gantt Chart:** A custom-built Gantt chart component in JavaFX that visualizes the final schedule, correctly stacking parallel operations on multiple machine instances.
* **Full Audit Trail:** Every user command, LLM response, and tool error is logged to a persistent `CommandLog` table in the database for debugging and analysis.

---

## 📐 System Architecture

This project follows a classic client-server architecture.

### 1. Backend (Python)
The "brain" of the operation, built with **FastAPI**.
* **`/api/scheduling/`:** The main API router.
    * `/login`: Authenticates a user and creates an `AppContext` session.
    * `/interpret`: The main orchestrator endpoint. It takes a user's command, validates their session token, and initiates the LLM tool-calling loop.
    * `/get_latest_schedule`: Fetches the officially saved schedule from the database for export.
* **`llm_service.py`:** Manages all communication with the Google Gemini API, including the system prompt and tool definitions.
* **`jssp_solver.py`:** Contains the Google OR-Tools model for solving the scheduling problem.
* **`database.py` / `jssp_model.py`:** Defines the database connection and all `SQLModel` tables (`User`, `Scenario`, `Job`, `MachineGroup`, `Schedule`, `CommandLog`, etc.).

### 2. Frontend (Java)
A rich desktop client built with **JavaFX**.
* **`MainApp.java` / `MainView.fxml`:** Defines the UI components (chat box, Gantt chart, data views).
* **`MainViewController.java`:** The main controller that handles button clicks, updates the UI, and sends commands to the backend.
* **`ApiClient.java`:** A dedicated service for all HTTP communication with the FastAPI backend. It manages the user's `session_token`.
* **`GanttChart.java`:** A custom `Pane` component that dynamically draws the schedule using JavaFX shapes.

---

## 🛠️ Technology Stack

| Component | Technology |
| :--- | :--- |
| **Backend** | Python 3.11+, FastAPI, SQLModel (Pydantic + SQLAlchemy) |
| **AI** | Google Gemini 2.5 Flash |
| **Solver** | Google OR-Tools (CP-SAT) |
| **Frontend** | Java 17+, JavaFX 24+, FXML |
| **Database** | Microsoft SQL Server (connected via `pyodbc`) |
| **Libraries** | `google-generativeai`, `jackson` (Java), `uuid` |

---

## 🚀 How to Run

### Prerequisites
* Python 3.10+
* Java JDK 17+ (with JavaFX SDK)
* A running Microsoft SQL Server instance

### 1. Backend Setup
1.  Clone the repository.
2.  Navigate to the `/backend` directory.
3.  Create and activate a virtual environment:
    ```sh
    python -m venv venv
    source venv/bin/activate  # (or .\venv\Scripts\activate on Windows)
    ```
4.  Install all required packages:
    ```sh
    pip install -r requirements.txt
    ```
5.  Create a `.env` file in the `/backend` directory and add your credentials:
    ```env
    GOOGLE_API_KEY="your_gemini_api_key_here"
    
    # Update this to your MS SQL Server connection string
    DATABASE_URL="mssql+pyodbc://USER:PASSWORD@SERVER/DB_NAME?driver=ODBC+Driver+17+for+SQL+Server&trusted_connection=yes"
    ```
6.  Run the FastAPI server:
    ```sh
    uvicorn main:app --reload
    ```
    The server will start, automatically create all database tables, and populate the `admin` user.

### 2. Frontend Setup
1.  Open the `/frontend` project folder in your IDE (e.g., VS Code with the Java Extension Pack, or IntelliJ IDEA).
2.  Ensure your IDE is configured with the Java 17+ SDK and the JavaFX SDK.
3.  Run the `tdtu.dang.jssp.MainApp.java` file.
4.  The application will launch and automatically log in as the default `admin` user.

---

## 💬 Example Commands

* "Solve the current schedule."
* "What is the current makespan?"
* "Add a new job 'Component Gamma' that needs 'Milling' for 3 hours and then 'Drilling' for 5 hours."
* "Change the quantity of the 'Milling' machine group to 4."
* "What would happen to the schedule if job 'J001' had a priority of 5?"
* "Okay, make that change real."
* "Set the priority for job 'J002' to be the highest."