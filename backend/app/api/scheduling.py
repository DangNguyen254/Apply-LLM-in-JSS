from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ..models.jssp_model import Job, MachineGroup, Operation, Schedule
from ..services.jssp_solver import solve_jssp
from ..services.llm_service import interpret_command
from .mock_data import TEST_PROBLEMS

app_state = { "problem_1": { "jobs": [Job(**j) for j in TEST_PROBLEMS["problem_1"]["jobs"]], "machine_groups": [MachineGroup(**mg) for mg in TEST_PROBLEMS["problem_1"]["machines"]] } }
router = APIRouter(prefix="/scheduling")

class UserCommand(BaseModel):
    command: str

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
        final_schedule = solve_jssp(jobs=problem_data["jobs"], machine_groups=problem_data["machine_groups"])
        if not final_schedule:
            raise HTTPException(status_code=500, detail="Solver failed to find a solution.")
        return final_schedule
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")

@router.post("/interpret", tags=["LLM"])
def interpret_user_command(user_command: UserCommand, problem_id: str = "problem_1"):
    problem_data = app_state.get(problem_id)
    if not problem_data:
        raise HTTPException(status_code=404, detail="Problem not found")

    try:
        llm_response = interpret_command(
            user_text=user_command.command,
            current_jobs=problem_data["jobs"],
            machine_groups=problem_data["machine_groups"]
        )

        action = llm_response.get("action")
        parameters = llm_response.get("parameters", {})

        if action == "error":
            return llm_response # Pass the error explanation to the user
        
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
            
            valid_machine_group_ids = {mg.id for mg in problem_data["machine_groups"]}

            # Value Validation
            for op_data in operations_data:
                if op_data.get("machine_group_id") not in valid_machine_group_ids:
                    raise HTTPException(status_code=400, detail=f"Invalid machine_group_id '{op_data.get('machine_group_id')}' provided by LLM.")
                try:
                    processing_time = int(op_data.get("processing_time"))
                    if processing_time <= 0: raise ValueError
                    op_data["processing_time"] = processing_time
                except (ValueError, TypeError):
                    raise HTTPException(status_code=400, detail="Invalid processing_time provided by LLM.")
                
            if action == "add_job":
                existing_ids = {int(j.id[1:]) for j in problem_data["jobs"]}
                new_id_num = max(existing_ids) + 1 if existing_ids else 1
                new_job_id = f"J{new_id_num:03d}"

                new_operations = []
                for i, op_data in enumerate(operations_data):
                    op_id = f"{new_job_id}-OP{i+1:02d}"
                    predecessors = [f"{new_job_id}-OP{i:02d}"] if i > 0 else []
                    new_op = Operation(id=op_id, machine_group_id=op_data["machine_group_id"], processing_time=op_data["processing_time"], predecessors=predecessors)
                    new_operations.append(new_op)
                
                job_name = parameters.get("job_name", f"New Job {new_job_id}")
                new_job = Job(id=new_job_id, name=job_name, operation_list=new_operations, priority=parameters.get("priority", 1))

                problem_data["jobs"].append(new_job)
                llm_response["explanation"] += f"\nSuccessfully added '{job_name}' as Job ID: {new_job_id}"

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
                        op_id = f"{job_id_to_adjust}-OP{i+1:02d}"
                        predecessors = [f"{job_id_to_adjust}-OP{i:02d}"] if i > 0 else []
                        new_op = Operation(id=op_id, machine_groups=op_data["machine_group_id"], processing_time=op_data["processing_time"], predecessors=predecessors)
                        new_operations.append(new_op)
                    
                    job_to_adjust.operation_list = new_operations
                    llm_response["explanation"] += f"\nSuccessfully adjusted Job ID: {job_id_to_adjust}"

        elif action == "modify_job":
            job_id_to_modify = parameters.get("job_id")
            if not job_id_to_modify:
                raise HTTPException(status_code=400, detail="LLM response missing 'job_id' for modify action.")

            job_to_modify = next((job for job in problem_data["jobs"] if job.id == job_id_to_modify), None)

            if not job_to_modify:
                llm_response["explanation"] += f"\nWarning: Job ID '{job_id_to_modify}' not found for modification."
            else:
                updated = False
                new_priority = parameters.get("priority")
                new_job_name = parameters.get("job_name")
                if new_priority is not None:
                    job_to_modify.priority = new_priority
                    llm_response["explanation"] += f"\nSet priority for {job_id_to_modify} to {new_priority}."
                    updated = True
                if new_job_name is not None:
                    job_to_modify.name = new_job_name
                    llm_response["explanation"] += f"\nSet name for {job_id_to_modify} to '{new_job_name}'."
                    updated = True
                if not updated:
                     llm_response["explanation"] += f"\nNo new properties provided for {job_id_to_modify}."

        elif action == "add_machine_group":
            name = parameters.get("machine_name") # Use consistent 'machine_name'
            quantity = parameters.get("quantity")
            if not name or not isinstance(quantity, int) or quantity < 1:
                raise HTTPException(status_code=400, detail="LLM response missing name or valid quantity.")
            
            existing_ids = {int(mg.id[2:]) for mg in problem_data["machines"]}
            new_id_num = max(existing_ids) + 1 if existing_ids else 1
            new_mg_id = f"MG{new_id_num:03d}"
            
            new_machine_group = MachineGroup(id=new_mg_id, name=name, quantity=quantity)
            problem_data["machine_groups"].append(new_machine_group)
            llm_response["explanation"] += f"\nAdded group '{name}' as ID {new_mg_id}."

        elif action == "modify_machine_group":
            mg_id = parameters.get("machine_group_id")
            if not mg_id:
                raise HTTPException(status_code=400, detail="LLM response missing machine_group_id.")
            
            mg_to_modify = next((mg for mg in problem_data["machine_groups"] if mg.id == mg_id), None)
            if not mg_to_modify:
                llm_response["explanation"] += f"\nWarning: Group '{mg_id}' not found."
            else:
                new_name = parameters.get("machine_name")
                new_quantity = parameters.get("quantity")
                if new_name:
                    mg_to_modify.name = new_name
                if new_quantity is not None and isinstance(new_quantity, int) and new_quantity >= 0:
                    mg_to_modify.quantity = new_quantity
                llm_response["explanation"] += f"\nModified group {mg_id}."

        elif action == "swap_operations":
            job_id = parameters.get("job_id")
            op_idx_1 = parameters.get("operation_index_1")
            op_idx_2 = parameters.get("operation_index_2")
            if not job_id or not isinstance(op_idx_1, int) or not isinstance(op_idx_2, int):
                raise HTTPException(status_code=400, detail="LLM response missing parameters for swap_operations action.")
            job_to_modify = next((job for job in problem_data["jobs"] if job.id == job_id), None)
            if not job_to_modify:
                llm_response["explanation"] += f"\nWarning: Job ID '{job_id}' not found for swap."
            else:
                op_list = job_to_modify.operation_list
                op_count = len(op_list)
                if not (0 <= op_idx_1 < op_count and 0 <= op_idx_2 < op_count):
                    raise HTTPException(status_code=400, detail="LLM provided out-of-bounds indices for swap.")
                op_list[op_idx_1], op_list[op_idx_2] = op_list[op_idx_2], op_list[op_idx_1]
                # Rebuild IDs and predecessors
                for i, op in enumerate(op_list):
                    op.id = f"{job_to_modify.id}-OP{i+1:02d}"
                    if i == 0:
                        op.predecessors = []
                    else:
                        op.predecessors = [op_list[i-1].id]
                job_to_modify.operation_list = op_list
                llm_response["explanation"] += f"\nSuccessfully swapped operations in Job ID: {job_id}."

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
    app_state[problem_id] = {
        "jobs": [Job(**j) for j in TEST_PROBLEMS[problem_id]["jobs"]],
        "machine_groups": [MachineGroup(**mg) for mg in TEST_PROBLEMS[problem_id]["machines"]],
    }
    return {"message": f"Problem '{problem_id}' has been reset successfully."}