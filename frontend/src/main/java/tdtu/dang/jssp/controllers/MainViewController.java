package tdtu.dang.jssp.controllers;

import javafx.application.Platform;
import javafx.fxml.FXML;
import javafx.scene.control.*;
import javafx.scene.input.KeyCode;
import javafx.scene.input.KeyEvent;
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
    private final String problemId = "problem_1";

    @FXML
    public void initialize() {
        ganttChart = new GanttChart();
        AnchorPane.setTopAnchor(ganttChart, 0.0);
        AnchorPane.setBottomAnchor(ganttChart, 0.0);
        AnchorPane.setLeftAnchor(ganttChart, 0.0);
        AnchorPane.setRightAnchor(ganttChart, 0.0);
        ganttChartPane.getChildren().add(ganttChart);

        // Add an EventFilter to the promptInput to handle Tab key presses.
        // This is more reliable than an EventHandler for overriding default behavior.
        promptInput.addEventFilter(KeyEvent.KEY_PRESSED, event -> {
            if (event.getCode() == KeyCode.TAB) {
                // Consume the event to prevent the TextArea from inserting a '\t' character.
                event.consume();
                // Manually move focus to the next control.
                submitButton.requestFocus();
            }
        });

        refreshAllData();
        
        // Request focus on the prompt area after the UI is fully loaded.
        Platform.runLater(() -> promptInput.requestFocus());
    }

    private void refreshAllData() {
        try {
            List<Job> jobs = apiClient.getJobs(problemId);
            List<MachineGroup> machineGroups = apiClient.getMachineGroups(problemId);
            updateJobTreeView(jobs);
            updateMachineGroupDisplay(machineGroups);
        } catch (IOException | InterruptedException e) {
            statusDisplayArea.appendText("Error: Could not load initial problem data.\n");
            e.printStackTrace();
        }
    }

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
                                String.format("%s: Group %s, Time %d", op.getId(), op.getMachineGroupId(), op.getProcessingTime())
                        );
                        jobItem.getChildren().add(opItem);
                    }
                }
                rootItem.getChildren().add(jobItem);
            }
        }
        jobTreeView.setRoot(rootItem);
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
        // This handler now only needs to worry about the Enter key for submission.
        // The Tab key logic is handled by the EventFilter in the initialize() method.
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
            LLMResponse llmResponse = apiClient.interpretCommand(command, this.problemId);
            statusDisplayArea.appendText(llmResponse.getExplanation() + "\n");

            String action = llmResponse.getAction();
            
            if ("solve".equals(action)) {
                statusDisplayArea.appendText("Solving problem\n");
                handleSolveButton();
            } else if (!"error".equals(action)) {
                statusDisplayArea.appendText("Refreshing data...\n");
                refreshAllData();
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
            statusDisplayArea.appendText("Solving problem: " + problemId + "\n");
            Schedule schedule = apiClient.solveProblem(problemId);
            List<Job> jobs = apiClient.getJobs(problemId);
            List<MachineGroup> machineGroups = apiClient.getMachineGroups(problemId);
            
            statusDisplayArea.appendText("Solution found! Makespan: " + schedule.getMakespan() + "\n");
            ganttChart.displaySchedule(schedule, jobs, machineGroups);
            
            StringBuilder resultText = new StringBuilder();
            resultText.append(String.format("Makespan: %d\n", schedule.getMakespan()));
            resultText.append(String.format("Average Job Flow Time: %.2f\n\n", schedule.getAverageFlowTime()));
            resultText.append("Machine Utilization:\n");
            if (schedule.getMachineUtilization() != null) {
                schedule.getMachineUtilization().entrySet().stream()
                    .sorted(Map.Entry.comparingByKey())
                    .forEach(entry -> resultText.append(String.format("- %s: %.2f%%\n", entry.getKey(), entry.getValue() * 100)));
            }
            resultDisplayArea.setText(resultText.toString());

        } catch (IOException | InterruptedException e) {
            e.printStackTrace();
            statusDisplayArea.appendText("Error: " + e.getMessage() + "\n");
        }
    }

    @FXML
    private void handleSolveButtonKeyPress(KeyEvent event) {
        if (event.getCode() == KeyCode.TAB) {
            event.consume();
            resetButton.requestFocus();
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