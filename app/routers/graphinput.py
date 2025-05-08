from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Literal
from datetime import date
from neo4j import GraphDatabase,Driver
from typing import List, Optional, Dict, Any, Literal
from ..database import neo4j_connection
from openai import OpenAI

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


class StatusResponse(BaseModel):
    status: Literal['new', 'existing', 'equal']

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
        """, embedding=embedding, k=k)
        return [ConceptMatch(**r) for r in result]

class CompareResult(BaseModel):
    status: Literal['new', 'extend', 'equal']

def updated_compare_with_llm(new: ConceptInput, existing: ConceptMatch) -> CompareResult:
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

    Reply: status: extend
    """
    completion = client.beta.chat.completions.parse(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        response_format=CompareResult,
    )
    result = completion.choices[0].message.parsed
    # result = response["choices"][0]["message"]["content"].strip().lower()
    # Use the Pydantic model to validate and enforce allowed values
    return CompareResult(result.status)

@router.post("/compare-concept", response_model=CompareResult)
def compare_concept(new: ConceptInput, existing: ConceptMatch):
    return updated_compare_with_llm(new, existing)


def integrate_concept(new: ConceptInput, best_match: ConceptMatch, decision: CompareResult):
    driver: Optional[Driver] = None
    try:
        driver = neo4j_connection.connect()
    except Exception as e:
        print(f"Failed to connect to Neo4j: {e}")
        return []
    with driver.session() as session:
        if decision == "new":
            session.run("""
                MERGE (c:Concept {name: $name})
                SET c.description = $desc, c.createdAt = date(),
                    c.lastReviewed = date(), c.interval = 1,
                    c.embedding = $embedding
                WITH c
                MATCH (e:Concept {name: $existing})
                MERGE (c)-[:EXTENDS]->(e)
            """, name=new.name, desc=new.description,
                 existing=best_match.name, embedding=new.embedding)
        elif decision == "equal":
            session.run("""
                MATCH (c:Concept {name: $existing})
                SET c.description = $desc
            """, existing=best_match.name, desc=new.description)
        # if decision is 'existing', do nothing

# === ROUTE ===
@router.post("/submit-idea")
def submit_idea(idea: ConceptInput):
    if not idea.embedding:
        idea.embedding = get_embeddings(idea.description)
    matches = get_similar_concepts(idea.embedding)
   # Initialize scores with default Elo rating of 1500
    scores = {m.name: 1500 for m in matches}
    scores[idea.name] = 1500  # Initialize new idea's score
    
    for match in matches:
        winner = updated_compare_with_llm(idea, match)
        
        # Update ratings using our Elo calculation
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

    best = max(matches, key=lambda m: scores[m.name])
    final_decision = updated_compare_with_llm(idea, best)
    integrate_concept(idea, best, final_decision)

    return {"integrated_against": best.name, "decision": final_decision, "score": scores}
