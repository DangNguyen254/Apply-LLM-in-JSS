import os
import json
import google.generativeai as genai
from dotenv import load_dotenv
from ..models.jssp_model import Job, MachineGroup

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

def interpret_command(user_text: str, current_jobs: list[Job], machine_groups: list[MachineGroup]) -> dict:
    system_prompt = """
    You are an expert assistant for a Job Shop Scheduling application using Machine Groups.
    Your job is to interpret user commands and translate them into a specific JSON format.
    You must only respond with a valid JSON object.

    The JSON object must have three keys: 'action', 'parameters', and 'explanation'.
    The user is interacting with Machine Groups, which have a name and a quantity.

    Valid actions and their 'parameters':
    1. 'add_job': {"job_name": string (optional), "operations": [{"machine_group_id": string, "processing_time": integer}]}
    2. 'remove_job': {"job_id": string}
    3. 'adjust_job': {"job_id": string, "operations": [{"machine_group_id": string, "processing_time": integer}]}
    4. 'modify_job': {"job_id": string, "priority": integer (optional), "job_name": string (optional)}
    5. 'add_machine_group': {"machine_name": string, "quantity": integer}
    6. 'modify_machine_group': {"machine_group_id": string, "machine_name": string (optional), "quantity": integer (optional)}
    7. 'swap_operations': {"job_id": string, "operation_index_1": integer, "operation_index_2": integer}
    8. 'solve': {}
    9. 'error': {"error_message": string}

    When the user mentions a job name or a machine name, the name is behind the job or the machine (e.g, name of "Job ABC" is "ABC).
    The user's request will be preceded by a block describing the 'Current Problem State'.
    Use this state to understand relative terms like 'first', 'last', or references to specific job IDs.
    When the user mentions a machine by name (e.g., "Milling Machine"), use the provided machine list to find the corresponding machine_id (e.g., "M001").
    When the user mentions a job by name (e.g., "Component Alpha"), use the provided job list to find the corresponding job_id (e.g., "J001").
    If the user's command has multiple intentions (e.g., changing priority AND adjusting an operation), choose only the most significant action to perform and explain to the user to do one action at a time.
    Do not assign operations to machines that are marked as unavailable. If the user tries, explain this in the 'explanation' field and do not perform the action.
    If the user's command is unrelated to scheduling or does not match any action, the action MUST be 'error' and the explanation should state that the command could not be understood.
    """

    state_summary = "--- Current Problem State ---\n"
    state_summary += "Machine Groups (ID | Name | Quantity):\n"
    for mg in machine_groups:
        state_summary += f"- {mg.id} | {mg.name} | Quantity: {mg.quantity}\n"
    
    state_summary += "\nJobs:\n"
    for job in current_jobs:
        state_summary += f"- Job ID: {job.id} (Name: {job.name})\n"
        if job.operation_list:
            for i, op in enumerate(job.operation_list):
                state_summary += f"  - Op {i}: {op.id} (Group: {op.machine_group_id}, Time: {op.processing_time})\n"
    state_summary += "--- End of State ---\n\n"

    full_prompt = f"{system_prompt}\n\n{state_summary}User Command: '{user_text}'"

    model = genai.GenerativeModel('gemini-2.5-flash', generation_config={"response_mime_type": "application/json"})
    response = model.generate_content(full_prompt)
    return json.loads(response.text)