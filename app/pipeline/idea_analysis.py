from typing import List
from app.core.openai_client import client
from app.models.concept import ConceptInput, ConceptMatch, CompareResult, CombinedSummary, EvolutionResult, RankingsResponse

# def updated_compare_with_llm(new: ConceptInput, existing: ConceptMatch) -> CompareResult:
#     user_input = f"""
#     New Idea:
#     {new.name}: {new.description}

#     Existing Idea:
#     {existing.name}: {existing.description}
#     """
    
#     prompt = f"""
#     Compare the two ideas:

#     New Idea:
#     {new.name}: {new.description}

#     Existing Idea:
#     {existing.name}: {existing.description}

#     Which idea extends an existing idea, is more novel or useful or equal to the existing idea? Reply with 'new', 'extend', or 'equal'.

#     Example Usage:
#     New Idea:
#     Small context note taking app connected to a knowledge graph using image of hand written text. 

#     Existing Idea:
#     An app connected to a knowledge graph to record what I write. 
#     """
    
#     completion = client.beta.chat.completions.parse(
#         model="gpt-4o-2024-08-06",
#         messages=[
#             {"role": "system", "content": prompt},
#             {"role": "user", "content": user_input}
#         ],
#         response_format=CompareResult
#     )
    
#     result = completion.choices[0].message.parsed
#     return result(**CompareResult)

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