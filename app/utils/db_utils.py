from neo4j import Driver
from app.core.database import neo4j_connection

def get_next_version(name: str, driver: Driver) -> int:
    """Get the next version number for a concept."""
    with driver.session() as session:
        result = session.run("""
            MATCH (c:Concept {name: $name})
            RETURN max(c.version) as max_version
        """, name=name)
        record = result.single()
        return (record["max_version"] or 0) + 1 