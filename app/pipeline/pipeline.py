# Pipeline orchestration function

from app.utils.embeddings import get_embeddings
from .vector_search import vector_search
from .cross_encoder import cross_encode_rerank
from .gpt_reranker import gpt_final_rerank
from models.concept import ConceptInput, ConceptMatch
from typing import List

def semantic_ranking_pipeline(query: ConceptInput) -> List[ConceptMatch]:
    query_embedding = get_embeddings(query.name + " " + query.description)
    vector_matches = vector_search(query_embedding)
    reranked_matches = cross_encode_rerank(query.name + " " + query.description, vector_matches)
    final_ranked = gpt_final_rerank(query, reranked_matches)
    return final_ranked
