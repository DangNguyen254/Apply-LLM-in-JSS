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
import tdtu.dang.jssp.MainApp; 
import tdtu.dang.jssp.models.*;
import tdtu.dang.jssp.services.ApiClient;
import tdtu.dang.jssp.views.GanttChart;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;

import tdtu.dang.jssp.models.Scenario;

import java.io.File;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.HashMap;
import java.util.Objects;
import java.util.Optional;
import java.util.stream.Collectors;

public class MainViewController {

    @FXML private TreeView<String> jobTreeView;
    @FXML private TextArea machineDisplayArea;
    // --- THIS IS THE FIX: 'resultDisplayArea' has been removed ---
    // @FXML private TextArea resultDisplayArea; 
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
    @FXML private ComboBox<Scenario> scenarioSelector;
    @FXML private Label activeScenarioLabel;
    @FXML private Button addScenarioButton;
    @FXML private Button renameScenarioButton;
    @FXML private Button importButton;
    @FXML private MenuButton helpMenuButton;
    @FXML private Label welcomeUserLabel;

    private GanttChart ganttChart;
    private ApiClient apiClient; 
    private MainApp mainApp; 
    
    private Map<Integer, List<Map<String, Object>>> scenarioHistories = new HashMap<>();
    private List<Map<String, Object>> activeConversationHistory;
    
    private Schedule currentSchedule;
    
    private List<Job> cachedJobs = new ArrayList<>();
    private List<MachineGroup> cachedMachineGroups = new ArrayList<>();
    
    private final ObjectMapper objectMapper = new ObjectMapper();
    private boolean isUpdatingScenarioList = false;

    @FXML
    public void initialize() {
        ganttChart = new GanttChart();
        AnchorPane.setTopAnchor(ganttChart, 0.0);
        AnchorPane.setBottomAnchor(ganttChart, 0.0);
        AnchorPane.setLeftAnchor(ganttChart, 0.0);
        AnchorPane.setRightAnchor(ganttChart, 0.0);
        ganttChartPane.getChildren().add(ganttChart);

        this.activeConversationHistory = new ArrayList<>();
        
        this.objectMapper.enable(SerializationFeature.INDENT_OUTPUT);
        exportButton.setDisable(true);

        if (scenarioSelector != null) {
            scenarioSelector.valueProperty().addListener((obs, oldScenario, newScenario) -> {
                if (isUpdatingScenarioList) {
                    return;
                }
                if (newScenario != null && (oldScenario == null || oldScenario.getId() != newScenario.getId())) {
                    onScenarioSelected(oldScenario, newScenario);
                }
            });
        }

        if (addScenarioButton != null) {
            addScenarioButton.setOnAction(event -> handleAddScenarioButton());
        }
        if (renameScenarioButton != null) {
            renameScenarioButton.setOnAction(event -> handleRenameScenarioButton());
        }
        if (importButton != null) {
            importButton.setOnAction(event -> handleImportButton());
        }

        promptInput.addEventFilter(KeyEvent.KEY_PRESSED, event -> {
            if (event.getCode() == KeyCode.TAB) {
                event.consume();
                submitButton.requestFocus();
            }
        });
        
        Platform.runLater(() -> promptInput.requestFocus());

        if (resetButton != null) {
            resetButton.setVisible(true);
            resetButton.setManaged(true);
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

    public void onLoginSuccess(ApiClient apiClient, String username) {
        this.apiClient = apiClient;
        if (welcomeUserLabel != null) {
            welcomeUserLabel.setText("Welcome, " + username);
        }
        
        promptInput.setDisable(false);
        submitButton.setDisable(false);
        solveButton.setDisable(false);
        resetButton.setDisable(false);
        
        try {
            appendMessageToUI("System", "Loading Live Data scenario...");
            refreshAllData();
            appendMessageToUI("System", "Data loaded.");
        } catch (Exception e) {
            appendMessageToUI("Error", "Failed to load data: " + e.getMessage());
            e.printStackTrace();
        }
    }

    public void setMainApp(MainApp mainApp) {
        this.mainApp = mainApp;
    }

    @FXML
    private void handleHelpMenuClick() {
        Alert alert = new Alert(Alert.AlertType.INFORMATION);
        alert.setTitle("JSSP Orchestrator - Help");
        alert.setHeaderText("How to use the Assistant");
        String helpText = """
            Welcome! You can interact with this application in two ways:
            
            1.  **Direct Actions (Buttons):**
                * **Solve:** Solves the active scenario and saves the result.
                * **New/Rename/Import:** Manage your scenarios directly.
                * **Scenario Dropdown:** Switch between your different scenarios. All jobs/machines will reload.

            2.  **LLM Assistant:**
                * Use the text box to ask for changes in natural language.
                * **Try:** "Add a new job named 'Test Job' that needs Stamping for 5 hours and then Paint-Shop for 2 hours."
                * **Try:** "What if the 'Body-Shop-Welding' group was reduced to 2 machines?"
                * **Try:** "Make the 'Priority-Fleet-01' job the highest priority."
            """;
        alert.setContentText(helpText);
        alert.showAndWait();
    }

    @FXML
    private void handleContactMenuClick() {
        Alert alert = new Alert(Alert.AlertType.INFORMATION);
        alert.setTitle("Contact Support");
        alert.setHeaderText("Application Support");
        alert.setContentText("For technical issues, please contact the IT department or email admin@jssp-internal.com.");
        alert.showAndWait();
    }
    
    @FXML
    private void handleSignOutMenuClick() {
        appendMessageToUI("System", "Signing out...");
        
        this.activeConversationHistory.clear();
        this.scenarioHistories.clear();
        this.cachedJobs.clear();
        this.cachedMachineGroups.clear();
        this.currentSchedule = null;
        
        if (apiClient != null) {
            apiClient.logout();
        }
        
        if (mainApp != null) {
            mainApp.showLoginView();
        }
    }

    private void refreshAllData() {
        try {
            updateScenarioList();

            cachedJobs = apiClient.getJobs();
            cachedMachineGroups = apiClient.getMachineGroups();
            
            updateJobTreeView(cachedJobs);
            updateMachineGroupDisplay(cachedMachineGroups);
            
            ganttChart.clear();
            if (kpiBox != null) kpiBox.getChildren().clear();
            // --- THIS IS THE FIX: 'resultDisplayArea' reference removed ---
            // resultDisplayArea.clear();
            this.currentSchedule = null;
            exportButton.setDisable(true);
            
            appendMessageToUI("System", "Loaded " + cachedJobs.size() + " jobs and " + cachedMachineGroups.size() + " machine groups for the active scenario.");
            
            try {
                appendMessageToUI("System", "Fetching latest schedule for this scenario...");
                Schedule latestSchedule = apiClient.getLatestSchedule();
                if (latestSchedule != null) {
                    displayScheduleResults(latestSchedule, this.cachedJobs, this.cachedMachineGroups);
                    appendMessageToUI("System", "Loaded existing schedule.");
                }
            } catch (Exception e) {
                appendMessageToUI("System", "No existing schedule found for this scenario.");
            }
            
        } catch (IOException | InterruptedException e) {
            appendMessageToUI("Error", "Could not load problem data: " + e.getMessage());
            e.printStackTrace();
        }
    }

    private void onScenarioSelected(Scenario oldScenario, Scenario newScenario) {
        if (newScenario == null) return;
        
        if (oldScenario != null) {
            scenarioHistories.put(oldScenario.getId(), this.activeConversationHistory);
        }
        this.activeConversationHistory = scenarioHistories.computeIfAbsent(newScenario.getId(), k -> new ArrayList<>());
        redrawConversationUI();

        appendMessageToUI("System", "Switching active scenario to '" + newScenario.getName() + "'...");
        try {
            apiClient.selectScenario(newScenario.getId());
            refreshAllData();
            
            if (activeScenarioLabel != null) {
                activeScenarioLabel.setText(newScenario.getName());
            }
            appendMessageToUI("System", "Scenario switched. All data reloaded.");

            if (renameScenarioButton != null) {
                renameScenarioButton.setDisable("Live Data".equalsIgnoreCase(newScenario.getName()));
            }

        } catch (Exception e) {
            appendMessageToUI("Error", "Failed to switch scenario: " + e.getMessage());
            e.printStackTrace();
            Platform.runLater(this::updateScenarioList);
        }
    }
    
    private void redrawConversationUI() {
        if (conversationContainer == null) return;
        conversationContainer.getChildren().clear();
        
        if (this.activeConversationHistory == null) return;

        for (Map<String, Object> entry : this.activeConversationHistory) {
            try {
                String role = (String) entry.get("role");
                List<Map<String, String>> parts = (List<Map<String, String>>) entry.get("parts");
                String content = "";
                
                if (parts != null && !parts.isEmpty()) {
                    for (Map<String, String> part : parts) {
                        if (part.containsKey("text")) {
                            content = part.get("text");
                            break;
                        }
                    }
                }
                
                if (!content.isEmpty()) {
                    appendMessageToUI(role, content);
                }

            } catch (Exception e) {
                System.err.println("Failed to redraw conversation entry: " + e.getMessage());
                e.printStackTrace();
            }
        }
    }

    private void appendConversationEntry(String role, String content) {
        Map<String, Object> newEntry = Map.of(
            "role", role,
            "parts", List.of(Map.of("text", content.trim()))
        );
        this.activeConversationHistory.add(newEntry);
        appendMessageToUI(role, content);
    }

    private void appendMessageToUI(String role, String content) {
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

    private void appendConversationUser(String content){ appendConversationEntry("user", content); }
    private void appendConversationAssistant(String content){ appendConversationEntry("assistant", content); }

    private void updateScenarioList() {
        if (scenarioSelector == null) return;

        this.isUpdatingScenarioList = true;
        try {
            List<Scenario> scenarios = apiClient.getScenarios();
            Scenario currentSelection = scenarioSelector.getValue();

            List<Scenario> filteredScenarios = scenarios.stream()
                .filter(s -> s.getName() != null && !s.getName().startsWith("temp-what-if-simulation"))
                .collect(Collectors.toList());

            scenarioSelector.getItems().clear();
            scenarioSelector.getItems().addAll(filteredScenarios);

            if (currentSelection != null && filteredScenarios.contains(currentSelection)) {
                scenarioSelector.setValue(currentSelection);
            } 
            else {
                Scenario liveData = filteredScenarios.stream()
                        .filter(s -> "Live Data".equalsIgnoreCase(s.getName()))
                        .findFirst()
                        .orElse(filteredScenarios.isEmpty() ? null : filteredScenarios.get(0));
                
                if (liveData != null) {
                    scenarioSelector.setValue(liveData);
                    if (activeScenarioLabel != null) {
                        activeScenarioLabel.setText(liveData.getName());
                    }
                }
            }

            Scenario activeScenario = scenarioSelector.getValue();
            if (renameScenarioButton != null) {
                renameScenarioButton.setDisable(activeScenario == null || "Live Data".equalsIgnoreCase(activeScenario.getName()));
            }

        } catch (Exception e) {
            appendMessageToUI("Error", "Could not update scenario list: " + e.getMessage());
        } finally {
            this.isUpdatingScenarioList = false;
        }
    }

    @FXML
    private void handleAddScenarioButton() {
        TextInputDialog dialog = new TextInputDialog("My New Scenario");
        dialog.setTitle("Create New Scenario");
        dialog.setHeaderText("Create a new, blank scenario.");
        dialog.setContentText("New scenario name:");
        Optional<String> result = dialog.showAndWait();
        result.ifPresent(name -> {
            if (name.trim().isEmpty()) {
                appendMessageToUI("Error", "Scenario name cannot be empty.");
                return;
            }
            try {
                appendMessageToUI("System", "Creating blank scenario: " + name.trim());
                Scenario newScenario = apiClient.createBlankScenario(name.trim());
                appendMessageToUI("System", "Successfully created '" + newScenario.getName() + "'.");
                Platform.runLater(() -> {
                    updateScenarioList();
                    scenarioSelector.setValue(newScenario);
                });
            } catch (Exception e) {
                appendMessageToUI("Error", "Failed to create scenario: " + e.getMessage());
            }
        });
    }

    @FXML
    private void handleRenameScenarioButton() {
        Scenario activeScenario = scenarioSelector.getValue();
        if (activeScenario == null || "Live Data".equalsIgnoreCase(activeScenario.getName())) {
            appendMessageToUI("Error", "Cannot rename the 'Live Data' scenario.");
            return;
        }
        TextInputDialog dialog = new TextInputDialog(activeScenario.getName());
        dialog.setTitle("Rename Scenario");
        dialog.setHeaderText("Rename the active scenario '" + activeScenario.getName() + "'.");
        dialog.setContentText("New name:");
        Optional<String> result = dialog.showAndWait();
        result.ifPresent(newName -> {
            if (newName.trim().isEmpty()) {
                appendMessageToUI("Error", "Scenario name cannot be empty.");
                return;
            }
            try {
                appendMessageToUI("System", "Renaming scenario...");
                Scenario updatedScenario = apiClient.renameScenario(activeScenario.getId(), newName.trim());
                appendMessageToUI("System", "Successfully renamed to '" + updatedScenario.getName() + "'.");
                Platform.runLater(this::updateScenarioList);
            } catch (Exception e) {
                appendMessageToUI("Error", "Failed to rename scenario: " + e.getMessage());
            }
        });
    }

    @FXML
    private void handleImportButton() {
        FileChooser fileChooser = new FileChooser();
        fileChooser.setTitle("Import Problem Data");
        fileChooser.getExtensionFilters().addAll(
            new FileChooser.ExtensionFilter("JSON Files", "*.json")
        );
        File file = fileChooser.showOpenDialog(importButton.getScene().getWindow());
        if (file != null) {
            try {
                appendMessageToUI("System", "Importing data from " + file.getName() + "...");
                String jsonContent = java.nio.file.Files.readString(file.toPath());
                apiClient.importData(jsonContent);
                appendMessageToUI("System", "Data imported successfully.");
                refreshAllData();
            } catch (Exception e) {
                appendMessageToUI("Error", "Failed to import data: " + e.getMessage());
                e.printStackTrace();
            }
        }
    }


    private void updateJobTreeView(List<Job> jobs) {
        Map<String, String> mgIdToNameMap = this.cachedMachineGroups.stream()
            .collect(Collectors.toMap(MachineGroup::getId, MachineGroup::getName, (a, b) -> a));

        TreeItem<String> rootItem = new TreeItem<>("Jobs (" + (jobs == null ? 0 : jobs.size()) + ")");
        rootItem.setExpanded(true);

        if (jobs != null) {
            for (Job job : jobs) {
                String jobLabel = String.format("%s (Priority: %d)", job.getName(), job.getPriority());
                TreeItem<String> jobItem = new TreeItem<>(jobLabel);

                if (job.getOpList() != null && !job.getOpList().isEmpty()) {
                    int seq = 1;
                    for (Operation op : job.getOpList()) {
                        String mgName = mgIdToNameMap.getOrDefault(op.getMachineGroupId(), op.getMachineGroupId());
                        String label = String.format("Op %02d: %s (Time: %d)", seq++, mgName, op.getProcessingTime());
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
            sb.append(String.format("%s (Quantity: %d)\n", group.getName(), group.getQuantity()));
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
            appendMessageToUI("Error", "Please enter a command.");
            return;
        }
        promptInput.clear();
        appendConversationEntry("user", command);
        runOrchestration(command);
    }

    @FXML
    private void handleSolveButton() {
        appendMessageToUI("System", "Solving current active scenario...");
        try {
            Schedule newSchedule = apiClient.solveActiveScenario();
            appendMessageToUI("System", "Solve complete. Displaying results.");
            displayScheduleResults(newSchedule, this.cachedJobs, this.cachedMachineGroups);
        } catch (Exception e) {
            appendMessageToUI("Error", "Failed to solve: " + e.getMessage());
            e.printStackTrace();
        }
    }

    private void runOrchestration(String command) {
        try {
            OrchestratorResponse llmResponse = apiClient.interpretCommand(command, this.activeConversationHistory);
            this.activeConversationHistory = llmResponse.getHistory();
            redrawConversationUI();
            appendMessageToUI("System", "Refreshing data lists...");
            refreshAllData(); 
            Schedule schedule = llmResponse.getSchedule();
            if (schedule != null) {
                appendMessageToUI("System", "Orchestrator returned schedule; displaying...");
                displayScheduleResults(schedule, this.cachedJobs, this.cachedMachineGroups);
            }
        } catch (IOException | InterruptedException e) {
            e.printStackTrace();
            appendMessageToUI("Error", e.getMessage());
        }
    }

    private void displayScheduleResults(Schedule schedule, List<Job> jobs, List<MachineGroup> machineGroups) {
        this.currentSchedule = schedule; 
        exportButton.setDisable(false);
        
        int schedOps = (schedule.getScheduledOperations()==null?0:schedule.getScheduledOperations().size());
        appendMessageToUI("System", "Schedule received: makespan=" + schedule.getMakespan() + ", operations=" + schedOps);
        
        if (schedOps == 0) {
            appendMessageToUI("Error", "Scheduled operations list is empty – cannot render Gantt chart.");
            ganttChart.clear();
        } else if (jobs==null || jobs.isEmpty()) {
            appendMessageToUI("Error", "Jobs list empty during schedule display – verify backend data.");
        } else if (machineGroups==null || machineGroups.isEmpty()) {
            appendMessageToUI("Error", "Machine groups empty during schedule display – verify backend data.");
        } else {
            ganttChart.displaySchedule(schedule, jobs, machineGroups);
            appendMessageToUI("System", "Gantt chart rendered.");
        }
        
        // --- THIS IS THE FIX: 'resultDisplayArea' logic is removed ---
        
        appendMessageToUI("System", "KPIs updated (makespan=" + schedule.getMakespan() + ", avg flow=" + String.format("%.2f", schedule.getAverageFlowTime()) + ").");
        renderKpis(schedule);
    }

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
                        double v = e.getValue() == null ? 0.0 : e.getValue();
                        ProgressBar bar = new ProgressBar(Math.max(0, Math.min(1, v)));
                        bar.setPrefWidth(140);
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
    private void handleSubmitButtonKeyPress(KeyEvent event) {
        if (event.getCode() == KeyCode.TAB) {
            event.consume();
            solveButton.requestFocus();
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
    private void handleResetButtonKeyPress(KeyEvent event) {
        if (event.getCode() == KeyCode.TAB) {
            event.consume();
            Platform.runLater(() -> {
                promptInput.requestFocus();
                promptInput.positionCaret(promptInput.getLength());
            });
        }
    }

    @FXML
    private void handleExportButton() {
        Schedule scheduleToExport;
        try {
            appendMessageToUI("System", "Fetching latest schedule from database for export...");
            scheduleToExport = apiClient.getLatestSchedule();
            if (scheduleToExport == null) {
                appendMessageToUI("Error", "No schedule data found in database to export.");
                return;
            }
            appendMessageToUI("System", "Latest schedule (Makespan: " + scheduleToExport.getMakespan() + ") received.");
        } catch (Exception e) {
            appendMessageToUI("Error", "Could not fetch schedule from database: " + e.getMessage());
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
                    exportScheduleAsCsv(file, scheduleToExport);
                } else { 
                    objectMapper.writeValue(file, scheduleToExport);
                }
                appendMessageToUI("System", "Schedule exported successfully to " + file.getAbsolutePath());
            } catch (IOException e) {
                appendMessageToUI("Error", "Error exporting schedule: " + e.getMessage());
                e.printStackTrace();
            }
        }
    }

    @FXML
    private void handleResetButton() {
        appendMessageToUI("System", "Resetting database to default...");
        try {
            String newSessionToken = apiClient.resetProblem();
            appendMessageToUI("System", "Database reset.");
            appendMessageToUI("System", "New session established: " + newSessionToken);
            this.activeConversationHistory.clear();
            this.scenarioHistories.clear();
            redrawConversationUI();
            ganttChart.clear();
            // --- THIS IS THE FIX: 'resultDisplayArea' reference removed ---
            // resultDisplayArea.clear(); 
            promptInput.clear();
            this.currentSchedule = null;
            exportButton.setDisable(true);
            refreshAllData();
        } catch (IOException | InterruptedException e) {
            appendMessageToUI("Error", "Reset failed: " + e.getMessage());
        }
    }

    private void exportScheduleAsCsv(File file, Schedule schedule) throws IOException {
        if (schedule == null) return;
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