import os
import json
import google.generativeai as genai
from dotenv import load_dotenv
from ..models.jssp_model import Job

# Load the API key once when the module is loaded
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
if api_key:
    genai.configure(api_key=api_key)
else:
    print("WARNING: GOOGLE_API_KEY not found. The LLM service will not work.")

def interpret_command(user_text: str, current_jobs: list, current_machines: list) -> dict:
    """
    Takes a user's command and the current list of jobs,
    and returns a structured JSON command from the LLM.
    """

    # Define System Prompt
    system_prompt = """
    You are an expert assistant for a Job Shop Scheduling application.
    Your job is to interpret user commands and translate them into a specific JSON format.
    You must only respond with a valid JSON object and nothing else.

    The JSON object must have three keys: 'action', 'parameters', and 'explanation'.

    Here are the valid actions and their required 'parameters':

    1. 'add_job': For creating a new job. Parameters: {"job_name": string (optional), "operations": A list of objects, where each object has:"machine_id": string, "processing_time": integer}
    2. 'remove_job': For deleting an existing job. Parameters: {"job_id": string}
    3. 'adjust_job': For replacing all operations in a job with a new list. Parameters: {"job_id": string, "operations": [...]}
    4. 'modify_job': For changing properties of a job, like its name or priority. Parameters: {"job_id": string, "priority": integer (optional), "job_name": string (optional)}
    5. 'add_machine': For creating a new machine. Parameters: {"machine_name": string}
    6. 'modify_machine': For changing properties of a machine, like its name or availability. Parameters: {"machine_id": string, "availability": boolean (optional), "machine_name": string (optional)}
    7. 'swap_operations': For reordering two operations within a job. Parameters: {"job_id": string, "operation_index_1": integer, "operation_index_2": integer}
    8. 'solve': For running the solver to generate a schedule. Parameters: {}
    9. 'error': For when a command cannot be understood. Parameters: {"error_message": string}

    When the user mentions a job name or a machine name, the name is behind the job or the machine (e.g, name of "Job ABC" is "ABC).
    The user's request will be preceded by a block describing the 'Current Problem State'.
    Use this state to understand relative terms like 'first', 'last', or references to specific job IDs.
    When the user mentions a machine by name (e.g., "Milling Machine"), use the provided machine list to find the corresponding machine_id (e.g., "M001").
    When the user mentions a job by name (e.g., "Component Alpha"), use the provided job list to find the corresponding job_id (e.g., "J001").
    If the user's command has multiple intentions (e.g., changing priority AND adjusting an operation), choose only the most significant action to perform and explain to the user to do one action at a time.
    Do not assign operations to machines that are marked as unavailable. If the user tries, explain this in the 'explanation' field and do not perform the action.
    If the user's command is unrelated to scheduling or does not match any action, the action MUST be 'error' and the explanation should state that the command could not be understood.
    """

    # State Summary
    state_summary = "--- Current Problem State ---\n"
    state_summary += "Machines (Index: ID | Name | Available):\n"
    for i, machine in enumerate(current_machines):
        state_summary += f"{i}: {machine.id} | {machine.name} | Available: {machine.availability}\n"
    
    state_summary += "\nJobs (ID: Name | Operations):\n"
    if not current_jobs:
        state_summary += "There are currently no jobs.\n"
    else:
        for job in current_jobs:
            op_summary = ", ".join([f"{op.id} on {op.machine_id}" for op in job.operation_list])
            state_summary += f"- Job ID: {job.id} (Name: {job.name}) | Operations: [{op_summary}]\n"
    state_summary += "--- End of State ---\n\n"

    # Combine into the full prompt
    full_prompt = f"{system_prompt}\n\n{state_summary}User Command: '{user_text}'"

    # Set up the model and call the API
    model = genai.GenerativeModel(
        'gemini-2.5-flash',
        generation_config={"response_mime_type": "application/json"}
    )
    response = model.generate_content(full_prompt)

    # Parse and return the JSON response as a Python dictionary
    return json.loads(response.text)