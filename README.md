# Apply LLM in JSS (JSSP Studio)

An end-to-end workbench for Job Shop Scheduling Problems enhanced with an LLM assistant. The system lets you:
* Model jobs, operations, and machine groups.
* Issue natural language commands to modify or query the scenario.
* Solve the active scenario and visualize the schedule on a Gantt chart.
* Inspect KPIs (makespan, average flow time, machine utilization).
* Export generated schedules.

## Architecture Overview
Backend (Python / FastAPI) provides REST endpoints for authentication, data retrieval, solving, and LLM orchestration. Frontend (JavaFX) offers a rich desktop interface for interactive exploration and visualization.

## Frontend (JavaFX)
Path: `frontend/`

### Features
* Jobs tree (jobs → operations) with live filtering.
* Machine groups display.
* KPI widgets (makespan, average flow, utilization bars).
* Command input area with Enter vs Shift+Enter behavior.
* Conversation history list (user vs assistant messages).
* System log (raw status outputs).
* Scrollable Gantt chart visualization.
* Export menu (JSON / CSV) for latest schedule.
* Hidden developer reset button (id: `resetButton`).

### Layout Summary
BorderPane:
* Top: Action bar (`Submit`, `Solve`, `Export`).
* Left: Titled panes (Jobs, Machines, KPIs).
* Center: Gantt chart + Result metrics pane.
* Right: Command, Conversation, Log panes.
* Bottom: Status bar with summary label.

### Run Instructions
Prerequisites: JDK + Maven, backend running at `http://127.0.0.1:8000`.
```powershell
# From repo root
mvn -f frontend/pom.xml clean javafx:run
```
Auto login uses `admin/admin123` (seeded user) for development.

### Export Details
* JSON: full `Schedule` object (includes operations, utilization, KPIs).
* CSV: flattened operations: `job_id,operation_id,machine_instance_id,start,end,duration`.

### Keyboard & Interaction
* Enter: submit command
* Shift+Enter: newline in command box
* Jobs filter: immediate tree refresh

### Styling
Custom dark theme (`style.css`) with semantic classes: `.sidebar`, `.assistant-panel`, `.gantt-chart-pane`, `.kpi-container`, `.status-bar`.

### Developer Reset
Toggle visibility of `resetButton` in `MainView.fxml` for reseeding database quickly.

### Suggested Next Enhancements
1. Inline edit context menu for jobs/operations.
2. Light theme toggle.
3. Persistent local conversation history.
4. Manual drag adjust layer on Gantt for hypothetical changes.
5. Performance profiling overlay (operation slack, critical path highlight).

## Backend (Python / FastAPI)
Path: `backend/` – Provides endpoints under `/api/scheduling` for login, jobs, machine groups, solving, interpreting commands (LLM orchestration), and resetting data.

### Running Backend (Example)
Create venv & install requirements:
```powershell
cd backend
python -m venv .venv
./.venv/Scripts/Activate.ps1
pip install -r requirements.txt
python run.py
```

## License
TBD (add your chosen license).

