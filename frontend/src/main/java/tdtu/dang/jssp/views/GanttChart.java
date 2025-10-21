package tdtu.dang.jssp.views;

import javafx.geometry.Insets;
import javafx.geometry.Pos;
import javafx.scene.control.Label;
import javafx.scene.control.Tooltip;
import javafx.scene.layout.Pane;
import javafx.scene.layout.StackPane;
import javafx.scene.layout.VBox;
import javafx.scene.paint.Color;
import javafx.scene.shape.Rectangle;
import javafx.scene.text.Font;
import javafx.scene.text.FontWeight;
import javafx.scene.text.Text;
import tdtu.dang.jssp.models.*;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class GanttChart extends Pane {

    // --- Chart Layout Constants ---
    private static final double TIME_SCALE = 50.0;
    private static final double ROW_HEIGHT = 70.0;
    private static final double HEADER_WIDTH = 120.0; // Increased for potentially longer machine names
    private static final double PADDING = 25.0;
    private static final double TIME_AXIS_HEIGHT = 30.0;
    private static final double RECT_V_PADDING = 8.0;

    // --- Color Management ---
    private final Map<String, Color> jobColors = new HashMap<>();
    private final List<Color> colorPalette = List.of(
            Color.web("#8ecae6"), Color.web("#219ebc"), Color.web("#023047"),
            Color.web("#ffb703"), Color.web("#fd9e02"), Color.web("#fb8500"),
            Color.web("#e63946"), Color.web("#a8dadc"), Color.web("#457b9d")
    );
    private int colorIndex = 0;

    /**
     * Renders the Gantt chart. Rows are now based on Machines.
     * All operations for the same Job will have the same color.
     */
    public void displaySchedule(Schedule schedule, List<Job> jobs, List<Machine> machines) {
        clear();
        if (schedule == null || schedule.getScheduledOperations().isEmpty()) {
            return;
        }

        // --- Y-Axis: Use Machine IDs to define rows ---
        List<String> machineIds = schedule.getScheduledOperations().stream()
                .map(ScheduledOperation::getMachineId)
                .distinct()
                .sorted()
                .toList();

        // --- Draw Chart Components ---
        drawTimeAxis(schedule.getMakespan());
        drawMachineLabels(machineIds, machines);
        drawOperationBlocks(schedule.getScheduledOperations(), machineIds);
    }

    /**
     * Draws the individual operation blocks onto the chart.
     */
    private void drawOperationBlocks(List<ScheduledOperation> operations, List<String> machineIds) {
        for (ScheduledOperation op : operations) {
            // --- Coloring based on Job ID ---
            Color jobColor = jobColors.computeIfAbsent(op.getJobId(), k -> getNextColor());

            // --- Calculate Position and Size ---
            double x = HEADER_WIDTH + PADDING + (op.getStartTime() * TIME_SCALE);
            double y = PADDING + TIME_AXIS_HEIGHT + (machineIds.indexOf(op.getMachineId()) * ROW_HEIGHT);
            double width = (op.getEndTime() - op.getStartTime()) * TIME_SCALE;

            if (width < 1.0) width = 1.0;

            // --- Create Visual Components ---
            StackPane taskContainer = new StackPane();
            taskContainer.setLayoutX(x);
            taskContainer.setLayoutY(y);

            Rectangle rect = new Rectangle(width, ROW_HEIGHT - (RECT_V_PADDING * 2));
            rect.setFill(jobColor.deriveColor(0, 1.2, 1, 0.7));
            rect.setStroke(jobColor.darker());
            rect.setArcWidth(12);
            rect.setArcHeight(12);
            
            // --- Create Text Labels for Inside the Block ---
            // Display Job ID and Operation ID, since the row already indicates the machine.
            Label jobIdLabel = new Label("Job: " + op.getJobId());
            jobIdLabel.setFont(Font.font("System", FontWeight.BOLD, 11));
            jobIdLabel.setTextFill(Color.WHITE);

            Label opIdLabel = new Label("Op: " + op.getOperationId());
            opIdLabel.setFont(Font.font("System", FontWeight.NORMAL, 10));
            opIdLabel.setTextFill(Color.WHITE.deriveColor(0, 1, 1, 0.9));

            VBox labelBox = new VBox(jobIdLabel, opIdLabel);
            labelBox.setAlignment(Pos.CENTER_LEFT);
            labelBox.setPadding(new Insets(0, 0, 0, 8));
            labelBox.setSpacing(2);

            // --- Assemble the Block ---
            taskContainer.getChildren().add(rect);

            // --- Text Fitting Logic ---
            Text tempText = new Text("Job: " + op.getJobId());
            tempText.setFont(Font.font("System", FontWeight.BOLD, 11));
            if (tempText.getLayoutBounds().getWidth() < width - 16) {
                taskContainer.getChildren().add(labelBox);
            }

            // --- Tooltip for Detailed Info on Hover ---
            String tooltipText = String.format(
                "Job ID: %s\nOperation ID: %s\nMachine ID: %s\n\nStart Time: %d\nEnd Time: %d\nDuration: %d",
                op.getJobId(), op.getOperationId(), op.getMachineId(),
                op.getStartTime(), op.getEndTime(), (op.getEndTime() - op.getStartTime())
            );
            Tooltip tooltip = new Tooltip(tooltipText);
            tooltip.setFont(Font.font("System", 14));
            Tooltip.install(taskContainer, tooltip);

            getChildren().add(taskContainer);
        }
    }

    /**
     * Draws the time axis at the top of the chart.
     */
    private void drawTimeAxis(int makespan) {
        int tickStep = 1;
        if (makespan > 50) tickStep = 5;
        else if (makespan > 20) tickStep = 2;

        for (int time = 0; time <= makespan; time += tickStep) {
            double x = HEADER_WIDTH + PADDING + (time * TIME_SCALE);
            Label timeLabel = new Label(String.valueOf(time));
            timeLabel.getStyleClass().add("axis-label");
            
            Text tempText = new Text(String.valueOf(time));
            tempText.setFont(Font.font("System", 11));
            double textWidth = tempText.getLayoutBounds().getWidth();
            
            timeLabel.setLayoutX(x - (textWidth / 2));
            timeLabel.setLayoutY(PADDING);
            getChildren().add(timeLabel);
        }
    }

    /**
     * Draws the machine labels on the Y-axis.
     */
    private void drawMachineLabels(List<String> machineIds, List<Machine> machines) {
        for (int i = 0; i < machineIds.size(); i++) {
            double y = PADDING + TIME_AXIS_HEIGHT + (i * ROW_HEIGHT) + (ROW_HEIGHT / 2) - 10;
            Label machineLabel = new Label(machines.get(i).getName());
            machineLabel.getStyleClass().add("machine-label");
            machineLabel.setLayoutX(PADDING);
            machineLabel.setLayoutY(y);
            getChildren().add(machineLabel);
        }
    }

    public void clear() {
        getChildren().clear();
        jobColors.clear();
        colorIndex = 0;
    }

    private Color getNextColor() {
        Color color = colorPalette.get(colorIndex % colorPalette.size());
        colorIndex++;
        return color;
    }
}