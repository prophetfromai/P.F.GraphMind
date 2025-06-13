# routers/database.py
from fastapi import APIRouter, HTTPException
from app.config import settings
from app.core.database import neo4j_connection
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
            # Convert Neo4j DateTime objects to Python datetime objects
            records = []
            for record in result:
                data = record.data()
                # Convert any Neo4j DateTime objects to Python datetime objects
                for key, value in data.items():
                    if hasattr(value, 'to_native'):
                        data[key] = value.to_native()
                records.append(data)
            return records
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error checking indexes: {e}")