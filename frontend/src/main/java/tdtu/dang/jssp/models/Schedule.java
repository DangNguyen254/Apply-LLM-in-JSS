package tdtu.dang.jssp.models;
import java.util.List;
import java.util.Map;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

@JsonIgnoreProperties(ignoreUnknown = true)
public class Schedule{
    private int makespan;

    @JsonProperty("scheduled_operations")
    private List<ScheduledOperation> scheduledOperations;

    @JsonProperty("machine_utilization")
    private Map<String, Double> machineUtilization;
    
    @JsonProperty("average_flow_time")
    private double averageFlowTime;

    public Schedule(){

    }

    public Schedule(int makespan, List<ScheduledOperation> scheduledOperations){
        this.setMakespan(makespan);
        this.setScheduledOperations(scheduledOperations);   
    }
    public double getAverageFlowTime() {
        return averageFlowTime;
    }
    public Map<String, Double> getMachineUtilization() {
        return machineUtilization;
    }
    public int getMakespan() {
        return makespan;
    }
    public List<ScheduledOperation> getScheduledOperations() {
        return scheduledOperations;
    }
    public void setAverageFlowTime(double averageFlowTime) {
        this.averageFlowTime = averageFlowTime;
    }
    public void setMachineUtilization(Map<String, Double> machineUtilization) {
        this.machineUtilization = machineUtilization;
    }
    public void setMakespan(int makespan) {
        this.makespan = makespan;
    }
    public void setScheduledOperations(List<ScheduledOperation> scheduledOperations) {
        this.scheduledOperations = scheduledOperations;
    }
    
}