# GPT-based final reranker

from typing import List, Dict, Optional
from pydantic import BaseModel
from datetime import datetime
from app.core.openai_client import client
from app.models.concept import ConceptInput, ConceptMatch, RankingsResponse


def gpt_final_rerank(query: ConceptInput, matches: List[ConceptMatch], top_k: int = 3) -> List[ConceptMatch]:
    """
    Rerank a list of concept matches using GPT-4 based on semantic similarity and detail.
    """
    if not matches:
        return []

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
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a precise ranking system that evaluates semantic relationships between ideas."},
            {"role": "user", "content": prompt}
        ],
        response_format=RankingsResponse
    )

    if not completion.choices[0].message.content:
        return sorted(matches, key=lambda x: x.score, reverse=True)[:top_k]

    rankings = RankingsResponse.model_validate_json(completion.choices[0].message.content)

    for match in matches:
        if match.name in rankings.rankings:
            match.similarity = rankings.rankings[match.name].relevance
        else:
            match.similarity = match.score

    return sorted(matches, key=lambda x: match.similarity or 0.0, reverse=True)[:top_k]
