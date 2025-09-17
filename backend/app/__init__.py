from fastapi import FastAPI
from .api import api_router

app = FastAPI(
    title="LLM-JSSP API",
    description="API for the Job Shop Scheduling Problem Solver",
    version="1.0.0"
)

@app.get("/", tags=["Root"])
def read_root():
    """Root endpoint to check if the API is working."""
    return {"message": "The server is running well."}

app.include_router(api_router, prefix="/api")