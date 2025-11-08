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

    // This will store the session token after a successful login
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
     * @param username The user's username
     * @param password The user's password
     * @return The username of the logged-in user
     * @throws IOException
     * @throws InterruptedException
     */
    public String login(String username, String password) throws IOException, InterruptedException {
        String url = BASE_URL + "/login";

        // Create the request body JSON
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

        // Parse the response to get the token
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

        return objectMapper.readValue(response.body(), new TypeReference<>() {});
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
        return objectMapper.readValue(response.body(), new TypeReference<>() {});
    }

    /**
     * Solves the user's active scenario.
     */
    public Schedule solveProblem() throws IOException, InterruptedException {
        checkAuth(); // Ensure we are logged in
        String url = BASE_URL + "/solve";

        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(url))
                .header("X-Session-Token", this.sessionToken) // Add the session token
                .POST(HttpRequest.BodyPublishers.noBody())
                .build();

        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());

        if (response.statusCode() != 200) {
            throw new IOException("Solver failed: " + response.body());
        }

        return objectMapper.readValue(response.body(), Schedule.class);
    }

    /**
     * Sends a command to the LLM orchestrator for the user's active session.
     */
    public OrchestratorResponse interpretCommand(String commandText, List<Map<String, Object>> history) throws IOException, InterruptedException {
        checkAuth(); // Ensure we are logged in
        String url = BASE_URL + "/interpret";

        // Create the request body JSON
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

        return objectMapper.readValue(response.body(), OrchestratorResponse.class);
    }

    /**
     * Resets the *entire database* (Developer tool).
     * This will invalidate the current session token.
     * @return The *new* session token to use.
     */
    public String resetProblem() throws IOException, InterruptedException {
        checkAuth(); // Ensure we are logged in (though this token will be invalidated)
        String url = BASE_URL + "/reset";

        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(url))
                .header("X-Session-Token", this.sessionToken) // Add the session token
                .POST(HttpRequest.BodyPublishers.noBody())
                .build();

        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());

        if (response.statusCode() != 200) {
            throw new IOException("Failed to reset problem state: " + response.body());
        }
        
        // Parse the response to get the *new* token
        JsonNode responseJson = objectMapper.readTree(response.body());
        String newSessionToken = responseJson.get("new_session_token").asText();
        
        // Automatically update the client's token
        this.sessionToken = newSessionToken;
        
        return newSessionToken;
    }
}