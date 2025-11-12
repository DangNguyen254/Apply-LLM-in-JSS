package tdtu.dang.jssp.services;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import tdtu.dang.jssp.models.*;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.util.List;
import java.util.Map;

public class ApiClient {

    private final HttpClient httpClient;
    private final ObjectMapper objectMapper;
    private static final String BASE_URL = "http://127.0.0.1:8000/api/scheduling";

    private String sessionToken;

    public ApiClient() {
        this.httpClient = HttpClient.newBuilder()
                .version(HttpClient.Version.HTTP_1_1)
                .build();
        this.objectMapper = new ObjectMapper();
        this.sessionToken = null; // Start as logged out
    }

    /**
     * Attempts to log in. Returns username on success, null on failure.
     */
    public String login(String username, String password) throws IOException, InterruptedException {
        String url = BASE_URL + "/login";

        ObjectNode requestBody = objectMapper.createObjectNode();
        requestBody.put("username", username);
        requestBody.put("password", password);
        String requestBodyString = objectMapper.writeValueAsString(requestBody);

        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(url))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(requestBodyString))
                .build();

        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());

        if (response.statusCode() == 401) {
            // 401 is "Unauthorized", a normal failed login
            return null;
        }

        if (response.statusCode() != 200) {
            // Other errors (like 500) are exceptions
            throw new IOException("Login failed: " + response.body());
        }

        JsonNode responseJson = objectMapper.readTree(response.body());
        this.sessionToken = responseJson.get("session_token").asText();
        String loggedInUsername = responseJson.get("username").asText();
        
        System.out.println("Login successful. Token set.");
        return loggedInUsername;
    }

    /**
     * Logs the user out by invalidating the token on the server.
     */
    public void logout() {
        if (this.sessionToken == null) {
            return; // Already logged out
        }
        
        String url = BASE_URL + "/logout";
        try {
            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(url))
                    .header("X-Session-Token", this.sessionToken)
                    .POST(HttpRequest.BodyPublishers.noBody())
                    .build();
            
            // Send asynchronously, we don't care about the response
            httpClient.sendAsync(request, HttpResponse.BodyHandlers.ofString());
            
        } catch (Exception e) {
            // Don't crash the app if logout fails
            System.err.println("Failed to send logout request: " + e.getMessage());
        } finally {
            // Always clear the token locally
            clearSessionToken();
        }
    }

    /**
     * Allows the LoginController to set the token.
     */
    public void setSessionToken(String token) {
        this.sessionToken = token;
    }
    
    /**
     * Clears the session token locally.
     */
    public void clearSessionToken() {
        this.sessionToken = null;
        System.out.println("Local session token cleared.");
    }

    /**
     * Checks if the client is authenticated (has a session token).
     */
    private void checkAuth() throws IOException {
        if (this.sessionToken == null || this.sessionToken.isEmpty()) {
            throw new IOException("Client is not authenticated. Please log in.");
        }
    }
    
    /**
     * Fetches jobs for the user's active scenario.
     */
    public List<Job> getJobs() throws IOException, InterruptedException {
        checkAuth(); // Ensure we are logged in
        String url = BASE_URL + "/jobs";

        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(url))
                .header("X-Session-Token", this.sessionToken) // Add the session token
                .GET()
                .build();

        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());

        if (response.statusCode() != 200) {
            throw new IOException("Failed to fetch jobs: " + response.body());
        }

        String raw = response.body();
        System.out.println("[DEBUG getJobs] Raw JSON length=" + raw.length());
        System.out.println("[DEBUG getJobs] Raw JSON snippet=" + (raw.length() > 400 ? raw.substring(0,400)+"..." : raw));

        // This parsing will now work thanks to the backend returning JobRead
        List<Job> jobs = objectMapper.readValue(raw, new TypeReference<List<Job>>() {});
        for (Job j : jobs) {
            int ops = (j.getOpList()==null?0:j.getOpList().size());
            System.out.println("[DEBUG getJobs] Job=" + j.getId() + " name=" + j.getName() + " priority=" + j.getPriority() + " ops=" + ops);
            if (ops>0) {
                for (Operation op : j.getOpList()) {
                    System.out.println("   -> Op id=" + op.getId() + " mg=" + op.getMachineGroupId() + " pt=" + op.getProcessingTime() + " preds=" + (op.getPredecessors()==null?"[]":op.getPredecessors()));
                }
            }
        }
        return jobs;
    }

    /**
     * Fetches machine groups for the user's active scenario.
     */
    public List<MachineGroup> getMachineGroups() throws IOException, InterruptedException {
        checkAuth(); // Ensure we are logged in
        String url = BASE_URL + "/machine_groups";
        
        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(url))
                .header("X-Session-Token", this.sessionToken) // Add the session token
                .GET()
                .build();
                
        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
        if (response.statusCode() != 200) throw new IOException("Failed to fetch machine groups: " + response.body());
        return objectMapper.readValue(response.body(), new TypeReference<List<MachineGroup>>() {});
    }

    /**
     * Fetches all scenarios available for the current user.
     */
    public List<Scenario> getScenarios() throws IOException, InterruptedException {
        checkAuth(); // Ensure we are logged in
        String url = BASE_URL + "/scenarios";
        
        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(url))
                .header("X-Session-Token", this.sessionToken) // Add the session token
                .GET()
                .build();
                
        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
        if (response.statusCode() != 200) throw new IOException("Failed to fetch scenarios: " + response.body());
        
        List<Scenario> scenarios = objectMapper.readValue(response.body(), new TypeReference<List<Scenario>>() {});
        System.out.println("[DEBUG getScenarios] Found " + scenarios.size() + " scenarios.");
        return scenarios;
    }

    /**
     * Tells the backend to change the user's active scenario.
     */
    public void selectScenario(int scenarioId) throws IOException, InterruptedException {
        checkAuth(); // Ensure we are logged in
        String url = BASE_URL + "/select_scenario/" + scenarioId;
        
        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(url))
                .header("X-Session-Token", this.sessionToken) // Add the session token
                .POST(HttpRequest.BodyPublishers.noBody())
                .build();
                
        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
        if (response.statusCode() != 200) throw new IOException("Failed to select scenario: " + response.body());
        
        System.out.println("[DEBUG selectScenario] Backend response: " + response.body());
    }

    /**
     * Creates a new, blank scenario.
     */
    public Scenario createBlankScenario(String name) throws IOException, InterruptedException {
        checkAuth(); // Ensure we are logged in
        String url = BASE_URL + "/scenario/create_blank";

        ObjectNode requestBody = objectMapper.createObjectNode();
        requestBody.put("name", name);
        String requestBodyString = objectMapper.writeValueAsString(requestBody);

        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(url))
                .header("Content-Type", "application/json")
                .header("X-Session-Token", this.sessionToken)
                .POST(HttpRequest.BodyPublishers.ofString(requestBodyString))
                .build();

        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());

        if (response.statusCode() != 200) { // Expects 200 OK now
            throw new IOException("Failed to create blank scenario: " + response.body());
        }

        return objectMapper.readValue(response.body(), Scenario.class);
    }

    /**
     * Renames an existing scenario.
     */
    public Scenario renameScenario(int scenarioId, String newName) throws IOException, InterruptedException {
        checkAuth(); // Ensure we are logged in
        // This URL now matches the backend endpoint
        String url = BASE_URL + "/scenarios/" + scenarioId;

        ObjectNode requestBody = objectMapper.createObjectNode();
        requestBody.put("name", newName);
        String requestBodyString = objectMapper.writeValueAsString(requestBody);

        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(url))
                .header("Content-Type", "application/json")
                .header("X-Session-Token", this.sessionToken) // Add the session token
                .PUT(HttpRequest.BodyPublishers.ofString(requestBodyString)) // Use PUT
                .build();

        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());

        if (response.statusCode() != 200) {
            throw new IOException("Failed to rename scenario: " + response.body());
        }

        return objectMapper.readValue(response.body(), Scenario.class);
    }
    
    /**
     * NEW: Fetches the latest *saved* schedule from the database.
     * Used by the "Export" button.
     */
    public Schedule getLatestSchedule() throws IOException, InterruptedException {
        checkAuth(); // Ensure we are logged in
        String url = BASE_URL + "/get_latest_schedule";

        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(url))
                .header("X-Session-Token", this.sessionToken) // Add the session token
                .GET()
                .build();

        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());

        if (response.statusCode() != 200) {
            throw new IOException("Failed to fetch latest schedule: " + response.body());
        }
        String raw = response.body();
        System.out.println("[DEBUG getLatestSchedule] Raw JSON=" + raw);
        Schedule schedule = objectMapper.readValue(raw, Schedule.class);
        int ops = (schedule.getScheduledOperations()==null?0:schedule.getScheduledOperations().size());
        System.out.println("[DEBUG getLatestSchedule] makespan=" + schedule.getMakespan() + " avgFlow=" + schedule.getAverageFlowTime() + " scheduledOps=" + ops);
        return schedule;
    }

    /**
     * Solves the user's currently active scenario. Bypasses the LLM.
     */
    public Schedule solveActiveScenario() throws IOException, InterruptedException {
        checkAuth(); // Ensure we are logged in
        String url = BASE_URL + "/solve_active_scenario";

        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(url))
                .header("X-Session-Token", this.sessionToken)
                .POST(HttpRequest.BodyPublishers.noBody())
                .build();

        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());

        if (response.statusCode() != 200) {
            throw new IOException("Failed to solve schedule: " + response.body());
        }

        return objectMapper.readValue(response.body(), Schedule.class);
    }
    
    /**
     * Sends a command to the LLM orchestrator for the user's active session.
     */
    public OrchestratorResponse interpretCommand(String commandText, List<Map<String, Object>> history) throws IOException, InterruptedException {
        checkAuth(); // Ensure we are logged in
        String url = BASE_URL + "/interpret";

        ObjectNode requestBody = objectMapper.createObjectNode();
        requestBody.put("command", commandText);
        requestBody.set("history", objectMapper.valueToTree(history));

        String requestBodyString = objectMapper.writeValueAsString(requestBody);

        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(url))
                .header("Content-Type", "application/json")
                .header("X-Session-Token", this.sessionToken) // Add the session token
                .POST(HttpRequest.BodyPublishers.ofString(requestBodyString))
                .build();

        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());

        if (response.statusCode() != 200) {
            throw new IOException("API Error " + response.statusCode() + ": " + response.body());
        }
        String raw = response.body();
        System.out.println("[DEBUG interpretCommand] Raw JSON=" + (raw.length()>600?raw.substring(0,600)+"...":raw));
        OrchestratorResponse resp = objectMapper.readValue(raw, OrchestratorResponse.class);
        if (resp.getSchedule()!=null) {
            Schedule s = resp.getSchedule();
            int ops = (s.getScheduledOperations()==null?0:s.getScheduledOperations().size());
            // This parsing will now work because the backend returns ScheduleRead
            System.out.println("[DEBUG interpretCommand] schedule makespan=" + s.getMakespan() + " ops=" + ops);
        }
        return resp;
    }

    /**
     * Imports data into the user's active scenario from a JSON string.
     */
    public void importData(String jsonContent) throws IOException, InterruptedException {
        checkAuth(); // Ensure we are logged in
        String url = BASE_URL + "/scenario/import_data";
        
        // We send the raw JSON content as the request body.
        // FastAPI will handle parsing it into the ImportRequest model.
        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(url))
                .header("Content-Type", "application/json")
                .header("X-Session-Token", this.sessionToken)
                .POST(HttpRequest.BodyPublishers.ofString(jsonContent))
                .build();

        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());

        if (response.statusCode() != 200) {
            throw new IOException("Failed to import data: " + response.body());
        }
    }

    /**
     * Resets the *entire database* (Developer tool).
     */
    public String resetProblem() throws IOException, InterruptedException {
        checkAuth(); 
        String url = BASE_URL + "/reset";

        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(url))
                .header("X-Session-Token", this.sessionToken) 
                .POST(HttpRequest.BodyPublishers.noBody())
                .build();

        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());

        if (response.statusCode() != 200) {
            throw new IOException("Failed to reset problem state: " + response.body());
        }
        
        JsonNode responseJson = objectMapper.readTree(response.body());
        String newSessionToken = responseJson.get("new_session_token").asText();
        
        this.sessionToken = newSessionToken;
        
        return newSessionToken;
    }
}