package tdtu.dang.jssp.models;
import java.util.List;
import com.fasterxml.jackson.annotation.JsonProperty;

public class Operation{
    private String id;

    @JsonProperty("machine_id")
    private String machineId;

    @JsonProperty("processing_time")
    private int processingTime;
    private List<String> predecessors; // List of predecessors id

    public Operation(){

    }

    public Operation(String id, String machineId, int processingTime, List<String> predecessors){
        this.setId(id);
        this.setMachineId(machineId); 
        this.setPredecessors(predecessors);
        this.setProcessingTime(processingTime);
    }

    public String getId() {
        return id;
    }
    public String getMachineId() {
        return machineId;
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

    public void setMachineId(String machineId) {
        this.machineId = machineId;
    }
    public void setPredecessors(List<String> predecessors) {
        this.predecessors = predecessors;
    }
    public void setProcessingTime(int processingTime) {
        this.processingTime = processingTime;
    }

}