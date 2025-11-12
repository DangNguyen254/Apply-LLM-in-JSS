from sqlmodel import SQLModel, create_engine, Session, select
from sqlalchemy.engine import Engine

# Import all models, including the new DB-backed schedules
from app.models.jssp_model import (
    Job, Operation, MachineGroup, Scenario, User, CommandLog,
    Schedule, ScheduledOperation,
    SolverSchedule # <-- ADD THIS IMPORT
)
# Import the new mock data structure
from app.api.mock_data import TEST_PROBLEMS 

# --- ADD THESE IMPORTS ---
from app.services.jssp_solver import solve_jssp
import datetime
from sqlalchemy.orm import selectinload
from typing import Optional
# --- END OF NEW IMPORTS ---


DATABASE_URL = "mssql+pyodbc://ACER\\NMDSERVER/jssp_db?driver=ODBC+Driver+17+for+SQL+Server&trusted_connection=yes"

engine: Engine = create_engine(DATABASE_URL, echo=True)

def populate_database(session: Session) -> (int, int):
    """
    Populates the database with a default User and a "Live" Scenario
    based on the 'automotive_plant_live' data.
    Returns (user_id, scenario_id)
    """
    print("Database is empty, creating default user and 'Live' scenario...")
    
    live_data_key = "automotive_plant_live"
    if live_data_key not in TEST_PROBLEMS:
        raise ValueError(f"Mock data key '{live_data_key}' not found in mock_data.py")
    
    live_data = TEST_PROBLEMS[live_data_key]

    # 1. Create a Default User
    default_user = User(username="admin", hashed_password="admin123")
    session.add(default_user)
    session.commit()
    session.refresh(default_user)
    print(f"Created user: {default_user.username}")

    # 2. Create a "Live" Scenario for that User
    live_scenario = Scenario(name="Live Data", user_id=default_user.id)
    session.add(live_scenario)
    session.commit()
    session.refresh(live_scenario)
    print(f"Created Scenario: {live_scenario.name} for user {default_user.username}")

    # 3. Create Machine Groups linked to the "Live" scenario
    mg_map = {}
    for mg_data in live_data.get("machines", []):
        mg = MachineGroup(
            **mg_data, 
            scenario_id=live_scenario.id
        )
        session.add(mg)
        mg_map[mg.id] = mg
        
    # 4. Create Jobs and Operations linked to the "Live" scenario
    all_ops = []
    all_jobs = []
    
    for job_data in live_data.get("jobs", []):
        job = Job(
            id=job_data["id"],
            name=job_data["name"],
            priority=job_data["priority"],
            scenario_id=live_scenario.id,
            operation_list=[]
        )
        all_jobs.append(job)
        
        for op_data in job_data.get("operation_list", []):
            op = Operation(
                id=op_data["id"],
                processing_time=op_data["processing_time"],
                predecessors=op_data["predecessors"],
                machine_group_id=op_data["machine_group_id"],
                job_id=job.id,
                scenario_id=live_scenario.id
            )
            all_ops.append(op)
    
    session.add_all(all_jobs)
    session.add_all(all_ops)

    session.commit()
    print("New automotive mock data populated for 'Live Data' scenario.")
    
    # --- START: NEW BLOCK TO SOLVE INITIAL SCHEDULE ---
    try:
        print("Running initial solve for 'Live Data' scenario...")
        # We must eager-load the operations for the solver
        jobs_with_ops = session.exec(
            select(Job)
            .where(Job.scenario_id == live_scenario.id)
            .options(selectinload(Job.operation_list))
        ).all()
        
        machine_groups = session.exec(
            select(MachineGroup).where(MachineGroup.scenario_id == live_scenario.id)
        ).all()

        if not jobs_with_ops or not machine_groups:
            print("Warning: No jobs or machines found, skipping initial solve.")
        else:
            solver_result: Optional[SolverSchedule] = solve_jssp(
                jobs=jobs_with_ops, 
                machine_groups=machine_groups
            )
            
            if solver_result:
                # Create the new Schedule DB object
                new_schedule_db = Schedule(
                    makespan=solver_result.makespan,
                    average_flow_time=solver_result.average_flow_time,
                    machine_utilization=solver_result.machine_utilization,
                    scenario_id=live_scenario.id,
                    timestamp=datetime.datetime.now()
                )
                session.add(new_schedule_db)
                
                # Create all the new ScheduledOperation DB objects
                new_ops_db = []
                for op_result in solver_result.scheduled_operations:
                    new_ops_db.append(
                        ScheduledOperation(
                            job_id=op_result.job_id,
                            operation_id=op_result.operation_id,
                            machine_instance_id=op_result.machine_instance_id,
                            start_time=op_result.start_time,
                            end_time=op_result.end_time,
                            schedule=new_schedule_db # Link to the parent
                        )
                    )
                session.add_all(new_ops_db)
                session.commit()
                print(f"Successfully saved initial schedule for 'Live Data' with Makespan: {solver_result.makespan}.")
            else:
                print("Error: Initial solve failed to find a solution.")

    except Exception as e:
        print(f"Error during initial solve: {e}")
        session.rollback()
    # --- END: NEW BLOCK ---

    return default_user.id, live_scenario.id

def create_db_and_tables():
    """
    Creates all database tables and populates them if they are empty.
    """
    SQLModel.metadata.create_all(engine)
    
    with Session(engine) as session:
        statement = select(User).where(User.username == "admin")
        user = session.exec(statement).first()
        
        if not user:
            # Database is empty, this will now populate AND solve
            user_id, scenario_id = populate_database(session)
        else:
            # User exists, find their "Live Data" scenario
            scenario_stmt = select(Scenario).where(Scenario.user_id == user.id, Scenario.name == "Live Data")
            live_scenario = session.exec(scenario_stmt).first()
            
            if live_scenario:
                print("Database already populated. Default context found.")
            else:
                print("Error: Database in broken state. Manually running populate.")
                populate_database(session)

def get_session():
    """
    This is a generator function that FastAPI's 'Depends'
    can use to inject a session.
    """
    session = Session(engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()