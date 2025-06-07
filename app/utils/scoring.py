# Scoring utilities

from typing import List
from app.models.concept import ConceptMatch
import numpy as np

def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    # Cosine Similarity
    # Main metric for vector search embeddings.
    # Fast, well-understood, captures semantic similarity well.
    vec1, vec2 = np.array(vec1), np.array(vec2)
    if np.linalg.norm(vec1) == 0 or np.linalg.norm(vec2) == 0:
        return 0.0
    return float(np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2)))

def min_max_normalize(scores: List[float]) -> List[float]:
    # Min-Max Normalization
    # Normalize scores between 0 and 1 for easier combination and thresholding.
    # Use this especially if you combine vector scores with cross-encoder or GPT scores, which might have different ranges.
    min_score, max_score = min(scores), max(scores)
    if max_score == min_score:
        return [0.0 for _ in scores]
    return [(s - min_score) / (max_score - min_score) for s in scores]

def top_k(matches: List[ConceptMatch], scores: List[float], k: int) -> List[ConceptMatch]:
    # Top-K Filter
    # Keep only the most relevant matches after reranking.
    # Simple but important for efficiency and clarity downstream.
    paired = list(zip(matches, scores))
    paired.sort(key=lambda x: x[1], reverse=True)
    return [p[0] for p in paired[:k]]


# Optional (Add Later)
# Weighted average if you want to blend vector similarity + cross-encoder + GPT scores into one final number.
# Other distance metrics only if you find cosine doesn’t suit your embeddings.