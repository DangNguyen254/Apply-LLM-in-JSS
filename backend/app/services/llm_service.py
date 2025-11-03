import os
import json
import google.generativeai as genai
from dotenv import load_dotenv
from google.generativeai.types import FunctionDeclaration, Tool
from ..models.jssp_model import Job, MachineGroup
from typing import Dict, Any, List, Optional
import traceback


load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

# Tool Schemas (Function Declarations)

# Define schema for solve_schedule
solve_schedule = FunctionDeclaration(
    name="solve_schedule",
    description="Runs the Job Shop Scheduling solver on the current problem state and returns the schedule KPIs.",
    parameters={
        "type": "object",
        "properties": {} # No parameters needed for the current implementation
    }
)

simulate_solve = FunctionDeclaration(
    name="simulate_solve",
    description="Runs the solver for a 'what-if' scenario WITHOUT saving the result. Use this for simulations. Returns the same schedule KPIs as solve_schedule.",
    parameters={
        "type": "object",
        "properties": {} # No parameters needed
    }
)

# Define schema for get_schedule_kpis
get_schedule_kpis = FunctionDeclaration(
    name="get_schedule_kpis",
    description="Retrieves the Key Performance Indicators (KPIs) like makespan, average flow time, and machine utilization from the most recently computed schedule, without re-running the solver.",
    parameters={
        "type": "object",
        "properties": {} # No parameters needed
    }
)

# Define schema for add_job
add_job = FunctionDeclaration(
    name="add_job",
    description="Adds a new job to the scheduling problem.",
    parameters={
        "type": "object",
        "properties": {
            "job_name": {
                "type": "string",
                "description": "Optional name for the new job. If not provided, a default name will be generated."
            },
            "priority": {
                "type": "integer",
                "description": "Optional priority for the job (integer, default is 1)."
            },
            "operations": {
                "type": "array",
                "description": "A list of operations for the job, in sequence. Each operation must specify the machine group and processing time.",
                "items": {
                    "type": "object",
                    "properties": {
                        "machine_group_id": {
                            "type": "string",
                            "description": "The ID of the machine group required for this operation (e.g., 'MG001')."
                        },
                        "processing_time": {
                            "type": "integer",
                            "description": "The time required for this operation (positive integer)."
                        }
                    },
                    "required": ["machine_group_id", "processing_time"]
                }
            }
        },
        "required": ["operations"]
    }
)

# Define schema for remove_job
remove_job = FunctionDeclaration(
    name="remove_job",
    description="Removes a specific job from the scheduling problem.",
    parameters={
        "type": "object",
        "properties": {
            "job_id": {
                "type": "string",
                "description": "The ID of the job to remove (e.g., 'J001')."
            }
        },
        "required": ["job_id"]
    }
)

# Define schema for adjust_job
adjust_job = FunctionDeclaration(
    name="adjust_job",
    description="Replaces the entire sequence of operations for an existing job. Use this for significant changes to a job's process.",
    parameters={
        "type": "object",
        "properties": {
            "job_id": {
                "type": "string",
                "description": "The ID of the job to adjust (e.g., 'J001')."
            },
            "operations": {
                "type": "array",
                "description": "The new list of operations for the job, in sequence. Each operation must specify the machine group and processing time.",
                "items": {
                    "type": "object",
                    "properties": {
                        "machine_group_id": {
                            "type": "string",
                            "description": "The ID of the machine group required for this operation (e.g., 'MG001')."
                        },
                        "processing_time": {
                            "type": "integer",
                            "description": "The time required for this operation (positive integer)."
                        }
                    },
                    "required": ["machine_group_id", "processing_time"]
                }
            }
        },
        "required": ["job_id", "operations"]
    }
)

# Define schema for modify_job
modify_job = FunctionDeclaration(
    name="modify_job",
    description="Modifies attributes (like priority or name) of an existing job without changing its operations.",
    parameters={
        "type": "object",
        "properties": {
            "job_id": {
                "type": "string",
                "description": "The ID of the job to modify (e.g., 'J001')."
            },
            "new_priority": {
                "type": "integer",
                "description": "The new priority value for the job (optional integer)."
            },
            "new_job_name": {
                "type": "string",
                "description": "The new name for the job (optional string)."
            }
        },
        "required": ["job_id"]
    }
)

# Define schema for add_machine_group
add_machine_group = FunctionDeclaration(
    name="add_machine_group",
    description="Adds a new group of identical machines to the system.",
    parameters={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "The descriptive name for the new machine group (e.g., 'Lathes', 'Milling Station B')."
            },
            "quantity": {
                "type": "integer",
                "description": "The number of identical machines available in this group (must be 1 or greater)."
            }
        },
        "required": ["name", "quantity"]
    }
)

# Define schema for modify_machine_group
modify_machine_group = FunctionDeclaration(
    name="modify_machine_group",
    description="Modifies the name or quantity of an existing machine group. Setting quantity to 0 can simulate a breakdown.",
    parameters={
        "type": "object",
        "properties": {
            "mg_id": { # Parameter name matches the python function
                "type": "string",
                "description": "The ID of the machine group to modify (e.g., 'MG001')."
            },
            "new_name": {
                "type": "string",
                "description": "The new name for the machine group (optional string)."
            },
            "new_quantity": {
                "type": "integer",
                "description": "The new number of machines in the group (optional integer, must be 0 or greater)."
            }
        },
        "required": ["mg_id"]
    }
)

# Define schema for swap_operations
swap_operations = FunctionDeclaration(
    name="swap_operations",
    description="Swaps the position of two operations within the sequence of a specific job.",
    parameters={
        "type": "object",
        "properties": {
            "job_id": {
                "type": "string",
                "description": "The ID of the job whose operations should be swapped."
            },
            "idx1": { # Parameter name matches the python function
                "type": "integer",
                "description": "The zero-based index of the first operation to swap."
            },
            "idx2": { # Parameter name matches the python function
                "type": "integer",
                "description": "The zero-based index of the second operation to swap."
            }
        },
        "required": ["job_id", "idx1", "idx2"]
    }
)

# Define schema for get_current_problem_state
get_current_problem_state = FunctionDeclaration(
    name="get_current_problem_state",
    description="Retrieves the complete current definition of the scheduling problem, including all jobs (with operations) and all machine groups (with quantities).",
    parameters={"type": "object", "properties": {}} # No parameters needed
)

# Define schema for get_job_details
get_job_details = FunctionDeclaration(
    name="get_job_details",
    description="Gets detailed information about a single specified job.",
    parameters={
        "type": "object",
        "properties": {
            "job_id": {
                "type": "string",
                "description": "The ID of the job to retrieve details for."
            }
        },
        "required": ["job_id"]
    }
)

# Define schema for get_machine_group_details
get_machine_group_details = FunctionDeclaration(
    name="get_machine_group_details",
    description="Gets detailed information about a single specified machine group.",
    parameters={
        "type": "object",
        "properties": {
            "machine_group_id": { # Parameter name matches the python function
                "type": "string",
                "description": "The ID of the machine group to retrieve details for."
            }
        },
        "required": ["machine_group_id"]
    }
)

# Define schema for reset_problem
reset_problem = FunctionDeclaration(
    name="reset_problem",
    description="Resets the current scheduling problem back to its original state (based on the loaded mock data). Useful for starting a new scenario analysis.",
    parameters={"type": "object", "properties": {}} # No parameters needed currently
)

# Define schema for find_job_id_by_name
find_job_id_by_name = FunctionDeclaration(
    name="find_job_id_by_name",
    description="Looks up a Job ID based on a potentially partial job name provided by the user. Use this BEFORE calling tools that require a job_id if the user provides a name.",
    parameters={
        "type": "object",
        "properties": {
            "job_name": {
                "type": "string",
                "description": "The name or partial name of the job to find."
            }
        },
        "required": ["job_name"]
    }
)

# Define schema for find_machine_group_id_by_name
find_machine_group_id_by_name = FunctionDeclaration(
    name="find_machine_group_id_by_name",
    description="Looks up a Machine Group ID based on a potentially partial machine group name provided by the user. Use this BEFORE calling tools that require a machine_group_id (or mg_id) if the user provides a name.",
    parameters={
        "type": "object",
        "properties": {
            "machine_name": {
                "type": "string",
                "description": "The name or partial name of the machine group to find."
            }
        },
        "required": ["machine_name"]
    }
)

# Assemble Tool 
# Create a Tool object containing all defined function declarations
scheduling_tool = Tool(function_declarations=[
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
    reset_problem,
    find_job_id_by_name,
    find_machine_group_id_by_name,
])

# Updated System Prompt 
system_prompt = """
You are an expert assistant for a Job Shop Scheduling application using Machine Groups.
Your role is to act as an orchestrator. You receive high-level user goals or questions related to scheduling, potentially involving scenario analysis ('what-if' questions).
You must break down these goals into a step-by-step plan.

**ID LOOKUP:** Users might refer to items by NAME.
- If a user provides a job NAME (e.g., 'Job ABC') when an ID (e.g., 'J001') is needed, you MUST FIRST use the `find_job_id_by_name` tool to get its ID.
- If a user provides a machine group NAME (e.g., 'Milling') when an ID (e.g., 'MG001') is needed, you MUST FIRST use the `find_machine_group_id_by_name` tool to get its ID.
Use the ID returned by the lookup tool in subsequent tool calls (e.g., `modify_job`, `add_job` operations). If the lookup tool returns no ID (null/None), inform the user the name was not found and stop that part of the plan.

To execute your plan, you have access to a set of tools. Determine which tool to use, call it with the correct parameters (using IDs obtained via lookup if necessary), and wait for the result.
The tool results will be provided back to you. Use these results to inform the next step.

- For simple questions (e.g., "how many jobs?"), use 'get_current_problem_state' first, then answer.
- For KPIs of the *last* schedule, use 'get_schedule_kpis'.
- If the user wants to solve and *save* the schedule (e.g., "solve the problem"), use `solve_schedule`.

**WHAT-IF SCENARIOS (SIMULATIONS):**
If the user asks to "simulate", "what if", "what happens if", or "compare" a change:
1. Get baseline KPIs first using `get_schedule_kpis`.
2. Use lookup tools (e.g., `get_machine_group_details`) to find the **original values** of what will be changed (e.g., the current quantity of 'MG001').
3. Use modification tools (e.g., `modify_machine_group`) to apply the temporary scenario change.
4. Use `simulate_solve` to get the new KPIs. This tool does NOT save the schedule.
5. **CRITICAL:** Call the modification tool *again* to **revert the change** back to its original value (e.g., `modify_machine_group` with the original quantity found in step 2).
6. Formulate the final answer, comparing the baseline and new KPIs (e.g., "The original makespan was X. After simulating the breakdown, the new makespan is Y...").

Continue calling tools until you can fully answer the user's request.
**IMPORTANT:** When you have all the information needed to answer the user, provide the final answer as text. Do NOT include a tool call and a text answer in the same turn. A text answer signifies the end of your plan.
If you need to call a tool, respond ONLY with the function call request.
If a request is unclear or cannot be mapped to tools, explain why.
"""


def interpret_command(history: List[Dict[str, Any]], current_jobs: list[Job], machine_groups: list[MachineGroup]) -> Any:
    """
    Interprets user command using the LLM with function calling capabilities.

    Args:
        history: The full conversation history (must not be empty).
        current_jobs: Current list of Job objects (for context summary).
        machine_groups: Current list of MachineGroup objects (for context summary).

    Returns:
        A dictionary containing either:
        - The actual Content object from the LLM response (containing tool_call or final_answer text).
        - {'error': str} if an error occurs during generation.
    """
    
    # Context summary is added to the system prompt, not the history
    state_summary = f"Current state: {len(current_jobs)} jobs, {len(machine_groups)} machine groups."
    full_system_prompt = f"{system_prompt}\n\n{state_summary}"

    try:
        model = genai.GenerativeModel(
            'gemini-2.5-flash',
            tools=[scheduling_tool],
            system_instruction=full_system_prompt
        )

        # Generate content using the history
        response = model.generate_content(history)

        # Check for blocked response or lack of content
        if not response.candidates or not response.candidates[0].content.parts:
            finish_reason = response.candidates[0].finish_reason if response.candidates else "Unknown"
            safety_ratings = response.candidates[0].safety_ratings if response.candidates else "Unknown"
            error_message = f"LLM response empty/blocked. Finish Reason: {finish_reason}. Safety: {safety_ratings}"
            print(f"Warning: {error_message}")
            return {'error': "Could not get valid response from LLM."}

        # Return the actual Content object for the orchestrator to process
        return response.candidates[0].content

    except Exception as e:
        print(f"Error during LLM communication: {e}")
        traceback.print_exc()
        history_repr = json.dumps(history, indent=2) if history else "None"
        if "contents must not be empty" in str(e):
             return {'error': f"LLM communication error: 'contents must not be empty'. History sent: {history_repr}"}
        return {'error': f"LLM communication error: {e}"}