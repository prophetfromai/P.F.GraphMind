from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, APIRouter
from .database import neo4j_connection
from .routers import graphinput
from pydantic import BaseModel
from typing import Optional, Dict, Any
from neo4j import Driver
from contextlib import asynccontextmanager
import os

load_dotenv()
print(f'database name {os.getenv("NEO4J_DATABASE_NEW")} and {os.getenv("NEO4J_URI")}') 
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


class ItemCreate(BaseModel):
    name: str
    description: str
    category: str
    location_name: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "location_name": self.location_name
        }

@api_router.get("/health")
async def health_check():
    driver: Optional[Driver] = None
    try:
        driver = neo4j_connection.connect
        if not driver:
            raise HTTPException(status_code=500, detail="Failed to connect to database")
        driver.verify_connectivity()
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if driver:
            driver.close()

# Include all routers
app.include_router(api_router)
app.include_router(graphinput.router)