package tdtu.dang.jssp.models;
import java.util.List;
import com.fasterxml.jackson.annotation.JsonProperty;

public class Schedule{
    private int makespan;

    @JsonProperty("scheduled_operations")
    private List<ScheduledOperation> scheduledOperations;

    public Schedule(){

    }

    public Schedule(int makespan, List<ScheduledOperation> scheduledOperations){
        this.setMakespan(makespan);
        this.setScheduledOperations(scheduledOperations);   
    }

    public int getMakespan() {
        return makespan;
    }
    public List<ScheduledOperation> getScheduledOperations() {
        return scheduledOperations;
    }
    public void setMakespan(int makespan) {
        this.makespan = makespan;
    }
    public void setScheduledOperations(List<ScheduledOperation> scheduledOperations) {
        this.scheduledOperations = scheduledOperations;
    }
}