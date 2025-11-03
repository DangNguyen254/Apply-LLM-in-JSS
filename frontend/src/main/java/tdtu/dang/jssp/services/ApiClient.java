package tdtu.dang.jssp.services;

import com.fasterxml.jackson.core.type.TypeReference;
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

public class ApiClient{

    private final HttpClient httpClient;
    private final ObjectMapper objectMapper;
    private static final String BASE_URL = "http://127.0.0.1:8000/api/scheduling"; // Backend server address

    public ApiClient(){
        this.httpClient = HttpClient.newBuilder()
                .version(HttpClient.Version.HTTP_1_1)
                .build();
        this.objectMapper = new ObjectMapper();
    }
    public List<Job> getJobs(String problemId) throws IOException, InterruptedException{
        // Ex: http://127.0.0.1:8000/api/scheduling/jobs?problem_id=problem_2
        String url = BASE_URL + "/jobs?problem_id=" + problemId;

        // Start building a request 
        HttpRequest request = HttpRequest.newBuilder()
            .uri(URI.create(url)) // Set the URL
            .GET()               // Specify the GET method
            .build();            // Build the request

        // Send the request and get the response as a String
        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());

        // Check if the request success
        if(response.statusCode() != 200){
            throw new IOException("Failed to fetch jobs: "+ response.body());
        }

        // Parse the JSON string into a List of JOb
        List<Job> jobs = objectMapper.readValue(response.body(), new TypeReference<List<Job>>() {
            
        });
        return jobs;
    }

    public List<MachineGroup> getMachineGroups(String problemId) throws IOException, InterruptedException {
        String url = BASE_URL + "/machine_groups?problem_id=" + problemId;
        HttpRequest request = HttpRequest.newBuilder().uri(URI.create(url)).GET().build();
        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
        if (response.statusCode() != 200) throw new IOException("Failed to fetch machine groups: " + response.body());
        return objectMapper.readValue(response.body(), new TypeReference<>() {});
    }

    public Schedule solveProblem(String problemId) throws IOException, InterruptedException{
        String url = BASE_URL + "/solve?problem_id=" + problemId;

        // Start buidling request
        HttpRequest request = HttpRequest.newBuilder()
            .uri(URI.create(url))
            .POST(HttpRequest.BodyPublishers.noBody()) // Specify POST with an empty body
            .build();

        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());

        if(response.statusCode() != 200){
            throw new IOException("Solver failed: " + response.body());
        }

        Schedule schedule = objectMapper.readValue(response.body(), Schedule.class);
        return schedule;
    }

    // Send history and receive OrchestratorResponse
    public OrchestratorResponse interpretCommand(String commandText, String problemId, List<Map<String, Object>> history) throws IOException, InterruptedException {
        String url = BASE_URL + "/interpret?problem_id=" + problemId;

        // Create the request body JSON
        ObjectNode requestBody = objectMapper.createObjectNode();
        requestBody.put("command", commandText);
        requestBody.set("history", objectMapper.valueToTree(history));
        
        String requestBodyString = objectMapper.writeValueAsString(requestBody);

        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(url))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(requestBodyString))
                .build();

        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());

        if (response.statusCode() != 200) {
            throw new IOException("API Error " + response.statusCode() + ": " + response.body());
        }

        // Parse response model
        OrchestratorResponse llmResponse = objectMapper.readValue(response.body(), OrchestratorResponse.class);
        return llmResponse;
    }

    public void resetProblem(String problemId) throws IOException, InterruptedException {
        String url = BASE_URL + "/reset?problem_id=" + problemId;

        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(url))
                .POST(HttpRequest.BodyPublishers.noBody())
                .build();

        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());

        if (response.statusCode() != 200) {
            throw new IOException("Failed to reset problem state: " + response.body());
        }
    }
}