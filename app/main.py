from dotenv import load_dotenv
load_dotenv(override=True)
from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.utils.neo4j_client import neo4j_connection
from app.routers import ideas, health, database
import os

@asynccontextmanager
async def lifespan(app: FastAPI):
    if not neo4j_connection.verify_connection():
        raise Exception("Neo4j connection failed")
    yield
    neo4j_connection.close()

app = FastAPI(title="Neo4j FastAPI Example", lifespan=lifespan)

# Mount routers
app.include_router(health.router)
app.include_router(database.router)
app.include_router(ideas.router)
