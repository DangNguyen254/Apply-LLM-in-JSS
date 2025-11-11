from pydantic import BaseModel
from typing import List, Dict, Optional, Any
# Import String, Column, JSON, AND ForeignKey, Integer, Text, DateTime
from sqlalchemy import String, Column, JSON, ForeignKey, Integer, Text, DateTime
# Import the SQLModel base components
from sqlmodel import SQLModel, Field, Relationship
# Import datetime for timestamping
import datetime

# --- SQLModel Table Definitions ---

# LEVEL 1: The User (Login/Workspace)
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(sa_column=Column(String(255), unique=True, index=True))
    hashed_password: str = Field(sa_column=Column(String(255)))

    # A User owns multiple "Scenarios"
    scenarios: List["Scenario"] = Relationship(back_populates="user")
    
    # A User owns multiple "Logs"
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

    # A Scenario owns multiple "Logs"
    command_logs: List["CommandLog"] = Relationship(back_populates="scenario")
    
    # NEW: A Scenario can have many "Schedules" (solutions)
    schedules: List["Schedule"] = Relationship(
        back_populates="scenario",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"} # Delete schedules if scenario is deleted
    )


# --- LOGGING TABLE ---
class CommandLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    
    timestamp: datetime.datetime = Field(
        sa_column=Column(DateTime, default=datetime.datetime.now)
    )
    
    user_command: str = Field(sa_column=Column(Text))
    final_response: str = Field(sa_column=Column(Text))
    full_history: str = Field(sa_column=Column(Text))
    
    user_id: int = Field(sa_column=Column(Integer, ForeignKey("user.id")))
    user: User = Relationship(back_populates="command_logs")
    
    scenario_id: int = Field(sa_column=Column(Integer, ForeignKey("scenario.id")))
    scenario: Scenario = Relationship(back_populates="command_logs")


# --- DATA TABLES (All are now linked to a Scenario) ---

class Job(SQLModel, table=True):
    id: str = Field(sa_column=Column(String(50), primary_key=True))
    name: str = Field(sa_column=Column(String(255)))
    priority: int

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
    
    scenario_id: int = Field(sa_column=Column(Integer, ForeignKey("scenario.id")))
    scenario: Scenario = Relationship(back_populates="operations")

    job: Optional[Job] = Relationship(back_populates="operation_list")
    machine_group: MachineGroup = Relationship(back_populates="operations")


# --- NEW: SCHEDULE RESULT TABLES ---
# These models are now SQLModel tables to persist results

class Schedule(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    
    makespan: int
    average_flow_time: float
    machine_utilization: Dict[str, float] = Field(sa_column=Column(JSON))
    
    timestamp: datetime.datetime = Field(
        sa_column=Column(DateTime, default=datetime.datetime.now)
    )

    # Link back to the Scenario this schedule is for
    scenario_id: int = Field(sa_column=Column(Integer, ForeignKey("scenario.id")))
    scenario: Scenario = Relationship(back_populates="schedules")

    # This schedule owns many scheduled operations
    scheduled_operations: List["ScheduledOperation"] = Relationship(
        back_populates="schedule",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )


class ScheduledOperation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    
    job_id: str = Field(sa_column=Column(String(50)))
    operation_id: str = Field(sa_column=Column(String(50)))
    machine_instance_id: str = Field(sa_column=Column(String(100)))
    start_time: int
    end_time: int

    # Link back to the parent Schedule this operation belongs to
    schedule_id: int = Field(sa_column=Column(Integer, ForeignKey("schedule.id")))
    schedule: Schedule = Relationship(back_populates="scheduled_operations")