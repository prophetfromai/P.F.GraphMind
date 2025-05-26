from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI, HTTPException, APIRouter
from .database import neo4j_connection
from .routers import graphinput
from contextlib import asynccontextmanager
import os
from typing import List, Optional, Dict, Any, Literal
from neo4j import Driver


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    if not neo4j_connection.verify_connection():
        raise Exception("Failed to connect to Neo4j database")
    yield
    # Shutdown
    neo4j_connection.close()

app = FastAPI(title="Neo4j FastAPI Example", lifespan=lifespan)
api_router = APIRouter(prefix="/api/v1")

@api_router.get("/health")
async def health_check():
    try:
        driver = neo4j_connection.connect()
        if not driver:
            raise HTTPException(status_code=500, detail="Failed to connect to database")
        server_info = neo4j_connection.verify_connection()
        return {"status": "healthy", "database": os.getenv("NEO4J_DATABASE_NEW"), "server_info": server_info}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
# === ROUTE ===
@api_router.get("/get-database-info", tags=["database"])
def get_database_info() -> Dict[str, Any]:
    """
    Returns the name of the current Neo4j database and a list of all available databases.

    Returns:
        Dict[str, Any]: {
            "current_database": "<name>",
            "available_databases": ["db1", "db2", ...]
        }
    """
    driver: Optional[Driver] = None
    try:
        driver = neo4j_connection.connect()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to connect to Neo4j: {e}")
    databasename = os.getenv("NEO4J_DATABASE")
    with driver.session(database="lostandfound") as session:
        try:
            # Get current database
            current_db_result = session.run("SHOW HOME DATABASE")
            current_db = current_db_result.single()["name"]
            # Get all databases
            databases_result = session.run("SHOW DATABASES")
            available_databases = [record["name"] for record in databases_result]

            return {
                "current_database": current_db,
                "available_databases": available_databases
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error querying databases: {e}")



@api_router.get("/get_database_indexes",tags=["database"])
def get_database_indexes() -> List[Dict[str, Any]]:
    """
    Get all indexes from the Neo4j database.
    
    Returns:
        List[Dict[str, Any]]: List of index information including name, type, labels, properties, and status
    """
    driver: Optional[Driver] = None
    try:
        driver = neo4j_connection.connect()
    except Exception as e:
        print(f"Failed to connect to Neo4j: {e}")
        return []
        
    with driver.session(database="lostandfound") as session:
        try:
            # First get the current database name
            db_result = session.run("SHOW HOME DATABASE")
            result = session.run("SHOW INDEXES")
            return db_result
        except Exception as e:
            print(f"Error checking indexes: {e}")
            return []



# Include all routers
app.include_router(api_router)
app.include_router(graphinput.router)

