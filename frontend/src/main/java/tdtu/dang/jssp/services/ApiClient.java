package tdtu.dang.jssp.services;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import tdtu.dang.jssp.models.*; // Import all your models

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.util.List;

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
    public List<Machine> getMachines(String problemId) throws IOException, InterruptedException{
        String url = BASE_URL + "/machines?problem_id=" + problemId;

        HttpRequest request = HttpRequest.newBuilder()
            .uri(URI.create(url))
            .GET()
            .build();

        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());

        if(response.statusCode() != 200){
            throw new IOException("Failed to fetch machines: "+response.body());
        }

        List<Machine> machines = objectMapper.readValue(response.body(), new TypeReference<List<Machine>>() {
            
        });
        return machines;
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

        // We don't need TypeReference because Schedule is not a generic list
        Schedule schedule = objectMapper.readValue(response.body(), Schedule.class);
        return schedule;
    }

    public LLMResponse interpretCommand(String commandText, String problemId) throws IOException, InterruptedException {
        String url = BASE_URL + "/interpret?problem_id=" + problemId;

        String requestBody = objectMapper.createObjectNode()
                .put("command", commandText)
                .toString();
                
        // Debug print
        // System.out.println(">>> Sending Request Body: " + requestBody);

        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(url))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(requestBody))
                .build();

        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());

        if (response.statusCode() != 200) {
            throw new IOException("API Error " + response.statusCode() + ": " + response.body());
        }

        LLMResponse llmResponse = objectMapper.readValue(response.body(), LLMResponse.class);
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