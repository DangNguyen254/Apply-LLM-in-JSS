from pydantic import BaseModel
from typing import List, Dict

class Operation(BaseModel):
    id: str
    machine_id: str
    processing_time: int
    predecessors: List[str] #List of opers id
    
class Job(BaseModel):
    id: str
    name: str
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
    machine_utilization: Dict[str, float]  # e.g., {"M001": 0.85, "M002": 0.9}
    average_flow_time: float
