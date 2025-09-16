package tdtu.dang.jssp.models;
import com.fasterxml.jackson.annotation.JsonProperty;

public class ScheduledOperation{
    @JsonProperty("job_id")
    private String jobId;

    @JsonProperty("operation_id")
    private String opId;

    @JsonProperty("machine_id")
    private String machineId;

    @JsonProperty("start_time")
    private int startTime;

    @JsonProperty("end_time")
    private int endTime;

    public ScheduledOperation(){

    }

    public ScheduledOperation(String jobId, String opId, String machineId, int startTime, int endTime){
        this.setEndTime(endTime);
        this.setJobId(jobId);
        this.setMachineId(machineId);
        this.setOpId(opId);
        this.setStartTime(startTime);
    }

    public int getEndTime() {
        return endTime;
    }
    public String getJobId() {
        return jobId;
    }
    public String getMachineId() {
        return machineId;
    }
    public String getOpId() {
        return opId;
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
    public void setMachineId(String machineId) {
        this.machineId = machineId;
    }
    public void setOpId(String opId) {
        this.opId = opId;
    }
    public void setStartTime(int startTime) {
        this.startTime = startTime;
    }
}