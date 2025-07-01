#!/usr/bin/env python3
"""
Enhanced MCP Server for Knowledge Graph with Neo4j Integration
"""

import asyncio
import json
import os
import sys
import requests
from typing import Dict, Any, List, Optional
import logging
import re
from neo4j import GraphDatabase

# Add debugging
sys.stderr.write("Starting Enhanced Knowledge Graph MCP Server...\n")
sys.stderr.write(f"Python: {sys.executable}\n")
sys.stderr.write(f"API URL: {os.getenv('API_BASE_URL', 'http://localhost:8000')}\n")

from mcp.server import FastMCP

# Create the MCP server
mcp = FastMCP("enhanced-knowledge-graph")

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

# Neo4j connection
class Neo4jConnection:
    def __init__(self, uri, username, password):
        self.driver = GraphDatabase.driver(uri, auth=(username, password))
    
    def close(self):
        self.driver.close()
    
    def execute_query(self, query: str, parameters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        with self.driver.session() as session:
            result = session.run(query, parameters or {})
            return [record.data() for record in result]

# Initialize Neo4j connection
neo4j_conn = None
try:
    neo4j_conn = Neo4jConnection(NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD)
    # Test the connection
    with neo4j_conn.driver.session() as session:
        result = session.run("RETURN 1 as test")
        result.single()
    sys.stderr.write(f"✓ Connected to Neo4j at {NEO4J_URI}\n")
except Exception as e:
    sys.stderr.write(f"⚠️  Neo4j connection failed: {e}\n")
    sys.stderr.write(f"   Will fall back to text2cypher API when neo4j_cypher is used\n")
    neo4j_conn = None

# Natural language to Cypher conversion patterns
CYPHER_PATTERNS = [
    # Balance queries
    (r"minimum balance|min balance", 
     "MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk) WHERE toLower(c.text) CONTAINS 'minimum' AND toLower(c.text) CONTAINS 'balance' RETURN DISTINCT d.filename as document, c.text as content, c.page_num as page ORDER BY c.page_num LIMIT {limit}"),
    
    # Fee queries
    (r"fees?|charges?",
     "MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk) WHERE toLower(c.text) CONTAINS 'fee' OR toLower(c.text) CONTAINS 'charge' RETURN DISTINCT d.filename as document, c.text as content, c.page_num as page ORDER BY c.page_num LIMIT {limit}"),
    
    # Interest rate queries
    (r"interest rate|rate.*interest",
     "MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk) WHERE toLower(c.text) CONTAINS 'interest' AND toLower(c.text) CONTAINS 'rate' RETURN DISTINCT d.filename as document, c.text as content, c.page_num as page ORDER BY c.page_num LIMIT {limit}"),
    
    # Product queries
    (r"product|account.*type|types.*account",
     "MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk)-[:CONTAINS_ENTITY]->(e:Entity) WHERE e.type = 'PRODUCT' RETURN DISTINCT d.filename as document, e.name as product, c.text as content, c.page_num as page LIMIT {limit}"),
    
    # Document queries
    (r"document.*about|information.*about",
     "MATCH (d:Document) WHERE toLower(d.filename) CONTAINS toLower('{search_term}') RETURN d.filename as document, d.id as id, d.total_pages as pages LIMIT {limit}"),
    
    # Entity queries
    (r"entities|organizations|companies",
     "MATCH (e:Entity) WHERE e.type IN ['ORG', 'COMPANY', 'ORGANIZATION'] RETURN DISTINCT e.name as entity, e.type as type, size((e)<-[:CONTAINS_ENTITY]-()) as mentions ORDER BY mentions DESC LIMIT {limit}"),
    
    # Requirement queries
    (r"requirement|eligibility|criteria",
     "MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk) WHERE toLower(c.text) CONTAINS 'require' OR toLower(c.text) CONTAINS 'eligible' OR toLower(c.text) CONTAINS 'criteria' RETURN DISTINCT d.filename as document, c.text as content, c.page_num as page ORDER BY c.page_num LIMIT {limit}"),
    
    # Terms and conditions
    (r"terms.*conditions|t&c|terms",
     "MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk) WHERE toLower(d.filename) CONTAINS 'terms' OR (toLower(c.text) CONTAINS 'terms' AND toLower(c.text) CONTAINS 'conditions') RETURN DISTINCT d.filename as document, c.text as content, c.page_num as page LIMIT {limit}"),
    
    # Specific document search
    (r"show.*document|find.*document|get.*document",
     "MATCH (d:Document) WHERE toLower(d.filename) CONTAINS toLower('{search_term}') RETURN d.filename as document, d.id as id, d.total_pages as pages LIMIT {limit}"),
    
    # General entity search
    (r"find.*entity|search.*entity|show.*entity",
     "MATCH (e:Entity) WHERE toLower(e.name) CONTAINS toLower('{search_term}') RETURN e.name as entity, e.type as type, size((e)<-[:CONTAINS_ENTITY]-()) as mentions ORDER BY mentions DESC LIMIT {limit}")
]

def natural_language_to_cypher(query: str, limit: int = 10) -> Optional[str]:
    """Convert natural language query to Cypher query"""
    query_lower = query.lower()
    
    # Check each pattern
    for pattern, cypher_template in CYPHER_PATTERNS:
        if re.search(pattern, query_lower):
            # Extract search terms from the query
            search_terms = re.sub(pattern, "", query_lower).strip()
            search_term = search_terms if search_terms else ".*"
            
            # Format the Cypher query
            cypher = cypher_template.format(limit=limit, search_term=search_term)
            return cypher
    
    # Default: full-text search across chunks
    escaped_query = query.replace("'", "\\'")
    return f"""
    MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk)
    WHERE toLower(c.text) CONTAINS toLower('{escaped_query}')
    RETURN DISTINCT d.filename as document, c.text as content, c.page_num as page
    ORDER BY c.page_num
    LIMIT {limit}
    """

def execute_neo4j_direct(query: str, limit: int = 10) -> Dict[str, Any]:
    """Execute natural language query directly on Neo4j"""
    if not neo4j_conn:
        return {"error": "Neo4j connection not available. Falling back to text2cypher API."}
    
    try:
        # Convert natural language to Cypher
        cypher_query = natural_language_to_cypher(query, limit)
        sys.stderr.write(f"Generated Cypher: {cypher_query}\n")
        
        # Execute the query
        results = neo4j_conn.execute_query(cypher_query)
        
        # Format results to match expected structure
        formatted_results = []
        for record in results:
            result = {
                "document_id": record.get("document", record.get("id", "Unknown")),
                "text": record.get("content", record.get("summary", str(record))),
                "page_num": record.get("page", record.get("pages", "N/A")),
                "score": 1.0  # Direct Neo4j results don't have scores
            }
            
            # Add any additional fields from the record
            for key, value in record.items():
                if key not in ["document", "content", "page", "id", "summary", "pages"]:
                    result[key] = value
            
            formatted_results.append(result)
        
        return {
            "query": query,
            "cypher_query": cypher_query,
            "results": formatted_results,
            "total_results": len(formatted_results)
        }
        
    except Exception as e:
        sys.stderr.write(f"Neo4j query error: {e}\n")
        return {"error": f"Neo4j query failed: {str(e)}"}

def format_search_results(data: Dict[str, Any], search_type: str) -> str:
    """Format search results for display"""
    results = []
    results.append(f"**Query**: {data.get('query', 'N/A')}")
    results.append(f"**Search Type**: {search_type}")
    
    # Show Cypher query if available
    if data.get('cypher_query'):
        results.append(f"**Generated Cypher Query**:\n```cypher\n{data.get('cypher_query')}\n```")
    
    results.append(f"**Total Results**: {len(data.get('results', []))}\n")
    
    for i, result in enumerate(data.get('results', [])[:10], 1):
        results.append(f"\n### Result {i}")
        results.append(f"**Document**: {result.get('document_id', 'Unknown')}")
        results.append(f"**Page**: {result.get('page_num', 'N/A')}")
        results.append(f"**Score**: {result.get('score', 0):.3f}")
        if result.get('rerank_score'):
            results.append(f"**Rerank Score**: {result.get('rerank_score'):.3f}")
        
        text = result.get('text', '')
        preview = text[:300] + "..." if len(text) > 300 else text
        results.append(f"\n{preview}")
        results.append("---")
    
    return "\n".join(results)

def format_cypher_results(results: List[Dict[str, Any]]) -> str:
    """Format Cypher query results"""
    if not results:
        return "No results found."
    
    output = []
    output.append(f"**Found {len(results)} results**\n")
    
    for i, record in enumerate(results[:10], 1):
        output.append(f"\n### Record {i}")
        for key, value in record.items():
            if isinstance(value, dict):
                output.append(f"**{key}**:")
                for k, v in value.items():
                    output.append(f"  - {k}: {v}")
            else:
                output.append(f"**{key}**: {value}")
        output.append("---")
    
    return "\n".join(output)

@mcp.tool()
async def search_knowledge(
    query: str, 
    search_type: str = "neo4j_cypher", 
    limit: int = 5,
    rerank: bool = True
) -> str:
    """
    Search the knowledge graph using Neo4j Cypher queries.
    
    Args:
        query: The search query
        search_type: Currently only 'neo4j_cypher' is supported (default: neo4j_cypher)
        limit: Maximum number of results to return
        rerank: Not applicable for neo4j_cypher queries
    
    Returns:
        Search results from the knowledge graph
    """
    try:
        # Force neo4j_cypher search type
        if search_type != "neo4j_cypher":
            return "⚠️ Only 'neo4j_cypher' search type is currently enabled. Please use search_type='neo4j_cypher' or omit it to use the default."
        
        # Handle Neo4j MCP-style queries with direct Neo4j connection
        if search_type == "neo4j_cypher" and neo4j_conn:
            # Execute directly on Neo4j
            data = execute_neo4j_direct(query, limit)
            if "error" in data:
                return f"Neo4j Error: {data['error']}"
            return format_search_results(data, "neo4j_cypher")
        elif search_type == "neo4j_cypher":
            # Fallback to text2cypher if Neo4j connection not available
            search_type = "text2cypher"
            rerank = False
        
        response = requests.post(
            f"{API_BASE_URL}/search",
            json={
                "query": query,
                "search_type": search_type,
                "limit": limit,
                "rerank": rerank and search_type != "text2cypher"
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            return format_search_results(data, search_type)
        else:
            return f"API Error: {response.status_code} - {response.text}"
            
    except requests.exceptions.ConnectionError:
        return "Error: Cannot connect to Knowledge Graph API. Make sure it's running at " + API_BASE_URL
    except Exception as e:
        sys.stderr.write(f"Error in search_knowledge: {e}\n")
        return f"Error: {str(e)}"

@mcp.tool()
async def execute_cypher(query: str, limit: int = 10) -> str:
    """
    Execute a Cypher query directly on the Neo4j database.
    
    Args:
        query: The Cypher query to execute
        limit: Maximum number of results
    
    Returns:
        Query results
    """
    try:
        # Use text2cypher endpoint for Cypher-like queries
        response = requests.post(
            f"{API_BASE_URL}/text2cypher",
            json={
                "query": query,
                "limit": limit
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', [])
            return format_cypher_results(results)
        else:
            return f"API Error: {response.status_code}"
            
    except Exception as e:
        return f"Error executing Cypher query: {str(e)}"

@mcp.tool()
async def get_neo4j_schema() -> str:
    """
    Get the Neo4j database schema information.
    
    Returns:
        Schema information including node labels, relationships, and properties
    """
    try:
        # Get stats which includes some schema info
        response = requests.get(f"{API_BASE_URL}/stats", timeout=10)
        
        if response.status_code == 200:
            stats = response.json()
            
            result = "**Neo4j Knowledge Graph Schema**\n\n"
            result += "**Node Types:**\n"
            result += "- Document: Represents PDF documents\n"
            result += "- Chunk: Text chunks from documents\n"
            result += "- Entity: Extracted entities (products, requirements, etc.)\n\n"
            
            result += "**Relationships:**\n"
            result += "- (:Document)-[:HAS_CHUNK]->(:Chunk)\n"
            result += "- (:Chunk)-[:CONTAINS_ENTITY]->(:Entity)\n"
            result += "- (:Chunk)-[:NEXT_CHUNK]->(:Chunk)\n"
            result += "- (:Entity)-[:RELATED_TO]->(:Entity)\n\n"
            
            result += "**Statistics:**\n"
            result += f"- Documents: {stats.get('documents', 0)}\n"
            result += f"- Chunks: {stats.get('chunks', 0)}\n"
            result += f"- Entities: {stats.get('entities', 0)}\n"
            result += f"- Relationships: {stats.get('relationships', 0)}\n"
            
            return result
        else:
            return f"API Error: {response.status_code}"
            
    except Exception as e:
        return f"Error getting schema: {str(e)}"

@mcp.tool()
async def text2cypher_search(query: str, limit: int = 5) -> str:
    """
    Search using natural language that gets converted to Cypher queries.
    
    Args:
        query: Natural language query (e.g., "What is the minimum balance?")
        limit: Maximum number of results
    
    Returns:
        Search results from pattern-based Cypher query generation
    """
    return await search_knowledge(query, "text2cypher", limit, False)

@mcp.tool()
async def get_knowledge_stats() -> str:
    """
    Get statistics about the knowledge base.
    
    Returns:
        Statistics including document count, chunks, entities, etc.
    """
    try:
        response = requests.get(f"{API_BASE_URL}/stats", timeout=10)
        
        if response.status_code == 200:
            stats = response.json()
            
            result = "**Knowledge Base Statistics**\n\n"
            result += f"- **Documents**: {stats.get('documents', 0)}\n"
            result += f"- **Chunks**: {stats.get('chunks', 0)}\n"
            result += f"- **Entities**: {stats.get('entities', 0)}\n"
            result += f"- **Relationships**: {stats.get('relationships', 0)}\n"
            result += f"- **Reranking**: {'Enabled' if stats.get('reranking_enabled') else 'Disabled'}\n"
            
            return result
        else:
            return f"API Error: {response.status_code}"
            
    except Exception as e:
        sys.stderr.write(f"Error in get_stats: {e}\n")
        return f"Error: {str(e)}"

# Run the server
if __name__ == "__main__":
    try:
        mcp.run()
    finally:
        if neo4j_conn:
            neo4j_conn.close()