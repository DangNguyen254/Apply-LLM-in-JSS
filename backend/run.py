import uvicorn
from app.db.database import create_db_and_tables

def init():
    print("Creating database and tables if they don't exist...")
    create_db_and_tables()
    print("Database tables are ready.")
    
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
    
if __name__ == "__main__":
    init()