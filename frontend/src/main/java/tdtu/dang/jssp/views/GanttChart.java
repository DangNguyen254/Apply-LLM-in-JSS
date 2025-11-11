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

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;

public class GanttChart extends Pane {

    // --- CHART STYLING CONSTANTS ---
    private static final double TIME_SCALE = 50.0;  // Pixels per time unit
    private static final double ROW_HEIGHT = 60.0;  // Height for one machine instance
    private static final double HEADER_WIDTH = 140.0; // Width of the Y-axis label area
    private static final double PADDING = 20.0;
    private static final double TIME_AXIS_HEIGHT = 30.0; // Height for time numbers
    private static final double RECT_V_PADDING = 8.0; // Padding inside the row

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

        // --- DATA PREPARATION ---
        
        // Create a map of GroupID -> GroupObject
        Map<String, MachineGroup> groupMap = machineGroups.stream()
                .collect(Collectors.toMap(MachineGroup::getId, Function.identity()));

        // Create a map of JobID -> JobObject
        Map<String, Job> jobMap = jobs.stream()
                .collect(Collectors.toMap(Job::getId, Function.identity()));
        
        // --- Y-AXIS (ROW) CALCULATION ---
        // This is the "Option 1" logic
        
        // 1. Unroll machine groups into a list of machine *instances*
        // We sort by ID to ensure "Drilling-1" always comes before "Drilling-2"
        List<String> machineInstanceRows = new ArrayList<>();
        List<MachineGroup> sortedGroups = machineGroups.stream()
                .sorted(Comparator.comparing(MachineGroup::getId))
                .collect(Collectors.toList());
        
        for (MachineGroup group : sortedGroups) {
            for (int i = 0; i < group.getQuantity(); i++) {
                // The format is "GroupID_InstanceIndex", e.g., "MG003_1"
                machineInstanceRows.add(group.getId() + "_" + i);
            }
        }
        
        int totalRows = machineInstanceRows.size();
        
        // 2. Create a map to find the row index for any instance ID
        // e.g., "MG003_1" -> row index 3
        Map<String, Integer> instanceRowIndexMap = new HashMap<>();
        for (int i = 0; i < totalRows; i++) {
            instanceRowIndexMap.put(machineInstanceRows.get(i), i);
        }

        // --- DRAWING ---
        
        // 1. Draw the Y-Axis labels (e.g., "Drilling-1", "Milling-1")
        drawMachineInstanceLabels(machineInstanceRows, groupMap);
        
        // 2. Draw the operation blocks onto the chart
        drawOperationBlocks(
            schedule.getScheduledOperations(), 
            instanceRowIndexMap, 
            groupMap, 
            jobMap
        );

        // 3. Draw the X-Axis (Time)
        drawTimeAxis(schedule.getMakespan(), totalRows);
        
        // --- SCROLLPANE SIZING ---
        // Calculate total size needed and set it
        // This forces the parent ScrollPane to show scrollbars
        double totalWidth = HEADER_WIDTH + (schedule.getMakespan() * TIME_SCALE) + (PADDING * 2);
        double totalHeight = TIME_AXIS_HEIGHT + (totalRows * ROW_HEIGHT) + (PADDING * 2);
        
        setMinWidth(totalWidth);
        setMinHeight(totalHeight);
        setPrefSize(totalWidth, totalHeight); // Also set pref size
    }
    
    private void drawMachineInstanceLabels(List<String> machineInstanceRows, Map<String, MachineGroup> groupMap) {
        for (int i = 0; i < machineInstanceRows.size(); i++) {
            String instanceId = machineInstanceRows.get(i); // "MG003_1"
            String[] parts = instanceId.split("_");
            String groupId = parts[0];
            String instanceIndex = parts[1];
            
            // Find the group name, default to ID if not found
            MachineGroup group = groupMap.get(groupId);
            String groupName = (group != null) ? group.getName() : groupId;

            // Create the label as per "Option 1"
            String labelText = String.format("%s-%s", groupName, Integer.parseInt(instanceIndex) + 1);
            Label machineLabel = new Label(labelText);
            machineLabel.getStyleClass().add("machine-label");
            
            // Center the label vertically in its row
            double y = PADDING + TIME_AXIS_HEIGHT + (i * ROW_HEIGHT) + (ROW_HEIGHT / 2) - 10;
            machineLabel.setLayoutX(PADDING);
            machineLabel.setLayoutY(y);
            getChildren().add(machineLabel);
        }
    }

    private void drawOperationBlocks(List<ScheduledOperation> operations, Map<String, Integer> instanceRowIndexMap, Map<String, MachineGroup> groupMap, Map<String, Job> jobMap) {

        for (ScheduledOperation op : operations) {
            String instanceId = op.getMachineInstanceId(); // "MG003_1"
            
            // Find which row this operation belongs to
            Integer rowIndex = instanceRowIndexMap.get(instanceId);
            if (rowIndex == null) continue; // Skip if op is for an unknown machine

            // Get Job Name for the label
            Job job = jobMap.get(op.getJobId());
            String jobName = (job != null) ? job.getName() : op.getJobId();
            
            // Get Group Name for the tooltip
            String[] parts = instanceId.split("_");
            MachineGroup group = groupMap.get(parts[0]);
            String groupName = (group != null) ? group.getName() : parts[0];
            int instanceNum = Integer.parseInt(parts[1]);

            Color jobColor = jobColors.computeIfAbsent(op.getJobId(), k -> getNextColor());

            // --- Calculate block position and size ---
            double x = HEADER_WIDTH + PADDING + (op.getStartTime() * TIME_SCALE);
            double y = PADDING + TIME_AXIS_HEIGHT + (rowIndex * ROW_HEIGHT) + (RECT_V_PADDING / 2.0);
            
            double width = (op.getEndTime() - op.getStartTime()) * TIME_SCALE;
            double height = ROW_HEIGHT - RECT_V_PADDING; // Use full row height

            if (width < 1.0) width = 1.0;

            // --- Create the visual block ---
            StackPane taskContainer = new StackPane();
            taskContainer.setLayoutX(x);
            taskContainer.setLayoutY(y);

            Rectangle rect = new Rectangle(width, height);
            rect.setFill(jobColor.deriveColor(0, 1.2, 1, 0.7));
            rect.setStroke(jobColor.darker());
            rect.setArcWidth(12);
            rect.setArcHeight(12);

            // --- Create Labels (Job Name + Op ID) ---
            Label jobNameLabel = new Label(jobName); // Use Job Name
            jobNameLabel.setFont(Font.font("System", FontWeight.BOLD, 11));
            jobNameLabel.setTextFill(Color.WHITE);

            Label opIdLabel = new Label(op.getOperationId());
            opIdLabel.setFont(Font.font("System", FontWeight.NORMAL, 10));
            opIdLabel.setTextFill(Color.WHITE.deriveColor(0, 1, 1, 0.9));

            VBox labelBox = new VBox(jobNameLabel, opIdLabel);
            labelBox.setAlignment(Pos.CENTER_LEFT);
            labelBox.setPadding(new Insets(0, 0, 0, 8));
            labelBox.setSpacing(2);

            taskContainer.getChildren().add(rect);

            // Check if text will fit before adding it
            Text tempText = new Text(jobName);
            tempText.setFont(Font.font("System", FontWeight.BOLD, 11));
            if (tempText.getLayoutBounds().getWidth() < width - 16) {
                taskContainer.getChildren().add(labelBox);
            }

            // --- Create Tooltip ---
            String tooltipText = String.format(
                "Job: %s (%s)\nOperation ID: %s\nMachine: %s-%d\n\nStart: %d\nEnd: %d\nDuration: %d",
                op.getJobId(), jobName, op.getOperationId(), 
                groupName, instanceNum + 1,
                op.getStartTime(), op.getEndTime(), (op.getEndTime() - op.getStartTime())
            );
            Tooltip tooltip = new Tooltip(tooltipText);
            tooltip.setFont(Font.font("System", 14));
            Tooltip.install(taskContainer, tooltip);

            getChildren().add(taskContainer);
        }
    }

    private void drawTimeAxis(int makespan, int totalRows) {
        int tickStep = 1;
        double chartWidth = makespan * TIME_SCALE;
        
        // Dynamically adjust tick step based on total width
        if (chartWidth > 3000) tickStep = 10;
        else if (chartWidth > 1500) tickStep = 5;
        else if (chartWidth > 800) tickStep = 2;

        for (int time = 0; time <= makespan; time += tickStep) {
            double x = HEADER_WIDTH + PADDING + (time * TIME_SCALE);
            
            // Draw tick label
            Label timeLabel = new Label(String.valueOf(time));
            timeLabel.getStyleClass().add("axis-label");
            
            Text tempText = new Text(String.valueOf(time));
            tempText.setFont(Font.font("System", 11));
            double textWidth = tempText.getLayoutBounds().getWidth();
            
            timeLabel.setLayoutX(x - (textWidth / 2));
            timeLabel.setLayoutY(PADDING);
            getChildren().add(timeLabel);
            
            // Draw faint vertical grid line
            Rectangle gridLine = new Rectangle(
                x, 
                PADDING + TIME_AXIS_HEIGHT, 
                1, // 1px wide
                totalRows * ROW_HEIGHT
            );
            gridLine.setFill(Color.web("#000000", 0.1));
            getChildren().add(gridLine);
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