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
from app.utils.embeddings import get_embeddings, get_similar_concepts
from app.core.idea_analysis import updated_compare_with_llm, combine_ideas_llm, analyze_evolution, rerank_matches
from app.pipeline.concept_management import integrate_concept, create_new_concept

router = APIRouter(prefix="/api/v1/input", tags=["input"])


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
    initial_matches = get_similar_concepts(idea.embedding, k=10)
    return initial_matches

@router.post("/get-similar-ideas-reranked")
def get_similar_ideas_reranked(idea: ConceptInput):
    # Step 1: Generate embedding
    idea.embedding = get_embeddings(f'name: {idea.name} description: {idea.description}')
    
    # Step 2: Find similar concepts using vector search
    initial_matches = get_similar_concepts(idea.embedding, k=10)
    reranked_matches = rerank_matches(idea, initial_matches)
    return reranked_matches


