from datetime import datetime
from neo4j import Driver
from app.database import neo4j_connection
from app.models.concept import ConceptInput, EvolutionResult
from app.utils.db_utils import get_next_version
from typing import Optional

def integrate_concept(new: ConceptInput, evolution: EvolutionResult) -> bool:
    """
    Integrate the new concept into the graph with bitemporal tracking.
    """
    driver: Optional[Driver] = None
    try:
        driver = neo4j_connection.connect()
    except Exception as e:
        print(f"Failed to connect to Neo4j: {e}")
        return False

    if not driver:
        return False

    now = datetime.now()
    valid_from = new.valid_from or now

    with driver.session() as session:
        # Get next version number
        version = get_next_version(new.name, driver)
        
        # Create new version
        session.run("""
            MERGE (c:Concept {name: $name})
            CREATE (v:ConceptVersion {
                name: $name,
                description: $desc,
                embedding: $embedding,
                valid_from: $valid_from,
                valid_to: null,
                transaction_from: $transaction_from,
                transaction_to: null,
                version: $version,
                context: $context
            })
            MERGE (c)-[:HAS_VERSION]->(v)
            SET c.current_version = $version
        """, name=new.name,
             desc=new.description,
             embedding=new.embedding,
             valid_from=valid_from,
             transaction_from=now,
             version=version,
             context=new.context)
        
        # Create evolutionary relationships
        for parent in evolution.parent_versions:
            session.run("""
                MATCH (v:ConceptVersion {name: $child_name, version: $child_version})
                MATCH (p:ConceptVersion {name: $parent_name, version: $parent_version})
                MERGE (v)-[r:EVOLVED_FROM]->(p)
                SET r.type = $evolution_type,
                    r.confidence = $confidence,
                    r.explanation = $explanation,
                    r.transaction_from = $transaction_from
            """, child_name=new.name,
                 child_version=version,
                 parent_name=parent["name"],
                 parent_version=parent["version"],
                 evolution_type=evolution.evolution_type,
                 confidence=evolution.confidence,
                 explanation=evolution.explanation,
                 transaction_from=now)
        
        return True

def create_new_concept(concept: ConceptInput):
    driver: Optional[Driver] = None
    try:
        driver = neo4j_connection.connect()
    except Exception as e:
        print(f"Failed to connect to Neo4j: {e}")
        return False

    with driver.session() as session:
        session.run("""
            CREATE (c:Concept {
                name: $name,
                description: $desc,
                createdAt: date(),
                lastReviewed: date(),
                interval: 1,
                embedding: $embedding
            })
        """, name=concept.name, desc=concept.description, embedding=concept.embedding)
    
    return True 