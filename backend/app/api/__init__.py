from fastapi import APIRouter
from . import scheduling

api_router = APIRouter()

api_router.include_router(scheduling.router, prefix="/scheduling")