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
import tdtu.dang.jssp.models.Job;
import tdtu.dang.jssp.models.MachineGroup;
import tdtu.dang.jssp.models.Schedule;
import tdtu.dang.jssp.models.ScheduledOperation;

import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;

public class GanttChart extends Pane {

    private static final double TIME_SCALE = 50.0;
    private static final double ROW_HEIGHT = 100.0;
    private static final double HEADER_WIDTH = 120.0;
    private static final double PADDING = 10.0;
    private static final double TIME_AXIS_HEIGHT = 30.0;
    private static final double RECT_V_PADDING = 4.0;

    private final Map<String, Color> jobColors = new HashMap<>();
    private final List<Color> colorPalette = List.of(
            Color.web("#8ecae6"), Color.web("#219ebc"), Color.web("#023047"),
            Color.web("#ffb703"), Color.web("#fd9e02"), Color.web("#fb8500"),
            Color.web("#e63946"), Color.web("#a8dadc"), Color.web("#457b9d")
    );
    private int colorIndex = 0;

    public void displaySchedule(Schedule schedule, List<Job> jobs, List<MachineGroup> machineGroups) {
        clear();
        if (schedule == null || schedule.getScheduledOperations().isEmpty() || machineGroups == null) {
            return;
        }

        List<MachineGroup> sortedGroups = machineGroups.stream()
                .sorted(Comparator.comparing(MachineGroup::getId))
                .collect(Collectors.toList());

        Map<String, MachineGroup> groupMap = sortedGroups.stream()
                .collect(Collectors.toMap(MachineGroup::getId, Function.identity()));
                
        Map<String, Job> jobMap = jobs.stream()
                .collect(Collectors.toMap(Job::getId, Function.identity()));

        drawTimeAxis(schedule.getMakespan());
        drawMachineGroupLabels(sortedGroups);
        drawOperationBlocks(schedule.getScheduledOperations(), sortedGroups, groupMap, jobMap);
    }

    private void drawOperationBlocks(List<ScheduledOperation> operations, List<MachineGroup> sortedGroups, Map<String, MachineGroup> groupMap, Map<String, Job> jobMap) {
        Map<String, Integer> groupRowIndexMap = new HashMap<>();
        for (int i = 0; i < sortedGroups.size(); i++) {
            groupRowIndexMap.put(sortedGroups.get(i).getId(), i);
        }

        for (ScheduledOperation op : operations) {
            String[] instanceParts = op.getMachineInstanceId().split("_");
            if (instanceParts.length < 2) continue;

            String groupId = instanceParts[0];
            int instanceIndex = Integer.parseInt(instanceParts[1]);

            MachineGroup group = groupMap.get(groupId);
            if (group == null || group.getQuantity() == 0) continue;

            Color jobColor = jobColors.computeIfAbsent(op.getJobId(), k -> getNextColor());

            double subRowHeight = ROW_HEIGHT / group.getQuantity();
            int groupRowIndex = groupRowIndexMap.get(groupId);

            double x = HEADER_WIDTH + PADDING + (op.getStartTime() * TIME_SCALE);
            double groupY = PADDING + TIME_AXIS_HEIGHT + (groupRowIndex * ROW_HEIGHT);
            double y = groupY + (instanceIndex * subRowHeight);
            double width = (op.getEndTime() - op.getStartTime()) * TIME_SCALE;
            double height = subRowHeight - (RECT_V_PADDING / 2.0);

            if (width < 1.0) width = 1.0;
            if (height < 1.0) height = 1.0;

            StackPane taskContainer = new StackPane();
            taskContainer.setLayoutX(x);
            taskContainer.setLayoutY(y + (RECT_V_PADDING / 4.0));

            Rectangle rect = new Rectangle(width, height);
            rect.setFill(jobColor.deriveColor(0, 1.2, 1, 0.7));
            rect.setStroke(jobColor.darker());
            rect.setArcWidth(12);
            rect.setArcHeight(12);

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

            taskContainer.getChildren().add(rect);

            Text tempText = new Text("Job: " + op.getJobId());
            tempText.setFont(Font.font("System", FontWeight.BOLD, 11));
            if (tempText.getLayoutBounds().getWidth() < width - 16) {
                taskContainer.getChildren().add(labelBox);
            }

            Job job = jobMap.get(op.getJobId());
            String jobName = (job != null) ? job.getName() : "N/A";

            String tooltipText = String.format(
                "Job: %s (%s)\nOperation ID: %s\nMachine Group: %s\nMachine Instance: %d\n\nStart Time: %d\nEnd Time: %d\nDuration: %d",
                op.getJobId(), jobName, op.getOperationId(), group.getName(), instanceIndex,
                op.getStartTime(), op.getEndTime(), (op.getEndTime() - op.getStartTime())
            );
            Tooltip tooltip = new Tooltip(tooltipText);
            tooltip.setFont(Font.font("System", 14));
            Tooltip.install(taskContainer, tooltip);

            getChildren().add(taskContainer);
        }
    }

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

    private void drawMachineGroupLabels(List<MachineGroup> machineGroups) {
        for (int i = 0; i < machineGroups.size(); i++) {
            double y = PADDING + TIME_AXIS_HEIGHT + (i * ROW_HEIGHT) + (ROW_HEIGHT / 2) - 10;
            Label machineLabel = new Label(machineGroups.get(i).getName());
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