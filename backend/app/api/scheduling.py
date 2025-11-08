from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from sqlmodel import Session, select, delete
import google.generativeai as genai
# NEW: Import datetime
import datetime

# Import all models and the get_session function
from ..models.jssp_model import (
    Job, MachineGroup, Operation, Schedule, ScheduledOperation, 
    User, Scenario, CommandLog # NEW: Import CommandLog
)
# We now import create_db_and_tables to run at startup
from ..db.database import get_session, engine, create_db_and_tables
from ..services.jssp_solver import solve_jssp
from ..services.llm_service import interpret_command
from .mock_data import TEST_PROBLEMS # Still needed for reset

from typing import Dict, Any, List, Optional, Tuple, Set, Callable
import copy
import traceback
import json 
import collections.abc
import uuid # For generating unique IDs

from google.protobuf.struct_pb2 import ListValue, Struct, Value
try:
    from google.protobuf.internal.containers import RepeatedCompositeFieldContainer, RepeatedScalarFieldContainer
    PROTO_CONTAINERS = (RepeatedCompositeFieldContainer, RepeatedScalarFieldContainer)
except ImportError:
    PROTO_CONTAINERS = ()
    print("Warning: Could not import Protobuf internal containers.")

router = APIRouter(prefix="/scheduling")

class UserCommand(BaseModel):
    command: str
    history: Optional[List[Dict[str, Any]]] = None

# This model is used for the new /login endpoint
class UserLogin(BaseModel):
    username: str
    password: str

# --- CONTEXT MANAGER (Unchanged) ---
# This class now represents a *single user's session*
class AppContext:
    def __init__(self):
        self.current_user_id: Optional[int] = None
        self.current_scenario_id: Optional[int] = None
        self.last_schedules: Dict[int, Schedule] = {} # Keyed by scenario_id

    def set_user_and_scenario(self, user_id: int, scenario_id: int):
        self.current_user_id = user_id
        self.current_scenario_id = scenario_id
        print(f"AppContext initialized: User ID {user_id}, Scenario ID {scenario_id}")

    def set_scenario(self, scenario_id: int):
        # Clear cache for the old scenario
        if self.current_scenario_id is not None:
             self.clear_last_schedule(self.current_scenario_id)
        self.current_scenario_id = scenario_id

    def get_last_schedule(self) -> Optional[Schedule]:
        if self.current_scenario_id:
            return self.last_schedules.get(self.current_scenario_id)
        return None
    
    def set_last_schedule(self, schedule: Schedule):
        if self.current_scenario_id:
            self.last_schedules[self.current_scenario_id] = schedule

    def clear_last_schedule(self, scenario_id: int):
        if scenario_id in self.last_schedules:
            del self.last_schedules[scenario_id]

# --- NEW SESSION MANAGEMENT ---
# This dictionary holds all active user sessions ("Shopping Carts")
# The key is the session_token (a UUID)
user_sessions: Dict[str, AppContext] = {}

# --- NEW LOGIN ENDPOINT ---
@router.post("/login", tags=["Authentication"], response_model=Dict[str, Any])
def login(login_data: UserLogin, db: Session = Depends(get_session)):
    """
    Handles user login, creates a session context, and returns a session token.
    """
    # Find the user by username
    statement = select(User).where(User.username == login_data.username)
    user = db.exec(statement).first()

    # WARNING: This is not a secure password check.
    # For a real-world system, use a library like 'passlib'
    # to hash passwords. This is just for project functionality.
    if not user or user.hashed_password != login_data.password:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    # Find the user's "Live Data" scenario
    scenario_stmt = select(Scenario).where(Scenario.user_id == user.id, Scenario.name == "Live Data")
    live_scenario = db.exec(scenario_stmt).first()
    
    if not live_scenario:
         raise HTTPException(status_code=404, detail="User has no 'Live Data' scenario. Please reset database.")

    # Create a new session context for this user
    session_token = str(uuid.uuid4())
    new_context = AppContext()
    new_context.set_user_and_scenario(user.id, live_scenario.id)
    
    # Store the context in our server-side session cache
    user_sessions[session_token] = new_context
    
    print(f"User '{user.username}' logged in. Session token {session_token} created.")

    # Return the token and user info to the client
    return {"session_token": session_token, "username": user.username}

# --- NEW DEPENDENCY FUNCTION ---
def get_user_context(
    session_token: str = Header(..., alias="X-Session-Token")
) -> AppContext:
    """
    This FastAPI Dependency reads the 'X-Session-Token' header,
    finds the correct user's AppContext from the session store,
    and injects it into the endpoint.
    """
    context = user_sessions.get(session_token)
    if not context:
        raise HTTPException(status_code=401, detail="Invalid or expired session token.")
    
    # We also do a quick check to make sure the user/scenario still exist
    if not context.current_user_id or not context.current_scenario_id:
        raise HTTPException(status_code=401, detail="User context is incomplete.")
        
    return context


# --- Helper Functions (Unchanged) ---
# These do not need modification as they are pure logic.
def validate_operations(ops_data: Optional[List[Dict[str, Any]]], valid_mg_ids: Set[str]) -> Tuple[bool, str]:
    if not ops_data: return False, "Missing 'operations' data."
    for i, op_data in enumerate(ops_data):
        mg_id = op_data.get("machine_group_id")
        proc_time = op_data.get("processing_time")
        if mg_id not in valid_mg_ids: return False, f"Invalid machine_group_id '{mg_id}' in operation {i}."
        try:
            time_int = int(proc_time)
            if time_int <= 0: raise ValueError("Processing time must be positive.")
            op_data["processing_time"] = time_int
        except (ValueError, TypeError, AssertionError):
            return False, f"Invalid processing_time '{proc_time}' in operation {i} (must be a positive integer)."
    return True, ""

def _find_item_id_by_name(db_items: List[Any], name_query: str) -> Optional[str]:
    if not name_query or not db_items: return None
    name_query_lower = name_query.lower()
    for item in db_items:
        if hasattr(item, 'name') and name_query_lower in item.name.lower():
            return item.id
    return None

def convert_proto_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool, type(None))): return value
    if isinstance(value, ListValue) or (PROTO_CONTAINERS and isinstance(value, PROTO_CONTAINERS)): return [convert_proto_value(item) for item in value]
    if isinstance(value, Struct): return {k: convert_proto_value(v) for k, v in value.items()}
    if isinstance(value, Value):
        kind = value.WhichOneof('kind');
        if kind == 'struct_value': return convert_proto_value(value.struct_value)
        if kind == 'list_value': return convert_proto_value(value.list_value)
        if kind == 'string_value': return value.string_value
        if kind == 'number_value': return value.number_value
        if kind == 'bool_value': return value.bool_value
        if kind == 'null_value': return None
        return None
    if isinstance(value, collections.abc.Sequence): return [convert_proto_value(item) for item in value]
    if isinstance(value, collections.abc.Mapping): return {k: convert_proto_value(v) for k, v in value.items()}
    print(f"Warning: Encountered unknown type during conversion: {type(value)}. Using str(). Value: {value!r}"); return str(value)


# --- API Endpoints (Refactored to use 'get_user_context' dependency) ---
# All endpoints now receive the correct user's context automatically.

@router.get("/machine_groups", response_model=list[MachineGroup], tags=["Scheduling"])
def get_machine_groups(
    db: Session = Depends(get_session),
    context: AppContext = Depends(get_user_context) # Injects the user's session
):
    # Selects machine groups ONLY from the user's active scenario
    statement = select(MachineGroup).where(MachineGroup.scenario_id == context.current_scenario_id)
    return db.exec(statement).all()

@router.get("/jobs", response_model=list[Job], tags=["Scheduling"])
def get_jobs_for_problem(
    db: Session = Depends(get_session),
    context: AppContext = Depends(get_user_context) # Injects the user's session
):
    # Selects jobs ONLY from the user's active scenario
    statement = select(Job).where(Job.scenario_id == context.current_scenario_id)
    return db.exec(statement).all()

@router.post("/solve", response_model=Schedule, tags=["Scheduling"])
def solve_schedule_endpoint(
    db: Session = Depends(get_session),
    context: AppContext = Depends(get_user_context) # Injects the user's session
):
    """
    Solves the *current active scenario* for the logged-in user.
    """
    try:
        # Get data only from the user's active scenario
        jobs = db.exec(select(Job).where(Job.scenario_id == context.current_scenario_id)).all()
        machine_groups = db.exec(select(MachineGroup).where(MachineGroup.scenario_id == context.current_scenario_id)).all()
        
        if not jobs or not machine_groups:
             raise HTTPException(status_code=400, detail="Cannot solve: Active scenario has no jobs or no machine groups.")

        final_schedule = solve_jssp(jobs=jobs, machine_groups=machine_groups)
        if not final_schedule:
            context.clear_last_schedule(context.current_scenario_id)
            raise HTTPException(status_code=500, detail="Solver failed to find a solution.")

        # Save the schedule to the user's session context
        context.set_last_schedule(final_schedule)
        return final_schedule
    except Exception as e:
        context.clear_last_schedule(context.current_scenario_id); traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during solving: {e}")

# --- NEW CONTEXT TOOLS (Refactored for Context) ---
# All tools now take 'context: AppContext' as an argument.
# The orchestrator endpoint will inject this dependency.

def _tool_get_active_scenario(db: Session, context: AppContext) -> Dict[str, Any]:
    """Gets details of the currently active scenario."""
    scenario = db.get(Scenario, context.current_scenario_id)
    if not scenario:
        return {"error": "No active scenario found, though one was selected."}
    return scenario.model_dump()

def _tool_list_scenarios(db: Session, context: AppContext) -> Dict[str, Any]:
    """Lists scenarios for the active user."""
    statement = select(Scenario).where(Scenario.user_id == context.current_user_id)
    scenarios = db.exec(statement).all()
    return {"scenarios": [s.model_dump() for s in scenarios]}

def _tool_select_scenario(db: Session, context: AppContext, scenario_id: int) -> str:
    """Selects an active scenario, verifying the user owns it."""
    scenario = db.get(Scenario, scenario_id)
    if not scenario:
        return f"Error: Scenario ID {scenario_id} not found."
    if scenario.user_id != context.current_user_id:
        return "Error: This scenario does not belong to you."
    
    # This now updates the user's session state
    context.set_scenario(scenario.id)
    return f"Active scenario changed to: '{scenario.name}' (ID: {scenario.id})."

def _tool_rename_scenario(db: Session, context: AppContext, new_name: str) -> str:
    """
    Renames the currently active scenario.
    """
    scenario = db.get(Scenario, context.current_scenario_id)
    if not scenario:
        return "Error: Active scenario not found."
    
    scenario.name = new_name
    db.add(scenario)
    db.commit()
    db.refresh(scenario)
    return f"Active scenario (ID: {context.current_scenario_id}) has been renamed to '{new_name}'."

def _tool_delete_scenario(db: Session, context: AppContext, scenario_id: int) -> str:
    """Deletes a 'what-if' scenario."""
    scenario = db.get(Scenario, scenario_id)
    if not scenario:
        return f"Error: Scenario ID {scenario_id} not found."
    if scenario.user_id != context.current_user_id:
        return "Error: You do not have permission to delete this."
    if scenario.name == "Live Data":
        return "Error: Cannot delete the primary 'Live Data' scenario."
    if scenario.id == context.current_scenario_id:
        return "Error: Cannot delete the currently active scenario. Please select 'Live Data' first."

    # Use cascade delete (set up in jssp_model.py)
    db.delete(scenario)
    db.commit()
    return f"Successfully deleted scenario: '{scenario.name}'."

def _tool_create_scenario(db: Session, context: AppContext, new_scenario_name: str, base_scenario_id: int) -> Dict[str, Any]:
    """
    Copies an existing scenario to create a new "what-if" scenario.
    """
    base_scenario = db.get(Scenario, base_scenario_id)
    if not base_scenario or base_scenario.user_id != context.current_user_id:
        return {"error": f"Base scenario ID {base_scenario_id} not found for this user."}

    # Create the new scenario linked to the correct user
    new_scenario = Scenario(name=new_scenario_name, user_id=context.current_user_id)
    db.add(new_scenario)
    db.commit()
    db.refresh(new_scenario)
    new_scenario_id = new_scenario.id

    # --- Deep Copy Logic ---
    # This logic is complex but robust. It copies all data and remaps foreign keys.
    
    mg_id_map = {} # old_mg_id -> new_mg_id
    base_mgs = db.exec(select(MachineGroup).where(MachineGroup.scenario_id == base_scenario.id)).all()
    for mg in base_mgs:
        # Create a new unique ID for the machine group
        new_id = f"S{new_scenario_id}-{str(uuid.uuid4())[:8]}"
        new_mg = MachineGroup(
            id=new_id, name=mg.name, quantity=mg.quantity,
            scenario_id=new_scenario_id # Link to new scenario
        )
        db.add(new_mg)
        mg_id_map[mg.id] = new_id

    job_id_map = {} # old_job_id -> new_job_id
    op_id_map = {}  # old_op_id -> new_op_id
    base_jobs = db.exec(select(Job).where(Job.scenario_id == base_scenario.id)).all()
    
    new_jobs_list = []
    # First pass: Create new Jobs
    for job in base_jobs:
        new_job_id = f"S{new_scenario_id}-{str(uuid.uuid4())[:8]}"
        new_job = Job(
            id=new_job_id, name=job.name, priority=job.priority,
            scenario_id=new_scenario_id, operation_list=[] # Link to new scenario
        )
        db.add(new_job)
        job_id_map[job.id] = new_job_id
        new_jobs_list.append((new_job, job)) # Store (new_job, old_job)
    
    db.commit() 
    
    all_new_ops = []
    # Second pass: Create new Operations, re-linking Job and MachineGroup FKs
    for new_job, old_job in new_jobs_list:
        # We must re-fetch the old operations using the relationship
        old_ops_list = db.exec(select(Operation).where(Operation.job_id == old_job.id)).all()
        
        for i, op in enumerate(sorted(old_ops_list, key=lambda o: o.id)):
            new_op_id = f"{new_job.id}-OP{i+1}"
            op_id_map[op.id] = new_op_id
            
            new_op = Operation(
                id=new_op_id,
                processing_time=op.processing_time,
                predecessors=[], # Placeholder, will update in next pass
                machine_group_id=mg_id_map[op.machine_group_id], # Use new MG ID
                job_id=new_job.id, # Use new Job ID
                scenario_id=new_scenario_id # Link to new scenario
            )
            all_new_ops.append((new_op, op)) # Store (new_op, old_op)
    
    db.add_all([new_op for new_op, old_op in all_new_ops])
    db.commit()

    # Third pass: Update predecessors using the new Operation IDs
    for new_op, old_op in all_new_ops:
        if old_op.predecessors:
            new_preds = [op_id_map[p_id] for p_id in old_op.predecessors if p_id in op_id_map]
            new_op.predecessors = new_preds
            db.add(new_op)
    
    db.commit()
    db.refresh(new_scenario)
    return new_scenario.model_dump() # Return the new scenario


# --- DATA TOOLS (Refactored for Context) ---
# All tools now use context.current_scenario_id to filter their queries

def _tool_remove_job(db: Session, context: AppContext, job_id: str) -> str:
    scenario_id = context.current_scenario_id
    # Find the job *in the active scenario*
    job_to_remove = db.exec(select(Job).where(Job.id == job_id, Job.scenario_id == scenario_id)).first()
    if not job_to_remove:
        return f"Warning: Job ID '{job_id}' not found in the active scenario."
    
    # Deleting the job will cascade and delete its operations
    db.delete(job_to_remove)
    db.commit()
    return f"Successfully removed Job ID: {job_id}."

def _tool_add_job(db: Session, context: AppContext, operations: List[Dict[str, Any]], job_name: Optional[str] = None, priority: int = 1) -> str:
    scenario_id = context.current_scenario_id
    # Get machine groups *from the active scenario*
    valid_mg_ids = set(db.exec(select(MachineGroup.id).where(MachineGroup.scenario_id == scenario_id)).all())
    is_valid, msg = validate_operations(operations, valid_mg_ids)
    if not is_valid: return f"Error: Invalid operations data. {msg}"

    # Create new Job linked to the active scenario
    new_job_id = f"S{scenario_id}-J{str(uuid.uuid4())[:6]}"
    effective_job_name = job_name if job_name else f"New Job {new_job_id}"
    new_job = Job(id=new_job_id, name=effective_job_name, priority=priority, scenario_id=scenario_id, operation_list=[])

    new_operations = []
    for i, op_data in enumerate(operations):
        op_id = f"{new_job_id}-OP{i+1:02d}"
        predecessors = [f"{new_job_id}-OP{i:02d}"] if i > 0 else []
        new_op = Operation(
            id=op_id, machine_group_id=op_data["machine_group_id"],
            processing_time=op_data["processing_time"], predecessors=predecessors,
            job_id=new_job_id, job=new_job, scenario_id=scenario_id
        )
        new_operations.append(new_op)
    
    new_job.operation_list = new_operations
    db.add(new_job); db.commit(); db.refresh(new_job)
    return f"Successfully added '{effective_job_name}' as Job ID: {new_job_id}."

def _tool_adjust_job(db: Session, context: AppContext, job_id: str, operations: List[Dict[str, Any]]) -> str:
    scenario_id = context.current_scenario_id
    # Get job *from the active scenario*
    job_to_adjust = db.exec(select(Job).where(Job.id == job_id, Job.scenario_id == scenario_id)).first()
    if not job_to_adjust:
        return f"Warning: Job ID '{job_id}' not found in active scenario."
    
    # Get machine groups *from the active scenario*
    valid_mg_ids = set(db.exec(select(MachineGroup.id).where(MachineGroup.scenario_id == scenario_id)).all())
    is_valid, msg = validate_operations(operations, valid_mg_ids)
    if not is_valid: return f"Error: Invalid operations data. {msg}"

    # Delete old operations
    old_ops = db.exec(select(Operation).where(Operation.job_id == job_id)).all()
    for op in old_ops: db.delete(op)
    db.commit() # Commit deletions first
    
    # Create new operations
    new_operations = []
    for i, op_data in enumerate(operations):
        op_id = f"{job_id}-OP{i+1:02d}"
        predecessors = [f"{job_id}-OP{i:02d}"] if i > 0 else []
        new_op = Operation(
            id=op_id, machine_group_id=op_data["machine_group_id"],
            processing_time=op_data["processing_time"], predecessors=predecessors,
            job_id=job_id, job=job_to_adjust, scenario_id=scenario_id
        )
        new_operations.append(new_op)
    
    # Add new operations to the session
    db.add_all(new_operations)
    db.commit()
    
    return f"Successfully adjusted operations for Job ID: {job_id}."

def _tool_modify_job(db: Session, context: AppContext, job_id: str, new_priority: Optional[int] = None, new_job_name: Optional[str] = None) -> str:
    scenario_id = context.current_scenario_id
    # Get job *from the active scenario*
    job_to_modify = db.exec(select(Job).where(Job.id == job_id, Job.scenario_id == scenario_id)).first()
    if not job_to_modify:
        return f"Warning: Job ID '{job_id}' not found in active scenario."
    
    updated_messages = []
    if new_priority is not None:
        job_to_modify.priority = int(new_priority); updated_messages.append("Set priority.")
    if new_job_name is not None:
        job_to_modify.name = str(new_job_name); updated_messages.append("Set name.")
    if not updated_messages: return "No valid properties provided."
    
    db.add(job_to_modify); db.commit(); db.refresh(job_to_modify)
    return f"Modified Job ID {job_id}: {' '.join(updated_messages)}"

def _tool_add_machine_group(db: Session, context: AppContext, name: str, quantity: int) -> str:
    scenario_id = context.current_scenario_id
    if int(quantity) <= 0: return "Error: Quantity must be positive."
    if not name: return "Error: Name is required."
    
    # Create new Machine Group linked to the active scenario
    new_mg_id = f"S{scenario_id}-MG{str(uuid.uuid4())[:6]}"
    new_mg = MachineGroup(id=new_mg_id, name=name, quantity=int(quantity), scenario_id=scenario_id)
    db.add(new_mg); db.commit(); db.refresh(new_mg)
    return f"Added group '{name}' as ID {new_mg_id} with quantity {quantity}."

def _tool_modify_machine_group(db: Session, context: AppContext, mg_id: str, new_name: Optional[str] = None, new_quantity: Optional[int] = None) -> str:
    scenario_id = context.current_scenario_id
    # Get machine group *from the active scenario*
    mg_to_modify = db.exec(select(MachineGroup).where(MachineGroup.id == mg_id, MachineGroup.scenario_id == scenario_id)).first()
    if not mg_to_modify:
        return f"Warning: Group '{mg_id}' not found in active scenario."
    
    updated_messages = []
    if new_name is not None:
        mg_to_modify.name = str(new_name); updated_messages.append("Set name.")
    if new_quantity is not None:
        if int(new_quantity) < 0: updated_messages.append("Warning: Invalid quantity.")
        else: mg_to_modify.quantity = int(new_quantity); updated_messages.append("Set quantity.")
    if not updated_messages: return "No valid properties provided."

    db.add(mg_to_modify); db.commit(); db.refresh(mg_to_modify)
    return f"Modified Group ID {mg_id}: {' '.join(updated_messages)}"

def _tool_swap_operations(db: Session, context: AppContext, job_id: str, idx1: int, idx2: int) -> str:
    scenario_id = context.current_scenario_id
    # Get job *from the active scenario*
    job_to_modify = db.exec(select(Job).where(Job.id == job_id, Job.scenario_id == scenario_id)).first()
    if not job_to_modify:
        return f"Warning: Job ID '{job_id}' not found."
    
    # Get operations for *this job only*
    op_list = sorted(
        db.exec(select(Operation).where(Operation.job_id == job_id)).all(), 
        key=lambda op: op.id
    )
    
    op_count = len(op_list)
    if not (0 <= idx1 < op_count and 0 <= idx2 < op_count): return "Error: Indices out of bounds."
    if idx1 == idx2: return "Warning: Cannot swap with self."
    
    op_list[idx1], op_list[idx2] = op_list[idx2], op_list[idx1]
    
    # Re-ID and re-link all operations for this job
    for i, op in enumerate(op_list):
        op.id = f"{job_to_modify.id}-OP{i+1:02d}"
        op.predecessors = [op_list[i-1].id] if i > 0 else []
        db.add(op)
    db.commit()
    return f"Successfully swapped operations for Job ID: {job_id}."

def _tool_get_current_problem_state(db: Session, context: AppContext) -> Dict[str, Any]:
    scenario_id = context.current_scenario_id
    # Get data *from the active scenario*
    jobs = db.exec(select(Job).where(Job.scenario_id == scenario_id)).all()
    mgs = db.exec(select(MachineGroup).where(MachineGroup.scenario_id == scenario_id)).all()
    return {
        "jobs": [job.model_dump(exclude={'operation_list', 'scenario'}) for job in jobs],
        "machine_groups": [mg.model_dump(exclude={'scenario'}) for mg in mgs]
    }

def _tool_get_job_details(db: Session, context: AppContext, job_id: str) -> Dict[str, Any]:
    scenario_id = context.current_scenario_id
    # Get job *from the active scenario*
    job = db.exec(select(Job).where(Job.id == job_id, Job.scenario_id == scenario_id)).first()
    if not job:
        return {"error": f"Job ID '{job_id}' not found in active scenario."}
    
    job_data = job.model_dump(exclude={'scenario'})
    job_data['operation_list'] = [
        op.model_dump(exclude={'scenario', 'job'}) 
        for op in db.exec(select(Operation).where(Operation.job_id == job_id)).all()
    ]
    return {"job": job_data}

def _tool_get_machine_group_details(db: Session, context: AppContext, machine_group_id: str) -> Dict[str, Any]:
    scenario_id = context.current_scenario_id
    # Get machine group *from the active scenario*
    mg = db.exec(select(MachineGroup).where(MachineGroup.id == machine_group_id, MachineGroup.scenario_id == scenario_id)).first()
    if not mg:
        return {"error": f"Machine Group ID '{machine_group_id}' not found in active scenario."}
    return {"machine_group": mg.model_dump(exclude={'scenario'})}

def _tool_get_schedule_kpis(db: Session, context: AppContext) -> Dict[str, Any]:
    scenario_id = context.current_scenario_id
    # Get schedule *from the active session context*
    last_schedule = context.get_last_schedule()
    if last_schedule:

        avg_flow = round(last_schedule.average_flow_time, 2)
        util = {k: f"{v*100:.2f}%" for k, v in last_schedule.machine_utilization.items()}

        return {
            "makespan": last_schedule.makespan,
            "average_flow_time": avg_flow,
            "machine_utilization": util
        }
    return {"error": f"No schedule has been computed for active scenario {scenario_id}."}

def _tool_solve_schedule(db: Session, context: AppContext) -> Dict[str, Any]:
    scenario_id = context.current_scenario_id
    try:
        # Get data *from the active scenario*
        jobs = db.exec(select(Job).where(Job.scenario_id == scenario_id)).all()
        mgs = db.exec(select(MachineGroup).where(MachineGroup.scenario_id == scenario_id)).all()
        if not jobs or not mgs: return {"error": "Cannot solve: No jobs or machines in scenario."}

        final_schedule = solve_jssp(jobs=jobs, machine_groups=mgs)
        if not final_schedule:
            context.clear_last_schedule(scenario_id)
            return {"error": "Solver failed to find a solution."}
        
        # Save the schedule *to the active session context*
        context.set_last_schedule(final_schedule)

        avg_flow = round(final_schedule.average_flow_time, 2)
        util = {k: f"{v*100:.2f}%" for k, v in final_schedule.machine_utilization.items()}

        return {
            "status": "Success", "makespan": final_schedule.makespan,
            "average_flow_time": avg_flow,
            "machine_utilization": util
        }
    except Exception as e:
        context.clear_last_schedule(scenario_id); traceback.print_exc()
        return {"error": f"An unexpected error occurred during solving: {e}"}

def _tool_simulate_solve(db: Session, context: AppContext) -> Dict[str, Any]:
    scenario_id = context.current_scenario_id
    try:
        # Get data *from the active scenario*
        jobs = db.exec(select(Job).where(Job.scenario_id == scenario_id)).all()
        mgs = db.exec(select(MachineGroup).where(MachineGroup.scenario_id == scenario_id)).all()
        if not jobs or not mgs: return {"error": "Cannot solve: No jobs or machines in scenario."}

        final_schedule = solve_jssp(jobs=jobs, machine_groups=mgs)
        if not final_schedule:
            return {"error": "Solver failed to find a solution."}
        
        avg_flow = round(final_schedule.average_flow_time, 2)
        util = {k: f"{v*100:.2f}%" for k, v in final_schedule.machine_utilization.items()}

        return {
            "status": "Success", "makespan": final_schedule.makespan,
            "average_flow_time": avg_flow,
            "machine_utilization": util
        }
    except Exception as e:
        traceback.print_exc()
        return {"error": f"An unexpected error occurred during solving: {e}"}

def _tool_find_job_id_by_name(db: Session, context: AppContext, job_name: str) -> Dict[str, Optional[str]]:
    scenario_id = context.current_scenario_id
    # Find job *in the active scenario*
    jobs = db.exec(select(Job).where(Job.scenario_id == scenario_id)).all()
    job_id = _find_item_id_by_name(jobs, job_name)
    return {"job_id": job_id}

def _tool_find_machine_group_id_by_name(db: Session, context: AppContext, machine_name: str) -> Dict[str, Optional[str]]:
    scenario_id = context.current_scenario_id
    # Find machine group *in the active scenario*
    mgs = db.exec(select(MachineGroup).where(MachineGroup.scenario_id == scenario_id)).all()
    mg_id = _find_item_id_by_name(mgs, machine_name)
    return {"machine_id": mg_id}

# --- DEVELOPER-ONLY RESET TOOL (Updated) ---
def _developer_tool_reset_all(db: Session, context: AppContext) -> str:
    """
    Resets the entire database, clears all sessions, and returns a NEW
    session token for the 'admin' user.
    """
    try:
        # Clear all sessions
        user_sessions.clear()
        
        # Clear all tables
        # NEW: Delete from CommandLog first
        db.exec(delete(CommandLog))
        db.exec(delete(Operation)); db.exec(delete(Job));
        db.exec(delete(MachineGroup)); db.exec(delete(Scenario));
        db.exec(delete(User));
        
        # We must re-import the populate function from its new home
        from ..db.database import populate_database
        user_id, scenario_id = populate_database(session=db)
        db.commit()
        
        # Re-create and re-cache the session for the 'admin' user
        session_token = str(uuid.uuid4())
        new_context = AppContext()
        new_context.set_user_and_scenario(user_id, scenario_id)
        user_sessions[session_token] = new_context
        
        # We must return the *new token* so the client can use it
        return f"Problem has been reset. New session token: {session_token}"
    except Exception as e:
        db.rollback(); traceback.print_exc()
        return f"Error resetting problem: {e}"

# --- TOOL MAPPING ---
# This map links the string name from the LLM to the actual Python function
tool_function_map: Dict[str, Callable] = {
    "get_active_scenario": _tool_get_active_scenario,
    "list_scenarios": _tool_list_scenarios,
    "select_scenario": _tool_select_scenario,
    "create_scenario": _tool_create_scenario,
    "delete_scenario": _tool_delete_scenario,
    "rename_scenario": _tool_rename_scenario,
    "solve_schedule": _tool_solve_schedule,
    "simulate_solve": _tool_simulate_solve,
    "get_schedule_kpis": _tool_get_schedule_kpis,
    "add_job": _tool_add_job,
    "remove_job": _tool_remove_job,
    "adjust_job": _tool_adjust_job,
    "modify_job": _tool_modify_job,
    "add_machine_group": _tool_add_machine_group,
    "modify_machine_group": _tool_modify_machine_group,
    "swap_operations": _tool_swap_operations,
    "get_current_problem_state": _tool_get_current_problem_state,
    "get_job_details": _tool_get_job_details,
    "get_machine_group_details": _tool_get_machine_group_details,
    "find_job_id_by_name": _tool_find_job_id_by_name,
    "find_machine_group_id_by_name": _tool_find_machine_group_id_by_name,
}

# --- ORCHESTRATOR ENDPOINT (Updated with Logging) ---

@router.post("/interpret", tags=["LLM"], response_model=Dict[str, Any])
async def interpret_user_command_orchestrator(
    command_request: UserCommand, 
    db: Session = Depends(get_session),
    context: AppContext = Depends(get_user_context) # This is the magic!
):
    """
    This endpoint is the main orchestrator.
    It uses the user's session context (injected by `get_user_context`)
    to process their command.
    """
    history = command_request.history or []
    history.append({'role': 'user', 'parts': [{'text': command_request.command}]})
    
    max_turns = 10 # Safety limit
    for turn in range(max_turns):
        print(f"\nTurn {turn} for User {context.current_user_id}")
        
        try:
            # Get the LLM's next desired action (text or tool call)
            llm_response_content_or_error = interpret_command(history=history)

            if isinstance(llm_response_content_or_error, dict) and 'error' in llm_response_content_or_error:
                raise HTTPException(status_code=500, detail=f"LLM Error: {llm_response_content_or_error['error']}")

            llm_response_content = llm_response_content_or_error
            model_turn_parts = []
            
            # Process the response parts
            if llm_response_content.parts:
                for part in llm_response_content.parts:
                    part_dict = {}
                    if hasattr(part, 'text') and part.text:
                        part_dict['text'] = part.text
                    elif hasattr(part, 'function_call') and part.function_call:
                        fc = part.function_call; converted_args = {}
                        if fc.args:
                            for key, value in fc.args.items(): converted_args[key] = convert_proto_value(value)
                        part_dict['function_call'] = {'name': fc.name or 'Unknown', 'args': converted_args}
                    if part_dict: model_turn_parts.append(part_dict)

            if not model_turn_parts:
                raise HTTPException(status_code=500, detail="LLM response empty/unprocessable.")
            
            # Add the model's response (tool call or text) to history
            history.append({'role': 'model', 'parts': model_turn_parts})
            print(f"Appended Model Turn: {json.dumps(history[-1], indent=2)}")

            # Check if the model's response was a tool call
            function_call_part = next((part for part in model_turn_parts if 'function_call' in part), None)

            if function_call_part:
                # --- This is a Tool Call turn ---
                tool_name = function_call_part['function_call'].get('name', 'Unknown')
                tool_args = function_call_part['function_call'].get('args', {})
                print(f"Turn {turn}: LLM requested tool '{tool_name}' with args: {tool_args}")

                if tool_name not in tool_function_map:
                    tool_result = {"error": f"Unknown tool '{tool_name}' requested."}
                else:
                    tool_function = tool_function_map[tool_name]
                    try:
                        # Inject the user's context and the db session
                        tool_result = tool_function(db=db, context=context, **tool_args)
                    except HTTPException as http_exc:
                        tool_result = {"error": f"Tool execution error: {http_exc.detail}"}
                    except TypeError as e: 
                        tool_result = {"error": f"Invalid args for '{tool_name}'. Details: {str(e)}"}
                    except Exception as e: 
                        tool_result = {"error": f"Error executing '{tool_name}': {str(e)}"}

                print(f"Turn {turn}: Tool '{tool_name}' result: {tool_result}")
                
                try: result_content_value = json.dumps(tool_result)
                except TypeError: result_content_value = f"Error: Non-serializable result from '{tool_name}'."

                # Add the tool's result to history for the next loop
                history.append({
                    'role': 'function',
                    'parts': [{'function_response': {'name': tool_name, 'response': {'content': result_content_value}}}]
                })
                print(f"Appended Function Turn: {json.dumps(history[-1], indent=2)}")
                continue # Go to the next turn

            else:
                # --- This is a Final Answer turn ---
                final_answer = "\n".join(part.get('text', '') for part in model_turn_parts if 'text' in part).strip()
                if not final_answer:
                    raise HTTPException(status_code=500, detail="LLM provided an empty response.")
                
                print(f"Turn {turn}: LLM provided final answer. Ending loop.")

                # --- NEW: Write SUCCESS to CommandLog ---
                try:
                    new_log = CommandLog(
                        user_id=context.current_user_id,
                        scenario_id=context.current_scenario_id,
                        user_command=command_request.command,
                        final_response=final_answer,
                        full_history=json.dumps(history), # Store the whole conversation
                        timestamp=datetime.datetime.now()
                    )
                    db.add(new_log)
                    # We commit here, separate from the main session
                    # because logging should not be rolled back if other logic fails
                    db.commit()
                except Exception as log_e:
                    print(f"CRITICAL: Failed to write to audit log: {log_e}")
                    db.rollback() # Rollback the log only
                # --- End of Logging ---

                schedule_to_return = None
                schedule = context.get_last_schedule()
                if schedule:
                    schedule_to_return = schedule.model_dump()
                
                return {
                    "explanation": final_answer, 
                    "history": history,
                    "schedule": schedule_to_return
                }

        except HTTPException as http_exc:
             # --- NEW: Write HTTP ERROR to CommandLog ---
            try:
                new_log = CommandLog(
                    user_id=context.current_user_id,
                    scenario_id=context.current_scenario_id,
                    user_command=command_request.command,
                    final_response=f"HTTPException: {http_exc.detail}",
                    full_history=json.dumps(history),
                    timestamp=datetime.datetime.now()
                )
                db.add(new_log)
                db.commit()
            except Exception as log_e:
                print(f"CRITICAL: Failed to write ERROR to audit log: {log_e}")
                db.rollback()
            # --- End of Logging ---
            print(f"HTTP Exception on Turn {turn}: {http_exc.detail}"); raise http_exc
        
        except Exception as e:
            # --- NEW: Write GENERAL ERROR to CommandLog ---
            try:
                new_log = CommandLog(
                    user_id=context.current_user_id,
                    scenario_id=context.current_scenario_id,
                    user_command=command_request.command,
                    final_response=f"Orchestrator loop error: {e}",
                    full_history=json.dumps(history),
                    timestamp=datetime.datetime.now()
                )
                db.add(new_log)
                db.commit()
            except Exception as log_e:
                print(f"CRITICAL: Failed to write ERROR to audit log: {log_e}")
                db.rollback()
            # --- End of Logging ---
            print(f"Loop error on Turn {turn}: {e}"); traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Orchestrator loop error on turn {turn}: {e}")

    # This exception is for the loop running too long
    raise HTTPException(status_code=500, detail=f"Orchestration exceeded maximum turns ({max_turns}).")

@router.post("/reset", tags=["Scheduling"])
def reset_problem_state_endpoint(
    db: Session = Depends(get_session),
    context: AppContext = Depends(get_user_context)
):
    """
    (Developer-Only Endpoint)
    API endpoint to reset the database to its original mock data.
    This will log out all users and create a new session for you.
    """
    status_or_token = _developer_tool_reset_all(db=db, context=context)
    if status_or_token.startswith("Error"):
         raise HTTPException(status_code=500, detail=status_or_token)
    
    # The client needs the new token to continue
    return {"message": "Database reset successfully.", "new_session_token": status_or_token.split(": ")[-1]}

# --- This runs when the API router is loaded ---
@router.on_event("startup")
def on_startup():
    """
    This function runs when the application starts.
    It creates the DB tables. It no longer sets up a global context.
    """
    print("Running startup event...")
    create_db_and_tables()
    print("Database and tables verified.")