package tdtu.dang.jssp.models;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;

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

    public static class LLMParameters {
        // Job-related parameters
        @JsonProperty("job_id")
        private String jobId;
        @JsonProperty("job_name")
        private String jobName;
        private Integer priority;
        private List<OperationData> operations;

        // MachineGroup-related parameters
        @JsonProperty("machine_group_id")
        private String machineGroupId;
        @JsonProperty("machine_name")
        private String machineName;
        private Integer quantity;

        // Swap-related parameters
        @JsonProperty("operation_index_1")
        private Integer operationIndex1;
        @JsonProperty("operation_index_2")
        private Integer operationIndex2;
        
        // Error parameter
        @JsonProperty("error_message")
        private String errorMessage;

        public String getErrorMessage() {
            return errorMessage;
        }
        public String getJobId() {
            return jobId;
        }
        public String getJobName() {
            return jobName;
        }
        public String getMachineGroupId() {
            return machineGroupId;
        }
        public String getMachineName() {
            return machineName;
        }
        public Integer getOperationIndex1() {
            return operationIndex1;
        }
        public Integer getOperationIndex2() {
            return operationIndex2;
        }
        public List<OperationData> getOperations() {
            return operations;
        }
        public Integer getPriority() {
            return priority;
        }
        public Integer getQuantity() {
            return quantity;
        }
        public void setErrorMessage(String errorMessage) {
            this.errorMessage = errorMessage;
        }
        public void setJobId(String jobId) {
            this.jobId = jobId;
        }
        public void setJobName(String jobName) {
            this.jobName = jobName;
        }
        public void setMachineGroupId(String machineGroupId) {
            this.machineGroupId = machineGroupId;
        }
        public void setMachineName(String machineName) {
            this.machineName = machineName;
        }
        public void setOperationIndex1(Integer operationIndex1) {
            this.operationIndex1 = operationIndex1;
        }
        public void setOperationIndex2(Integer operationIndex2) {
            this.operationIndex2 = operationIndex2;
        }
        public void setOperations(List<OperationData> operations) {
            this.operations = operations;
        }
        public void setPriority(Integer priority) {
            this.priority = priority;
        }
        public void setQuantity(Integer quantity) {
            this.quantity = quantity;
        }

    }

    public static class OperationData {
        // UPDATED: to use machine_group_id
        @JsonProperty("machine_group_id")
        private String machineGroupId;

        @JsonProperty("processing_time")
        private int processingTime;

        public String getMachineGroupId() {
            return machineGroupId;
        }
        public int getProcessingTime() {
            return processingTime;
        }
        public void setMachineGroupId(String machineGroupId) {
            this.machineGroupId = machineGroupId;
        }
        public void setProcessingTime(int processingTime) {
            this.processingTime = processingTime;
        }
        
    }
}