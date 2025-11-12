package tdtu.dang.jssp.models;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

// This allows Jackson to ignore any extra fields from Python (like 'user', 'jobs')
@JsonIgnoreProperties(ignoreUnknown = true)
public class Scenario {

    private int id;
    private String name;
    private int userId;

    // Getters
    public int getId(){ return id; }
    public String getName() { return name; }
    public int getUserId() { return userId; }

    // Setters (needed for Jackson deserialization)
    public void setId(int id) { this.id = id; }
    public void setName(String name) { this.name = name; }
    public void setUserId(int userId) { this.userId = userId; }

    // This is the important part that will be displayed in the ComboBox
    @Override
    public String toString() {
        return String.format("%s (ID: %d)", this.name, this.id);
    }

    // Optional: Add equals/hashCode for proper ComboBox selection management
    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;
        Scenario scenario = (Scenario) o;
        return id == scenario.id;
    }

    @Override
    public int hashCode() {
        return java.util.Objects.hash(id);
    }
}