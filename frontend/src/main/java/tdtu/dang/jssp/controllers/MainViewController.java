package tdtu.dang.jssp.controllers;

import javafx.application.Platform;
import javafx.fxml.FXML;
import javafx.scene.control.*;
import javafx.scene.input.KeyCode;
import javafx.scene.input.KeyEvent;
import javafx.scene.layout.AnchorPane;
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
    @FXML private TextArea statusDisplayArea;

    private GanttChart ganttChart;
    private final ApiClient apiClient = new ApiClient();

    // Stores the conversation state
    private List<Map<String, Object>> conversationHistory;

    // Store the last successful schedule for export
    private Schedule currentSchedule;
    
    // ObjectMapper for writing JSON
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

        // Configure the ObjectMapper
        this.objectMapper.enable(SerializationFeature.INDENT_OUTPUT);
        
        // Disable export button by default
        exportButton.setDisable(true);

        promptInput.addEventFilter(KeyEvent.KEY_PRESSED, event -> {
            if (event.getCode() == KeyCode.TAB) {
                // Consume the event to prevent the TextArea from inserting a '\t' character.
                event.consume();
                // Manually move focus to the next control.
                submitButton.requestFocus();
            }
        });

        // --- NEW LOGIN AND DATA LOADING ---
        // We must log in before we can do anything else.
        // For a "real" app, you would show a login screen.
        // For this enterprise project, we'll auto-login as the default 'admin' user.
        try {
            statusDisplayArea.setText("Authenticating with server...\n");
            String username = apiClient.login("admin", "admin123");
            statusDisplayArea.appendText("Login successful. Welcome, " + username + ".\n");
            statusDisplayArea.appendText("Loading 'Live Data' scenario...\n");
            
            // Load initial data *after* logging in
            refreshAllData();
            statusDisplayArea.appendText("Data loaded.\n");

        } catch (Exception e) {
            statusDisplayArea.appendText("FATAL ERROR: Could not log in or load data.\n");
            statusDisplayArea.appendText(e.getMessage() + "\n");
            // Disable controls if login fails
            promptInput.setDisable(true);
            submitButton.setDisable(true);
            solveButton.setDisable(true);
            resetButton.setDisable(true);
            exportButton.setDisable(true);
        }
        
        // Request focus on the prompt area
        Platform.runLater(() -> promptInput.requestFocus());
    }

    private void refreshAllData() {
        try {
            // All API calls no longer need problemId
            List<Job> jobs = apiClient.getJobs();
            List<MachineGroup> machineGroups = apiClient.getMachineGroups();
            updateJobTreeView(jobs);
            updateMachineGroupDisplay(machineGroups);
        } catch (IOException | InterruptedException e) {
            statusDisplayArea.appendText("Error: Could not load problem data.\n");
            e.printStackTrace();
        }
    }

    // This method is unchanged
    private void updateJobTreeView(List<Job> jobs) {
        TreeItem<String> rootItem = new TreeItem<>("Jobs");
        rootItem.setExpanded(true);

        if (jobs != null) {
            for (Job job : jobs) {
                String jobLabel = String.format("%s: %s (Priority: %d)", job.getId(), job.getName(), job.getPriority());
                TreeItem<String> jobItem = new TreeItem<>(jobLabel);

                // FIX: Check if the list is not null AND not empty
                if (job.getOpList() != null && !job.getOpList().isEmpty()) {
                    for (Operation op : job.getOpList()) {
                        TreeItem<String> opItem = new TreeItem<>(
                                String.format("%s: Group %s, Time %d", op.getId(), op.getMachineGroupId(), op.getProcessingTime())
                        );
                        jobItem.getChildren().add(opItem);
                    }
                } else {
                    // Add a placeholder if there are no operations
                    TreeItem<String> noOpsItem = new TreeItem<>("No operations defined");
                    jobItem.getChildren().add(noOpsItem);
                }
                rootItem.getChildren().add(jobItem);
            }
        }
        jobTreeView.setRoot(rootItem);
    }

    // This method is unchanged
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
            statusDisplayArea.appendText("Please enter a command.\n");
            return;
        }
        promptInput.clear();
        statusDisplayArea.appendText("\n> " + command + "\n");
        
        try {
            // Pass the current history to the API client
            // No problemId is needed
            OrchestratorResponse llmResponse = apiClient.interpretCommand(command, this.conversationHistory);

            // Update the local history with the new history from the response
            this.conversationHistory = llmResponse.getHistory();

            // Display the final text explanation
            statusDisplayArea.appendText(llmResponse.getExplanation() + "\n");
            
            // Refresh the Job and Machine lists to reflect any changes
            statusDisplayArea.appendText("Refreshing data lists...\n");
            refreshAllData();

            // Check if the response included a schedule
            Schedule schedule = llmResponse.getSchedule();
            if (schedule != null) {
                statusDisplayArea.appendText("Orchestrator solved and returned a new schedule. Displaying...\n");
                // We need the *current* jobs and machines to display the chart correctly
                // No problemId is needed
                List<Job> currentJobs = apiClient.getJobs();
                List<MachineGroup> currentMachineGroups = apiClient.getMachineGroups();
                // Call the existing display helper method
                displayScheduleResults(schedule, currentJobs, currentMachineGroups);
            }

        } catch (IOException | InterruptedException e) {
            e.printStackTrace();
            statusDisplayArea.appendText("Error: " + e.getMessage() + "\n");
        }
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
        try {
            statusDisplayArea.appendText("Solving current active scenario...\n");
            // No problemId is needed
            Schedule schedule = apiClient.solveProblem();
            List<Job> jobs = apiClient.getJobs();
            List<MachineGroup> machineGroups = apiClient.getMachineGroups();
            
            if (schedule == null) {
                statusDisplayArea.appendText("Solver failed to find a solution for the current state.\n");
                ganttChart.clear();
                resultDisplayArea.clear();
                this.currentSchedule = null;
                exportButton.setDisable(true);
                return;
            }

            statusDisplayArea.appendText("Solution found! Makespan: " + schedule.getMakespan() + "\n");
            
            // Display the schedule results (Gantt Chart and KPIs)
            displayScheduleResults(schedule, jobs, machineGroups);

        } catch (IOException | InterruptedException e) {
            e.printStackTrace();
            statusDisplayArea.appendText("Error: " + e.getMessage() + "\n");
        }
    }

    // This method is unchanged
    private void displayScheduleResults(Schedule schedule, List<Job> jobs, List<MachineGroup> machineGroups) {
        // NEW: Save the schedule for export
        this.currentSchedule = schedule;
        
        // NEW: Enable the export button
        exportButton.setDisable(false);
        
        // Draw Gantt Chart
        ganttChart.displaySchedule(schedule, jobs, machineGroups);
        
        // Display KPIs (Unchanged)
        StringBuilder resultText = new StringBuilder();
        resultText.append(String.format("Makespan: %d\n", schedule.getMakespan()));
        resultText.append(String.format("Average Job Flow Time: %.2f\n\n", schedule.getAverageFlowTime()));
        resultText.append("Machine Utilization:\n");
        if (schedule.getMachineUtilization() != null) {
            schedule.getMachineUtilization().entrySet().stream()
                .sorted(Map.Entry.comparingByKey())
                .forEach(entry -> resultText.append(String.format("- %s: %s\n", entry.getKey(), entry.getValue()))); // Use %s for pre-formatted string
        }
        resultDisplayArea.setText(resultText.toString());
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
        if (currentSchedule == null) {
            statusDisplayArea.appendText("Error: No schedule data to export.\n");
            return;
        }

        FileChooser fileChooser = new FileChooser();
        fileChooser.setTitle("Save Schedule as JSON");
        fileChooser.setInitialFileName("schedule_export.json");
        fileChooser.getExtensionFilters().add(
            new FileChooser.ExtensionFilter("JSON Files", "*.json")
        );
        
        // Get the main window (Stage)
        File file = fileChooser.showSaveDialog(exportButton.getScene().getWindow());

        if (file != null) {
            try {
                // Write the Java Schedule object directly to the file as JSON
                objectMapper.writeValue(file, currentSchedule);
                statusDisplayArea.appendText("Schedule exported successfully to " + file.getAbsolutePath() + "\n");
            } catch (IOException e) {
                statusDisplayArea.appendText("Error exporting schedule: " + e.getMessage() + "\n");
                e.printStackTrace();
            }
        }
    }

    @FXML
    private void handleResetButton() {
        statusDisplayArea.appendText("Resetting database to default...\n");
        
        try {
            String newSessionToken = apiClient.resetProblem();
            statusDisplayArea.appendText("Database has been reset.\n");
            statusDisplayArea.appendText("New session established.\n");
            
            this.conversationHistory.clear();
            ganttChart.clear();
            resultDisplayArea.clear();
            promptInput.clear();
            
            this.currentSchedule = null;
            exportButton.setDisable(true);
            
            refreshAllData();
            
        } catch (IOException | InterruptedException e) {
            statusDisplayArea.appendText("FATAL: Could not reset database.\n");
            statusDisplayArea.appendText(e.getMessage() + "\n");
        }
    }

    @FXML
    private void handleResetButtonKeyPress(KeyEvent event) {
        if (event.getCode() == KeyCode.TAB) {
            event.consume();
            
            // Use Platform.runLater to decouple the focus change from the event cycle.
            Platform.runLater(() -> {
                promptInput.requestFocus();
                promptInput.positionCaret(promptInput.getLength());
            });
        }
    }
}