#!/usr/bin/env python3
"""
Optimized Neo4j MCP Server - Fast and accurate search
Based on insights from performance testing
"""

import sys
import os
import json
from typing import Dict, Any, Optional, List

sys.stderr.write("Starting Optimized Neo4j MCP Server...\n")
sys.stderr.flush()

try:
    from mcp.server import FastMCP
except ImportError as e:
    sys.stderr.write(f"Failed to import MCP: {e}\n")
    sys.stderr.flush()
    sys.exit(1)

# Create the MCP server
mcp = FastMCP("knowledge-graph-search")

# Configuration
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "knowledge123")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

# Global variables for lazy loading
neo4j_driver = None
embedding_model = None
reranker_model = None

def get_neo4j_driver():
    """Get or create Neo4j driver"""
    global neo4j_driver
    if neo4j_driver is None:
        try:
            from neo4j import GraphDatabase
            neo4j_driver = GraphDatabase.driver(
                NEO4J_URI,
                auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
            )
            neo4j_driver.verify_connectivity()
            sys.stderr.write(f"✓ Neo4j connection established\n")
            sys.stderr.flush()
        except Exception as e:
            sys.stderr.write(f"❌ Neo4j connection failed: {e}\n")
            sys.stderr.flush()
            raise
    return neo4j_driver

def get_embedding_model():
    """Get or create embedding model - only if really needed"""
    global embedding_model
    if embedding_model is None:
        try:
            sys.stderr.write("Loading embedding model...\n")
            sys.stderr.flush()
            from sentence_transformers import SentenceTransformer
            embedding_model = SentenceTransformer('BAAI/bge-small-en-v1.5')
            sys.stderr.write("✓ Embedding model loaded\n")
            sys.stderr.flush()
        except Exception as e:
            sys.stderr.write(f"❌ Failed to load embedding model: {e}\n")
            sys.stderr.flush()
            raise
    return embedding_model

def get_reranker_model():
    """Get or create reranker model - only if really needed"""
    global reranker_model
    if reranker_model is None:
        try:
            sys.stderr.write("Loading reranker model...\n")
            sys.stderr.flush()
            from sentence_transformers import CrossEncoder
            reranker_model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
            sys.stderr.write("✓ Reranker model loaded\n")
            sys.stderr.flush()
        except Exception as e:
            sys.stderr.write(f"❌ Failed to load reranker model: {e}\n")
            sys.stderr.flush()
            raise
    return reranker_model

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
    try:
        driver = get_neo4j_driver()
        records = []
        with driver.session(database=NEO4J_DATABASE) as session:
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
        sys.stderr.flush()
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
    try:
        driver = get_neo4j_driver()
        with driver.session(database=NEO4J_DATABASE) as session:
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
        sys.stderr.flush()
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
    try:
        driver = get_neo4j_driver()
        schema = {
            "node_labels": [],
            "relationships": [],
            "constraints": [],
            "indexes": []
        }
        
        with driver.session(database=NEO4J_DATABASE) as session:
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
        
        return json.dumps(schema, indent=2)
        
    except Exception as e:
        sys.stderr.write(f"Schema query error: {e}\n")
        sys.stderr.flush()
        return json.dumps({
            "error": str(e)
        }, indent=2)

@mcp.tool()
async def search_documents(
    query: str, 
    top_k: int = 10,
    use_vector_search: bool = False,
    use_reranking: bool = False
) -> str:
    """
    Optimized search that defaults to fast keyword search.
    Vector search and reranking are optional for when accuracy is critical.
    
    Args:
        query: The search query
        top_k: Number of results to return (default: 10)
        use_vector_search: Enable hybrid vector search (slower but more accurate)
        use_reranking: Enable cross-encoder reranking (requires vector search)
    
    Returns:
        Search results with documents and relevance information
    """
    try:
        driver = get_neo4j_driver()
        
        # Extract keywords - include more words for better matching
        all_words = [w.lower() for w in query.split() if len(w) > 2 and w.lower() not in ['the', 'for', 'and', 'are', 'what', 'how', 'can', 'do']]
        key_words = [w.lower() for w in query.split() if len(w) > 4]
        
        # If not using vector search, do fast keyword search
        if not use_vector_search:
            with driver.session(database=NEO4J_DATABASE) as session:
                # Strategy 1: Find chunks with ANY keyword match
                result = session.run("""
                    MATCH (c:Chunk)<-[:HAS_CHUNK]-(d:Document)
                    WHERE """ + " OR ".join([f"toLower(c.text) CONTAINS '{word}'" for word in all_words]) + """
                    WITH d, c, """ + " + ".join([f"CASE WHEN toLower(c.text) CONTAINS '{word}' THEN 1 ELSE 0 END" for word in all_words]) + """ as match_count
                    WHERE match_count > 0
                    RETURN c.id as chunk_id,
                           c.text as text,
                           c.page_num as page_num,
                           d.filename as document,
                           match_count as score,
                           c.semantic_density as semantic_density,
                           c.chunk_type as chunk_type
                    ORDER BY match_count DESC, c.semantic_density DESC
                    LIMIT $limit
                """, limit=top_k)
                
                results = [dict(record) for record in result]
                
                # Also try entity-based search if few results
                if len(results) < top_k // 2 and key_words:
                    entity_result = session.run("""
                        MATCH (e:Entity)<-[:CONTAINS_ENTITY]-(c:Chunk)<-[:HAS_CHUNK]-(d:Document)
                        WHERE """ + " OR ".join([f"toLower(e.text) CONTAINS '{word}'" for word in key_words]) + """
                        WITH d, c, COUNT(DISTINCT e) as entity_count
                        RETURN c.id as chunk_id,
                               c.text as text,
                               c.page_num as page_num,
                               d.filename as document,
                               entity_count as score,
                               c.semantic_density as semantic_density,
                               c.chunk_type as chunk_type
                        ORDER BY entity_count DESC
                        LIMIT $limit
                    """, limit=top_k - len(results))
                    
                    # Add entity results if not duplicates
                    existing_chunks = {r['chunk_id'] for r in results}
                    for record in entity_result:
                        if record['chunk_id'] not in existing_chunks:
                            results.append(dict(record))
        
        else:
            # Use hybrid search with vector embeddings
            model = get_embedding_model()
            query_embedding = model.encode(query).tolist()
            
            with driver.session(database=NEO4J_DATABASE) as session:
                # Lower similarity threshold and adjust weights for better recall
                result = session.run("""
                    MATCH (c:Chunk)
                    WITH c, 
                         reduce(similarity = 0.0, i IN range(0, size(c.embedding)-1) |
                            similarity + c.embedding[i] * $query_embedding[i]
                         ) as cosine_similarity,
                         SIZE([keyword IN $keywords WHERE toLower(c.text) CONTAINS keyword]) as keyword_matches
                    WHERE cosine_similarity > 0.3 OR keyword_matches > 0
                    WITH c, cosine_similarity, keyword_matches,
                         (cosine_similarity * 0.4 + (toFloat(keyword_matches) / SIZE($keywords)) * 0.6) as hybrid_score
                    ORDER BY hybrid_score DESC
                    LIMIT $limit
                    MATCH (c)<-[:HAS_CHUNK]-(d:Document)
                    RETURN c.id as chunk_id,
                           c.text as text,
                           c.page_num as page_num,
                           d.filename as document,
                           hybrid_score as score,
                           cosine_similarity,
                           keyword_matches,
                           c.semantic_density as semantic_density,
                           c.chunk_type as chunk_type
                """, query_embedding=query_embedding, keywords=all_words, limit=top_k * 2 if use_reranking else top_k)
                
                results = [dict(record) for record in result]
            
            # Apply reranking if requested
            if use_reranking and results:
                try:
                    reranker = get_reranker_model()
                    texts = [r['text'] for r in results]
                    query_text_pairs = [[query, text] for text in texts]
                    cross_encoder_scores = reranker.predict(query_text_pairs)
                    
                    for i, result in enumerate(results):
                        # Balanced scoring with more weight on reranker
                        result['final_score'] = float(cross_encoder_scores[i]) * 0.7 + result['score'] * 0.3
                    
                    results.sort(key=lambda x: x['final_score'], reverse=True)
                    results = results[:top_k]
                except Exception as e:
                    sys.stderr.write(f"Reranking failed, using original scores: {e}\n")
                    sys.stderr.flush()
        
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
                    "search_method": "vector_hybrid" if use_vector_search else "keyword"
                }
            })
        
        return json.dumps({
            "success": True,
            "query": query,
            "results": formatted_results,
            "count": len(formatted_results),
            "search_config": {
                "vector_search": use_vector_search,
                "reranking": use_reranking,
                "keywords_used": all_words
            }
        }, indent=2)
        
    except Exception as e:
        sys.stderr.write(f"Search error: {e}\n")
        sys.stderr.flush()
        return json.dumps({
            "success": False,
            "error": str(e)
        }, indent=2)

@mcp.tool()
async def search_entities(
    entity_text: str,
    community_id: Optional[int] = None,
    limit: int = 10
) -> str:
    """
    Search for entities and their related documents.
    Useful for finding specific terms, organizations, or concepts.
    
    Args:
        entity_text: Text to search for in entities
        community_id: Optional community ID to filter by
        limit: Number of results to return
    
    Returns:
        Entities and their associated documents
    """
    try:
        driver = get_neo4j_driver()
        
        with driver.session(database=NEO4J_DATABASE) as session:
            if community_id is not None:
                result = session.run("""
                    MATCH (e:Entity)<-[:CONTAINS_ENTITY]-(c:Chunk)<-[:HAS_CHUNK]-(d:Document)
                    WHERE toLower(e.text) CONTAINS toLower($text)
                      AND e.community_id = $community_id
                    WITH e, d, COUNT(c) as chunk_count, COLLECT(DISTINCT c.page_num)[..5] as pages
                    RETURN e.text as entity,
                           e.type as entity_type,
                           e.community_id as community,
                           d.filename as document,
                           chunk_count,
                           pages
                    ORDER BY chunk_count DESC
                    LIMIT $limit
                """, text=entity_text, community_id=community_id, limit=limit)
            else:
                result = session.run("""
                    MATCH (e:Entity)<-[:CONTAINS_ENTITY]-(c:Chunk)<-[:HAS_CHUNK]-(d:Document)
                    WHERE toLower(e.text) CONTAINS toLower($text)
                    WITH e, d, COUNT(c) as chunk_count, COLLECT(DISTINCT c.page_num)[..5] as pages
                    RETURN e.text as entity,
                           e.type as entity_type,
                           e.community_id as community,
                           d.filename as document,
                           chunk_count,
                           pages
                    ORDER BY chunk_count DESC
                    LIMIT $limit
                """, text=entity_text, limit=limit)
            
            results = [dict(record) for record in result]
            
            return json.dumps({
                "success": True,
                "query": entity_text,
                "results": results,
                "count": len(results)
            }, indent=2)
            
    except Exception as e:
        sys.stderr.write(f"Entity search error: {e}\n")
        sys.stderr.flush()
        return json.dumps({
            "success": False,
            "error": str(e)
        }, indent=2)

# Cleanup
import atexit

def cleanup():
    global neo4j_driver
    if neo4j_driver:
        neo4j_driver.close()
        sys.stderr.write("Closed Neo4j connection\n")
        sys.stderr.flush()

atexit.register(cleanup)

# Run the server
if __name__ == "__main__":
    sys.stderr.write("Optimized MCP server ready\n")
    sys.stderr.flush()
    mcp.run()