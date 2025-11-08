package tdtu.dang.jssp.models;
import java.util.List;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

@JsonIgnoreProperties(ignoreUnknown = true)
public class Operation{
    private String id;

    @JsonProperty("machine_group_id")
    private String machineGroupId;

    @JsonProperty("processing_time")
    private int processingTime;
    
    private List<String> predecessors; // List of predecessors id

    public Operation(){

    }

    public Operation(String id, String machineGroupId, int processingTime, List<String> predecessors){
        this.setId(id);
        this.setMachineGroupId(machineGroupId); 
        this.setPredecessors(predecessors);
        this.setProcessingTime(processingTime);
    }

    public String getId() {
        return id;
    }
    public String getMachineGroupId() {
        return machineGroupId;
    }
    public List<String> getPredecessors() {
        return predecessors;
    }
    public int getProcessingTime() {
        return processingTime;
    }
    public void setId(String id) {
        this.id = id;
    }

    public void setMachineGroupId(String machineGroupId) {
        this.machineGroupId = machineGroupId;
    }
    public void setPredecessors(List<String> predecessors) {
        this.predecessors = predecessors;
    }
    public void setProcessingTime(int processingTime) {
        this.processingTime = processingTime;
    }

}