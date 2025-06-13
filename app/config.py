# Core Settings for App
# .env loading logic
# Constants and environment variable access
# Any helper functions for accessing settings
# Pydantic BaseSettings model (optional but best practice)
# core/config.py

import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Neo4j Configuration
    NEO4J_URI: str
    NEO4J_USER: str
    NEO4J_PASSWORD: str
    NEO4J_DATABASE: str = "neo4j"
    NEO4J_DATABASE_NEW: str = "neo4j"

    # App Info
    app_name: str = "Awesome API"
    admin_email: str = "zachary.gander@prophetfrom.ai"
    items_per_user: int = 50

    OPENAI_API_KEY: str


    class Config:
        env_file = ".env"

settings = Settings()
