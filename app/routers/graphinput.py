from fastapi import FastAPI, Body
from pydantic import BaseModel
from typing import List
from datetime import date
from neo4j import GraphDatabase,Driver
import openai
from typing import List, Optional, Dict, Any, Literal
from ..database import neo4j_connection

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
    embedding: List[float]

class ConceptMatch(BaseModel):
    name: str
    description: str
    score: float

# === INIT ===
app = FastAPI()


# === UTILS ===
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

def compare_with_llm(new: ConceptInput, existing: ConceptMatch) -> str:
    prompt = f"""
    Compare the two ideas:

    New Idea:
    {new.name}: {new.description}

    Existing Idea:
    {existing.name}: {existing.description}

    Which idea is more novel or useful? Reply with 'new', 'existing', or 'equal'.
    """
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return response["choices"][0]["message"]["content"].strip().lower()

def integrate_concept(new: ConceptInput, best_match: ConceptMatch, decision: str):
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
@app.post("/submit-idea")
def submit_idea(idea: ConceptInput):
    matches = get_similar_concepts(idea.embedding)
    scores = {m.name: 1200 for m in matches}

    for match in matches:
        winner = compare_with_llm(idea, match)
        if winner == "new":
            scores[idea.name] = scores.get(idea.name, 1200) + 30
            scores[match.name] -= 30
        elif winner == "existing":
            scores[match.name] += 30
            scores[idea.name] = scores.get(idea.name, 1200) - 30

    best = max(matches, key=lambda m: scores[m.name])
    final_decision = compare_with_llm(idea, best)
    integrate_concept(idea, best, final_decision)

    return {"integrated_against": best.name, "decision": final_decision, "score": scores}
