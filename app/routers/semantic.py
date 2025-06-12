from fastapi import APIRouter, HTTPException
from app.pipeline.pipeline import semantic_ranking_pipeline
from app.models.concept import ConceptInput, ConceptMatch
from typing import List

router = APIRouter(
    prefix="/semantic",
    tags=["semantic"],
    responses={404: {"description": "Not found"}},
)

@router.post("/rank", response_model=List[ConceptMatch])
async def rank_concepts(query: ConceptInput) -> List[ConceptMatch]:
    """
    Rank concepts semantically based on the input query.
    
    Args:
        query (ConceptInput): The input query containing name and description
        
    Returns:
        List[ConceptMatch]: List of ranked concept matches
    """
    try:
        return semantic_ranking_pipeline(query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 