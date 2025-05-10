from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Literal
from datetime import date
from neo4j import GraphDatabase,Driver
from typing import List, Optional, Dict, Any, Literal
from ..database import neo4j_connection
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()
import os
import json

router = APIRouter(prefix="/api/v1/input", tags=["input"])

client = OpenAI()

# === CONFIG ===
# NEO4J_URI = "bolt://localhost:7687"
# NEO4J_USER = "neo4j"
# NEO4J_PASSWORD = "your_password"
# OPENAI_API_KEY = "your_openai_key"
# openai.api_key = OPENAI_API_KEY

# === MODELS ===
class ConceptInput(BaseModel):
    name: str
    description: str
    embedding: Optional[List[float]] = None

class ConceptMatch(BaseModel):
    name: str
    description: str
    score: float
    combined_summary: Optional[str] = None


class StatusResponse(BaseModel):
    status: Literal['new', 'extend', 'equal']

# # === INIT ===
# app = FastAPI()


# === UTILS ===
def calculate_elo_rating(rating1: float, rating2: float, result: float, k_factor: float = 32) -> tuple[float, float]:
    """
    Calculate new Elo ratings for two players.
    
    Args:
        rating1: Current rating of first player
        rating2: Current rating of second player
        result: Result of the match (1.0 for first player win, 0.0 for second player win, 0.5 for draw)
        k_factor: K-factor determines how much ratings change (default: 32)
    
    Returns:
        tuple: (new_rating1, new_rating2)
    """
    # Calculate expected scores
    expected1 = 1 / (1 + 10 ** ((rating2 - rating1) / 400))
    expected2 = 1 - expected1
    
    # Calculate new ratings
    new_rating1 = rating1 + k_factor * (result - expected1)
    new_rating2 = rating2 + k_factor * ((1 - result) - expected2)
    
    return new_rating1, new_rating2

def get_embeddings(input: str):
    response = client.embeddings.create(
    input=input,
    model="text-embedding-3-small"
    )

    return(response.data[0].embedding)

def get_similar_concepts(embedding: List[float], k: int = 5) -> List[ConceptMatch]:
    driver: Optional[Driver] = None
    try:
        driver = neo4j_connection.connect()
    except Exception as e:
        print(f"Failed to connect to Neo4j: {e}")
        return []
    
    with driver.session() as session:
        result = session.run("""
            CALL db.index.vector.queryNodes("conceptVectorIndex", $k, $embedding)
            YIELD node, score
            RETURN node.name AS name, node.description AS description, score
            ORDER BY score DESC
        """, k=k, embedding=embedding)
        return_value = [ConceptMatch(**r) for r in result]
        print(f'first in the list {return_value[0]}')
        return return_value

class CompareResult(BaseModel):
    status: Literal['new', 'extend', 'equal']

def updated_compare_with_llm(new: ConceptInput, existing: ConceptMatch) -> CompareResult:
    user_input = f"""
    New Idea:
    {new.name}: {new.description}

    Existing Idea:
    {existing.name}: {existing.description}
    """
    

    prompt = f"""
    Compare the two ideas:

    New Idea:
    {new.name}: {new.description}

    Existing Idea:
    {existing.name}: {existing.description}

    Which idea extends an existing idea, is more novel or useful or equal to the existing idea? Reply with 'new', 'extend', or 'equal'.

    Example Usage:
    New Idea:
    Small context note taking app connected to a knowledge graph using image of hand written text. 

    Existing Idea:
    An app connected to a knowledge graph to record what I write. 
    """
    completion = client.beta.chat.completions.parse(
        model="gpt-4o-2024-08-06",
        messages=[{"role": "system", "content": prompt},
                   {"role": "user", "content": user_input}],
        response_format=CompareResult,
    )
    result = completion.choices[0].message.parsed
    # result = response["choices"][0]["message"]["content"].strip().lower()
    # Use the Pydantic model to validate and enforce allowed values
    return result.status


@router.post("/compare-concept", response_model=CompareResult)
def compare_concept(new: ConceptInput, existing: ConceptMatch):
    return updated_compare_with_llm(new, existing)

@router.post("/concept/create", response_model=Dict[str, str])
def create_concept(concept: ConceptInput):
    success = create_new_concept(concept)
    if success:
        return {"status": "Concept created successfully"}
    else:
        return {"status": "Failed to create concept"}

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


def integrate_concept(new: ConceptInput, best_match: ConceptMatch, decision: CompareResult):
    driver: Optional[Driver] = None
    try:
        driver = neo4j_connection.connect()
    except Exception as e:
        print(f"Failed to connect to Neo4j: {e}")
        return []

    with driver.session() as session:
        if decision == "extend":
            session.run("""
                MERGE (c:Concept {name: $name})
                SET c.description = $desc, c.createdAt = date(),
                    c.lastReviewed = date(), c.interval = 1,
                    c.embedding = $embedding, c.combinted_summary = $combinted_summary
                WITH c
                MATCH (e:Concept {name: $existing})
                MERGE (c)-[:EXTENDS]->(e)
                SET e.interval = e.interval + 1, e.lastReviewed = date()
            """, name=new.name, desc=new.description,
                 existing=best_match.name, embedding=new.embedding, 
                 combinted_summary=best_match.combined_summary)
        
        elif decision == "equal":
            session.run("""
                MATCH (c:Concept {name: $existing})
                SET c.description = $desc
            """, existing=best_match.name, desc=new.description)

        elif decision == "new":
            session.run("""
                MERGE (c:Concept {name: $name})
                SET c.description = $desc, c.createdAt = date(),
                    c.lastReviewed = date(), c.interval = 1,
                    c.embedding = $embedding
            """, name=new.name, desc=new.description, embedding=new.embedding)


# === ROUTE ===
@router.get("/get-database-info", tags=["database"])
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



@router.get("/get_database_indexes",tags=["database"])
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


@router.post("/submit-idea")
def submit_idea(idea: ConceptInput):
    print(f'zac test submit idea embeddings {idea.description}')
    idea.embedding = get_embeddings(f'name: {idea.name} description: {idea.description}')

    matches = get_similar_concepts(idea.embedding)
   # Initialize scores with default Elo rating of 1500
   # Start with the closest ranking to the idea > connectedness/x_connectiondepth... of the top k results.
   # Consolidating and distilling knowledge upwards.
   # Small human context window with your lense/s applied; personal current context.
   # Influence and prime your system two and system one to make reliable decisions,
   # influenced by your own choice/s and perspective/s and taste/s. 
   # I believe that the manufacturable minerals of the future digital fossil fuels (like mining 1 bitcoin in a week on a normal computer) 
   # is in the organic, opinionated construction of knowledge graphs which also include meta-thinking and mapping of decision making graph structures 
   # that can be developed/grown organically, slowly, over time. 
    scores = {m.name: 1500 for m in matches}
    scores[idea.name] = 1500  # Initialize new idea's score
    
    for match in matches:
        winner = updated_compare_with_llm(idea, match)
        
        # Update ratings using our Elo calculation
        # 
        if winner == "new":
            scores[idea.name], scores[match.name] = calculate_elo_rating(
                scores[idea.name], 
                scores[match.name],
                result=1.0  # new idea wins
            )
        elif winner == "extend":
            scores[idea.name], scores[match.name] = calculate_elo_rating(
                scores[idea.name], 
                scores[match.name],
                result=0.0  # existing idea wins
            )
        else:  # winner == "equal"
            scores[idea.name], scores[match.name] = calculate_elo_rating(
                scores[idea.name], 
                scores[match.name],
                result=0.5  # draw
            )

    if len(matches) >0:
        best = max(matches, key=lambda m: scores[m.name])
    final_decision = updated_compare_with_llm(idea, best)
    integrate_concept(idea, best, final_decision)

    return {"integrated_against": best.name, "decision": final_decision, "score": scores}
