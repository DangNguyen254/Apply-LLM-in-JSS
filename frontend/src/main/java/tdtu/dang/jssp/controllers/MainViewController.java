package tdtu.dang.jssp.controllers;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import tdtu.dang.jssp.models.*;
import tdtu.dang.jssp.views.GanttChart;
import tdtu.dang.jssp.services.ApiClient;

import javafx.fxml.FXML;
import javafx.scene.control.Button;
import javafx.scene.control.TextArea;
import javafx.scene.layout.AnchorPane;
import tdtu.dang.jssp.models.Schedule;
import tdtu.dang.jssp.models.ScheduledOperation;


public class MainViewController {
    // @FXML private TextArea jobDisplayArea;
    @FXML private javafx.scene.control.TreeView<String> jobTreeView;
    @FXML private TextArea machineDisplayArea;
    @FXML private TextArea resultDisplayArea;

    @FXML private AnchorPane ganttChartPane;

    @FXML private Button submitButton;
    @FXML private Button solveButton;
    @FXML private Button resetButton;

    @FXML private TextArea promptInput;
    @FXML private TextArea statusDisplayArea;

    private GanttChart ganttChart;

    @FXML
    public void initialize(){
        System.out.println("Initialized !");

        ganttChart = new GanttChart();
        AnchorPane.setTopAnchor(ganttChart, 0.0);
        AnchorPane.setBottomAnchor(ganttChart, 0.0);
        AnchorPane.setLeftAnchor(ganttChart, 0.0);
        AnchorPane.setRightAnchor(ganttChart, 0.0);
        ganttChartPane.getChildren().add(ganttChart);
    }

    @FXML
    private void handleSubmitButton(){
        String command = promptInput.getText();
        statusDisplayArea.setText("Command submitted: " + command);
    }

    @FXML
    private void handleSolveButton() {
        // You would create your ApiClient instance here or have it as a class member
        ApiClient apiClient = new ApiClient();
        String problemId = "problem_1"; // Get from a UI element later

        try {
            statusDisplayArea.setText("Solving problem: " + problemId + "...");
            
            // Make the API call
            Schedule schedule = apiClient.solveProblem(problemId);

            // If successful, update the UI
            statusDisplayArea.setText("Solution found! Makespan: " + schedule.getMakespan());
            ganttChart.displaySchedule(schedule);

        } catch (IOException | InterruptedException e) {
            // This block runs if either exception occurs

            // 1. Log the full error for debugging purposes
            e.printStackTrace();

            // 2. Show a friendly error message to the user in the UI
            statusDisplayArea.setText("Error: Failed to get schedule. Is the backend server running?");
        }
    }

    @FXML
    private void handleResetButton(){
        statusDisplayArea.setText("Reset button clicked! Clearing the view.");
    }
}
