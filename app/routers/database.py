# routers/database.py
from fastapi import APIRouter, HTTPException
from app.core.config import settings
from app.database import neo4j_connection
from typing import List, Dict, Any
from neo4j import Driver

router = APIRouter(prefix="/api/v1", tags=["database"])

@router.get("/get-database-info")
def get_database_info() -> Dict[str, Any]:
    driver: Driver = neo4j_connection.connect()
    with driver.session(database=settings.NEO4J_DATABASE) as session:
        try:
            current_db_result = session.run("SHOW HOME DATABASE")
            current_db = current_db_result.single()["name"]
            databases_result = session.run("SHOW DATABASES")
            available = [r["name"] for r in databases_result]
            return {"current_database": current_db, "available_databases": available}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error querying databases: {e}")


@router.get("/get_database_indexes")
def get_database_indexes() -> List[Dict[str, Any]]:
    driver: Driver = neo4j_connection.connect()
    with driver.session(database=settings.NEO4J_DATABASE) as session:
        try:
            result = session.run("SHOW INDEXES")
            return [record.data() for record in result]
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error checking indexes: {e}")
