import os
import json
import google.generativeai as genai
from dotenv import load_dotenv
from google.generativeai.types import FunctionDeclaration, Tool, GenerationConfig
from typing import Dict, Any, List, Optional
import traceback


load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

# --- Tool Schemas (All Unchanged) ---

get_active_scenario = FunctionDeclaration(
    name="get_active_scenario",
    description="Gets the details (ID and Name) of the user's currently active scenario. This is typically 'Live Data'. Call this first in a 'what-if' plan.",
    parameters={"type": "object", "properties": {}}
)

select_scenario = FunctionDeclaration(
    name="select_scenario",
    description="Selects one of the user's scenarios to make it the active one for all other tools. This is used by the assistant to silently switch contexts, e.g., into a temporary 'what-if' scenario or back to 'Live Data'.",
    parameters={
        "type": "object",
        "properties": {"scenario_id": {"type": "integer"}},
        "required": ["scenario_id"]
    }
)

create_scenario = FunctionDeclaration(
    name="create_scenario",
    description="Creates a new 'what-if' scenario by copying an existing one. Returns the new scenario's details, including its ID.",
    parameters={
        "type": "object",
        "properties": {
            "new_scenario_name": {"type": "string", "description": "e.g., 'temp-what-if-breakdown'"},
            "base_scenario_id": {"type": "integer", "description": "The ID of the scenario to copy from (e.g., the 'Live Data' scenario)."}
        },
        "required": ["new_scenario_name", "base_scenario_id"]
    }
)

delete_scenario = FunctionDeclaration(
    name="delete_scenario",
    description="Deletes a temporary 'what-if' scenario. This CANNOT be used to delete the 'Live Data' scenario.",
    parameters={
        "type": "object",
        "properties": {"scenario_id": {"type": "integer"}},
        "required": ["scenario_id"]
    }
)

solve_schedule = FunctionDeclaration(
    name="solve_schedule",
    description="Runs the solver on the *active scenario*, saves the result, and returns KPIs.",
    parameters={"type": "object", "properties": {}}
)

simulate_solve = FunctionDeclaration(
    name="simulate_solve",
    description="Runs the solver on the *active scenario* WITHOUT saving the result. Use for 'what-if' simulations.",
    parameters={"type": "object", "properties": {}}
)

get_schedule_kpis = FunctionDeclaration(
    name="get_schedule_kpis",
    description="Retrieves the KPIs from the last *saved* schedule for the *active scenario*.",
    parameters={"type": "object", "properties": {}}
)

add_job = FunctionDeclaration(
    name="add_job",
    description="Adds a new job to the *active scenario*.",
    parameters={
        "type": "object",
        "properties": {
            "job_name": {"type": "string", "description": "Optional name for the new job."},
            "priority": {
                "type": "integer",
                "description": "Optional priority for the job. (Defaults to 1 if not provided)"
            },
            "operations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "machine_group_id": {"type": "string"},
                        "processing_time": {"type": "integer"}
                    },
                    "required": ["machine_group_id", "processing_time"]
                }
            }
        },
        "required": ["operations"]
    }
)

remove_job = FunctionDeclaration(
    name="remove_job",
    description="Removes a job from the *active scenario*.",
    parameters={
        "type": "object",
        "properties": {"job_id": {"type": "string"}},
        "required": ["job_id"]
    }
)

adjust_job = FunctionDeclaration(
    name="adjust_job",
    description="Replaces the operations list for a job in the *active scenario*.",
    parameters={
        "type": "object",
        "properties": {
            "job_id": {"type": "string"},
            "operations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "machine_group_id": {"type": "string"},
                        "processing_time": {"type": "integer"}
                    },
                    "required": ["machine_group_id", "processing_time"]
                }
            }
        },
        "required": ["job_id", "operations"]
    }
)

modify_job = FunctionDeclaration(
    name="modify_job",
    description="Modifies attributes of a job in the *active scenario*.",
    parameters={
        "type": "object",
        "properties": {
            "job_id": {"type": "string"},
            "new_priority": {"type": "integer"},
            "new_job_name": {"type": "string"}
        },
        "required": ["job_id"]
    }
)

add_machine_group = FunctionDeclaration(
    name="add_machine_group",
    description="Adds a new machine group to the *active scenario*.",
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "quantity": {"type": "integer"}
        },
        "required": ["name", "quantity"]
    }
)

modify_machine_group = FunctionDeclaration(
    name="modify_machine_group",
    description="Modifies a machine group in the *active scenario*.",
    parameters={
        "type": "object",
        "properties": {
            "mg_id": {"type": "string"},
            "new_name": {"type": "string"},
            "new_quantity": {"type": "integer"}
        },
        "required": ["mg_id"]
    }
)

swap_operations = FunctionDeclaration(
    name="swap_operations",
    description="Swaps two operations in a job in the *active scenario*.",
    parameters={
        "type": "object",
        "properties": {
            "job_id": {"type": "string"},
            "idx1": {"type": "integer"},
            "idx2": {"type": "integer"}
        },
        "required": ["job_id", "idx1", "idx2"]
    }
)

get_current_problem_state = FunctionDeclaration(
    name="get_current_problem_state",
    description="Retrieves all jobs and machines for the *active scenario*.",
    parameters={"type": "object", "properties": {}}
)

get_job_details = FunctionDeclaration(
    name="get_job_details",
    description="Gets details for a single job in the *active scenario*.",
    parameters={
        "type": "object",
        "properties": {"job_id": {"type": "string"}},
        "required": ["job_id"]
    }
)

get_machine_group_details = FunctionDeclaration(
    name="get_machine_group_details",
    description="Gets details for a single machine group in the *active scenario*.",
    parameters={
        "type": "object",
        "properties": {"machine_group_id": {"type": "string"}},
        "required": ["machine_group_id"]
    }
)

find_job_id_by_name = FunctionDeclaration(
    name="find_job_id_by_name",
    description="Looks up a Job ID by name in the *active scenario*.",
    parameters={
        "type": "object",
        "properties": {"job_name": {"type": "string"}},
        "required": ["job_name"]
    }
)

find_machine_group_id_by_name = FunctionDeclaration(
    name="find_machine_group_id_by_name",
    description="Looks up a Machine Group ID by name in the *active scenario*.",
    parameters={
        "type": "object",
        "properties": {"machine_name": {"type": "string"}},
        "required": ["machine_name"]
    }
)


# Assemble Tool
scheduling_tool = Tool(function_declarations=[
    get_active_scenario,
    select_scenario,
    create_scenario,
    delete_scenario,
    solve_schedule,
    simulate_solve,
    get_schedule_kpis,
    add_job,
    remove_job,
    adjust_job,
    modify_job,
    add_machine_group,
    modify_machine_group,
    swap_operations,
    get_current_problem_state,
    get_job_details,
    get_machine_group_details,
    find_job_id_by_name,
    find_machine_group_id_by_name,
])

# System Prompt (Unchanged)
system_prompt = """
You are an expert assistant for a multi-user, scenario-based Job Shop Scheduling application.
Your role is to act as an orchestrator. You manage a user's workspace and help them analyze scheduling scenarios.

**CONTEXT & WORKFLOW:**
The user is already logged in and their "Live Data" scenario is active by default.
All simple commands (like `add_job`, `solve_schedule`) apply directly to this active "Live Data" scenario.
You do NOT need to ask the user to select a scenario at the start.

**ID LOOKUP:**
- If a user provides a job NAME (e.g., 'Job ABC') when an ID (e.g., 'J001') is needed, you MUST FIRST use `find_job_id_by_name`.
- If a user provides a machine group NAME (e.g., 'Milling') when an ID (e.g., 'MG001') is needed, you MUST FIRST use `find_machine_group_id_by_name`.

**WHAT-IF SCENARIOS (SIMULATIONS):**
This is a key feature.
1.  If the user asks a "what-if" or "simulate" question (e.g., "what if a machine breaks?"), your plan MUST be:
    a. Call `get_active_scenario` to get the ID of the user's "Live Data" scenario (e.g., `base_scenario_id = 1`).
    b. Call `create_scenario(new_scenario_name="temp-what-if-simulation", base_scenario_id=1)`. This tool will return the new scenario's details, including its ID.
    c. Call `select_scenario(scenario_id=...)` to *silently* switch your context to this new temporary scenario.
    d. Apply the simulation's modifications (e.g., `modify_machine_group(...)`) to this temporary scenario.
    e. Call `simulate_solve()` to get the results (this does not save).
    f. **CRITICAL:** Call `select_scenario(scenario_id=1)` to switch the context *back* to the user's "Live Data" scenario.
    g. **CRITICAL:** Call `delete_scenario(scenario_id=...)` to clean up the temporary scenario (use the ID from step b).
    h. Present the results to the user (e.g., "If you made that change, the makespan would be X.").

**MAKING A "WHAT-IF" CHANGE REAL:**
If the user *likes* the simulation result and says "make that real," "save that," or "I want to do that":
1.  The user's active scenario is already "Live Data" (because you switched back in step 'f').
2.  Your plan is to *re-apply the modification* from the simulation, but this time to the "Live Data" scenario.
3.  Call the modification tool (e.g., `modify_machine_group(...)`).
4.  Call `solve_schedule()` (the *real* one) to save this new state.
5.  Inform the user, "Done. I have applied that change to your 'Live Data' schedule."

**IMPORTANT:**
- Only respond with a tool call *or* a text answer, never both.
- A text answer means your plan is finished for that turn.
"""

def interpret_command(history: List[Dict[str, Any]]) -> Any:
    """
    Interprets user command using the LLM with function calling capabilities.
    """
    
    try:
        config = GenerationConfig(
            max_output_tokens=8192,
            temperature=0.2 
        )

        # --- FIX 1: Use the full model identifier ---
        model = genai.GenerativeModel(
            'gemini-2.0-flash',
            tools=[scheduling_tool],
            system_instruction=system_prompt,
        )

        response = model.generate_content(
            history,
            generation_config=config,
        )

        if not response.candidates or not response.candidates[0].content.parts:
            finish_reason = response.candidates[0].finish_reason if response.candidates else "Unknown"
            safety_ratings = response.candidates[0].safety_ratings if response.candidates else "Unknown"
            error_message = f"LLM response empty/blocked. Finish Reason: {finish_reason}. Safety: {safety_ratings}"
            print(f"Warning: {error_message}")
            
            # --- FIX 2: Return the *detailed* error message ---
            return {'error': f"Could not get valid response from LLM. Reason: {finish_reason}"}

        return response.candidates[0].content

    except Exception as e:
        print(f"Error during LLM communication: {e}")
        traceback.print_exc()
        history_repr = json.dumps(history, indent=2) if history else "None"
        if "contents must not be empty" in str(e):
             return {'error': f"LLM communication error: 'contents must not be empty'. History sent: {history_repr}"}
        return {'error': f"LLM communication error: {e}"}