# Neo4j DB connectors/queries

from neo4j import GraphDatabase
import os
from typing import Optional
import logging


class Neo4jConnection:
    def __init__(self):
        self.uri: str = os.getenv("NEO4J_URI", "")
        self.user: str = os.getenv("NEO4J_USER", "")
        self.password: str = os.getenv("NEO4J_PASSWORD", "")
        self.driver: Optional[GraphDatabase.driver] = None
        self.database: str = os.getenv("NEO4J_DATABASE_NEW", "")

        # Verify required environment variables
        if not all([self.uri, self.user, self.password]):
            raise ValueError("Missing required environment variables for Neo4j connection")

    def connect(self):
        if not all([self.uri, self.user, self.password]):
            raise ValueError("Missing required environment variables for Neo4j connection")
        self.driver = GraphDatabase.driver(
            self.uri,
            auth=(self.user, self.password),
        )
        return self.driver

    def close(self):
        if self.driver is not None:
            self.driver.close()

    def verify_connection(self):
        try:
            with self.connect() as driver:
                print(f"Connection successful! database name:{self.database}")

                verify = driver.verify_connectivity()
                server_info = driver.get_server_info()
                print(f'ZAC TEST verify {verify} {driver.get_server_info()}')
                return server_info
        except Exception as e:
            print(f"Connection error: {e}")
            return False

# Create a single instance to be used across the application
neo4j_connection = Neo4jConnection() 