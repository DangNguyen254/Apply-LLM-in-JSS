package tdtu.dang.jssp.models;
import java.util.List;
import com.fasterxml.jackson.annotation.JsonProperty;

public class Job{
    private String id;
    private int priority;

    @JsonProperty("operation_list")
    private List<Operation> opList;

    public Job(){

    }

    public Job(String id, int priority, List<Operation> opList){
        this.setId(id);
        this.setOpList(opList);
        this.setPriority(priority);
    }

    public String getId() {
        return id;
    }
    public List<Operation> getOpList() {
        return opList;
    }
    public int getPriority() {
        return priority;
    }
    public void setId(String id) {
        this.id = id;
    }
    public void setOpList(List<Operation> opList) {
        this.opList = opList;
    }
    public void setPriority(int priority) {
        this.priority = priority;
    }

}