package tdtu.dang.jssp.models;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;

@JsonIgnoreProperties(ignoreUnknown = true)
public class Job {
    private String id;
    private String name;
    private int priority;
    
    @JsonProperty("operation_list") 
    private List<Operation> opList;

    // Getters
    public String getId() { return id; }
    public String getName() { return name; }
    public int getPriority() { return priority; }
    public List<Operation> getOpList() { return opList; }

    // Setters
    public void setId(String id) { this.id = id; }
    public void setName(String name) { this.name = name; }
    public void setPriority(int priority) { this.priority = priority; }
    public void setOpList(List<Operation> opList) { this.opList = opList; }
}