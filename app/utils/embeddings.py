from typing import List
from app.core.openai_client import client
from app.models.concept import ConceptMatch
from typing import Optional

def get_embeddings(input: str) -> List[float]:
    response = client.embeddings.create(
        input=input,
        model="text-embedding-3-small"
    )
    print(f"Retrieved embedding for {input}")
    return response.data[0].embedding

def get_similar_concepts(embedding: List[float], k: int = 5) -> List[ConceptMatch]:
    from app.database import neo4j_connection
    from app.models.concept import ConceptMatch
    from neo4j import Driver
    
    driver: Optional[Driver] = None
    try:
        driver = neo4j_connection.connect()
    except Exception as e:
        print(f"Failed to connect to Neo4j: {e}")
        return []
    
    if not driver:
        return []
    print(f"Searching for similar concepts in Neo4j with embeddings")
    with driver.session() as session:
        result = session.run("""
            CALL {
                // Search Concept nodes
                CALL db.index.vector.queryNodes("conceptVectorIndex", $k, $embedding)
                YIELD node, score
                WHERE node.embedding IS NOT NULL
                RETURN node.name AS name, 
                       node.description AS description, 
                       score,
                       node.embedding AS embedding,
                       datetime() AS valid_from,
                       null AS valid_to,
                       1 AS version
                UNION
                // Search ConceptVersion nodes
                CALL db.index.vector.queryNodes("conceptVersionVectorIndex", $k, $embedding)
                YIELD node, score
                WHERE node.transaction_to IS NULL  // Only current versions
                RETURN node.name AS name, 
                       node.description AS description, 
                       score,
                       node.embedding AS embedding,
                       node.valid_from AS valid_from,
                       node.valid_to AS valid_to,
                       node.version AS version
            }
            RETURN name, description, score, embedding, valid_from, valid_to, version
            ORDER BY score DESC
            LIMIT $k
        """, k=k, embedding=embedding)
        results = [ConceptMatch(**record) for record in result] 
        print(f"results: {results}")
        return results