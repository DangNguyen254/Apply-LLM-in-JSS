package tdtu.dang.jssp.controllers;

import javafx.fxml.FXML;
import javafx.scene.control.*;
import javafx.scene.layout.AnchorPane;
import tdtu.dang.jssp.models.*;
import tdtu.dang.jssp.services.ApiClient;
import tdtu.dang.jssp.views.GanttChart;

import java.io.IOException;
import java.util.List;
import java.util.Map;

public class MainViewController {

    @FXML private TreeView<String> jobTreeView;
    @FXML private TextArea machineDisplayArea;
    @FXML private TextArea resultDisplayArea;
    @FXML private AnchorPane ganttChartPane;
    @FXML private Button submitButton;
    @FXML private Button solveButton;
    @FXML private Button resetButton;
    @FXML private TextArea promptInput;
    @FXML private TextArea statusDisplayArea;

    private GanttChart ganttChart;
    private final ApiClient apiClient = new ApiClient();
    private final String problemId = "problem_1"; // Default problem ID

    @FXML
    public void initialize() {
        ganttChart = new GanttChart();
        AnchorPane.setTopAnchor(ganttChart, 0.0);
        AnchorPane.setBottomAnchor(ganttChart, 0.0);
        AnchorPane.setLeftAnchor(ganttChart, 0.0);
        AnchorPane.setRightAnchor(ganttChart, 0.0);
        ganttChartPane.getChildren().add(ganttChart);

        // Load initial data when the application starts
        refreshAllData();
    }

    // Central method to refresh data displays
    private void refreshAllData() {
        try {
            List<Job> jobs = apiClient.getJobs(problemId);
            List<Machine> machines = apiClient.getMachines(problemId);
            updateJobTreeView(jobs);
            updateMachineDisplay(machines);
        } catch (IOException | InterruptedException e) {
            statusDisplayArea.appendText("Error: Could not load initial problem data.\n");
            e.printStackTrace();
        }
    }

    // Method to populate the TreeView with job data
    private void updateJobTreeView(List<Job> jobs) {
        TreeItem<String> rootItem = new TreeItem<>("Jobs");
        rootItem.setExpanded(true);

        if (jobs != null) {
            for (Job job : jobs) {
                String jobLabel = String.format("%s: %s (Priority: %d)", job.getId(), job.getName(), job.getPriority());
                TreeItem<String> jobItem = new TreeItem<>(jobLabel);
                if (job.getOpList() != null) {
                    for (Operation op : job.getOpList()) {
                        TreeItem<String> opItem = new TreeItem<>(
                                String.format("%s: Machine %s, Time %d", op.getId(), op.getMachineId(), op.getProcessingTime())
                        );
                        jobItem.getChildren().add(opItem);
                    }
                }
                rootItem.getChildren().add(jobItem);
            }
        }
        jobTreeView.setRoot(rootItem);
    }

    // Method to populate the TextArea with machine data
    private void updateMachineDisplay(List<Machine> machines) {
        StringBuilder sb = new StringBuilder();
        for (Machine machine : machines) {
            sb.append(String.format("ID: %s, Name: %s, Available: %b\n",
                    machine.getId(), machine.getName(), machine.isAvailability()));
        }
        machineDisplayArea.setText(sb.toString());
    }
    @FXML
    private void handlePromptKeyPress(javafx.scene.input.KeyEvent event) {
        // Submit on Enter, but allow Shift+Enter for new lines
        if (event.getCode() == javafx.scene.input.KeyCode.ENTER && !event.isShiftDown()) {
            event.consume(); // Prevents a newline from being added to the text area
            handleSubmitButton(); // Trigger the submit action
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

        statusDisplayArea.appendText("Interpreting command...\n");
        try {
            LLMResponse llmResponse = apiClient.interpretCommand(command, this.problemId);
            statusDisplayArea.appendText(llmResponse.getExplanation()+"\n");

            String action = llmResponse.getAction();
            // if ("add_job".equals(action) || "remove_job".equals(action) || "adjust_job".equals(action) || "modify_job".equals(action)
            // || "add_machine".equals(action) || "modify_machine".equals(action)) {
            //     refreshAllData(); // Refresh the job/machine lists
            // }
            if("solve".equals(action)){
                statusDisplayArea.appendText("Solving problem by prompt.\n");
                handleSolveButton();
            }
            else{
                statusDisplayArea.appendText("Refreshing data\n");
                refreshAllData();
            }
        } catch (IOException | InterruptedException e) {
            e.printStackTrace();
            statusDisplayArea.setText("Error: " + e.getMessage());
        }
    }

    @FXML
    private void handleSolveButton() {
        try {
            statusDisplayArea.appendText("Solving problem: " + problemId + "\n");
            Schedule schedule = apiClient.solveProblem(problemId);
            List<Job> jobs = apiClient.getJobs(problemId);
            List<Machine> machines = apiClient.getMachines(problemId);

            statusDisplayArea.appendText("Solution found! Makespan: " + schedule.getMakespan() + "\n");
            ganttChart.displaySchedule(schedule, jobs, machines);
            
            // Build a detailed result string
            StringBuilder resultText = new StringBuilder();
            resultText.append(String.format("Makespan: %d\n", schedule.getMakespan()));
            resultText.append(String.format("Average Job Flow Time: %.2f\n\n", schedule.getAverageFlowTime()));
            resultText.append("Machine Utilization:\n");
            if (schedule.getMachineUtilization() != null) {
                for (Map.Entry<String, Double> entry : schedule.getMachineUtilization().entrySet()) {
                    resultText.append(String.format("- %s: %.2f%%\n", entry.getKey(), entry.getValue() * 100));
                }
            }
            resultDisplayArea.appendText(resultText.toString());

        } catch (IOException | InterruptedException e) {
            e.printStackTrace();
            statusDisplayArea.appendText("Error: " + e.getMessage() + "\n");
        }
    }

    @FXML
    private void handleResetButton() {
        try {
            statusDisplayArea.appendText("Resetting problem state...\n");
            apiClient.resetProblem(problemId);
            ganttChart.clear();
            resultDisplayArea.clear();
            promptInput.clear();
            refreshAllData();
            statusDisplayArea.appendText("Problem has been reset to its original state.\n");
        } catch (IOException | InterruptedException e) {
            e.printStackTrace();
            statusDisplayArea.appendText("Error: Failed to reset problem state.\n");
        }
    }
}