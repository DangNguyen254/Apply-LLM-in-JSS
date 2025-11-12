from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from sqlmodel import Session, select, delete
from sqlalchemy.orm import selectinload
import google.generativeai as genai
# NEW: Import datetime
import datetime

# Import all models and the get_session function
from ..models.jssp_model import (
    Job, MachineGroup, Operation, 
    Schedule, ScheduledOperation, # These are the DB tables
    User, Scenario, CommandLog,
    JobRead, ScheduleRead, # These are the Pydantic (JSON) models
    SolverSchedule, SolverScheduledOperation # These are the solver output models
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

class BlankScenarioRequest(BaseModel):
    name: str

class ImportOperation(BaseModel):
    machine_group_id: str  # The ID of the machine group
    processing_time: int

class ImportJob(BaseModel):
    name: str
    priority: int = 1
    operations: List[ImportOperation]

class ImportMachineGroup(BaseModel):
    name: str
    quantity: int

class ImportRequest(BaseModel):
    machine_groups: Optional[List[ImportMachineGroup]] = None
    jobs: Optional[List[ImportJob]] = None

# --- CONTEXT MANAGER (Unchanged) ---
class AppContext:
    def __init__(self):
        self.current_user_id: Optional[int] = None
        self.current_scenario_id: Optional[int] = None

    def set_user_and_scenario(self, user_id: int, scenario_id: int):
        self.current_user_id = user_id
        self.current_scenario_id = scenario_id
        print(f"AppContext initialized: User ID {user_id}, Scenario ID {scenario_id}")

    def set_scenario(self, scenario_id: int):
        self.current_scenario_id = scenario_id

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

@router.post("/logout", tags=["Authentication"], response_model=Dict[str, str])
def logout(
    session_token: str = Header(..., alias="X-Session-Token")
):
    """
    Logs the user out by invalidating their session token.
    """
    if session_token in user_sessions:
        del user_sessions[session_token]
        print(f"Session token {session_token} invalidated.")
        return {"message": "Logged out successfully"}
    
    # If the token is already invalid, it's still a success
    return {"message": "No active session found, logged out."}

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
@router.get("/machine_groups", response_model=list[MachineGroup], tags=["Scheduling"])
def get_machine_groups(
    db: Session = Depends(get_session),
    context: AppContext = Depends(get_user_context) 
):
    statement = select(MachineGroup).where(MachineGroup.scenario_id == context.current_scenario_id)
    return db.exec(statement).all()

@router.get("/jobs", response_model=list[JobRead], tags=["Scheduling"])
def get_jobs_for_problem(
    db: Session = Depends(get_session),
    context: AppContext = Depends(get_user_context) 
):
    """
    Fetches all jobs for the active scenario, with their operations
    eagerly loaded to populate the frontend TreeView.
    """
    statement = (
        select(Job)
        .where(Job.scenario_id == context.current_scenario_id)
        .options(selectinload(Job.operation_list)) 
    )
    jobs = db.exec(statement).all()
    # Convert SQLModel objects to Pydantic JobRead objects
    return [JobRead.model_validate(job) for job in jobs]

@router.get("/get_latest_schedule", response_model=ScheduleRead, tags=["Scheduling"])
def get_latest_schedule_for_scenario(
    db: Session = Depends(get_session),
    context: AppContext = Depends(get_user_context)
):
    """
    Fetches the most recent, complete schedule from the database
    for the user's active scenario.
    """
    schedule = db.exec(
        select(Schedule)
        .where(Schedule.scenario_id == context.current_scenario_id)
        .order_by(Schedule.timestamp.desc()) # Get the newest one
        .options(selectinload(Schedule.scheduled_operations)) # Eager load operations
    ).first()
    
    if not schedule:
        raise HTTPException(status_code=404, detail="No schedule has been saved for this scenario yet.")
    
    # Convert to the Pydantic Read model to include operations
    return ScheduleRead.model_validate(schedule)

# OBSOLETE: The /solve endpoint is now handled by the LLM tool
# The frontend "Solve" button will call /interpret with the command "solve"
# We keep this (unused) for now to avoid breaking old frontend builds, but it's deprecated.
@router.post("/solve", response_model=ScheduleRead, tags=["Scheduling (Deprecated)"])
def solve_schedule_endpoint_DEPRECATED(
    db: Session = Depends(get_session),
    context: AppContext = Depends(get_user_context) 
):
    """
    DEPRECATED: This is now handled by the '_tool_solve_schedule' tool.
    This endpoint will solve and SAVE the schedule.
    """
    # We just call the tool function directly
    result = _tool_solve_schedule(db, context)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    # Fetch the schedule we just saved
    return get_latest_schedule_for_scenario(db, context)

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

def _tool_rename_scenario(db: Session, context: AppContext, new_name: str) -> str:
    """
    Renames the currently active scenario.
    """
    scenario = db.get(Scenario, context.current_scenario_id)
    if not scenario:
        return "Error: Active scenario not found."
    
    if scenario.name == "Live Data":
        return "Error: Cannot rename the primary 'Live Data' scenario."
    
    # Check if the new name is a reserved temporary name
    if new_name.startswith("temp-what-if-simulation"):
        return "Error: Cannot use a reserved temporary name."

    scenario.name = new_name
    db.add(scenario)
    db.commit()
    db.refresh(scenario)
    return f"Active scenario (ID: {context.current_scenario_id}) has been renamed to '{new_name}'."

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

@router.put("/scenarios/{scenario_id}", response_model=Scenario, tags=["Scenario Management"])
def rename_scenario_endpoint(
    scenario_id: int,
    request_data: BlankScenarioRequest, # Re-using the simple {name: "..."} model
    db: Session = Depends(get_session),
    context: AppContext = Depends(get_user_context)
):
    """
    Renames a specific scenario. Bypasses the LLM.
    """
    scenario = db.get(Scenario, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found.")
    
    if scenario.user_id != context.current_user_id:
        raise HTTPException(status_code=403, detail="User does not have access to this scenario.")

    if scenario.name == "Live Data":
        raise HTTPException(status_code=400, detail="Cannot rename the 'Live Data' scenario.")
        
    if not request_data.name or request_data.name.startswith("temp-what-if"):
        raise HTTPException(status_code=400, detail="Invalid or reserved scenario name.")

    scenario.name = request_data.name
    db.add(scenario)
    db.commit()
    db.refresh(scenario)
    return scenario

@router.post("/scenario/import_data", response_model=Dict[str, str], tags=["Scenario Management"])
def import_data_to_scenario(
    request_data: ImportRequest,
    db: Session = Depends(get_session),
    context: AppContext = Depends(get_user_context)
):
    """
    Imports a set of new machines and/or jobs into the active scenario.
    This re-uses the internal tool logic for adding items.
    """
    scenario_id = context.current_scenario_id
    
    # 1. Add Machine Groups
    if request_data.machine_groups:
        for mg in request_data.machine_groups:
            _tool_add_machine_group(db, context, mg.name, mg.quantity)
            
    # --- THIS IS THE FIX ---
    # We must explicitly "expire" the session's cache.
    # This forces the next 'select' to fetch the new machine groups
    # we just committed from the database, rather than using its old cache.
    db.expire_all()
    # --- END OF FIX ---

    # 2. Build a lookup map of ALL machine group names to their IDs
    all_mgs_in_scenario = db.exec(
        select(MachineGroup).where(MachineGroup.scenario_id == scenario_id)
    ).all()
    
    name_to_id_map = {mg.name: mg.id for mg in all_mgs_in_scenario}

    # 3. Add Jobs
    if request_data.jobs:
        for job in request_data.jobs:
            ops_list = []
            for op in job.operations:
                if op.machine_group_id not in name_to_id_map:
                    raise HTTPException(
                        status_code=400, 
                        detail=f"Job '{job.name}' references unknown machine group name: {op.machine_group_id}"
                    )
                
                actual_machine_id = name_to_id_map[op.machine_group_id]
                
                ops_list.append({
                    "machine_group_id": actual_machine_id,
                    "processing_time": op.processing_time
                })
            
            _tool_add_job(db, context, ops_list, job.name, job.priority)

    return {"message": "Data imported successfully into active scenario."}

@router.get("/scenarios", response_model=list[Scenario], tags=["Scenario Management"])
def get_user_scenarios(
    db: Session = Depends(get_session),
    context: AppContext = Depends(get_user_context)
):
    """
    Fetches a list of all scenarios (e.g., "Live Data", "What-If 1")
    that belong to the currently authenticated user.
    """
    statement = select(Scenario).where(Scenario.user_id == context.current_user_id)
    scenarios = db.exec(statement).all()
    return scenarios

@router.post("/scenario/create_blank", response_model=Scenario, tags=["Scenario Management"])
def create_blank_scenario(
    request_data: BlankScenarioRequest,
    db: Session = Depends(get_session),
    context: AppContext = Depends(get_user_context)
):
    """
    Creates a new, completely blank scenario for the current user.
    """
    if not request_data.name or request_data.name.startswith("temp-what-if"):
        raise HTTPException(status_code=400, detail="Invalid or reserved scenario name.")

    new_scenario = Scenario(name=request_data.name, user_id=context.current_user_id)
    db.add(new_scenario)
    db.commit()
    db.refresh(new_scenario)
    return new_scenario

@router.post("/select_scenario/{scenario_id}", response_model=Dict[str, Any], tags=["Scenario Management"])
def select_user_scenario(
    scenario_id: int,
    db: Session = Depends(get_session),
    context: AppContext = Depends(get_user_context)
):
    """
    Sets the 'active' scenario in the user's session context.
    All future API calls (e.g., solve, add_job) will apply to this scenario.
    """
    scenario = db.get(Scenario, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found.")
    
    if scenario.user_id != context.current_user_id:
        raise HTTPException(status_code=403, detail="User does not have access to this scenario.")

    # This updates the session state on the server
    context.set_scenario(scenario.id)
    
    print(f"User {context.current_user_id} switched active scenario to: {scenario.name} (ID: {scenario.id})")
    return {"message": "Active scenario changed", "scenario_id": scenario.id, "scenario_name": scenario.name}

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
    
    # Get all MachineGroup objects for this scenario
    all_mgs = db.exec(select(MachineGroup).where(MachineGroup.scenario_id == scenario_id)).all()
    valid_mg_ids = {mg.id for mg in all_mgs}
    name_to_id_map = {mg.name: mg.id for mg in all_mgs}

    # Validate and translate operations
    translated_ops = []
    for i, op_data in enumerate(operations):
        mg_id_or_name = op_data.get("machine_group_id")
        proc_time = op_data.get("processing_time")
        
        final_mg_id = None
        if mg_id_or_name in valid_mg_ids:
            final_mg_id = mg_id_or_name  # It was a valid ID
        elif mg_id_or_name in name_to_id_map:
            final_mg_id = name_to_id_map[mg_id_or_name] # It was a name, we translated it
        
        if not final_mg_id:
            return f"Error: Invalid machine_group_id or name '{mg_id_or_name}' in operation {i}."

        try:
            time_int = int(proc_time)
            if time_int <= 0: raise ValueError("Processing time must be positive")
            op_data["processing_time"] = time_int
        except Exception:
            return f"Error: Invalid processing_time '{proc_time}' in operation {i}."
        
        translated_ops.append({
            "machine_group_id": final_mg_id,
            "processing_time": op_data["processing_time"]
        })

    # Create new Job linked to the active scenario
    new_job_id = f"S{scenario_id}-J{str(uuid.uuid4())[:6]}"
    effective_job_name = job_name if job_name else f"New Job {new_job_id}"
    new_job = Job(id=new_job_id, name=effective_job_name, priority=priority, scenario_id=scenario_id, operation_list=[])

    new_operations = []
    for i, op_data in enumerate(translated_ops):
        op_id = f"{new_job_id}-OP{i+1:02d}"
        predecessors = [f"{new_job_id}-OP{i:02d}"] if i > 0 else []
        new_op = Operation(
            id=op_id,
            machine_group_id=op_data["machine_group_id"],
            processing_time=op_data["processing_time"],
            predecessors=predecessors,
            job_id=new_job_id, 
            job=new_job, 
            scenario_id=scenario_id
        )
        new_operations.append(new_op)
    
    new_job.operation_list = new_operations
    db.add(new_job); db.commit(); db.refresh(new_job)
    return f"Successfully added '{effective_job_name}' as Job ID: {new_job_id}."

def _tool_adjust_job(db: Session, context: AppContext, job_id: str, operations: List[Dict[str, Any]]) -> str:
    scenario_id = context.current_scenario_id
    
    job_to_adjust = db.exec(select(Job).where(Job.id == job_id, Job.scenario_id == scenario_id)).first()
    if not job_to_adjust:
        return f"Warning: Job ID '{job_id}' not found in active scenario."
    
    # Get all MachineGroup objects for this scenario
    all_mgs = db.exec(select(MachineGroup).where(MachineGroup.scenario_id == scenario_id)).all()
    valid_mg_ids = {mg.id for mg in all_mgs}
    name_to_id_map = {mg.name: mg.id for mg in all_mgs}

    # Validate and translate operations
    translated_ops = []
    for i, op_data in enumerate(operations):
        mg_id_or_name = op_data.get("machine_group_id")
        proc_time = op_data.get("processing_time")
        
        final_mg_id = None
        if mg_id_or_name in valid_mg_ids:
            final_mg_id = mg_id_or_name  # It was a valid ID
        elif mg_id_or_name in name_to_id_map:
            final_mg_id = name_to_id_map[mg_id_or_name] # It was a name, we translated it
        
        if not final_mg_id:
            return f"Error: Invalid machine_group_id or name '{mg_id_or_name}' in operation {i}."

        try:
            time_int = int(proc_time)
            if time_int <= 0: raise ValueError("Processing time must be positive")
            op_data["processing_time"] = time_int
        except Exception:
            return f"Error: Invalid processing_time '{proc_time}' in operation {i}."
        
        translated_ops.append({
            "machine_group_id": final_mg_id,
            "processing_time": op_data["processing_time"]
        })

    # Delete old operations
    old_ops = db.exec(select(Operation).where(Operation.job_id == job_id)).all()
    for op in old_ops: db.delete(op)
    db.commit()
    
    # Create new operations
    new_operations = []
    for i, op_data in enumerate(translated_ops):
        op_id = f"{job_id}-OP{i+1:02d}"
        predecessors = [f"{job_id}-OP{i:02d}"] if i > 0 else []
        new_op = Operation(
            id=op_id,
            machine_group_id=op_data["machine_group_id"],
            processing_time=op_data["processing_time"],
            predecessors=predecessors,
            job_id=job_id, 
            job=job_to_adjust, 
            scenario_id=scenario_id
        )
        new_operations.append(new_op)
    
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
    """
    Fetches the KPIs of the LATEST schedule saved in the database
    for the user's active scenario.
    """
    scenario_id = context.current_scenario_id
    
    # Get the most recent schedule from the DB
    schedule = db.exec(
        select(Schedule)
        .where(Schedule.scenario_id == scenario_id)
        .order_by(Schedule.timestamp.desc())
    ).first()
    
    if schedule:
        # Format the KPIs for the LLM
        avg_flow = round(schedule.average_flow_time, 2)
        util = {k: round(v, 4) for k, v in schedule.machine_utilization.items()}
        
        return {
            "makespan": schedule.makespan,
            "average_flow_time": avg_flow,
            "machine_utilization": util
        }
    return {"error": f"No schedule has been computed for active scenario {scenario_id}."}

def _tool_solve_schedule(db: Session, context: AppContext) -> Dict[str, Any]:
    """
    Solves the active scenario, SAVES the new schedule to the database,
    and returns the KPIs.
    """
    scenario_id = context.current_scenario_id
    try:
        # 1. Get data from the active scenario
        jobs = db.exec(select(Job).where(Job.scenario_id == scenario_id)).all()
        mgs = db.exec(select(MachineGroup).where(MachineGroup.scenario_id == scenario_id)).all()
        if not jobs or not mgs: 
            return {"error": "Cannot solve: No jobs or machines in scenario."}

        # 2. Run the solver
        solver_result: Optional[SolverSchedule] = solve_jssp(jobs=jobs, machine_groups=mgs)
        if not solver_result:
            return {"error": "Solver failed to find a solution."}
        
        # 3. Clear old schedules for this scenario
        old_schedules = db.exec(select(Schedule).where(Schedule.scenario_id == scenario_id)).all()
        for s in old_schedules:
            db.delete(s)
        # We commit the deletion separately
        db.commit() 
        
        # 4. Create the new Schedule DB object
        new_schedule_db = Schedule(
            makespan=solver_result.makespan,
            average_flow_time=solver_result.average_flow_time,
            machine_utilization=solver_result.machine_utilization,
            scenario_id=scenario_id,
            timestamp=datetime.datetime.now()
        )
        db.add(new_schedule_db)
        
        # 5. Create all the new ScheduledOperation DB objects
        new_ops_db = []
        for op_result in solver_result.scheduled_operations:
            new_ops_db.append(
                ScheduledOperation(
                    job_id=op_result.job_id,
                    operation_id=op_result.operation_id,
                    machine_instance_id=op_result.machine_instance_id,
                    start_time=op_result.start_time,
                    end_time=op_result.end_time,
                    schedule=new_schedule_db # Link to the parent schedule
                )
            )
        db.add_all(new_ops_db)
        
        # 6. Commit the new schedule to the database
        db.commit()
        db.refresh(new_schedule_db)

        # 7. Format KPIs for the LLM
        avg_flow = round(new_schedule_db.average_flow_time, 2)
        util = {k: round(v, 4) for k, v in new_schedule_db.machine_utilization.items()}
        
        return {
            "status": "Success", 
            "makespan": new_schedule_db.makespan,
            "average_flow_time": avg_flow,
            "machine_utilization": util,
            "new_schedule_id": new_schedule_db.id
        }
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        return {"error": f"An unexpected error occurred during solving: {e}"}

def _tool_simulate_solve(db: Session, context: AppContext) -> Dict[str, Any]:
    """
    Solves the active scenario but DOES NOT save to the database.
    This is for 'what-if' analysis.
    """
    scenario_id = context.current_scenario_id
    try:
        jobs = db.exec(
            select(Job)
            .where(Job.scenario_id == scenario_id)
            .options(selectinload(Job.operation_list))
        ).all()
        mgs = db.exec(select(MachineGroup).where(MachineGroup.scenario_id == scenario_id)).all()
        if not jobs or not mgs: 
            return {"error": "Cannot solve: No jobs or machines in scenario."}

        # Run the solver
        final_schedule: Optional[SolverSchedule] = solve_jssp(jobs=jobs, machine_groups=mgs)
        if not final_schedule:
            return {"error": "Solver failed to find a solution."}
        
        # Format KPIs for the LLM
        avg_flow = round(final_schedule.average_flow_time, 2)
        util = {k: round(v, 4) for k, v in final_schedule.machine_utilization.items()}
        
        return {
            "status": "Success", "makespan": final_schedule.makespan,
            "average_flow_time": avg_flow,
            "machine_utilization": util
        }
    except Exception as e:
        traceback.print_exc()
        return {"error": f"An unexpected error occurred during solving: {e}"}

@router.post("/solve_active_scenario", response_model=ScheduleRead, tags=["Scenario Management"])
def solve_active_scenario(
    db: Session = Depends(get_session),
    context: AppContext = Depends(get_user_context)
):
    """
    Solves the currently active scenario and saves the result.
    This is a direct-action endpoint, bypassing the LLM.
    """
    result = _tool_solve_schedule(db, context)
    
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    # Fetch the newly created schedule to return it
    new_schedule_id = result.get("new_schedule_id")
    if not new_schedule_id:
         raise HTTPException(status_code=500, detail="Solver succeeded but did not return a schedule ID.")

    schedule_db = db.exec(
        select(Schedule)
        .where(Schedule.id == new_schedule_id)
        .options(selectinload(Schedule.scheduled_operations))
    ).first()
    
    if not schedule_db:
        raise HTTPException(status_code=404, detail="Could not retrieve newly solved schedule.")

    return ScheduleRead.model_validate(schedule_db)

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
    try:
        user_sessions.clear()
        
        # Clear all tables. Order matters due to ForeignKeys.
        # We must delete tables with ForeignKeys FIRST.
        db.exec(delete(ScheduledOperation))
        db.exec(delete(Schedule))
        db.exec(delete(CommandLog))
        db.exec(delete(Operation))
        db.exec(delete(Job))
        db.exec(delete(MachineGroup))
        db.exec(delete(Scenario))
        db.exec(delete(User))
        
        from ..db.database import populate_database
        user_id, scenario_id = populate_database(session=db)
        db.commit()
        
        session_token = str(uuid.uuid4())
        new_context = AppContext()
        new_context.set_user_and_scenario(user_id, scenario_id)
        user_sessions[session_token] = new_context
        
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

@router.post("/interpret", tags=["LLM"], response_model=Dict[str, Any])
async def interpret_user_command_orchestrator(
    command_request: UserCommand, 
    db: Session = Depends(get_session),
    context: AppContext = Depends(get_user_context) 
):
    history = command_request.history or []
    history.append({'role': 'user', 'parts': [{'text': command_request.command}]})
    
    # This will be set to the ID of a newly created schedule
    new_schedule_id: Optional[int] = None 
    
    max_turns = 10 
    for turn in range(max_turns):
        print(f"\nTurn {turn} for User {context.current_user_id}")
        
        try:
            llm_response_content_or_error = await interpret_command(history=history)
            if isinstance(llm_response_content_or_error, dict) and 'error' in llm_response_content_or_error:
                raise HTTPException(status_code=500, detail=f"LLM Error: {llm_response_content_or_error['error']}")

            llm_response_content = llm_response_content_or_error
            model_turn_parts = []
            
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
            
            history.append({'role': 'model', 'parts': model_turn_parts})
            print(f"Appended Model Turn: {json.dumps(history[-1], indent=2)}")

            function_call_part = next((part for part in model_turn_parts if 'function_call' in part), None)

            if function_call_part:
                tool_name = function_call_part['function_call'].get('name', 'Unknown')
                tool_args = function_call_part['function_call'].get('args', {})
                print(f"Turn {turn}: LLM requested tool '{tool_name}' with args: {tool_args}")

                if tool_name not in tool_function_map:
                    tool_result = {"error": f"Unknown tool '{tool_name}' requested."}
                else:
                    tool_function = tool_function_map[tool_name]
                    try:
                        tool_result = tool_function(db=db, context=context, **tool_args)
                        
                        # NEW: Check if this was a successful solve
                        if tool_name == 'solve_schedule' and 'new_schedule_id' in tool_result:
                            new_schedule_id = tool_result['new_schedule_id']

                    except HTTPException as http_exc:
                        tool_result = {"error": f"Tool execution error: {http_exc.detail}"}
                    except TypeError as e: 
                        tool_result = {"error": f"Invalid args for '{tool_name}'. Details: {str(e)}"}
                    except Exception as e: 
                        tool_result = {"error": f"Error executing '{tool_name}': {str(e)}"}

                print(f"Turn {turn}: Tool '{tool_name}' result: {tool_result}")
                try: result_content_value = json.dumps(tool_result)
                except TypeError: result_content_value = f"Error: Non-serializable result from '{tool_name}'."
                history.append({
                    'role': 'function',
                    'parts': [{'function_response': {'name': tool_name, 'response': {'content': result_content_value}}}]
                })
                print(f"Appended Function Turn: {json.dumps(history[-1], indent=2)}")
                continue 

            else:
                final_answer = "\n".join(part.get('text', '') for part in model_turn_parts if 'text' in part).strip()
                if not final_answer:
                    raise HTTPException(status_code=500, detail="LLM provided an empty response.")
                
                print(f"Turn {turn}: LLM provided final answer. Ending loop.")
                try:
                    new_log = CommandLog(
                        user_id=context.current_user_id,
                        scenario_id=context.current_scenario_id,
                        user_command=command_request.command,
                        final_response=final_answer,
                        full_history=json.dumps(history),
                        timestamp=datetime.datetime.now()
                    )
                    db.add(new_log); db.commit()
                except Exception as log_e:
                    print(f"CRITICAL: Failed to write to audit log: {log_e}"); db.rollback()

                schedule_to_return = None
                
                # NEW: If a schedule was just generated, fetch it
                if new_schedule_id:
                    schedule_db = db.exec(
                        select(Schedule)
                        .where(Schedule.id == new_schedule_id)
                        .options(selectinload(Schedule.scheduled_operations))
                    ).first()
                    if schedule_db:
                        # Convert to the Pydantic Read model for the JSON response
                        schedule_to_return = ScheduleRead.model_validate(schedule_db).model_dump()
                
                return {
                    "explanation": final_answer, 
                    "history": history,
                    "schedule": schedule_to_return
                }

        except HTTPException as http_exc:
            try:
                new_log = CommandLog(
                    user_id=context.current_user_id,
                    scenario_id=context.current_scenario_id,
                    user_command=command_request.command,
                    final_response=f"HTTPException: {http_exc.detail}",
                    full_history=json.dumps(history),
                    timestamp=datetime.datetime.now()
                )
                db.add(new_log); db.commit()
            except Exception as log_e:
                print(f"CRITICAL: Failed to write ERROR to audit log: {log_e}"); db.rollback()
            print(f"HTTP Exception on Turn {turn}: {http_exc.detail}"); raise http_exc
        
        except Exception as e:
            try:
                new_log = CommandLog(
                    user_id=context.current_user_id,
                    scenario_id=context.current_scenario_id,
                    user_command=command_request.command,
                    final_response=f"Orchestrator loop error: {e}",
                    full_history=json.dumps(history),
                    timestamp=datetime.datetime.now()
                )
                db.add(new_log); db.commit()
            except Exception as log_e:
                print(f"CRITICAL: Failed to write ERROR to audit log: {log_e}"); db.rollback()
            print(f"Loop error on Turn {turn}: {e}"); traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Orchestrator loop error on turn {turn}: {e}")

    raise HTTPException(status_code=500, detail=f"Orchestration exceeded maximum turns ({max_turns}).")

@router.post("/reset", tags=["Scheduling"])
def reset_problem_state_endpoint(
    db: Session = Depends(get_session),
    context: AppContext = Depends(get_user_context)
):
    status_or_token = _developer_tool_reset_all(db=db, context=context)
    if status_or_token.startswith("Error"):
         raise HTTPException(status_code=500, detail=status_or_token)
    return {"message": "Database reset successfully.", "new_session_token": status_or_token.split(": ")[-1]}

# --- This runs when the API router is loaded ---
@router.on_event("startup")
def on_startup():
    print("Running startup event...")
    create_db_and_tables()
    print("Database and tables verified.")