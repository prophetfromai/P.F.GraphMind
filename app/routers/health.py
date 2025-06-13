# routers/health.py
from fastapi import APIRouter, HTTPException
from app.core.neo4j_client import neo4j_connection
from app.config import settings

router = APIRouter(prefix="/api/v1", tags=["health"])

@router.get("/info")
async def info():
    return {
        "app_name": settings.app_name,
        "admin_email": settings.admin_email,
        "items_per_user": settings.items_per_user,
    }

@router.get("/health")
async def health_check():
    try:
        driver = neo4j_connection.connect()
        if not driver:
            raise HTTPException(status_code=500, detail="Failed to connect to database")
        server_info = neo4j_connection.verify_connection()
        return {
            "status": "healthy",
            "database": settings.NEO4J_DATABASE_NEW,
            "server_info": server_info
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
