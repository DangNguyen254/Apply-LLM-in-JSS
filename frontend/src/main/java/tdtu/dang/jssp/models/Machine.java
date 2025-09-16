package tdtu.dang.jssp.models;

public class Machine{
    private String id;
    private String name;
    private boolean availability = true; // Broken or not

    public Machine(){

    }
    
    public Machine(String id, String name, boolean availability){
        this.setAvailability(availability);
        this.setId(id);
        this.setName(name);
    }

    public String getId() {
        return id;
    }
    public String getName() {
        return name;
    }
    public boolean isAvailability(){
        return availability;
    }

    public void setAvailability(boolean availability) {
        this.availability = availability;
    }
    public void setId(String id) {
        this.id = id;
    }
    public void setName(String name) {
        this.name = name;
    }

}