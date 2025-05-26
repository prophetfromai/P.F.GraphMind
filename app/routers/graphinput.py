import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from neo4j import Driver
from typing import List, Optional, Dict, Any, Literal
from ..database import neo4j_connection
from openai import OpenAI


router = APIRouter(prefix="/api/v1/input", tags=["input"])
client = OpenAI()

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
    embedding: Optional[List[float]] = None
    similarity: Optional[float] = None
    


class CompareResult(BaseModel):
    status: Literal['new', 'extend', 'equal']

class CombinedSummary(BaseModel):
    name: str
    description: str
    notes: Optional[str] = None  # any additional clarification or nuance

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
    
    print(f'Zac test rating1, rating2 {rating1}, {rating2}')
    
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
        real_return = [x for x in result]
        print(f'ZAC TEST  - real result {real_return} and first position {real_return[0]}')
        return_value = [ConceptMatch(**r) for r in result]
        print(f'Best match found in the list {return_value[0]}')
        return return_value

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
    print(f'zac test result {result} new idea {new.name} and existing {existing.name}')
    return result

def combine_ideas_llm(new: ConceptInput, existing: ConceptMatch) -> CombinedSummary:
    user_input = f"""
    New Idea:
    {new.name}: {new.description}

    Existing Idea:
    {existing.name}: {existing.description}
    """

    prompt = """
    You are an assistant helping a user maintain an accurate and detailed knowledge graph of their ideas.
    Your job is to merge two ideas — keeping all original information intact and not hallucinating or inferring beyond what is written.

    Generate a single, combined version of the two ideas. You must:
    - Preserve all meaningful information from both the new and existing idea.
    - Not invent, assume, or compress ideas beyond what is written.
    - Create a clear, merged title and description that unifies both without losing meaning.
    - Include optional notes if any distinctions between the two should be preserved.

    Reply in this format:
    {
        "name": "...",
        "description": "...",
        "notes": "..."
    }
    """

    completion = client.beta.chat.completions.parse(
        model="gpt-4o-2024-08-06",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_input}
        ],
        response_format=CombinedSummary
    )
    return completion.choices[0].message.parsed

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
                    c.embedding = $embedding, c.combined_summary = $combined_summary
                WITH c
                MATCH (e:Concept {name: $existing})
                MERGE (c)-[:EXTENDS]->(e)
                SET e.interval = e.interval + 1, e.lastReviewed = date()
            """, name=new.name, desc=new.description,
                 existing=best_match.name, embedding=new.embedding, 
                 combined_summary=best_match.combined_summary)
        
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


# === ROUTES ===
@router.post("/combine-ideas", response_model=CombinedSummary)
def combine_ideas_endpoint(new: ConceptInput, existing: ConceptMatch):
    return combine_ideas_llm(new, existing)

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



@router.post("/submit-idea")
def submit_idea(idea: ConceptInput):
    print(f'zac test submit idea embeddings {idea.description}')
    
    # Step 1: Generate embedding
    idea.embedding = get_embeddings(f'name: {idea.name} description: {idea.description}')
    
    # Step 2: Find similar concepts (already sorted by similarity)
    matches = get_similar_concepts(idea.embedding)  # Should return a list sorted by similarity
    
    # Step 3: Pick the top match
    best = matches[0] if matches else None
    
    # Step 4: Decide what to do
    if best:
        final_decision = updated_compare_with_llm(idea, best)
        
        if final_decision == "extend":
            combined = combine_ideas_llm(idea, best)
            best.combined_summary = f'name: {combined.name}, description: {combined.description}, notes: {combined.notes}'
            best.embedding = get_embeddings(
                f'name: {best.name} description: {best.description} combined_summary: {best.combined_summary}'
            )
        
        integrate_concept(idea, best, final_decision)
        
        return {
            "integrated_against": best.name,
            "similarity": best.similarity,
            "decision": final_decision
        }

    # Step 5: No match found — treat as new
    integrate_concept(idea, None, "new")
    return {
        "integrated_against": None,
        "decision": "new"
    }


# def workflow(idea: ConceptInput):
#     '''
#     First tell it as a story
#     1. find the top 5 closest ideas using the idea as embeddings
#     2. decide how if at all it is similar, dissimilar
#         if its similar or the same, either extend the existing idea or create a new idea
#     3. To extend an existing idea because its almost the same, first check the connections it has and what nodes
#         and use them in the prompt to analyse the new entry for likeness. ONLY allowing a maximum of x new connections and nodes
#         if they are required. 
#     4. 
#     linked one 

#     Finish with your action to start the next time faster e.g. Carry on from exactly here graphinput line 310, we were listing the 
#     way we are building the app > split into features and start building. Task list. Doesn't matter, just keep coming back. 
#     50 pullups, 50 pressups, 50 writing code. This is a diary now, this should be going into the graph.

#     '''