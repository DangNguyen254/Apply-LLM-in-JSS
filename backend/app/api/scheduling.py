from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import google.generativeai as genai

from ..models.jssp_model import Job, MachineGroup, Operation, Schedule
from ..services.jssp_solver import solve_jssp
from ..services.llm_service import interpret_command
from .mock_data import TEST_PROBLEMS

from typing import Dict, Any, List, Optional, Tuple, Set, Callable
import copy
import traceback
import json 
import collections.abc

from google.protobuf.struct_pb2 import ListValue, Struct, Value
try:
    from google.protobuf.internal.containers import RepeatedCompositeFieldContainer, RepeatedScalarFieldContainer
    PROTO_CONTAINERS = (RepeatedCompositeFieldContainer, RepeatedScalarFieldContainer)
except ImportError:
    # Fallback if internal paths change or are not available
    PROTO_CONTAINERS = ()
    print("Warning: Could not import Protobuf internal containers. Conversion might be incomplete.")

app_state = { "problem_1": { "jobs": [Job(**j) for j in TEST_PROBLEMS["problem_1"]["jobs"]], "machine_groups": [MachineGroup(**mg) for mg in TEST_PROBLEMS["problem_1"]["machines"]] } }
router = APIRouter(prefix="/scheduling")

class UserCommand(BaseModel):
    command: str
    history: Optional[List[Dict[str, Any]]] = None

# Helper functions
def validate_operations(ops_data: Optional[List[Dict[str, Any]]], valid_mg_ids: Set[str]) -> Tuple[bool, str]:
    """
    Validates the structure and content of operations data provided by the LLM.

    Args:
        ops_data: The list of operation dictionaries from LLM parameters.
        valid_mg_ids: A set of currently valid machine group IDs.

    Returns:
        A tuple containing a boolean (True if valid) and an error message string (empty if valid).
    """
    if not ops_data:
        return False, "Missing 'operations' data."
    for i, op_data in enumerate(ops_data):
        mg_id = op_data.get("machine_group_id")
        proc_time = op_data.get("processing_time")
        if mg_id not in valid_mg_ids:
            return False, f"Invalid machine_group_id '{mg_id}' in operation {i}."
        try:
            time_int = int(proc_time)
            if time_int <= 0:
                raise ValueError("Processing time must be positive.")
            # Ensure the data passed later is integer
            op_data["processing_time"] = time_int
        except (ValueError, TypeError, AssertionError):
            return False, f"Invalid processing_time '{proc_time}' in operation {i} (must be a positive integer)."
    return True, ""

def _find_item_id_by_name(items: List[Any], name_query: str) -> Optional[str]:
    """
    Finds ID of first item matching name_query (case-insensitive, substring).
    
    Args: 
        items (list of Job or MachineGroup), 
        name_query.

    Returns: 
        Item ID string or None.
    """
    if not name_query or not items: return None
    name_query_lower = name_query.lower()
    for item in items:
        if hasattr(item, 'name') and name_query_lower in item.name.lower():
            return item.id
    return None # Not found

def convert_proto_value(value: Any) -> Any:
    """
    Robustly convert Protobuf Struct/ListValue/Value/RepeatedComposite
    and nested structures to basic Python types (dict, list, str, int, float, bool, None).
    """
    # Handle basic types directly
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    # Handle Protobuf list-like types (ListValue and Repeated containers)
    elif isinstance(value, ListValue) or (PROTO_CONTAINERS and isinstance(value, PROTO_CONTAINERS)):
        return [convert_proto_value(item) for item in value]
    # Handle Protobuf dict-like type (Struct)
    elif isinstance(value, Struct):
         return {k: convert_proto_value(v) for k, v in value.items()}
    # Handle Protobuf Value wrapper type (extracts underlying value)
    elif isinstance(value, Value):
        kind = value.WhichOneof('kind')
        if kind == 'struct_value': return convert_proto_value(value.struct_value)
        if kind == 'list_value': return convert_proto_value(value.list_value)
        if kind == 'string_value': return value.string_value
        if kind == 'number_value': return value.number_value # float
        if kind == 'bool_value': return value.bool_value
        if kind == 'null_value': return None
        return None # Should not happen
    # Handle standard Python lists/tuples (recurse within)
    elif isinstance(value, collections.abc.Sequence): # Excludes str
        return [convert_proto_value(item) for item in value]
    # Handle standard Python dicts (recurse within)
    elif isinstance(value, collections.abc.Mapping):
        return {k: convert_proto_value(v) for k, v in value.items()}
    # Fallback for unknown types -> convert to string
    else:
        print(f"Warning: Encountered unknown type during conversion: {type(value)}. Using str(). Value: {value!r}")
        return str(value)

# API endpoints
@router.get("/machine_groups", response_model=list[MachineGroup], tags=["Scheduling"])
def get_machine_groups(problem_id: str = "problem_1"):
    problem = app_state.get(problem_id)
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    return problem["machine_groups"]

@router.get("/problems", tags=["Scheduling"])
def list_problems():
    return list(app_state.keys())

@router.get("/jobs", response_model=list[Job], tags=["Scheduling"])
def get_jobs_for_problem(problem_id: str = "problem_1"):
    problem = app_state.get(problem_id)
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    return problem["jobs"]

@router.post("/solve", response_model=Schedule, tags=["Scheduling"])
def solve_schedule_endpoint(problem_id: str = "problem_1"):
    problem_data = app_state.get(problem_id)
    if not problem_data:
        raise HTTPException(status_code=404, detail="Problem not found")

    try:
        current_jobs = problem_data.get("jobs", [])
        current_machine_groups = problem_data.get("machine_groups", [])
        if not current_jobs or not current_machine_groups:
             raise HTTPException(status_code=400, detail="Cannot solve: Problem has no jobs or no machine groups defined.")

        final_schedule = solve_jssp(jobs=current_jobs, machine_groups=current_machine_groups)

        if not final_schedule:
            # Clear previous schedule if solver fails
            problem_data.pop("last_schedule", None)
            raise HTTPException(status_code=500, detail="Solver failed to find a solution.")

        # Store the latest successful schedule in the app_state
        problem_data["last_schedule"] = final_schedule
        return final_schedule
    except HTTPException as http_exc:
        # Re-raise HTTP exceptions from validation or solver failure
        raise http_exc
    except Exception as e:
        # Catch unexpected errors during solving
        problem_data.pop("last_schedule", None) # Clear potentially inconsistent state
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during solving: {e}")

# Tools
def _tool_remove_job(problem_data: Dict[str, Any], job_id: str) -> str:
    """
    Tool function to remove a job from the problem state.

    Args:
        problem_data: The dictionary containing 'jobs' and 'machine_groups'.
        job_id: The ID of the job to remove.

    Returns:
        A status message string.
    """
    if not job_id:
        # Raise an internal error or return a specific message if job_id is missing
        # For now, let's return a message consistent with original logic's potential failure
        return "Error: LLM did not provide 'job_id' for remove action."

    initial_job_count = len(problem_data["jobs"])
    problem_data["jobs"] = [job for job in problem_data["jobs"] if job.id != job_id]

    if len(problem_data["jobs"]) == initial_job_count:
        return f"Warning: Job ID '{job_id}' not found."
    else:
        return f"Successfully removed Job ID: {job_id}."

def _tool_add_job(problem_data: Dict[str, Any], operations: List[Dict[str, Any]], job_name: Optional[str] = None, priority: int = 1) -> str:
    """
    Tool function to add a new job to the problem state. Assumes operations_data is validated.

    Args:
        problem_data: The dictionary containing 'jobs' and 'machine_groups'.
        operations_data: A list of dictionaries, each specifying 'machine_group_id' and 'processing_time'.
        job_name: Optional name for the new job.
        priority: Optional priority for the new job (default 1).

    Returns:
        A status message string including the new job ID.
    """
    existing_ids = {int(j.id[1:]) for j in problem_data["jobs"] if j.id.startswith('J') and j.id[1:].isdigit()}
    new_id_num = max(existing_ids) + 1 if existing_ids else 1
    new_job_id = f"J{new_id_num:03d}"

    new_operations: List[Operation] = []
    for i, op_data in enumerate(operations):
        op_id = f"{new_job_id}-OP{i+1:02d}"
        # Predecessors are based on the order in the list
        predecessors = [f"{new_job_id}-OP{i:02d}"] if i > 0 else []
        new_op = Operation(
            id=op_id,
            machine_group_id=op_data["machine_group_id"],
            processing_time=op_data["processing_time"],
            predecessors=predecessors
        )
        new_operations.append(new_op)

    effective_job_name = job_name if job_name else f"New Job {new_job_id}"
    new_job = Job(
        id=new_job_id,
        name=effective_job_name,
        operation_list=new_operations,
        priority=priority
    )

    problem_data["jobs"].append(new_job)
    return f"Successfully added '{effective_job_name}' as Job ID: {new_job_id}"

def _tool_adjust_job(problem_data: Dict[str, Any], job_id: str, operations_data: List[Dict[str, Any]]) -> str:
    """
    Tool function to replace the operations list for an existing job. Assumes operations_data is validated.

    Args:
        problem_data: The dictionary containing 'jobs' and 'machine_groups'.
        job_id: The ID of the job to adjust.
        operations_data: A list of dictionaries defining the new operations.

    Returns:
        A status message string.
    """
    job_to_adjust = next((job for job in problem_data["jobs"] if job.id == job_id), None)

    if not job_to_adjust:
        return f"Warning: Job ID '{job_id}' not found for adjustment."
    else:
        new_operations: List[Operation] = []
        for i, op_data in enumerate(operations_data):
            op_id = f"{job_id}-OP{i+1:02d}" # Use the existing job_id for the new op IDs
            predecessors = [f"{job_id}-OP{i:02d}"] if i > 0 else []
            new_op = Operation(
                id=op_id,
                machine_group_id=op_data["machine_group_id"],
                processing_time=op_data["processing_time"],
                predecessors=predecessors
            )
            new_operations.append(new_op)

        # Replace the entire operation list
        job_to_adjust.operation_list = new_operations
        return f"Successfully adjusted operations for Job ID: {job_id}"

def _tool_modify_job(problem_data: Dict[str, Any], job_id: str, new_priority: Optional[int] = None, new_job_name: Optional[str] = None) -> str:
    """
    Tool function to modify the priority or name of an existing job.

    Args:
        problem_data: The dictionary containing 'jobs' and 'machine_groups'.
        job_id: The ID of the job to modify.
        new_priority: The new priority value (optional).
        new_job_name: The new job name (optional).

    Returns:
        A status message string.
    """
    job_to_modify = next((job for job in problem_data["jobs"] if job.id == job_id), None)

    if not job_to_modify:
        return f"Warning: Job ID '{job_id}' not found for modification."
    else:
        updated_messages = []
        # Update priority if provided
        if new_priority is not None:
            try:
                # Ensure priority is an integer
                priority_int = int(new_priority)
                job_to_modify.priority = priority_int
                updated_messages.append(f"Set priority to {priority_int}.")
            except (ValueError, TypeError):
                # Return a warning if the value is invalid
                 updated_messages.append(f"Warning: Invalid priority value '{new_priority}' provided.")

        # Update name if provided
        if new_job_name is not None:
            # Ensure name is a string
            job_to_modify.name = str(new_job_name)
            updated_messages.append(f"Set name to '{new_job_name}'.")

        # Check if any updates were actually made or attempted
        if not updated_messages:
             return f"No valid properties (priority or job_name) provided for modification of {job_id}."
        else:
            return f"Modified Job ID {job_id}: {' '.join(updated_messages)}"

def _tool_add_machine_group(problem_data: Dict[str, Any], name: str, quantity: int) -> str:
    """
    Tool function to add a new machine group to the problem state. Assumes name and quantity are validated.

    Args:
        problem_data: The dictionary containing 'jobs' and 'machine_groups'.
        name: The name for the new machine group.
        quantity: The quantity for the new machine group (must be >= 1).

    Returns:
        A status message string including the new group ID.
    """
    # Find next available Machine Group ID (MGxxx)
    existing_ids = {int(mg.id[2:]) for mg in problem_data.get("machine_groups", []) if mg.id.startswith('MG') and mg.id[2:].isdigit()}
    new_id_num = max(existing_ids) + 1 if existing_ids else 1
    new_mg_id = f"MG{new_id_num:03d}"

    # Create and add the new machine group
    new_machine_group = MachineGroup(id=new_mg_id, name=str(name), quantity=int(quantity))
    if "machine_groups" not in problem_data:
         problem_data["machine_groups"] = []
    problem_data["machine_groups"].append(new_machine_group)

    return f"Added group '{name}' as ID {new_mg_id} with quantity {quantity}."
       
def _tool_modify_machine_group(problem_data: Dict[str, Any], mg_id: str, new_name: Optional[str] = None, new_quantity: Optional[int] = None) -> str:
    """
    Tool function to modify the name or quantity of an existing machine group.

    Args:
        problem_data: The dictionary containing 'jobs' and 'machine_groups'.
        mg_id: The ID of the machine group to modify.
        new_name: The new name (optional).
        new_quantity: The new quantity (optional, must be >= 0 if provided).

    Returns:
        A status message string.
    """
    mg_to_modify = next((mg for mg in problem_data["machine_groups"] if mg.id == mg_id), None)
    if not mg_to_modify:
        return f"Warning: Group '{mg_id}' not found."
    else:
        updated_messages = []
        # Update name if provided
        if new_name is not None:
            mg_to_modify.name = str(new_name)
            updated_messages.append(f"Set name to '{new_name}'.")
        # Update quantity if provided
        if new_quantity is not None:
            try:
                quantity_int = int(new_quantity)
                # Allow quantity 0 for simulating breakdown
                if quantity_int >= 0:
                    mg_to_modify.quantity = quantity_int
                    updated_messages.append(f"Set quantity to {quantity_int}.")
                else:
                    updated_messages.append(f"Warning: Invalid quantity '{new_quantity}' (must be >= 0) provided.")
            except (ValueError, TypeError):
                updated_messages.append(f"Warning: Invalid quantity value '{new_quantity}' provided.")
        # Check if any updates were attempted
        if not updated_messages:
             return f"No valid properties (machine_name or quantity) provided for modification of {mg_id}."
        else:
            return f"Modified Group ID {mg_id}: {' '.join(updated_messages)}"

def _tool_swap_operations(problem_data: Dict[str, Any], job_id: str, idx1: int, idx2: int) -> str:
    """
    Tool function to swap two operations within a job's sequence. Assumes indices are validated integers.

    Args:
        problem_data: The dictionary containing 'jobs' and 'machine_groups'.
        job_id: The ID of the job whose operations are to be swapped.
        idx1: The first zero-based index of the operation to swap.
        idx2: The second zero-based index of the operation to swap.

    Returns:
        A status message string.
    """
    job_to_modify = next((job for job in problem_data["jobs"] if job.id == job_id), None)
    if not job_to_modify:
        return f"Warning: Job ID '{job_id}' not found for swap."
    else:
        op_list = job_to_modify.operation_list
        op_count = len(op_list)

        original_idx1 = idx1
        original_idx2 = idx2
        try:
            # Explicitly cast indices received from LLM to integers
            idx1 = int(idx1)
            idx2 = int(idx2)
        except (ValueError, TypeError):
            # Handle cases where LLM provides non-numeric values
            return f"Error: Indices ({original_idx1}, {original_idx2}) must be integers."
        
        # Validate indices are within bounds
        if not (0 <= idx1 < op_count and 0 <= idx2 < op_count):
            return f"Error: Indices ({idx1}, {idx2}) out of bounds for job {job_id} (length {op_count})."
        # Check if indices are the same
        if idx1 == idx2:
             return f"Warning: Cannot swap an operation with itself (index {idx1})."
        else:
            # Perform the swap
            op_list[idx1], op_list[idx2] = op_list[idx2], op_list[idx1]
            # Rebuild IDs and predecessors after swap to maintain consistency
            for i, op in enumerate(op_list):
                op.id = f"{job_to_modify.id}-OP{i+1:02d}"
                op.predecessors = [op_list[i-1].id] if i > 0 else []
            return f"Successfully swapped operations at indices {idx1} and {idx2} in Job ID: {job_id}."

def _tool_get_current_problem_state(problem_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Tool function to retrieve the current state of jobs and machine groups.

    Args:
        problem_data: The dictionary containing 'jobs' and 'machine_groups'.

    Returns:
        A dictionary containing the current 'jobs' and 'machine_groups' lists,
        serialized suitable for JSON or LLM consumption.
    """
    # Use Pydantic's model_dump() for robust serialization
    return {
        "jobs": [job.model_dump() for job in problem_data.get("jobs", [])],
        "machine_groups": [mg.model_dump() for mg in problem_data.get("machine_groups", [])]
    }

def _tool_get_job_details(problem_data: Dict[str, Any], job_id: str) -> Dict[str, Any]:
    """
    Retrieves the details for a specific job.

    Args:
        problem_data: The dictionary containing 'jobs' and 'machine_groups'.
        job_id: The ID of the job to retrieve.

    Returns:
        A dictionary containing the job details if found, or an error message.
    """
    job = next((job for job in problem_data.get("jobs", []) if job.id == job_id), None)
    if job:
        return {"job": job.model_dump()}
    else:
        return {"error": f"Job ID '{job_id}' not found."}

def _tool_get_machine_group_details(problem_data: Dict[str, Any], machine_group_id: str) -> Dict[str, Any]:
    """
    Retrieves the details for a specific machine group.

    Args:
        problem_data: The dictionary containing 'jobs' and 'machine_groups'.
        machine_group_id: The ID of the machine group to retrieve.

    Returns:
        A dictionary containing the machine group details if found, or an error message.
    """
    mg = next((mg for mg in problem_data.get("machine_groups", []) if mg.id == machine_group_id), None)
    if mg:
        return {"machine_group": mg.model_dump()}
    else:
        return {"error": f"Machine Group ID '{machine_group_id}' not found."}
     
def _tool_get_schedule_kpis(problem_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Retrieves KPIs from the last computed schedule.

    Args:
        problem_data: Contains 'jobs', 'machine_groups', and potentially 'last_schedule'.

    Returns:
        Dictionary containing KPIs (makespan, average_flow_time, machine_utilization)
        or an error message if no schedule has been computed yet.
    """
    last_schedule: Optional[Schedule] = problem_data.get("last_schedule")
    if last_schedule:
        return {
            "makespan": last_schedule.makespan,
            "average_flow_time": last_schedule.average_flow_time,
            "machine_utilization": last_schedule.machine_utilization
        }
    else:
        return {"error": "No schedule has been computed yet. Please run the solver first."}

def _tool_solve_schedule(problem_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Runs the solver and returns KPIs or error.

    Args: 
        problem_data: Contains 'jobs', 'machine_groups', and potentially 'last_schedule'.

    Returns: 
        Dictionary with KPIs or error message.
    """
    try:
        current_jobs = problem_data.get("jobs", [])
        current_machine_groups = problem_data.get("machine_groups", [])
        if not current_jobs or not current_machine_groups:
             return {"error": "Cannot solve: No jobs or machine groups defined."}

        final_schedule = solve_jssp(jobs=current_jobs, machine_groups=current_machine_groups)

        if not final_schedule:
            problem_data.pop("last_schedule", None)
            return {"error": "Solver failed to find a solution."}
        else:
            # Store schedule and return KPIs
            problem_data["last_schedule"] = final_schedule
            return {
                "status": "Success",
                "makespan": final_schedule.makespan,
                "average_flow_time": final_schedule.average_flow_time,
                "machine_utilization": final_schedule.machine_utilization
            }
    except Exception as e:
        problem_data.pop("last_schedule", None)
        traceback.print_exc()
        return {"error": f"An unexpected error occurred during solving: {e}"}

def _tool_simulate_solve(problem_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Runs the solver for a simulation, does NOT save the result, and returns KPIs or error.

    Args: 
        problem_data: Contains 'jobs', 'machine_groups'.

    Returns: 
        Dictionary with KPIs or error message.
    """
    try:
        current_jobs = problem_data.get("jobs", [])
        current_machine_groups = problem_data.get("machine_groups", [])
        if not current_jobs or not current_machine_groups:
             return {"error": "Cannot solve: No jobs or machine groups defined."}

        final_schedule = solve_jssp(jobs=current_jobs, machine_groups=current_machine_groups)

        if not final_schedule:
            # DO NOT clear the last_schedule here
            return {"error": "Solver failed to find a solution."}
        else:
            # DO NOT save the schedule to problem_data
            # Just return the computed values
            return {
                "status": "Success",
                "makespan": final_schedule.makespan,
                "average_flow_time": final_schedule.average_flow_time,
                "machine_utilization": final_schedule.machine_utilization
            }
    except Exception as e:
        traceback.print_exc()
        return {"error": f"An unexpected error occurred during solving: {e}"}
    
def _tool_reset_problem(problem_id: str, problem_data: Dict[str, Any]) -> str:
    """
    Resets the problem state.
    
    Args: 
        problem_id:
        problem_data: Contains 'jobs', 'machine_groups', and potentially 'last_schedule'.

    Returns: 
        Status message.
    """
    if problem_id not in TEST_PROBLEMS:
        return f"Error: Problem ID '{problem_id}' definition not found for reset."

    # Use deepcopy
    app_state[problem_id] = {
        "jobs": [Job(**j) for j in copy.deepcopy(TEST_PROBLEMS[problem_id]["jobs"])],
        "machine_groups": [MachineGroup(**mg) for mg in copy.deepcopy(TEST_PROBLEMS[problem_id]["machines"])],
    }
    app_state[problem_id].pop("last_schedule", None) # Ensure last schedule is cleared
    return f"Problem '{problem_id}' has been reset successfully."

def _tool_find_job_id_by_name(problem_data: Dict[str, Any], job_name: str) -> Dict[str, Optional[str]]:
    """
    Finds a Job ID based on its name (case-insensitive, substring match).
    
    Args: 
        problem_data, 
        job_name.

    Returns: 
        Dictionary with 'job_id' (string or None if not found).
    """
    if not job_name: return {"job_id": None, "error": "No job name provided for lookup."}
    job_id = _find_item_id_by_name(problem_data.get("jobs", []), job_name)
    return {"job_id": job_id} # Return None if not found

def _tool_find_machine_group_id_by_name(problem_data: Dict[str, Any], machine_name: str) -> Dict[str, Optional[str]]:
    """
    Finds a Machine Group ID based on its name (case-insensitive, substring match).
    
    Args: 
        problem_data, 
        machine_name.

    Returns: 
        Dictionary with 'machine_group_id' (string or None if not found).
    """
    if not machine_name: return {"machine_group_id": None, "error": "No machine name provided for lookup."}
    mg_id = _find_item_id_by_name(problem_data.get("machine_groups", []), machine_name)
    return {"machine_group_id": mg_id} # Return None if not found

# Tool Function Mapping
# Maps tool names (from LLM schema) to the actual Python functions
tool_function_map: Dict[str, Callable] = {
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
    "reset_problem": _tool_reset_problem,
    "find_job_id_by_name": _tool_find_job_id_by_name,
    "find_machine_group_id_by_name": _tool_find_machine_group_id_by_name,
}

@router.post("/interpret", tags=["LLM"])
async def interpret_user_command_orchestrator(command_request: UserCommand, problem_id: str = "problem_1"):
    """
    Orchestrates interaction between user, LLM, and tools to fulfill requests.
    """
    problem_data = app_state.get(problem_id)
    if not problem_data:
        raise HTTPException(status_code=404, detail=f"Problem '{problem_id}' not found")

    history = command_request.history or []
    # Combine system prompt, state summary, and user request for the FIRST turn
    history.append({'role': 'user', 'parts': [{'text': command_request.command}]})
    max_turns = 10
    
    for turn in range(max_turns):
        print(f"\nTurn {turn}")
        print(f"Sending History (Turn > 0): {json.dumps(history, indent=2)}")
        try:
            # Call LLM service
            llm_response_content_or_error = interpret_command(
                history=history, # Context summary in llm_service
                current_jobs=problem_data.get("jobs", []),
                machine_groups=problem_data.get("machine_groups", []),
            )


            if isinstance(llm_response_content_or_error, dict) and 'error' in llm_response_content_or_error:
                # If llm_service returns an error dictionary directly
                raise HTTPException(status_code=500, detail=f"LLM Error: {llm_response_content_or_error['error']}")

            # If no error, it must be a Content object
            llm_response_content = llm_response_content_or_error

            if not history:
                history.append({'role': 'user', 'parts': [{'text': user_command.command}]})
                print(f"Appended Initial User Turn: {json.dumps(history[-1], indent=2)}")

            # Add model's response (Content object converted to dict) to history
            model_turn_parts = []
            if llm_response_content.parts:
                for part in llm_response_content.parts:
                    part_dict = {}
                    if hasattr(part, 'text') and part.text:
                        part_dict['text'] = part.text
                    elif hasattr(part, 'function_call') and part.function_call:
                        # Construct the function_call dictionary
                        fc = part.function_call

                        converted_args = {}
                        if fc.args:
                            for key, value in fc.args.items():
                                converted_args[key] = convert_proto_value(value) # Use robust conversion

                        part_dict['function_call'] = {
                            'name': fc.name if hasattr(fc, 'name') else 'UnknownFunction',
                            'args': converted_args # Use the converted args
                        }
                    # Add other part types if needed
                    if part_dict: 
                        model_turn_parts.append(part_dict)

            if not model_turn_parts:
                print(f"Warning: LLM response content parts were empty or unprocessable: {llm_response_content}")
                raise HTTPException(status_code=500, detail="LLM response empty/unprocessable.")
            else:
                # Append the turn with fully converted args to history
                history.append({
                    'role': llm_response_content.role if hasattr(llm_response_content, 'role') else 'model', 
                    'parts': model_turn_parts
                })
                
                print(f"Appended Model Turn: {json.dumps(history[-1], indent=2)}")

            # Find the first tool call in the response parts
            function_call_part = None
            for part in model_turn_parts:
                if 'function_call' in part:
                    function_call_part = part
                    break # Found the first tool call, prioritize it

            if function_call_part:
                # Case 1: A tool call was found. Execute it.
                function_call_dict = function_call_part['function_call']
                tool_name = function_call_dict.get('name', 'UnknownFunction')
                raw_args = function_call_dict.get('args')
                tool_args = raw_args if raw_args else {} # Args are already a Python dict

                print(f"Turn {turn}: LLM requested tool '{tool_name}' with args: {tool_args}")

                # Execute tool
                if tool_name not in tool_function_map:
                    tool_result = {"error": f"Unknown tool '{tool_name}' requested."}
                else:
                    tool_function = tool_function_map[tool_name]
                    try: # Execute tool with context
                        if tool_name == "reset_problem": tool_result = tool_function(problem_id=problem_id, problem_data=problem_data, **tool_args)
                        elif tool_name in ["solve_schedule", "get_schedule_kpis", "get_current_problem_state", "get_job_details", "get_machine_group_details", "find_job_id_by_name", "find_machine_group_id_by_name"]: tool_result = tool_function(problem_data=problem_data, **tool_args)
                        else: tool_result = tool_function(problem_data=problem_data, **tool_args)
                    except TypeError as e: 
                        error_str = f"Invalid args for '{tool_name}'. Details: {str(e)}"
                        tool_result = {"error": error_str}
                        print(tool_result["error"])
                        traceback.print_exc()
                    except Exception as e: 
                        error_str = f"Error executing '{tool_name}': {str(e)}"
                        tool_result = {"error": error_str}
                        print(tool_result["error"])
                        traceback.print_exc()

                print(f"Turn {turn}: Tool '{tool_name}' result: {tool_result}")

                # Format tool result for history
                if isinstance(tool_result, (str, int, float, bool)): result_content_value = str(tool_result)
                else:
                    try: result_content_value = json.dumps(tool_result)
                    except TypeError: result_content_value = f"Error: Non-serializable result from '{tool_name}'."

                # Append function response using dictionary structure
                function_response_turn = {
                    'role': 'function',
                    'parts': [{'function_response': {'name': tool_name, 'response': {'content': result_content_value}}}]
                }
                history.append(function_response_turn)
                print(f"Appended Function Turn: {json.dumps(history[-1], indent=2)}") # Debug log
                
                # Continue to the next turn in the loop
                continue 

            else:
                # Case 2: No tool call found. This must be the final answer.
                # Concatenate all text parts, if any.
                final_text_parts = [part.get('text', '') for part in model_turn_parts if 'text' in part]
                final_answer = "\n".join(final_text_parts).strip()

                if not final_answer:
                    # LLM stopped without a tool call and without text.
                    print(f"Turn {turn}: LLM stopped with no text or tool call.")
                    raise HTTPException(status_code=500, detail="LLM provided an empty response.")
                
                print(f"Turn {turn}: LLM provided final answer. Ending loop.")

                schedule_to_return = None
                last_tool_name = None
                
                # Look at the second-to-last turn (the 'function' response)
                if len(history) >= 2:
                    last_function_turn = history[-2]
                    if last_function_turn.get('role') == 'function':
                        last_part = last_function_turn.get('parts', [{}])[0]
                        function_response = last_part.get('function_response', {})
                        last_tool_name = function_response.get('name')

                if last_tool_name == 'solve_schedule':
                    # If the last tool was a solve, get the schedule from app_state
                    schedule = problem_data.get("last_schedule")
                    if schedule:
                        schedule_to_return = schedule.model_dump()
                
                # Return the final answer, history, and (optionally) the schedule
                return {
                    "explanation": final_answer, 
                    "history": history,
                    "schedule": schedule_to_return # This will be null or the full schedule
                }

        except HTTPException as http_exc:
            # Propagate FastAPI errors immediately
             print(f"HTTP Exception on Turn {turn}: {http_exc.detail}") # Debug log
             raise http_exc
        except Exception as e:
             # Catch other unexpected errors during the loop
             print(f"Loop error on Turn {turn}: {e}") # Debug log
             traceback.print_exc()
             raise HTTPException(status_code=500, detail=f"Orchestrator loop error on turn {turn}: {e}")

    # If the loop finishes without returning (i.e., max_turns reached)
    print(f"Orchestration exceeded max turns ({max_turns}).") # Debug log
    raise HTTPException(status_code=500, detail=f"Orchestration exceeded maximum turns ({max_turns}).")

@router.post("/reset", tags=["Scheduling"])
def reset_problem_state_endpoint(problem_id: str = "problem_1"):
    """
    API endpoint to reset the specified problem's state.
    """
    status = _tool_reset_problem(problem_id, app_state.get(problem_id, {})) # Use the tool function
    if status.startswith("Error"):
         raise HTTPException(status_code=404, detail=status)
    return {"message": status}