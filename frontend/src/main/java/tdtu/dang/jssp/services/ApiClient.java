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
    private static final String BASE_URL = "http://127.0.0.1:8000/api/scheduling"; // Backend server address

    private String sessionToken;

    public ApiClient() {
        this.httpClient = HttpClient.newBuilder()
                .version(HttpClient.Version.HTTP_1_1)
                .build();
        this.objectMapper = new ObjectMapper();
        this.sessionToken = null; // Start as logged out
    }

    /**
     * Attempts to log in to the backend. If successful, stores the
     * session token for all future requests.
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

        if (response.statusCode() != 200) {
            throw new IOException("Login failed: " + response.body());
        }

        JsonNode responseJson = objectMapper.readTree(response.body());
        this.sessionToken = responseJson.get("session_token").asText();
        String loggedInUsername = responseJson.get("username").asText();
        
        System.out.println("Login successful. Token set.");
        return loggedInUsername;
    }

    /**
     * Checks if the client is authenticated (has a session token).
     */
    private void checkAuth() throws IOException {
        if (this.sessionToken == null || this.sessionToken.isEmpty()) {
            throw new IOException("Client is not authenticated. Please call login() first.");
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
     * (DELETED) The solveProblem() method has been removed.
     * All solving is now done via interpretCommand("solve").
     */

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