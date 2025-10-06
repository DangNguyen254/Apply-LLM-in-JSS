package tdtu.dang.jssp.views;

import javafx.scene.layout.Pane;
import javafx.scene.paint.Color;
import javafx.scene.shape.Rectangle;
import javafx.scene.text.Text;
import tdtu.dang.jssp.models.Schedule;
import tdtu.dang.jssp.models.ScheduledOperation;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class GanttChart extends Pane {

    private static final double TIME_SCALE = 25.0;
    private static final double ROW_HEIGHT = 40.0;
    private static final double HEADER_WIDTH = 100.0;
    private static final double PADDING = 10.0;
    private static final double MINIMUM_RECT_WIDTH = 80.0;

    private final Map<String, Color> jobColors = new HashMap<>();
    private final List<Color> colorPalette = List.of(
            Color.web("#8ecae6"), Color.web("#219ebc"), Color.web("#023047"),
            Color.web("#ffb703"), Color.web("#fd9e02"), Color.web("#fb8500")
    );
    private int colorIndex = 0;

    public void displaySchedule(Schedule schedule) {
        clear();
        if (schedule == null || schedule.getScheduledOperations().isEmpty()) {
            return;
        }

        List<String> machineIds = new ArrayList<>(
            schedule.getScheduledOperations().stream()
                .map(ScheduledOperation::getMachineId)
                .distinct()
                .sorted()
                .toList()
        );

        double totalWidth = HEADER_WIDTH + (schedule.getMakespan() * TIME_SCALE) + (PADDING * 2);
        double totalHeight = machineIds.size() * ROW_HEIGHT + (PADDING * 2);
        setPrefSize(totalWidth, totalHeight);

        for (int i = 0; i < machineIds.size(); i++) {
            Text machineLabel = new Text(PADDING, i * ROW_HEIGHT + ROW_HEIGHT / 1.5 + PADDING, machineIds.get(i));
            machineLabel.setFill(Color.BLACK);
            getChildren().add(machineLabel);
        }

        // NEW: Map to track the last visual end X-coordinate for each machine row
        Map<String, Double> lastXEndPerMachine = new HashMap<>();

        for (ScheduledOperation op : schedule.getScheduledOperations()) {
            Color jobColor = jobColors.computeIfAbsent(op.getJobId(), k -> getNextColor());

            double calculatedX = HEADER_WIDTH + PADDING + (op.getStartTime() * TIME_SCALE);
            double y = machineIds.indexOf(op.getMachineId()) * ROW_HEIGHT + PADDING;

            // UPDATED: Ensure the rectangle starts after the previous one on the same machine
            double lastX = lastXEndPerMachine.getOrDefault(op.getMachineId(), 0.0);
            double x = Math.max(calculatedX, lastX);

            double calculatedWidth = (op.getEndTime() - op.getStartTime()) * TIME_SCALE;
            double width = Math.max(calculatedWidth, MINIMUM_RECT_WIDTH);

            Rectangle rect = new Rectangle(x, y, width, ROW_HEIGHT - 5);
            rect.setFill(jobColor);
            rect.setStroke(Color.BLACK);
            rect.setArcWidth(10);
            rect.setArcHeight(10);

            Text opLabel = new Text(x + 5, y + rect.getHeight() / 1.75, op.getJobId() + "-" + op.getOperationId());
            opLabel.setFill(Color.WHITE);
            opLabel.setWrappingWidth(width - 10);

            getChildren().addAll(rect, opLabel);
            
            // NEW: Update the last visual end position for this machine
            lastXEndPerMachine.put(op.getMachineId(), x + width + 5); // Added a 5px gap
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