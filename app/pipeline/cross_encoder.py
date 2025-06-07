# Cross-encoder reranking

from sentence_transformers import CrossEncoder
from typing import List
from app.models.concept import ConceptMatch

model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

def cross_encode_rerank(query: str, matches: List[ConceptMatch], top_k: int = 10) -> List[ConceptMatch]:
    pairs = [(query, m.description) for m in matches]
    scores = model.predict(pairs)
    for m, score in zip(matches, scores):
        m.similarity = score
    return sorted(matches, key=lambda x: x.similarity, reverse=True)[:top_k]
