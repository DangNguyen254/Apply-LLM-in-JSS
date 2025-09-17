from fastapi import APIRouter, HTTPException

# Module 1.2
from ..models.jssp_model import Job, Machine, Schedule

# Module 1.3
from ..services.jssp_solver import solve_jssp

# Mock data
from .mock_data import TEST_PROBLEMS

router = APIRouter()

@router.get("/problems", tags=["Scheduling"])
def list_problems():
    return list(TEST_PROBLEMS.keys())

@router.get("/jobs", tags=["Scheduling"])
def get_jobs_for_problem(problem_id: str = "problem_1"):
    problem = TEST_PROBLEMS.get(problem_id)
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    return problem["jobs"]

@router.get("/machines", tags=["Scheduling"])
def get_machines_for_problem(problem_id: str = "problem_1"):
    problem = TEST_PROBLEMS.get(problem_id)
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    return problem["machines"]

@router.post("/solve", response_model=Schedule, tags=["Scheduling"])
def solve_schedule_endpoint(problem_id: str = "problem_1"):
    problem_data = TEST_PROBLEMS.get(problem_id)
    if not problem_data:
        raise HTTPException(status_code=404, detail="Problem not found")

    try:
        # transform dictionary to Pydantic Model objects
        machines_to_solve = [Machine(**m) for m in problem_data["machines"]]
        jobs_to_solve = [Job(**j) for j in problem_data["jobs"]]

        final_schedule = solve_jssp(jobs=jobs_to_solve, machines=machines_to_solve)

        if final_schedule is None:
            raise HTTPException(status_code=500, detail="Solver failed to find a solution.")

        return final_schedule

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred during solving: {e}")