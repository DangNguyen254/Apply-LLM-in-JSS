from pydantic import BaseModel, ConfigDict
from typing import List, Dict, Optional, Any
from sqlalchemy import String, Column, JSON, ForeignKey, Integer, Text, DateTime, Float
from sqlmodel import SQLModel, Field, Relationship
import datetime

# --- Pydantic "Read" Models (NEW) ---

class OperationRead(BaseModel):
    """Pydantic model for reading an Operation."""
    id: str
    machine_group_id: str
    processing_time: int
    predecessors: List[str]

    # --- THIS IS THE FIX ---
    # This tells Pydantic that this model can be created from
    # the attributes of an Operation SQLModel object.
    model_config = ConfigDict(from_attributes=True) 

class JobRead(BaseModel):
    """Pydantic model for reading a Job, including its operations."""
    id: str
    name: str
    priority: int
    scenario_id: int
    operation_list: List[OperationRead] = [] 

    model_config = ConfigDict(from_attributes=True) 

class ScheduledOperationRead(BaseModel):
    """Pydantic model for reading a single scheduled operation."""
    job_id: str
    operation_id: str
    machine_instance_id: str
    start_time: int
    end_time: int
    
    model_config = ConfigDict(from_attributes=True)

class ScheduleRead(BaseModel):
    """Pydantic model for reading a full Schedule, including all operations."""
    id: int
    makespan: int
    average_flow_time: float
    machine_utilization: Dict[str, float]
    timestamp: datetime.datetime
    scenario_id: int
    scheduled_operations: List[ScheduledOperationRead] = [] 

    model_config = ConfigDict(from_attributes=True)


# --- SQLModel Table Definitions (Unchanged) ---

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(sa_column=Column(String(255), unique=True, index=True))
    hashed_password: str = Field(sa_column=Column(String(255)))
    scenarios: List["Scenario"] = Relationship(back_populates="user")
    command_logs: List["CommandLog"] = Relationship(back_populates="user")

class Scenario(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(sa_column=Column(String(255))) 
    user_id: int = Field(sa_column=Column(Integer, ForeignKey("user.id")))
    user: User = Relationship(back_populates="scenarios")
    jobs: List["Job"] = Relationship(back_populates="scenario")
    machine_groups: List["MachineGroup"] = Relationship(back_populates="scenario")
    operations: List["Operation"] = Relationship(back_populates="scenario")
    command_logs: List["CommandLog"] = Relationship(back_populates="scenario")
    schedules: List["Schedule"] = Relationship(
        back_populates="scenario",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )

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

class Schedule(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    makespan: int
    average_flow_time: float = Field(sa_column=Column(Float))
    machine_utilization: Dict[str, float] = Field(sa_column=Column(JSON))
    timestamp: datetime.datetime = Field(
        sa_column=Column(DateTime, default=datetime.datetime.now)
    )
    scenario_id: int = Field(sa_column=Column(Integer, ForeignKey("scenario.id")))
    scenario: Scenario = Relationship(back_populates="schedules")
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
    schedule_id: int = Field(sa_column=Column(Integer, ForeignKey("schedule.id")))
    schedule: Schedule = Relationship(back_populates="scheduled_operations")


# --- Pydantic Models for Solver (Unchanged) ---
class SolverScheduledOperation(BaseModel):
    job_id: str
    operation_id: str
    machine_instance_id: str
    start_time: int
    end_time: int

class SolverSchedule(BaseModel):
    makespan: int
    scheduled_operations: List[SolverScheduledOperation]
    machine_utilization: Dict[str, float]
    average_flow_time: float