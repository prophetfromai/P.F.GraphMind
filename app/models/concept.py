from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Literal, Union
from datetime import datetime

# === MODELS ===
class ConceptInput(BaseModel):
    name: str
    description: str
    embedding: Optional[List[float]] = None
    valid_from: Optional[datetime] = None  # When the concept became true
    context: Optional[str] = None  # Additional context about when/where/why

class ConceptVersion(BaseModel):
    name: str
    description: str
    embedding: Optional[List[float]] = None
    valid_from: datetime
    valid_to: Optional[datetime] = None
    transaction_from: datetime
    transaction_to: Optional[datetime] = None
    version: int
    context: Optional[str] = None

class ConceptMatch(BaseModel):
    name: str
    description: str
    score: float
    embedding: Optional[List[float]] = None
    similarity: Optional[float] = None
    valid_from: datetime
    valid_to: Optional[datetime] = None
    version: int

class EvolutionResult(BaseModel):
    parent_versions: List[Dict[str, Any]]  # List of parent concept versions
    evolution_type: Literal['variation', 'combination', 'refinement', 'branch']
    confidence: float
    explanation: str

class CompareResult(BaseModel):
    status: Literal['new', 'extend', 'equal']

class CombinedSummary(BaseModel):
    name: str
    description: str
    notes: Optional[str] = None

class RankingResult(BaseModel):
    relevance: float
    explanation: str

class RankingsResponse(BaseModel):
    rankings: Dict[str, RankingResult]