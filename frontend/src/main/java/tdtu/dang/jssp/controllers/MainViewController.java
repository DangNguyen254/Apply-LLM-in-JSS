package tdtu.dang.jssp.controllers;

import javafx.application.Platform;
import javafx.fxml.FXML;
import javafx.scene.control.*;
import javafx.scene.input.KeyCode;
import javafx.scene.input.KeyEvent;
import javafx.scene.layout.AnchorPane;
import javafx.scene.layout.VBox;
import javafx.scene.layout.HBox;
import javafx.stage.FileChooser;
import tdtu.dang.jssp.models.*;
import tdtu.dang.jssp.services.ApiClient;
import tdtu.dang.jssp.views.GanttChart;
import com.fasterxml.jackson.databind.ObjectMapper; 
import com.fasterxml.jackson.databind.SerializationFeature;

import java.io.File;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

public class MainViewController {

    @FXML private TreeView<String> jobTreeView;
    @FXML private TextArea machineDisplayArea;
    @FXML private TextArea resultDisplayArea;
    @FXML private AnchorPane ganttChartPane;
    @FXML private Button submitButton;
    @FXML private Button solveButton;
    @FXML private Button exportButton;
    @FXML private Button resetButton;
    @FXML private TextArea promptInput;
    @FXML private TextField jobSearchField; 
    @FXML private VBox kpiBox;              
    @FXML private Slider timeScaleSlider; 
    @FXML private VBox conversationContainer; 
    @FXML private ScrollPane conversationScroll; 

    private GanttChart ganttChart;
    private final ApiClient apiClient = new ApiClient();
    private List<Map<String, Object>> conversationHistory;
    
    // This now caches the *last displayed* schedule, used for zooming
    private Schedule currentSchedule; 
    
    // Cached data for filtering and KPI rendering
    private List<Job> cachedJobs = new ArrayList<>();
    private List<MachineGroup> cachedMachineGroups = new ArrayList<>();
    
    private final ObjectMapper objectMapper = new ObjectMapper();

    @FXML
    public void initialize() {
        ganttChart = new GanttChart();
        AnchorPane.setTopAnchor(ganttChart, 0.0);
        AnchorPane.setBottomAnchor(ganttChart, 0.0);
        AnchorPane.setLeftAnchor(ganttChart, 0.0);
        AnchorPane.setRightAnchor(ganttChart, 0.0);
        ganttChartPane.getChildren().add(ganttChart);

        this.conversationHistory = new ArrayList<>();
        this.objectMapper.enable(SerializationFeature.INDENT_OUTPUT);
        exportButton.setDisable(true); 

        promptInput.addEventFilter(KeyEvent.KEY_PRESSED, event -> {
            if (event.getCode() == KeyCode.TAB) {
                event.consume();
                submitButton.requestFocus();
            }
        });

        try {
            appendConversationEntry("System", "Authenticating with server...");
            String username = apiClient.login("admin", "admin123");
            appendConversationEntry("System", "Login successful. Welcome, " + username + ".");
            appendConversationEntry("System", "Loading Live Data scenario...");
            refreshAllData();
            appendConversationEntry("System", "Data loaded.");
        } catch (Exception e) {
            appendConversationEntry("Error", "Login failed: " + e.getMessage());
            promptInput.setDisable(true);
            submitButton.setDisable(true);
            solveButton.setDisable(true);
            resetButton.setDisable(true);
            exportButton.setDisable(true);
        }
        
        Platform.runLater(() -> promptInput.requestFocus());

        if (resetButton != null) {
            resetButton.setVisible(false);
            resetButton.setManaged(false);
        }

        if (conversationContainer != null) {
            conversationContainer.getChildren().clear();
        }

        if (timeScaleSlider != null) {
            timeScaleSlider.valueProperty().addListener((obs, oldV, newV) -> {
                ganttChart.setTimeScale(newV.doubleValue());
                if (currentSchedule != null) {
                    ganttChart.displaySchedule(currentSchedule, cachedJobs, cachedMachineGroups);
                }
            });
        }
    }

    private void refreshAllData() {
        try {
            // This call will now return Jobs with their Operation Lists
            cachedJobs = apiClient.getJobs(); 
            cachedMachineGroups = apiClient.getMachineGroups();
            
            // This will now correctly populate the TreeView
            updateJobTreeView(cachedJobs); 
            updateMachineGroupDisplay(cachedMachineGroups);
            
            ganttChart.clear();
            if (kpiBox != null) kpiBox.getChildren().clear();
            exportButton.setDisable(true);
            
            appendConversationEntry("System", "Loaded " + cachedJobs.size() + " jobs and " + cachedMachineGroups.size() + " machine groups.");
            
        } catch (IOException | InterruptedException e) {
            appendConversationEntry("Error", "Could not load problem data: " + e.getMessage());
            e.printStackTrace();
        }
    }

    // This method is now correct, thanks to the backend fix
    private void updateJobTreeView(List<Job> jobs) {
        TreeItem<String> rootItem = new TreeItem<>("Jobs (" + (jobs == null ? 0 : jobs.size()) + ")");
        rootItem.setExpanded(true);

        if (jobs != null) {
            for (Job job : jobs) {
                String jobLabel = String.format("%s: %s (Priority: %d)", job.getId(), job.getName(), job.getPriority());
                TreeItem<String> jobItem = new TreeItem<>(jobLabel);

                // This check will now succeed!
                if (job.getOpList() != null && !job.getOpList().isEmpty()) {
                    int seq = 1;
                    for (Operation op : job.getOpList()) {
                        String pred = (op.getPredecessors() == null || op.getPredecessors().isEmpty()) ? "-" : String.join(",", op.getPredecessors());
                        String label = String.format("Op %02d [%s] t=%d (pred: %s)", seq++, op.getMachineGroupId(), op.getProcessingTime(), pred);
                        TreeItem<String> opItem = new TreeItem<>(label);
                        jobItem.getChildren().add(opItem);
                    }
                } else {
                    TreeItem<String> noOpsItem = new TreeItem<>("(No operations)");
                    jobItem.getChildren().add(noOpsItem);
                }
                jobItem.setExpanded(true); 
                rootItem.getChildren().add(jobItem);
            }
        }
        jobTreeView.setRoot(rootItem);

        jobTreeView.setCellFactory(tv -> new TreeCell<>() {
            @Override
            protected void updateItem(String value, boolean empty) {
                super.updateItem(value, empty);
                getStyleClass().removeAll("tree-job-cell", "tree-op-cell", "tree-empty-cell");
                if (empty || value == null) {
                    setText(null);
                    setGraphic(null);
                } else {
                    setText(value);
                    if (value.startsWith("Op ")) {
                        getStyleClass().add("tree-op-cell");
                    } else if (value.startsWith("(")) {
                        getStyleClass().add("tree-empty-cell");
                    } else {
                        getStyleClass().add("tree-job-cell");
                    }
                }
            }
        });
    }

    private void updateMachineGroupDisplay(List<MachineGroup> machineGroups) {
        StringBuilder sb = new StringBuilder();
        for (MachineGroup group : machineGroups) {
            sb.append(String.format("Group ID: %s | Group Name: %s | Quantity: %d\n", group.getId(), group.getName(), group.getQuantity()));
        }
        machineDisplayArea.setText(sb.toString());
    }

    @FXML
    private void handlePromptKeyPress(KeyEvent event) {
        if (event.getCode() == KeyCode.ENTER && !event.isShiftDown()) {
            event.consume();
            handleSubmitButton();
        }
    }

    @FXML
    private void handleSubmitButton() {
        String command = promptInput.getText();
        if (command == null || command.trim().isEmpty()) {
            appendConversationEntry("Error", "Please enter a command.");
            return;
        }
        promptInput.clear();
        appendConversationUser(command);
        
        // This method now handles all logic
        runOrchestration(command);
    }

    @FXML
    private void handleSubmitButtonKeyPress(KeyEvent event) {
        if (event.getCode() == KeyCode.TAB) {
            event.consume();
            solveButton.requestFocus();
        }
    }

    @FXML
    private void handleSolveButton() {
        // REWRITTEN: This button now uses the same orchestrator
        appendConversationEntry("System", "Solving current active scenario...");
        
        // We use a clean, non-ambiguous command for the LLM
        runOrchestration("Solve the current schedule and get the new KPIs");
    }

    /**
     * NEW: Centralized function to run any command through the orchestrator.
     * This is called by both the "Submit" and "Solve" buttons.
     * @param command The text command to send to the LLM.
     */
    private void runOrchestration(String command) {
        try {
            OrchestratorResponse llmResponse = apiClient.interpretCommand(command, this.conversationHistory);
            this.conversationHistory = llmResponse.getHistory();
            appendConversationAssistant(llmResponse.getExplanation());
            
            appendConversationEntry("System", "Refreshing data lists...");
            refreshAllData(); // Refresh Job and Machine lists

            Schedule schedule = llmResponse.getSchedule();
            if (schedule != null) {
                // The orchestrator solved and returned a full schedule
                appendConversationEntry("System", "Orchestrator returned schedule; displaying...");
                
                // We use the *cached* jobs and machines for display
                // because we just called refreshAllData()
                displayScheduleResults(schedule, this.cachedJobs, this.cachedMachineGroups);
            }

        } catch (IOException | InterruptedException e) {
            e.printStackTrace();
            appendConversationEntry("Error", e.getMessage());
        }
    }


    private void displayScheduleResults(Schedule schedule, List<Job> jobs, List<MachineGroup> machineGroups) {
        // Cache the schedule for zooming and export
        this.currentSchedule = schedule; 
        
        // Enable the export button
        exportButton.setDisable(false);
        
        int schedOps = (schedule.getScheduledOperations()==null?0:schedule.getScheduledOperations().size());
        appendConversationEntry("System", "Schedule received: makespan=" + schedule.getMakespan() + ", operations=" + schedOps);
        
        if (schedOps == 0) {
            appendConversationEntry("Error", "Scheduled operations list is empty – cannot render Gantt chart.");
            ganttChart.clear();
        } else if (jobs==null || jobs.isEmpty()) {
            appendConversationEntry("Error", "Jobs list empty during schedule display – verify backend data.");
        } else if (machineGroups==null || machineGroups.isEmpty()) {
            appendConversationEntry("Error", "Machine groups empty during schedule display – verify backend data.");
        } else {
            ganttChart.displaySchedule(schedule, jobs, machineGroups);
            appendConversationEntry("System", "Gantt chart rendered.");
        }
        
        // Display KPIs in the "Result Details" text area
        StringBuilder resultText = new StringBuilder();
        resultText.append(String.format("Makespan: %d\n", schedule.getMakespan()));
        resultText.append(String.format("Average Job Flow Time: %.2f\n\n", schedule.getAverageFlowTime()));
        resultText.append("Machine Utilization:\n");
        if (schedule.getMachineUtilization() != null) {
            schedule.getMachineUtilization().entrySet().stream()
                .sorted(Map.Entry.comparingByKey())
                // Get the Double value and format it as a percentage string
                .forEach(entry -> resultText.append(String.format("- %s: %.2f%%\n", 
                                entry.getKey(), 
                                entry.getValue() * 100.0)));
        }
        resultDisplayArea.setText(resultText.toString());
        
        appendConversationEntry("System", "KPIs updated (makespan=" + schedule.getMakespan() + ", avg flow=" + String.format("%.2f", schedule.getAverageFlowTime()) + ").");

        // Render the compact KPI widgets (this was already correct)
        renderKpis(schedule);
    }

    // NEW: Live filter for Job tree
    @FXML
    private void handleJobSearchKey() {
        if (jobSearchField == null) return;
        String q = jobSearchField.getText();
        if (q == null || q.isBlank()) {
            updateJobTreeView(cachedJobs);
            return;
        }
        final String ql = q.toLowerCase();
        List<Job> filtered = new ArrayList<>();
        for (Job j : cachedJobs) {
            if ((j.getId() != null && j.getId().toLowerCase().contains(ql)) ||
                (j.getName() != null && j.getName().toLowerCase().contains(ql))) {
                filtered.add(j);
            }
        }
        updateJobTreeView(filtered);
    }

    // NEW: Render KPI widgets under left pane
    private void renderKpis(Schedule schedule) {
        if (kpiBox == null) return;
        kpiBox.getChildren().clear();
        if (schedule == null) return;

        Label mk = new Label("Makespan: " + schedule.getMakespan());
        mk.getStyleClass().add("kpi-label");

        Label flow = new Label(String.format("Avg Flow: %.2f", schedule.getAverageFlowTime()));
        flow.getStyleClass().add("kpi-label");

        VBox utilWrap = new VBox(4);
        utilWrap.getStyleClass().add("kpi-util-box");
        utilWrap.getChildren().add(new Label("Machine Utilization:"));

        if (schedule.getMachineUtilization() != null) {
            schedule.getMachineUtilization().entrySet().stream()
                    .sorted(Map.Entry.comparingByKey())
                    .forEach(e -> {
                        // We get the raw double value for the progress bar
                        double v = e.getValue() == null ? 0.0 : e.getValue();
                        ProgressBar bar = new ProgressBar(Math.max(0, Math.min(1, v)));
                        bar.setPrefWidth(140);
                        // And we get the pre-formatted string for the label
                        String utilString = String.format("%.2f%%", v * 100);
                        Label lab = new Label(e.getKey() + ": " + utilString);
                        lab.getStyleClass().add("util-label");
                        HBox row = new HBox(6, lab, bar);
                        row.getStyleClass().add("util-row");
                        utilWrap.getChildren().add(row);
                    });
        }
        kpiBox.getChildren().addAll(mk, flow, utilWrap);
    }

    @FXML
    private void handleSolveButtonKeyPress(KeyEvent event) {
        if (event.getCode() == KeyCode.TAB) {
            event.consume();
            resetButton.requestFocus();
        }
    }

    @FXML
    private void handleExportButton() {
        // REWRITTEN: This now fetches the *latest* schedule from the DB
        // for maximum data integrity.
        Schedule scheduleToExport;
        try {
            appendConversationEntry("System", "Fetching latest schedule from database for export...");
            scheduleToExport = apiClient.getLatestSchedule(); // NEW API CALL
            if (scheduleToExport == null) {
                appendConversationEntry("Error", "No schedule data found in database to export.");
                return;
            }
            appendConversationEntry("System", "Latest schedule (Makespan: " + scheduleToExport.getMakespan() + ") received.");

        } catch (Exception e) {
            appendConversationEntry("Error", "Could not fetch schedule from database: " + e.getMessage());
            return;
        }

        FileChooser fileChooser = new FileChooser();
        fileChooser.setTitle("Export Schedule");
        fileChooser.setInitialFileName("schedule_export.json");
        fileChooser.getExtensionFilters().addAll(
            new FileChooser.ExtensionFilter("JSON Files", "*.json"),
            new FileChooser.ExtensionFilter("CSV Files", "*.csv")
        );
        
        File file = fileChooser.showSaveDialog(exportButton.getScene().getWindow());

        if (file != null) {
            try {
                if (file.getName().toLowerCase().endsWith(".csv")) {
                    // Pass the newly fetched schedule to the CSV exporter
                    exportScheduleAsCsv(file, scheduleToExport);
                } else { 
                    // Write the newly fetched schedule to JSON
                    objectMapper.writeValue(file, scheduleToExport);
                }
                appendConversationEntry("System", "Schedule exported successfully to " + file.getAbsolutePath());
            } catch (IOException e) {
                appendConversationEntry("Error", "Error exporting schedule: " + e.getMessage());
                e.printStackTrace();
            }
        }
    }

    @FXML
    private void handleResetButton() {
        appendConversationEntry("System", "Resetting database to default...");
        
        try {
            apiClient.resetProblem();
            appendConversationEntry("System", "Database reset.");
            appendConversationEntry("System", "New session established.");
            
            this.conversationHistory.clear();
            ganttChart.clear();
            resultDisplayArea.clear();
            promptInput.clear();
            
            this.currentSchedule = null;
            exportButton.setDisable(true);
            
            refreshAllData();
            
        } catch (IOException | InterruptedException e) {
            appendConversationEntry("Error", "Reset failed: " + e.getMessage());
        }
    }

    @FXML
    private void handleResetButtonKeyPress(KeyEvent event) {
        if (event.getCode() == KeyCode.TAB) {
            event.consume();
            Platform.runLater(() -> {
                promptInput.requestFocus();
                promptInput.positionCaret(promptInput.getLength());
            });
        }
    }

    private void appendConversationEntry(String role, String content) {
        if (conversationContainer == null) return;
        String trimmed = content == null ? "" : content.trim();
        if (trimmed.isEmpty()) return;
        Label line = new Label(trimmed);
        line.setWrapText(true);
        line.getStyleClass().add("conv-entry");
        switch (role.toLowerCase()) {
            case "user" -> { line.getStyleClass().add("conv-user"); line.setText("> " + trimmed); }
            case "assistant" -> line.getStyleClass().add("conv-assistant");
            case "error" -> line.getStyleClass().add("conv-error");
            default -> line.getStyleClass().add("conv-system");
        }
        conversationContainer.getChildren().add(line);
        Platform.runLater(() -> {
            try {
                if (conversationScroll != null) {
                    conversationScroll.setVvalue(1.0);
                }
            } catch (Exception ignore) {}
        });
    }

    private void appendConversationUser(String content){ appendConversationEntry("User", content); }
    private void appendConversationAssistant(String content){ appendConversationEntry("Assistant", content); }

    // This method is now updated to take the schedule as an argument
    private void exportScheduleAsCsv(File file, Schedule schedule) throws IOException {
        if (schedule == null) return; // Guard clause
        StringBuilder sb = new StringBuilder();
        sb.append("job_id,operation_id,machine_instance_id,start_time,end_time,duration\n");
        for (ScheduledOperation op : schedule.getScheduledOperations()) {
            int duration = op.getEndTime() - op.getStartTime();
            sb.append(op.getJobId()).append(',')
              .append(op.getOperationId()).append(',')
              .append(op.getMachineInstanceId()).append(',')
              .append(op.getStartTime()).append(',')
              .append(op.getEndTime()).append(',')
              .append(duration).append('\n');
        }
        java.nio.file.Files.writeString(file.toPath(), sb.toString());
    }
}