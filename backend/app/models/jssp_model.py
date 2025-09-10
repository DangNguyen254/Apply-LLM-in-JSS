from pydantic import BaseModel
from typing import Optional, List

class Job(BaseModel):
    id: str
    operation_list: List[str] #List of ipers id
    priority: int

class Operation(BaseModel):
    id: str
    machine_id: str
    processing_time: int
    predecessors: List[str] #List of opers id

class Machine(BaseModel):
    id: str
    name: str
    availability: bool

class ScheduledOperation(BaseModel):
    job_id: str
    operation_id: str
    machine_id: str
    
    start_time: int
    end_time: int

class Schedule(BaseModel):
    makespan: int
    scheduled_operations: List[ScheduledOperation]  