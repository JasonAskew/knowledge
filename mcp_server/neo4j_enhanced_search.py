#!/usr/bin/env python3
"""
Enhanced Neo4j MCP Server with Search Capabilities
Includes vector search, hybrid search, and community-aware search
to achieve 85%+ accuracy on test queries
"""

import sys
import os
import json
import numpy as np
from typing import Dict, Any, Optional, List
from sentence_transformers import SentenceTransformer, CrossEncoder

sys.stderr.write("Starting Enhanced Neo4j Search MCP Server...\n")

from mcp.server import FastMCP

# Create the MCP server
mcp = FastMCP("knowledge-graph-search")

# Configuration
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "knowledge123")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

# Import Neo4j driver
neo4j_driver = None
try:
    from neo4j import GraphDatabase
    neo4j_driver = GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
    )
    neo4j_driver.verify_connectivity()
    sys.stderr.write(f"✓ Neo4j connection established to {NEO4J_URI}\n")
except Exception as e:
    sys.stderr.write(f"⚠️ Neo4j connection failed: {e}\n")

# Load ML models
sys.stderr.write("Loading ML models...\n")
embedding_model = None
reranker_model = None

try:
    embedding_model = SentenceTransformer('BAAI/bge-small-en-v1.5')
    sys.stderr.write("✓ Embedding model loaded\n")
except Exception as e:
    sys.stderr.write(f"⚠️ Failed to load embedding model: {e}\n")

try:
    reranker_model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
    sys.stderr.write("✓ Reranker model loaded\n")
except Exception as e:
    sys.stderr.write(f"⚠️ Failed to load reranker model: {e}\n")

# Keep the original Cypher tools for compatibility
@mcp.tool()
async def read_neo4j_cypher(query: str, params: Optional[Dict[str, Any]] = None) -> str:
    """
    Execute a Cypher read query against Neo4j database.
    
    Args:
        query: Cypher read query
        params: Optional query parameters
    
    Returns:
        Query results as JSON
    """
    if not neo4j_driver:
        return json.dumps({"error": "Neo4j connection not available"})
    
    try:
        records = []
        with neo4j_driver.session(database=NEO4J_DATABASE) as session:
            result = session.run(query, params or {})
            for record in result:
                record_dict = {}
                for key, value in dict(record).items():
                    if hasattr(value, '__dict__'):
                        record_dict[key] = dict(value)
                    else:
                        record_dict[key] = value
                records.append(record_dict)
        
        return json.dumps({
            "success": True,
            "records": records,
            "count": len(records)
        }, indent=2)
        
    except Exception as e:
        sys.stderr.write(f"Read query error: {e}\n")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, indent=2)

@mcp.tool()
async def write_neo4j_cypher(query: str, params: Optional[Dict[str, Any]] = None) -> str:
    """
    Execute a Cypher write/update query against Neo4j database.
    
    Args:
        query: Cypher update query
        params: Optional query parameters
    
    Returns:
        Summary of changes made
    """
    if not neo4j_driver:
        return json.dumps({"error": "Neo4j connection not available"})
    
    try:
        with neo4j_driver.session(database=NEO4J_DATABASE) as session:
            result = session.run(query, params or {})
            summary = result.consume()
            counters = summary.counters
            
            return json.dumps({
                "success": True,
                "summary": {
                    "nodes_created": counters.nodes_created,
                    "nodes_deleted": counters.nodes_deleted,
                    "relationships_created": counters.relationships_created,
                    "relationships_deleted": counters.relationships_deleted,
                    "properties_set": counters.properties_set,
                    "labels_added": counters.labels_added,
                    "labels_removed": counters.labels_removed
                }
            }, indent=2)
            
    except Exception as e:
        sys.stderr.write(f"Write query error: {e}\n")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, indent=2)

@mcp.tool()
async def get_neo4j_schema() -> str:
    """
    Get the schema of the Neo4j database including node labels, 
    relationships, and properties.
    
    Returns:
        Database schema as JSON
    """
    if not neo4j_driver:
        return json.dumps({"error": "Neo4j connection not available"})
    
    try:
        schema = {
            "node_labels": [],
            "relationships": [],
            "constraints": [],
            "indexes": []
        }
        
        with neo4j_driver.session(database=NEO4J_DATABASE) as session:
            result = session.run("CALL db.labels()")
            schema["node_labels"] = [record["label"] for record in result]
            
            result = session.run("CALL db.relationshipTypes()")
            schema["relationships"] = [record["relationshipType"] for record in result]
            
            result = session.run("SHOW CONSTRAINTS")
            for record in result:
                schema["constraints"].append({
                    "name": record.get("name"),
                    "type": record.get("type"),
                    "entity_type": record.get("entityType"),
                    "properties": record.get("properties", [])
                })
            
            result = session.run("SHOW INDEXES")
            for record in result:
                schema["indexes"].append({
                    "name": record.get("name"),
                    "type": record.get("type"),
                    "entity_type": record.get("entityType"),
                    "properties": record.get("properties", [])
                })
            
            schema["node_properties"] = {}
            for label in schema["node_labels"]:
                query = f"MATCH (n:{label}) RETURN n LIMIT 5"
                result = session.run(query)
                properties = set()
                for record in result:
                    node = record["n"]
                    properties.update(node.keys())
                schema["node_properties"][label] = list(properties)
            
            schema["relationship_properties"] = {}
            for rel_type in schema["relationships"]:
                query = f"MATCH ()-[r:{rel_type}]->() RETURN r LIMIT 5"
                result = session.run(query)
                properties = set()
                for record in result:
                    rel = record["r"]
                    properties.update(rel.keys())
                schema["relationship_properties"][rel_type] = list(properties)
        
        return json.dumps(schema, indent=2)
        
    except Exception as e:
        sys.stderr.write(f"Schema query error: {e}\n")
        return json.dumps({
            "error": str(e)
        }, indent=2)

# Enhanced search tools
@mcp.tool()
async def knowledge_search(
    query: str,
    search_type: str = "hybrid",
    top_k: int = 10,
    use_reranking: bool = True,
    community_weight: float = 0.3
) -> str:
    """
    Perform advanced search on the knowledge graph with multiple strategies.
    
    Args:
        query: The search query
        search_type: Type of search - "vector", "hybrid", "community", or "text2cypher"
        top_k: Number of results to return
        use_reranking: Whether to use cross-encoder reranking
        community_weight: Weight for community influence (0-1)
    
    Returns:
        Search results with documents, pages, and relevance scores
    """
    if not neo4j_driver:
        return json.dumps({"error": "Neo4j connection not available"})
    
    if not embedding_model:
        return json.dumps({"error": "Embedding model not available"})
    
    try:
        # Generate query embedding
        query_embedding = embedding_model.encode(query).tolist()
        
        results = []
        
        if search_type == "vector":
            results = await _vector_search(query, query_embedding, top_k)
        elif search_type == "hybrid":
            results = await _hybrid_search(query, query_embedding, top_k)
        elif search_type == "community":
            results = await _community_search(query, query_embedding, top_k, community_weight)
        elif search_type == "text2cypher":
            results = await _text2cypher_search(query, top_k)
        else:
            return json.dumps({"error": f"Unknown search type: {search_type}"})
        
        # Apply reranking if requested and available
        if use_reranking and reranker_model and results:
            results = _rerank_results(query, results)
        
        # Format results
        formatted_results = []
        for i, result in enumerate(results[:top_k]):
            formatted_results.append({
                "rank": i + 1,
                "document": result.get("document", ""),
                "page_num": result.get("page_num", 0),
                "chunk_id": result.get("chunk_id", ""),
                "text": result.get("text", ""),
                "score": float(result.get("final_score", result.get("score", 0))),
                "metadata": {
                    "chunk_type": result.get("chunk_type", ""),
                    "semantic_density": result.get("semantic_density", 0),
                    "community_metrics": result.get("community_metrics", {})
                }
            })
        
        return json.dumps({
            "success": True,
            "query": query,
            "search_type": search_type,
            "results": formatted_results,
            "count": len(formatted_results)
        }, indent=2)
        
    except Exception as e:
        sys.stderr.write(f"Search error: {e}\n")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, indent=2)

async def _vector_search(query: str, query_embedding: List[float], top_k: int) -> List[Dict]:
    """Perform vector similarity search"""
    with neo4j_driver.session(database=NEO4J_DATABASE) as session:
        result = session.run("""
            MATCH (c:Chunk)
            WITH c, reduce(similarity = 0.0, i IN range(0, size(c.embedding)-1) |
                similarity + c.embedding[i] * $query_embedding[i]
            ) as cosine_similarity
            ORDER BY cosine_similarity DESC
            LIMIT $limit
            MATCH (c)<-[:HAS_CHUNK]-(d:Document)
            RETURN c.id as chunk_id,
                   c.text as text,
                   c.page_num as page_num,
                   c.chunk_type as chunk_type,
                   c.semantic_density as semantic_density,
                   d.filename as document,
                   cosine_similarity as score
        """, query_embedding=query_embedding, limit=top_k * 2)
        
        return [dict(record) for record in result]

async def _hybrid_search(query: str, query_embedding: List[float], top_k: int) -> List[Dict]:
    """Perform hybrid search combining vector and keyword matching"""
    keywords = [w.lower() for w in query.split() if len(w) > 2]
    
    with neo4j_driver.session(database=NEO4J_DATABASE) as session:
        result = session.run("""
            MATCH (c:Chunk)
            WITH c, 
                 reduce(similarity = 0.0, i IN range(0, size(c.embedding)-1) |
                    similarity + c.embedding[i] * $query_embedding[i]
                 ) as cosine_similarity,
                 SIZE([keyword IN $keywords WHERE toLower(c.text) CONTAINS keyword]) as keyword_matches
            WHERE cosine_similarity > 0.5 OR keyword_matches > 0
            WITH c, cosine_similarity, keyword_matches,
                 (cosine_similarity * 0.7 + (toFloat(keyword_matches) / SIZE($keywords)) * 0.3) as hybrid_score
            ORDER BY hybrid_score DESC
            LIMIT $limit
            MATCH (c)<-[:HAS_CHUNK]-(d:Document)
            OPTIONAL MATCH (c)-[:CONTAINS_ENTITY]->(e:Entity)
            RETURN c.id as chunk_id,
                   c.text as text,
                   c.page_num as page_num,
                   c.chunk_type as chunk_type,
                   c.semantic_density as semantic_density,
                   d.filename as document,
                   hybrid_score as score,
                   cosine_similarity,
                   keyword_matches,
                   COUNT(e) as entity_count
        """, query_embedding=query_embedding, keywords=keywords, limit=top_k * 2)
        
        return [dict(record) for record in result]

async def _community_search(query: str, query_embedding: List[float], top_k: int, community_weight: float) -> List[Dict]:
    """Perform community-aware search"""
    keywords = [w.lower() for w in query.split() if len(w) > 3]
    
    with neo4j_driver.session(database=NEO4J_DATABASE) as session:
        # Find relevant communities
        entity_result = session.run("""
            MATCH (e:Entity)
            WHERE ANY(keyword IN $keywords WHERE toLower(e.text) CONTAINS keyword)
               OR ANY(word IN $query_words WHERE toLower(e.text) = word)
            RETURN e.text as entity, e.community_id as community_id
            LIMIT 20
        """, keywords=keywords, query_words=[w.lower() for w in query.split()])
        
        communities = set()
        for record in entity_result:
            if record['community_id'] is not None:
                communities.add(record['community_id'])
        
        if communities:
            # Search within communities
            result = session.run("""
                MATCH (c:Chunk)-[:CONTAINS_ENTITY]->(e:Entity)
                WHERE e.community_id IN $communities
                WITH c, COUNT(DISTINCT e.community_id) as community_coverage,
                     AVG(COALESCE(e.community_degree_centrality, 0)) as avg_centrality
                WITH c, community_coverage, avg_centrality,
                     reduce(similarity = 0.0, i IN range(0, size(c.embedding)-1) |
                        similarity + c.embedding[i] * $query_embedding[i]
                     ) as cosine_similarity
                MATCH (c)<-[:HAS_CHUNK]-(d:Document)
                WITH c, d, cosine_similarity, community_coverage, avg_centrality,
                     (cosine_similarity * (1 - $community_weight) + 
                      (community_coverage * 0.5 + avg_centrality * 0.5) * $community_weight) as final_score
                RETURN c.id as chunk_id,
                       c.text as text,
                       c.page_num as page_num,
                       c.chunk_type as chunk_type,
                       c.semantic_density as semantic_density,
                       d.filename as document,
                       cosine_similarity as score,
                       final_score,
                       community_coverage,
                       avg_centrality
                ORDER BY final_score DESC
                LIMIT $limit
            """, communities=list(communities), query_embedding=query_embedding, 
                 community_weight=community_weight, limit=top_k)
            
            results = [dict(record) for record in result]
            
            # Add community metrics
            for result in results:
                result['community_metrics'] = {
                    'coverage': result.pop('community_coverage', 0),
                    'avg_centrality': result.pop('avg_centrality', 0),
                    'community_weight': community_weight
                }
            
            return results
        else:
            # Fall back to vector search
            return await _vector_search(query, query_embedding, top_k)

async def _text2cypher_search(query: str, top_k: int) -> List[Dict]:
    """Convert natural language to Cypher query patterns"""
    # Simple pattern matching for common query types
    query_lower = query.lower()
    
    cypher_query = None
    
    # Pattern: questions about specific products or documents
    if "minimum" in query_lower and ("balance" in query_lower or "amount" in query_lower):
        cypher_query = """
            MATCH (c:Chunk)-[:CONTAINS_ENTITY]->(e:Entity)
            WHERE toLower(c.text) CONTAINS 'minimum'
              AND (toLower(c.text) CONTAINS 'balance' OR toLower(c.text) CONTAINS 'amount')
            MATCH (c)<-[:HAS_CHUNK]-(d:Document)
            RETURN DISTINCT c.id as chunk_id, c.text as text, c.page_num as page_num,
                   d.filename as document, 1.0 as score
            LIMIT $limit
        """
    elif "interest rate" in query_lower:
        cypher_query = """
            MATCH (c:Chunk)-[:CONTAINS_ENTITY]->(e:Entity)
            WHERE toLower(c.text) CONTAINS 'interest rate'
               OR (toLower(c.text) CONTAINS 'interest' AND toLower(c.text) CONTAINS 'rate')
            MATCH (c)<-[:HAS_CHUNK]-(d:Document)
            RETURN DISTINCT c.id as chunk_id, c.text as text, c.page_num as page_num,
                   d.filename as document, 1.0 as score
            LIMIT $limit
        """
    elif "complaint" in query_lower or "dispute" in query_lower:
        cypher_query = """
            MATCH (c:Chunk)
            WHERE toLower(c.text) CONTAINS 'complaint'
               OR toLower(c.text) CONTAINS 'dispute'
               OR toLower(c.text) CONTAINS 'grievance'
               OR toLower(c.text) CONTAINS 'australian financial complaints'
            MATCH (c)<-[:HAS_CHUNK]-(d:Document)
            RETURN DISTINCT c.id as chunk_id, c.text as text, c.page_num as page_num,
                   d.filename as document, 1.0 as score
            LIMIT $limit
        """
    else:
        # Generic keyword search
        keywords = [w for w in query.split() if len(w) > 3]
        cypher_query = """
            MATCH (c:Chunk)
            WHERE """ + " OR ".join([f"toLower(c.text) CONTAINS '{kw.lower()}'" for kw in keywords]) + """
            MATCH (c)<-[:HAS_CHUNK]-(d:Document)
            WITH c, d, SIZE([kw IN $keywords WHERE toLower(c.text) CONTAINS kw]) as matches
            RETURN c.id as chunk_id, c.text as text, c.page_num as page_num,
                   d.filename as document, toFloat(matches) / SIZE($keywords) as score
            ORDER BY score DESC
            LIMIT $limit
        """
    
    with neo4j_driver.session(database=NEO4J_DATABASE) as session:
        if "keywords" in cypher_query:
            result = session.run(cypher_query, keywords=keywords, limit=top_k)
        else:
            result = session.run(cypher_query, limit=top_k)
        
        return [dict(record) for record in result]

def _rerank_results(query: str, results: List[Dict]) -> List[Dict]:
    """Rerank results using cross-encoder"""
    if not results:
        return results
    
    # Prepare texts for reranking
    texts = [r['text'] for r in results]
    query_text_pairs = [[query, text] for text in texts]
    
    # Get cross-encoder scores
    cross_encoder_scores = reranker_model.predict(query_text_pairs)
    
    # Calculate final scores
    for i, result in enumerate(results):
        original_score = result.get('final_score', result.get('score', 0))
        cross_encoder_score = float(cross_encoder_scores[i])
        
        # Multi-factor reranking
        final_score = (
            cross_encoder_score * 0.5 +
            original_score * 0.3 +
            _calculate_keyword_match_score(query, result['text']) * 0.1 +
            _calculate_metadata_score(result) * 0.1
        )
        
        result['final_score'] = final_score
        result['cross_encoder_score'] = cross_encoder_score
    
    # Sort by final score
    results.sort(key=lambda x: x['final_score'], reverse=True)
    
    return results

def _calculate_keyword_match_score(query: str, text: str) -> float:
    """Calculate keyword match score"""
    query_words = set(query.lower().split())
    text_words = set(text.lower().split())
    
    if not query_words:
        return 0.0
    
    matches = len(query_words.intersection(text_words))
    return matches / len(query_words)

def _calculate_metadata_score(result: Dict) -> float:
    """Calculate score based on chunk metadata"""
    score = 0.0
    
    # Boost for high semantic density
    if result.get('semantic_density', 0) > 0.7:
        score += 0.3
    
    # Boost for definition chunks
    if result.get('chunk_type') == 'definition':
        score += 0.4
    
    # Boost for chunks with many entities
    if result.get('entity_count', 0) > 5:
        score += 0.3
    
    return min(score, 1.0)

@mcp.tool()
async def search_documents(
    query: str,
    top_k: int = 5
) -> str:
    """
    Simple search interface that automatically selects the best search strategy.
    
    Args:
        query: The search query
        top_k: Number of results to return (default: 5)
    
    Returns:
        Search results with documents and relevance information
    """
    # Use hybrid search with reranking by default for best accuracy
    return await knowledge_search(
        query=query,
        search_type="hybrid",
        top_k=top_k,
        use_reranking=True,
        community_weight=0.3
    )

# Cleanup
import atexit

def cleanup():
    if neo4j_driver:
        neo4j_driver.close()
        sys.stderr.write("Closed Neo4j connection\n")

atexit.register(cleanup)

# Run the server
if __name__ == "__main__":
    mcp.run()