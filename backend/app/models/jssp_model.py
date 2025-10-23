from pydantic import BaseModel
from typing import List, Dict

class Operation(BaseModel):
    id: str
    machine_group_id: str
    processing_time: int
    predecessors: List[str]

class Job(BaseModel):
    id: str
    name: str
    operation_list: List[Operation]
    priority: int

class MachineGroup(BaseModel):
    id: str
    name: str
    quantity: int # = 0 mean broken or unavail

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