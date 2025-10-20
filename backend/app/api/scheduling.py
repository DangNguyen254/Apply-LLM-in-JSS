import copy
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# Import models and services
from ..models.jssp_model import Job, Machine, Operation, Schedule
from ..services.jssp_solver import solve_jssp
from ..services.llm_service import interpret_command
# mock data
from .mock_data import TEST_PROBLEMS

# This dictionary acts as simple, in-memory "database".
app_state = {
    "problem_1": {
        "jobs": [Job(**j) for j in TEST_PROBLEMS["problem_1"]["jobs"]],
        "machines": [Machine(**m) for m in TEST_PROBLEMS["problem_1"]["machines"]],
    },
    "problem_2": {
        "jobs": [Job(**j) for j in TEST_PROBLEMS["problem_2"]["jobs"]],
        "machines": [Machine(**m) for m in TEST_PROBLEMS["problem_2"]["machines"]],
    }
}

router = APIRouter()

# Pydantic model for the request body (format)
class UserCommand(BaseModel):
    command: str

@router.get("/problems", tags=["Scheduling"])
def list_problems():
    return list(app_state.keys())

@router.get("/jobs", response_model=list[Job], tags=["Scheduling"])
def get_jobs_for_problem(problem_id: str = "problem_1"):
    problem = app_state.get(problem_id)
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    return problem["jobs"]

@router.get("/machines", response_model=list[Machine], tags=["Scheduling"])
def get_machines_for_problem(problem_id: str = "problem_1"):
    problem = app_state.get(problem_id)
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    return problem["machines"]

@router.post("/solve", response_model=Schedule, tags=["Scheduling"])
def solve_schedule_endpoint(problem_id: str = "problem_1"):
    problem_data = app_state.get(problem_id)
    if not problem_data:
        raise HTTPException(status_code=404, detail="Problem not found")

    try:
        # Pass the current state (Pydantic objects) to the solver
        final_schedule = solve_jssp(jobs=problem_data["jobs"], machines=problem_data["machines"])

        if final_schedule is None:
            raise HTTPException(status_code=500, detail="Solver failed to find a solution.")

        return final_schedule
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred during solving: {e}")

@router.post("/interpret", tags=["LLM"])
def interpret_user_command(user_command: UserCommand, problem_id: str = "problem_1"):
    problem_data = app_state.get(problem_id)
    if not problem_data:
        raise HTTPException(status_code=404, detail="Problem not found")

    try:
        llm_response = interpret_command(
            user_text=user_command.command,
            current_jobs=problem_data["jobs"]
        )

        action = llm_response.get("action")
        parameters = llm_response.get("parameters", {})

        valid_machine_ids = {m.id for m in problem_data["machines"]}

        if action == "solve":
            pass # Do nothing

        elif action == "remove_job":
            job_id_to_remove = parameters.get("job_id")
            if not job_id_to_remove:
                raise HTTPException(status_code=400, detail="LLM response missing 'job_id' for remove action.")
            
            initial_job_count = len(problem_data["jobs"])
            problem_data["jobs"] = [job for job in problem_data["jobs"] if job.id != job_id_to_remove]
            
            if len(problem_data["jobs"]) == initial_job_count:
                llm_response["explanation"] += f"\nWarning: Job ID '{job_id_to_remove}' not found."

        elif action == "add_job" or action == "adjust_job":
            operations_data = parameters.get("operations")
            if not operations_data:
                raise HTTPException(status_code=400, detail=f"LLM response missing 'operations' for {action} action.")
            
            # Value Validation
            for op_data in operations_data:
                if op_data.get("machine_id") not in valid_machine_ids:
                    raise HTTPException(status_code=400, detail=f"Invalid machine_id '{op_data.get('machine_id')}' provided by LLM.")
                if not isinstance(op_data.get("processing_time"), int) or op_data.get("processing_time") <= 0:
                    raise HTTPException(status_code=400, detail="Invalid processing_time '{op_data.get('processing_time')}' provided by LLM. Must be a positive integer.")

            if action == "add_job":
                existing_ids = {int(j.id.replace('J', '')) for j in problem_data["jobs"]}
                new_id_num = max(existing_ids) + 1 if existing_ids else 101
                new_job_id = f"J{new_id_num}"

                new_operations = []
                for i, op_data in enumerate(operations_data):
                    op_id = f"{new_job_id}_O{i+1}"
                    predecessors = [f"{new_job_id}_O{i}"] if i > 0 else []
                    new_op = Operation(id=op_id, machine_id=op_data["machine_id"], processing_time=op_data["processing_time"], predecessors=predecessors)
                    new_operations.append(new_op)
                
                new_job = Job(id=new_job_id, operation_list=new_operations, priority=parameters.get("priority", 1))
                problem_data["jobs"].append(new_job)
                llm_response["explanation"] += f"\nSuccessfully added as Job ID: {new_job_id}"

            elif action == "adjust_job":
                job_id_to_adjust = parameters.get("job_id")
                if not job_id_to_adjust:
                    raise HTTPException(status_code=400, detail="LLM response missing 'job_id' for adjust action.")

                job_to_adjust = next((job for job in problem_data["jobs"] if job.id == job_id_to_adjust), None)

                if not job_to_adjust:
                    llm_response["explanation"] += f"\nWarning: Job ID '{job_id_to_adjust}' not found for adjustment."
                else:
                    new_operations = []
                    for i, op_data in enumerate(operations_data):
                        op_id = f"{job_id_to_adjust}_O{i+1}"
                        predecessors = [f"{job_id_to_adjust}_O{i}"] if i > 0 else []
                        new_op = Operation(id=op_id, machine_id=op_data["machine_id"], processing_time=op_data["processing_time"], predecessors=predecessors)
                        new_operations.append(new_op)
                    
                    job_to_adjust.operation_list = new_operations
                    llm_response["explanation"] += f"\nSuccessfully adjusted Job ID: {job_id_to_adjust}"
                    
        elif action == "modify_job":
            job_id_to_modify = parameters.get("job_id")
            new_priority = parameters.get("priority")

            if not job_id_to_modify or not isinstance(new_priority, int):
                raise HTTPException(status_code=400, detail="LLM response missing 'job_id' or 'priority' for modify action.")

            job_to_modify = next((job for job in problem_data["jobs"] if job.id == job_id_to_modify), None)

            if not job_to_modify:
                llm_response["explanation"] += f"\nWarning: Job ID '{job_id_to_modify}' not found for modification."
            else:
                job_to_modify.priority = new_priority
                llm_response["explanation"] += f"\nSuccessfully changed priority for Job ID: {job_id_to_modify} to {new_priority}."

        return llm_response

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred during interpretation: {e}")
    
@router.post("/reset", tags=["Scheduling"])
def reset_problem_state(problem_id: str = "problem_1"):
    """
    Resets the specified problem's state to its original definition from mock_data.
    """
    if problem_id not in TEST_PROBLEMS:
        raise HTTPException(status_code=404, detail="Problem not found")

    # Re-initialize the state for the specified problem using a deep copy
    app_state[problem_id] = {
        "jobs": [Job(**j) for j in TEST_PROBLEMS[problem_id]["jobs"]],
        "machines": [Machine(**m) for m in TEST_PROBLEMS[problem_id]["machines"]],
    }
    return {"message": f"Problem '{problem_id}' has been reset successfully."}