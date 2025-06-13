# Pipeline orchestration function

from app.utils.embeddings import get_embeddings, get_similar_concepts
from .cross_encoder import cross_encode_rerank
from .gpt_reranker import gpt_final_rerank
from app.models.concept import ConceptInput, ConceptMatch
from typing import List


def semantic_ranking_pipeline(query: ConceptInput) -> List[ConceptMatch]:
    query_embedding = get_embeddings(query.name + " " + query.description)
    print(f"Query embedding: {query.name + " " + query.description}")

    vector_matches = get_similar_concepts(query_embedding)
    print(f"Vector matches: {vector_matches}")

    reranked_matches = cross_encode_rerank(query.name + " " + query.description, vector_matches)
    print(f"Reranked matches: {reranked_matches}")

    final_ranked = gpt_final_rerank(query, reranked_matches)
    print(f"Final ranked: {final_ranked}")

    return final_ranked
