#!/usr/bin/env python3
"""
Enhanced FastAPI with improved search capabilities
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
import logging
import time

# Import both search engines
from search_engine import KnowledgeSearchEngine
from enhanced_search import EnhancedKnowledgeSearchEngine, QueryIntent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Enhanced Knowledge Graph API",
    description="API with enhanced search capabilities for financial knowledge graph",
    version="2.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize search engines
neo4j_uri = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
neo4j_user = os.getenv("NEO4J_USER", "neo4j")
neo4j_password = os.getenv("NEO4J_PASSWORD", "knowledge123")

# Original search engine for backward compatibility
search_engine = KnowledgeSearchEngine(
    neo4j_uri=neo4j_uri,
    neo4j_user=neo4j_user,
    neo4j_password=neo4j_password
)

# Enhanced search engine
try:
    enhanced_engine = EnhancedKnowledgeSearchEngine(
        neo4j_uri=neo4j_uri,
        neo4j_user=neo4j_user,
        neo4j_password=neo4j_password
    )
    enhanced_available = True
except Exception as e:
    logger.error(f"Failed to load enhanced search engine: {e}")
    enhanced_engine = None
    enhanced_available = False

# Request/Response models
class SearchRequest(BaseModel):
    query: str
    search_type: str = "enhanced"  # Default to enhanced
    top_k: int = 10
    weights: Optional[Dict[str, float]] = None
    debug: bool = False

class SearchResponse(BaseModel):
    query: str
    search_type: str
    results: List[Dict[str, Any]]
    total_results: int
    query_time: float
    query_intent: Optional[Dict[str, Any]] = None

class HealthResponse(BaseModel):
    status: str
    neo4j_connected: bool
    enhanced_search: bool
    message: str

# API endpoints
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check API and Neo4j health"""
    try:
        # Test Neo4j connection
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        driver.verify_connectivity()
        driver.close()
        
        return HealthResponse(
            status="healthy",
            neo4j_connected=True,
            enhanced_search=enhanced_available,
            message="All systems operational"
        )
    except Exception as e:
        return HealthResponse(
            status="unhealthy",
            neo4j_connected=False,
            enhanced_search=enhanced_available,
            message=f"Neo4j connection error: {str(e)}"
        )

@app.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    """Perform search on knowledge graph"""
    start_time = time.time()
    query_intent = None
    
    try:
        # Use enhanced search if available and requested
        if request.search_type == "enhanced" and enhanced_available:
            logger.info(f"Performing enhanced search for: {request.query}")
            
            # Get query intent for debugging
            if request.debug:
                intent = enhanced_engine.preprocessor.analyze_query(request.query)
                query_intent = {
                    "query_type": intent.query_type,
                    "target_products": intent.target_products,
                    "key_terms": intent.key_terms,
                    "requires_multiple_docs": intent.requires_multiple_docs,
                    "complexity_score": intent.complexity_score
                }
            
            results = enhanced_engine.search(request.query, "enhanced", request.top_k)
            
        else:
            # Fall back to original search methods
            logger.info(f"Performing {request.search_type} search for: {request.query}")
            
            if request.search_type == "vector":
                results = search_engine.vector_search(request.query, request.top_k)
            elif request.search_type == "graph":
                results = search_engine.graph_search(request.query, request.top_k)
            elif request.search_type == "full_text":
                results = search_engine.full_text_search(request.query, request.top_k)
            elif request.search_type == "hybrid":
                results = search_engine.hybrid_search(request.query, request.top_k, request.weights)
            elif request.search_type == "graphrag":
                results = search_engine.graphrag_search(request.query, request.top_k)
            else:
                raise HTTPException(status_code=400, detail=f"Invalid search type: {request.search_type}")
        
        # Convert results to dict format
        results_dict = []
        for result in results:
            result_dict = {
                "chunk_id": result.chunk_id,
                "text": result.text,
                "score": result.score,
                "document_id": result.document_id,
                "page_num": result.page_num,
                "entities": result.entities,
                "search_type": result.search_type,
                "metadata": result.metadata
            }
            
            # Add enhanced fields if available
            if hasattr(result, 'document_title'):
                result_dict["document_title"] = result.document_title
            if hasattr(result, 'relevance_score'):
                result_dict["relevance_score"] = result.relevance_score
            if hasattr(result, 'keyword_matches'):
                result_dict["keyword_matches"] = result.keyword_matches
            if hasattr(result, 'explanation'):
                result_dict["explanation"] = result.explanation
            
            results_dict.append(result_dict)
        
        query_time = time.time() - start_time
        
        return SearchResponse(
            query=request.query,
            search_type=request.search_type,
            results=results_dict,
            total_results=len(results_dict),
            query_time=query_time,
            query_intent=query_intent
        )
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stats")
async def get_stats():
    """Get knowledge graph statistics"""
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        
        stats = {}
        with driver.session() as session:
            # Basic counts
            result = session.run("MATCH (d:Document) RETURN count(d) as count")
            stats["documents"] = result.single()["count"]
            
            result = session.run("MATCH (c:Chunk) RETURN count(c) as count")
            stats["chunks"] = result.single()["count"]
            
            result = session.run("MATCH (e:Entity) RETURN count(e) as count")
            stats["entities"] = result.single()["count"]
            
            result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
            stats["relationships"] = result.single()["count"]
            
            # Enhanced stats if available
            try:
                result = session.run("""
                    MATCH (c:Chunk)
                    RETURN avg(c.semantic_density) as avg_density,
                           sum(CASE WHEN c.has_definitions THEN 1 ELSE 0 END) as definition_chunks,
                           sum(CASE WHEN c.has_examples THEN 1 ELSE 0 END) as example_chunks
                """)
                record = result.single()
                stats["avg_semantic_density"] = record["avg_density"]
                stats["chunks_with_definitions"] = record["definition_chunks"]
                stats["chunks_with_examples"] = record["example_chunks"]
            except:
                pass
        
        driver.close()
        return stats
        
    except Exception as e:
        logger.error(f"Stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze")
async def analyze_query(request: SearchRequest):
    """Analyze query intent without performing search"""
    if not enhanced_available:
        raise HTTPException(status_code=503, detail="Enhanced search not available")
    
    try:
        intent = enhanced_engine.preprocessor.analyze_query(request.query)
        expanded = enhanced_engine.preprocessor.expand_query(request.query, intent)
        
        return {
            "original_query": request.query,
            "expanded_query": expanded,
            "intent": {
                "query_type": intent.query_type,
                "target_products": intent.target_products,
                "key_terms": intent.key_terms,
                "requires_multiple_docs": intent.requires_multiple_docs,
                "complexity_score": intent.complexity_score
            }
        }
    
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Enhanced Knowledge Graph API",
        "version": "2.0.0",
        "features": {
            "enhanced_search": enhanced_available,
            "query_preprocessing": enhanced_available,
            "result_reranking": enhanced_available,
            "search_types": ["vector", "graph", "full_text", "hybrid", "graphrag", "enhanced"]
        },
        "endpoints": {
            "health": "/health",
            "search": "/search",
            "stats": "/stats",
            "analyze": "/analyze",
            "docs": "/docs"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)