package tdtu.dang.jssp.models;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

@JsonIgnoreProperties(ignoreUnknown = true)
public class ScheduledOperation{
    @JsonProperty("job_id")
    private String jobId;

    @JsonProperty("operation_id")
    private String operationId;

    @JsonProperty("machine_instance_id")
    private String machineInstanceId;

    @JsonProperty("start_time")
    private int startTime;

    @JsonProperty("end_time")
    private int endTime;

    public ScheduledOperation(){

    }

    public ScheduledOperation(String jobId, String operationId, String machineInstanceId, int startTime, int endTime){
        this.setEndTime(endTime);
        this.setJobId(jobId);
        this.setMachineInstanceId(machineInstanceId);
        this.setOperationId(operationId);
        this.setStartTime(startTime);
    }

    public int getEndTime() {
        return endTime;
    }
    public String getJobId() {
        return jobId;
    }
    public String getMachineInstanceId() {
        return machineInstanceId;
    }
    public String getOperationId() {
        return operationId;
    }
    public int getStartTime() {
        return startTime;
    }

    public void setEndTime(int endTime) {
        this.endTime = endTime;
    }
    public void setJobId(String jobId) {
        this.jobId = jobId;
    }
    public void setMachineInstanceId(String machineInstanceId) {
        this.machineInstanceId = machineInstanceId;
    }
    public void setOperationId(String operationId) {
        this.operationId = operationId;
    }
    public void setStartTime(int startTime) {
        this.startTime = startTime;
    }
}