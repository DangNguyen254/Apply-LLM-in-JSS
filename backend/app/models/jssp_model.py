from pydantic import BaseModel
from typing import Optional, List

class Operation(BaseModel):
    id: str
    machine_id: str
    processing_time: int
    predecessors: List[str] #List of opers id
    
class Job(BaseModel):
    id: str
    operation_list: List[Operation] #List of ipers id
    priority: int

class Machine(BaseModel):
    id: str
    name: str
    availability: bool = True # Broken or not

class ScheduledOperation(BaseModel):
    job_id: str
    operation_id: str
    machine_id: str
    
    start_time: int
    end_time: int

class Schedule(BaseModel):
    makespan: int
    scheduled_operations: List[ScheduledOperation]  
