from sqlmodel import SQLModel, create_engine, Session, select
from sqlalchemy.engine import Engine

# Import all models, including the new DB-backed schedules
from app.models.jssp_model import (
    Job, Operation, MachineGroup, Scenario, User, CommandLog,
    Schedule, ScheduledOperation
)
# Import the new mock data structure
from app.api.mock_data import TEST_PROBLEMS 

DATABASE_URL = "mssql+pyodbc://ACER\\NMDSERVER/jssp_db?driver=ODBC+Driver+17+for+SQL+Server&trusted_connection=yes"

engine: Engine = create_engine(DATABASE_URL, echo=True)

def populate_database(session: Session) -> (int, int):
    """
    Populates the database with a default User and a "Live" Scenario
    based on the 'automotive_plant_live' data.
    Returns (user_id, scenario_id)
    """
    print("Database is empty, creating default user and 'Live' scenario...")
    
    # --- THIS IS THE NEW DATA KEY ---
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
            operation_list=[] # Will be populated by the relationship
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
    
    # Return the IDs we need
    return default_user.id, live_scenario.id

def create_db_and_tables():
    """
    Creates all database tables and populates them if they are empty.
    """
    # This will now create all 9 tables:
    # User, Scenario, MachineGroup, Job, Operation,
    # CommandLog, Schedule, ScheduledOperation
    SQLModel.metadata.create_all(engine)
    
    with Session(engine) as session:
        statement = select(User).where(User.username == "admin")
        user = session.exec(statement).first()
        
        if not user:
            # Database is empty
            user_id, scenario_id = populate_database(session)
        else:
            # User exists, find their "Live Data" scenario
            scenario_stmt = select(Scenario).where(Scenario.user_id == user.id, Scenario.name == "Live Data")
            live_scenario = session.exec(scenario_stmt).first()
            
            if live_scenario:
                print("Database already populated. Default context found.")
            else:
                # This state is broken (user exists, but no live scenario)
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