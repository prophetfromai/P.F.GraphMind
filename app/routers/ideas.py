import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from neo4j import Driver
from typing import List, Optional, Dict, Any, Literal, Union
from ..database import neo4j_connection
from openai.types.chat import ChatCompletionMessage
from datetime import datetime
from app.core.openai_client import client
from app.models.concept import ConceptInput, ConceptMatch, CompareResult, CombinedSummary, EvolutionResult, RankingsResponse

router = APIRouter(prefix="/api/v1/input", tags=["input"])

# === UTILS ===

def get_embeddings(input: str) -> List[float]:
    response = client.embeddings.create(
        input=input,
        model="text-embedding-3-small"
    )
    print(f"Embedding response: {response}")
    return response.data[0].embedding

def get_similar_concepts(embedding: List[float], k: int = 5) -> List[ConceptMatch]:
    driver: Optional[Driver] = None
    try:
        driver = neo4j_connection.connect()
    except Exception as e:
        print(f"Failed to connect to Neo4j: {e}")
        return []
    
    if not driver:
        return []
        
    with driver.session() as session:
        result = session.run("""
            CALL db.index.vector.queryNodes("conceptVectorIndex", $k, $embedding)
            YIELD node, score
            WHERE node.transaction_to IS NULL  // Only current versions
            RETURN node.name AS name, 
                   node.description AS description, 
                   score,
                   node.embedding AS embedding,
                   node.valid_from AS valid_from,
                   node.valid_to AS valid_to,
                   node.version AS version
            ORDER BY score DESC
        """, k=k, embedding=embedding)
        
        return [ConceptMatch(**record) for record in result]

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
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_input}
        ],
        response_format=CompareResult
    )
    
    result = completion.choices[0].message.parsed
    return result(**CompareResult)

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
    """

    completion = client.beta.chat.completions.parse(
        model="gpt-4o-2024-08-06",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_input}
        ],
        response_format=CombinedSummary
    )
    
    result = completion.choices[0].message.parsed
    return CombinedSummary(**result)

def analyze_evolution(new: ConceptInput, matches: List[ConceptMatch]) -> EvolutionResult:
    """
    Analyze how the new concept might evolve from existing concepts.
    """
    prompt = f"""
    Analyze how this new idea might have evolved from existing ideas in the knowledge graph.
    Consider:
    1. Which existing ideas might have influenced this new idea
    2. What type of evolution occurred (variation, combination, refinement, or branching)
    3. How confident you are in this analysis
    4. Why this evolution makes sense

    New Idea:
    {new.name}: {new.description}
    Context: {new.context}

    Existing Ideas:
    {[f"{m.name} (v{m.version}): {m.description}" for m in matches]}
    """
    
    completion = client.beta.chat.completions.parse(
        model="gpt-4o-2024-08-06",
        messages=[
            {"role": "system", "content": "You are an evolutionary analysis system that identifies how ideas evolve and connect."},
            {"role": "user", "content": prompt}
        ],
        response_format=EvolutionResult
    )
    
    if not completion.choices[0].message.content:
        return EvolutionResult(
            parent_versions=[],
            evolution_type="branch",
            confidence=0.0,
            explanation="No evolution analysis available"
        )
    print(f"--------Evolution result: {completion.choices[0].message.content}")
    return EvolutionResult.model_validate_json(completion.choices[0].message.content)

def get_next_version(name: str, driver: Driver) -> int:
    """Get the next version number for a concept."""
    with driver.session() as session:
        result = session.run("""
            MATCH (c:Concept {name: $name})
            RETURN max(c.version) as max_version
        """, name=name)
        record = result.single()
        return (record["max_version"] or 0) + 1

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

def rerank_matches(query: ConceptInput, matches: List[ConceptMatch], top_k: int = 3) -> List[ConceptMatch]:
    """
    Rerank the initial matches using semantic relevance to determine how closely
    the new idea matches existing concepts.
    """
    prompt = f"""
    Given a new idea and a list of existing ideas, analyze how closely they match.
    Consider both semantic meaning and specific details.
    
    New Idea:
    {query.name}: {query.description}
    
    Existing Ideas:
    {[f"{m.name}: {m.description}" for m in matches]}
    
    For each existing idea, provide:
    1. A relevance score (0-1) - how closely it matches the new idea
    2. A brief explanation of why it's relevant or not
    """
    
    completion = client.beta.chat.completions.parse(
        model="gpt-4o-2024-08-06",
        messages=[
            {"role": "system", "content": "You are a precise ranking system that evaluates semantic relationships between ideas."},
            {"role": "user", "content": prompt}
        ],
        response_format=ConceptMatch
    )
    
    if not completion.choices[0].message.content:
        return matches[:top_k]
        
    rankings = RankingsResponse.model_validate_json(completion.choices[0].message.content)
    
    # Update the similarity scores in the matches
    for match in matches:
        if match.name in rankings.rankings:
            match.similarity = rankings.rankings[match.name].relevance
        else:
            match.similarity = match.score
    
    # Sort by the relevance score
    matches.sort(key=lambda x: x.similarity if x.similarity is not None else 0.0, reverse=True)
    return matches[:top_k]

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
    # Step 1: Generate embedding
    idea.embedding = get_embeddings(f'name: {idea.name} description: {idea.description}')
    
    # Step 2: Find similar concepts using vector search
    initial_matches = get_similar_concepts(idea.embedding, k=10)
    
    # Step 3: Analyze evolution
    evolution = analyze_evolution(idea, initial_matches)
    
    # Step 4: Integrate into graph
    success = integrate_concept(idea, evolution)
    
    return {
        "status": "success" if success else "failed",
        "evolution": evolution,
        "related_concepts": [{"name": m.name, "version": m.version} for m in initial_matches[:3]]
    }

@router.get("/concept/{name}/history")
def get_concept_history(name: str):
    """Get the version history of a concept."""
    driver: Optional[Driver] = None
    try:
        driver = neo4j_connection.connect()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not driver:
        raise HTTPException(status_code=500, detail="Failed to connect to database")

    with driver.session() as session:
        result = session.run("""
            MATCH (c:Concept {name: $name})-[:HAS_VERSION]->(v:ConceptVersion)
            RETURN v
            ORDER BY v.version
        """, name=name)
        
        versions = [dict(record["v"]) for record in result]
        return {"name": name, "versions": versions}

@router.get("/concept/{name}/as-of/{timestamp}")
def get_concept_as_of(name: str, timestamp: datetime):
    """Get the state of a concept as of a specific point in time."""
    driver: Optional[Driver] = None
    try:
        driver = neo4j_connection.connect()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not driver:
        raise HTTPException(status_code=500, detail="Failed to connect to database")

    with driver.session() as session:
        result = session.run("""
            MATCH (c:Concept {name: $name})-[:HAS_VERSION]->(v:ConceptVersion)
            WHERE v.valid_from <= $timestamp
            AND (v.valid_to IS NULL OR v.valid_to > $timestamp)
            AND v.transaction_from <= $timestamp
            AND (v.transaction_to IS NULL OR v.transaction_to > $timestamp)
            RETURN v
            ORDER BY v.version DESC
            LIMIT 1
        """, name=name, timestamp=timestamp)
        
        record = result.single()
        if not record:
            raise HTTPException(status_code=404, detail="Concept not found for the specified time")
            
        return dict(record["v"])

@router.post("/get-similar-ideas")
def get_similar_ideas(idea: ConceptInput):
    # Step 1: Generate embedding
    idea.embedding = get_embeddings(f'name: {idea.name} description: {idea.description}')
    
    # Step 2: Find similar concepts using vector search
    initial_matches = get_similar_concepts(idea.embedding, k=10)  # Get more matches initially
    return initial_matches

@router.post("/get-similar-ideas-reranked")
def get_similar_ideas_reranked(idea: ConceptInput):
    # Step 1: Generate embedding
    idea.embedding = get_embeddings(f'name: {idea.name} description: {idea.description}')
    
    # Step 2: Find similar concepts using vector search
    initial_matches = get_similar_concepts(idea.embedding, k=10)  # Get more matches initially
    reranked_matches = rerank_matches(idea, initial_matches)
    return reranked_matches


