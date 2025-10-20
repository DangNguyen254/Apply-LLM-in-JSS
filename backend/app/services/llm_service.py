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

def interpret_command(user_text: str, current_jobs: list) -> dict:
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

    Here are the valid actions and the required structure for their 'parameters':

    1. If the action is 'add_job', the 'parameters' must contain:
    - "operations": A list of objects, where each object has:
        - "machine_id": string (e.g., "M1", "L1")
        - "processing_time": integer
    - "priority": integer (optional, defaults to 1)

    2. If the action is 'remove_job', the 'parameters' must contain:
    - "job_id": string (e.g., "J101")

    3. If the action is 'adjust_job', the 'parameters' must contain:
    - "job_id": string (the ID of the job to change)
    - "operations": A NEW, COMPLETE list of operation objects that will REPLACE the old ones. Even if the user asks to change just one operation, you must provide the full, updated list of all operations for the job.

    4. If the action is 'modify_job', the 'parameters' must contain:
    - "job_id": string
    - "priority": integer (the new priority for the job)

    5. If the action is 'solve', the 'parameters' object must be empty: {}

    The user's request will be preceded by a block describing the 'Current Problem State'.
    Use this state to understand relative terms like 'first', 'last', or references to specific job IDs.
    If the user's command has multiple intentions (e.g., changing priority AND adjusting an operation), choose only the most significant action to perform.
    """

    # Build the dynamic context string from the current jobs
    state_summary = "--- Current Problem State ---\n"
    if not current_jobs:
        state_summary += "There are currently no jobs.\n"
    else:
        state_summary += "Jobs:\n"
        for job in current_jobs:
            # Use job.id because 'job' is a Pydantic object
            state_summary += f"- Job ID: {job.id}\n"
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