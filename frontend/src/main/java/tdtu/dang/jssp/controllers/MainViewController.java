package tdtu.dang.jssp.controllers;
import java.util.ArrayList;
import java.util.List;
import tdtu.dang.jssp.models.*;
import tdtu.dang.jssp.views.GanttChart;

import javafx.fxml.FXML;
import javafx.scene.control.Button;
import javafx.scene.control.TextArea;
import javafx.scene.layout.AnchorPane;
import tdtu.dang.jssp.models.Schedule;
import tdtu.dang.jssp.models.ScheduledOperation;


public class MainViewController {
    @FXML private TextArea jobDisplayArea;
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

    private void handleSolveButton(){
        statusDisplayArea.setText("Solve button clicked! Calling the solver...");
        ganttChart.displaySchedule(createMockSchedule());
    }

    @FXML
    private void handleResetButton(){
        statusDisplayArea.setText("Reset button clicked! Clearing the view.");
    }

    private Schedule createMockSchedule() {
        List<ScheduledOperation> ops = new ArrayList<>();

        // Manually create a few scheduled operations
        ops.add(new ScheduledOperation("J001", "O001", "M001", 0, 3));
        ops.add(new ScheduledOperation("J002", "O004", "M001", 3, 5));
        ops.add(new ScheduledOperation("J001", "O002", "M002", 3, 5));
        ops.add(new ScheduledOperation("J003", "O007", "M002", 5, 9));
        ops.add(new ScheduledOperation("J001", "O003", "M003", 5, 7));
        ops.add(new ScheduledOperation("J002", "O005", "M003", 7, 8));

        // Create the final schedule object with a makespan
        return new Schedule(9, ops);
    }
}
