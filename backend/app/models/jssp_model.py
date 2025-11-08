from pydantic import BaseModel
from typing import List, Dict, Optional, Any
# Import String, Column, JSON, AND ForeignKey, Integer
# NEW: Import Text (for long log entries) and DateTime
from sqlalchemy import String, Column, JSON, ForeignKey, Integer, Text, DateTime
# Import the SQLModel base components
from sqlmodel import SQLModel, Field, Relationship
# NEW: Import datetime for timestamping
import datetime

# --- SQLModel Table Definitions ---
# This is our 2-level hierarchy: User -> Scenario -> (Data)

# LEVEL 1: The User (Login/Workspace)
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(sa_column=Column(String(255), unique=True, index=True))
    hashed_password: str = Field(sa_column=Column(String(255)))

    # A User owns multiple "Scenarios" (e.g., "Live", "What-if")
    scenarios: List["Scenario"] = Relationship(back_populates="user")
    
    # NEW: Add relationship to the command logs
    command_logs: List["CommandLog"] = Relationship(back_populates="user")

# LEVEL 2: The Scenario (A specific version of the user's problem)
class Scenario(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(sa_column=Column(String(255))) # e.g., "Live Data", "What-if Breakdown"

    # Link up to the User
    user_id: int = Field(sa_column=Column(Integer, ForeignKey("user.id")))
    user: User = Relationship(back_populates="scenarios")

    # A Scenario contains all the data for that version
    jobs: List["Job"] = Relationship(back_populates="scenario")
    machine_groups: List["MachineGroup"] = Relationship(back_populates="scenario")
    operations: List["Operation"] = Relationship(back_populates="scenario")

    # NEW: Add relationship to the command logs
    command_logs: List["CommandLog"] = Relationship(back_populates="scenario")


# --- NEW COMMAND LOG TABLE ---
# This table stores the audit trail
class CommandLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Use default_factory for a server-side timestamp
    timestamp: datetime.datetime = Field(
        sa_column=Column(DateTime, default=datetime.datetime.now)
    )
    
    # Store the user's raw command
    user_command: str = Field(sa_column=Column(Text))
    # Store the LLM's final text response
    final_response: str = Field(sa_column=Column(Text))
    # Store the entire conversation history as a JSON string
    full_history: str = Field(sa_column=Column(Text))
    
    # Link to the User
    user_id: int = Field(sa_column=Column(Integer, ForeignKey("user.id")))
    user: User = Relationship(back_populates="command_logs")
    
    # Link to the Scenario that was active
    scenario_id: int = Field(sa_column=Column(Integer, ForeignKey("scenario.id")))
    scenario: Scenario = Relationship(back_populates="command_logs")


# --- DATA TABLES (All are now linked to a Scenario) ---

class Job(SQLModel, table=True):
    id: str = Field(sa_column=Column(String(50), primary_key=True))
    name: str = Field(sa_column=Column(String(255)))
    priority: int

    # Link up to the Scenario
    scenario_id: int = Field(sa_column=Column(Integer, ForeignKey("scenario.id")))
    scenario: Scenario = Relationship(back_populates="jobs")

    operation_list: List["Operation"] = Relationship(
        back_populates="job", 
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )

class MachineGroup(SQLModel, table=True):
    id: str = Field(sa_column=Column(String(50), primary_key=True))
    name: str = Field(sa_column=Column(String(255)))
    quantity: int

    # Link up to the Scenario
    scenario_id: int = Field(sa_column=Column(Integer, ForeignKey("scenario.id")))
    scenario: Scenario = Relationship(back_populates="machine_groups")

    operations: List["Operation"] = Relationship(back_populates="machine_group")


class Operation(SQLModel, table=True):
    id: str = Field(sa_column=Column(String(50), primary_key=True))
    processing_time: int
    
    predecessors: List[str] = Field(sa_column=Column(JSON))

    machine_group_id: str = Field(
        sa_column=Column(String(50), ForeignKey("machinegroup.id"), nullable=False)
    )
    job_id: Optional[str] = Field(
        default=None, 
        sa_column=Column(String(50), ForeignKey("job.id"), nullable=True)
    )
    
    # Link up to the Scenario
    scenario_id: int = Field(sa_column=Column(Integer, ForeignKey("scenario.id")))
    scenario: Scenario = Relationship(back_populates="operations")

    # Relationships
    job: Optional[Job] = Relationship(back_populates="operation_list")
    machine_group: MachineGroup = Relationship(back_populates="operations")


# --- Pydantic Output Models ---
# (These are unchanged)

class ScheduledOperation(BaseModel):
    job_id: str
    operation_id: str
    machine_instance_id: str
    start_time: int
    end_time: int

class Schedule(BaseModel):
    makespan: int
    scheduled_operations: List[ScheduledOperation]
    machine_utilization: Dict[str, float]
    average_flow_time: float