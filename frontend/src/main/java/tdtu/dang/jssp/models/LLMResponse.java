package tdtu.dang.jssp.models;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;

// Class represents the entire JSON object returned by the /interpret endpoint.
public class LLMResponse {

    private String action;
    private LLMParameters parameters;
    private String explanation;

    public String getAction() {
        return action;
    }
    public String getExplanation() {
        return explanation;
    }
    public LLMParameters getParameters() {
        return parameters;
    }

    public void setAction(String action) {
        this.action = action;
    }
    public void setExplanation(String explanation) {
        this.explanation = explanation;
    }
    public void setParameters(LLMParameters parameters) {
        this.parameters = parameters;
    }

    // Class represents the 'parameters' object in the JSON.
    public static class LLMParameters {
        @JsonProperty("job_id")
        private String jobId;

        @JsonProperty("job_name")
        private String jobName;

        private Integer priority;
        private List<OperationData> operations;

        @JsonProperty("machine_id")
        private String machineId;

        @JsonProperty("machine_name")
        private String machineName;
        
        private boolean availability;

        @JsonProperty("error_message")
        private String errorMessage;

        @JsonProperty("operation_index_1")
        private Integer operationIndex1;

        @JsonProperty("operation_index_2")
        private Integer operationIndex2;

        public String getJobId() {
            return jobId;
        }
        public String getJobName() {
            return jobName;
        }
        public String getMachineId() {
            return machineId;
        }
        public String getMachineName() {
            return machineName;
        }
        public List<OperationData> getOperations() {
            return operations;
        }
        public Integer getPriority() {
            return priority;
        }
        public boolean isAvailability() {
            return availability;
        }   
        public String getErrorMessage() {
            return errorMessage;
        }
        public Integer getOperationIndex1() {
            return operationIndex1;
        }
        public Integer getOperationIndex2() {
            return operationIndex2;
        }


        public void setAvailability(boolean availability) {
            this.availability = availability;
        }
        public void setJobId(String jobId) {
            this.jobId = jobId;
        }
        public void setJobName(String jobName) {
            this.jobName = jobName;
        }
        public void setMachineId(String machineId) {
            this.machineId = machineId;
        }
        public void setMachineName(String machineName) {
            this.machineName = machineName;
        }
        public void setOperations(List<OperationData> operations) {
            this.operations = operations;
        }
        public void setPriority(Integer priority) {
            this.priority = priority;
        }
        public void setErrorMessage(String errorMessage) {
            this.errorMessage = errorMessage;
        }
        public void setOperationIndex1(Integer operationIndex1) {
            this.operationIndex1 = operationIndex1;
        }
        public void setOperationIndex2(Integer operationIndex2) {
            this.operationIndex2 = operationIndex2;
        }


    }

    // This nested class represents an object inside the 'operations' list.
    public static class OperationData {
        @JsonProperty("machine_id")
        private String machineId;

        @JsonProperty("processing_time")
        private int processingTime;

        public String getMachineId() {
            return machineId;
        }
        public int getProcessingTime() {
            return processingTime;
        }
        public void setMachineId(String machineId) {
            this.machineId = machineId;
        }
        public void setProcessingTime(int processingTime) {
            this.processingTime = processingTime;
        }

    }
}