"""
Enhanced API with improved reranking using chunk metadata
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
import logging
from contextlib import asynccontextmanager
from sentence_transformers import CrossEncoder
from search_engine import KnowledgeSearchEngine, SearchResult
import os
import sys
sys.path.append('/app')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variables
search_engine = None
cross_encoder = None
text2cypher = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize resources on startup"""
    global search_engine, cross_encoder, text2cypher
    
    logger.info("Initializing enhanced API with improved reranking...")
    
    # Initialize search engine
    search_engine = KnowledgeSearchEngine(
        neo4j_uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        neo4j_user=os.getenv("NEO4J_USER", "neo4j"),
        neo4j_password=os.getenv("NEO4J_PASSWORD", "knowledge123")
    )
    
    # Initialize cross-encoder for reranking
    logger.info("Loading cross-encoder model...")
    cross_encoder = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
    
    # Initialize Text2Cypher
    logger.info("Initializing Text2CypherRetriever...")
    from text2cypher_search import Text2CypherRetriever
    text2cypher = Text2CypherRetriever(
        neo4j_uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        neo4j_user=os.getenv("NEO4J_USER", "neo4j"),
        neo4j_password=os.getenv("NEO4J_PASSWORD", "knowledge123")
    )
    
    logger.info("API initialization complete")
    
    yield
    
    # Cleanup
    logger.info("Shutting down API...")

app = FastAPI(title="Knowledge Graph API with Enhanced Reranking", version="2.0", lifespan=lifespan)

def analyze_query_type(query: str) -> str:
    """Analyze query to determine type"""
    query_lower = query.lower()
    
    if any(term in query_lower for term in ['what is', 'what are', 'define']):
        return 'definition'
    elif any(term in query_lower for term in ['example', 'show me', 'demonstrate']):
        return 'example'
    elif any(term in query_lower for term in ['minimum', 'requirement', 'eligible']):
        return 'requirement'
    elif any(term in query_lower for term in ['how to', 'process', 'steps']):
        return 'procedure'
    elif any(term in query_lower for term in ['compare', 'difference', 'versus']):
        return 'comparison'
    else:
        return 'general'

def calculate_keyword_boost(query: str, text: str, filename: str) -> float:
    """Calculate keyword matching boost"""
    query_terms = set(query.lower().split())
    text_terms = set(text.lower().split())
    filename_terms = set(filename.lower().replace('.pdf', '').replace('-', ' ').split())
    
    # Direct query term matches
    text_matches = len(query_terms & text_terms)
    filename_matches = len(query_terms & filename_terms)
    
    # Calculate boost
    boost = 0.0
    if text_matches > 0:
        boost += min(text_matches * 0.05, 0.2)
    if filename_matches > 0:
        boost += 0.15
    
    return boost

def enhanced_rerank_results(query: str, results: List[SearchResult]) -> List[Dict[str, Any]]:
    """Enhanced reranking using chunk metadata"""
    if not results:
        return []
    
    # Analyze query
    query_type = analyze_query_type(query)
    
    # Prepare for cross-encoder
    pairs = [[query, result.text] for result in results]
    
    # Get cross-encoder scores
    try:
        ce_scores = cross_encoder.predict(pairs)
    except:
        ce_scores = [0.5] * len(results)
    
    # Convert to dict format and calculate scores
    reranked = []
    
    for i, result in enumerate(results):
        # Base score from cross-encoder
        rerank_score = float(ce_scores[i])
        
        # Original score
        original_score = result.score
        
        # Keyword boost
        keyword_boost = calculate_keyword_boost(
            query, 
            result.text, 
            result.metadata.get('filename', '')
        )
        
        # Enhanced metadata boosts
        metadata_boost = 0.0
        
        # Semantic density boost (prioritize information-rich chunks)
        semantic_density = result.metadata.get('semantic_density', 0.0)
        if semantic_density > 0.5:
            metadata_boost += 0.1
        elif semantic_density > 0.3:
            metadata_boost += 0.05
        
        # Query type matching with chunk type
        chunk_type = result.metadata.get('chunk_type', 'content')
        if query_type == 'definition' and chunk_type == 'definition':
            metadata_boost += 0.2
        elif query_type == 'example' and chunk_type == 'example':
            metadata_boost += 0.2
        elif query_type == 'definition' and result.metadata.get('has_definitions', False):
            metadata_boost += 0.15
        elif query_type == 'example' and result.metadata.get('has_examples', False):
            metadata_boost += 0.15
        
        # Product-specific boost
        if 'foreign currency' in query.lower() and 'fca' in result.text.lower():
            metadata_boost += 0.1
        elif 'interest rate swap' in query.lower() and 'irs' in result.text.lower():
            metadata_boost += 0.1
        
        # Calculate final score with enhanced weights
        final_score = (
            rerank_score * 0.4 +       # Cross-encoder weight
            original_score * 0.25 +    # Original score weight  
            keyword_boost * 0.15 +     # Keyword weight
            metadata_boost * 0.2       # Enhanced metadata weight
        )
        
        # Create result dict
        result_dict = {
            "chunk_id": result.chunk_id,
            "text": result.text,
            "score": result.score,
            "document_id": result.document_id,
            "page_num": result.page_num,
            "entities": result.entities,
            "search_type": result.search_type,
            "metadata": result.metadata,
            "rerank_score": rerank_score,
            "final_score": final_score,
            "query_type": query_type,
            "semantic_density": semantic_density,
            "chunk_type": chunk_type,
            "keyword_boost": keyword_boost,
            "metadata_boost": metadata_boost
        }
        
        reranked.append(result_dict)
    
    # Sort by final score
    reranked.sort(key=lambda x: x['final_score'], reverse=True)
    
    return reranked

# Request/Response models
class SearchRequest(BaseModel):
    query: str
    search_type: str = "vector"
    top_k: int = 10
    weights: Optional[Dict[str, float]] = None
    use_reranking: bool = True

class SearchResponse(BaseModel):
    query: str
    search_type: str
    results: List[Dict[str, Any]]
    total_results: int
    reranking_applied: bool

class StatsResponse(BaseModel):
    documents: int
    chunks: int
    entities: int
    relationships: int
    reranking_enabled: bool
    cross_encoder_model: str

@app.get("/stats", response_model=StatsResponse)
async def get_stats():
    """Get database statistics"""
    from neo4j import GraphDatabase
    
    stats = {}
    try:
        driver = GraphDatabase.driver(
            os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "knowledge123"))
        )
        
        with driver.session() as session:
            # Count documents
            result = session.run("MATCH (d:Document) RETURN count(d) as count")
            stats["documents"] = result.single()["count"]
            
            # Count chunks
            result = session.run("MATCH (c:Chunk) RETURN count(c) as count")
            stats["chunks"] = result.single()["count"]
            
            # Count entities
            result = session.run("MATCH (e:Entity) RETURN count(e) as count")
            stats["entities"] = result.single()["count"]
            
            # Count relationships
            result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
            stats["relationships"] = result.single()["count"]
        
        driver.close()
    except Exception as e:
        logger.error(f"Stats error: {e}")
        stats = {"documents": 0, "chunks": 0, "entities": 0, "relationships": 0}
    
    return StatsResponse(
        documents=stats.get("documents", 0),
        chunks=stats.get("chunks", 0),
        entities=stats.get("entities", 0),
        relationships=stats.get("relationships", 0),
        reranking_enabled=True,
        cross_encoder_model="cross-encoder/ms-marco-MiniLM-L-6-v2"
    )

@app.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    """Perform search with enhanced reranking"""
    try:
        # Get more candidates if reranking is enabled
        top_k = request.top_k * 2 if request.use_reranking else request.top_k
        
        # Perform search based on type
        if request.search_type == "vector":
            results = search_engine.vector_search(request.query, top_k)
        elif request.search_type == "graph":
            results = search_engine.graph_search(request.query, top_k)
        elif request.search_type == "full_text":
            results = search_engine.full_text_search(request.query, top_k)
        elif request.search_type == "hybrid":
            results = search_engine.hybrid_search(request.query, top_k, request.weights)
        elif request.search_type == "graphrag":
            results = search_engine.graphrag_search(request.query, top_k)
        elif request.search_type == "text2cypher":
            # Use Text2CypherRetriever for natural language queries
            cypher_result = text2cypher.execute_natural_query(request.query)
            if cypher_result['success'] and cypher_result['results']:
                # Convert cypher results to SearchResult format
                results = []
                for i, res in enumerate(cypher_result['results'][:top_k]):
                    # Try to extract text content
                    text = res.get('text', str(res))
                    if 'document' in res:
                        text = f"Document: {res['document']}\n{text}"
                    
                    result = SearchResult(
                        chunk_id=f"cypher_{i}",
                        text=text,
                        score=1.0 - (i * 0.1),  # Decreasing score
                        document_id=res.get('document', 'unknown'),
                        page_num=res.get('page', 0),
                        entities=[],
                        search_type='text2cypher',
                        metadata={
                            'cypher_query': cypher_result['cypher'],
                            'query_type': cypher_result['query_type'],
                            **res
                        }
                    )
                    results.append(result)
            else:
                results = []
        elif request.search_type in ["mcp_cypher", "neo4j_mcp"]:
            # Use enhanced MCP Neo4j client for queries
            from enhanced_mcp_client import get_enhanced_mcp_client
            mcp_client = get_enhanced_mcp_client()
            
            # Execute search through MCP
            mcp_results = await mcp_client.search_knowledge(request.query, limit=top_k)
            
            # Convert MCP results to SearchResult format
            results = []
            for mcp_result in mcp_results:
                result = SearchResult(
                    chunk_id=mcp_result["chunk_id"],
                    text=mcp_result["text"],
                    score=mcp_result["score"],
                    document_id=mcp_result["document_id"],
                    page_num=mcp_result["page_num"],
                    entities=mcp_result.get("entities", []),
                    search_type="mcp_cypher",
                    metadata=mcp_result.get("metadata", {})
                )
                results.append(result)
        else:
            raise HTTPException(status_code=400, detail=f"Invalid search type: {request.search_type}")
        
        # Apply enhanced reranking if enabled
        if request.use_reranking and results:
            logger.info(f"Applying enhanced reranking to {len(results)} results")
            results_dict = enhanced_rerank_results(request.query, results)
            results_dict = results_dict[:request.top_k]  # Return requested number
            reranking_applied = True
        else:
            # Convert to dict format without reranking
            results_dict = []
            for result in results[:request.top_k]:
                results_dict.append({
                    "chunk_id": result.chunk_id,
                    "text": result.text,
                    "score": result.score,
                    "document_id": result.document_id,
                    "page_num": result.page_num,
                    "entities": result.entities,
                    "search_type": result.search_type,
                    "metadata": result.metadata
                })
            reranking_applied = False
        
        return SearchResponse(
            query=request.query,
            search_type=request.search_type,
            results=results_dict,
            total_results=len(results_dict),
            reranking_applied=reranking_applied
        )
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "enhanced_reranking": True}

# Text2Cypher endpoints
class Text2CypherRequest(BaseModel):
    query: str

class Text2CypherResponse(BaseModel):
    success: bool
    query: str
    cypher: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    query_type: Optional[str] = None
    results: Optional[List[Dict[str, Any]]] = None
    count: Optional[int] = None
    error: Optional[str] = None

@app.post("/text2cypher", response_model=Text2CypherResponse)
async def text2cypher_query(request: Text2CypherRequest):
    """Execute a natural language query using Text2Cypher"""
    try:
        result = text2cypher.execute_natural_query(request.query)
        return Text2CypherResponse(**result)
    except Exception as e:
        logger.error(f"Text2Cypher error: {e}")
        return Text2CypherResponse(
            success=False,
            query=request.query,
            error=str(e)
        )

@app.get("/text2cypher/examples")
async def text2cypher_examples():
    """Get example queries for Text2Cypher"""
    return {
        "examples": text2cypher.suggest_queries(),
        "description": "Example natural language queries that can be processed"
    }

# MCP Neo4j endpoints
class MCPCypherRequest(BaseModel):
    query: str
    parameters: Optional[Dict[str, Any]] = None

class MCPCypherResponse(BaseModel):
    success: bool
    query: str
    parameters: Optional[Dict[str, Any]] = None
    results: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None

@app.post("/mcp/cypher", response_model=MCPCypherResponse)
async def mcp_cypher_query(request: MCPCypherRequest):
    """Execute a Cypher query directly through MCP Neo4j"""
    try:
        from enhanced_mcp_client import get_enhanced_mcp_client
        mcp_client = get_enhanced_mcp_client()
        
        result = await mcp_client.execute_cypher_query(
            request.query,
            request.parameters
        )
        
        return MCPCypherResponse(**result)
    except Exception as e:
        logger.error(f"MCP Cypher error: {e}")
        return MCPCypherResponse(
            success=False,
            query=request.query,
            parameters=request.parameters,
            error=str(e)
        )

@app.get("/mcp/status")
async def mcp_status():
    """Check MCP Neo4j connection status"""
    try:
        from enhanced_mcp_client import get_enhanced_mcp_client
        mcp_client = get_enhanced_mcp_client()
        
        # Test with a simple query
        result = await mcp_client.execute_cypher_query(
            "MATCH (n) RETURN count(n) as node_count LIMIT 1"
        )
        
        if result["success"]:
            return {
                "status": "connected",
                "mcp_server": mcp_client.mcp_server_name,
                "node_count": result["results"][0]["node_count"] if result["results"] else 0
            }
        else:
            return {
                "status": "error",
                "error": result.get("error", "Unknown error")
            }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)