#!/usr/bin/env python3
"""
Enhanced MCP Server - Final Version
Uses direct Neo4j connection for neo4j_cypher queries
"""

import asyncio
import json
import os
import sys
import requests
from typing import Dict, Any, List, Optional

# Add debugging
sys.stderr.write("Starting Enhanced Knowledge Graph MCP Server (Final)...\n")
sys.stderr.write(f"Python: {sys.executable}\n")
sys.stderr.write(f"API URL: {os.getenv('API_BASE_URL', 'http://localhost:8000')}\n")

from mcp.server import FastMCP

# Create the MCP server
mcp = FastMCP("enhanced-knowledge-graph")

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "knowledge123")

# Try to import Neo4j driver
neo4j_available = False
neo4j_driver = None

try:
    from neo4j import GraphDatabase
    neo4j_driver = GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
    )
    neo4j_driver.verify_connectivity()
    neo4j_available = True
    sys.stderr.write("✓ Neo4j connection established\n")
except ImportError:
    sys.stderr.write("⚠️ Neo4j driver not installed\n")
except Exception as e:
    sys.stderr.write(f"⚠️ Neo4j connection failed: {e}\n")

def natural_language_to_cypher(query: str, limit: int = 10) -> str:
    """Convert natural language to Cypher query"""
    query_lower = query.lower()
    
    # Check for specific patterns
    if "minimum balance" in query_lower:
        return f"""
        MATCH (c:Chunk)
        WHERE toLower(c.text) CONTAINS 'minimum' 
        AND toLower(c.text) CONTAINS 'balance'
        RETURN c.text as text, c.page_num as page, c.chunk_id as id
        ORDER BY c.page_num
        LIMIT {limit}
        """
    
    elif "interest rate" in query_lower:
        return f"""
        MATCH (c:Chunk)
        WHERE toLower(c.text) CONTAINS 'interest rate'
        RETURN c.text as text, c.page_num as page, c.chunk_id as id
        ORDER BY c.page_num
        LIMIT {limit}
        """
    
    elif "fee" in query_lower or "charge" in query_lower:
        return f"""
        MATCH (c:Chunk)
        WHERE toLower(c.text) CONTAINS 'fee' OR toLower(c.text) CONTAINS 'charge'
        RETURN c.text as text, c.page_num as page, c.chunk_id as id
        ORDER BY c.page_num
        LIMIT {limit}
        """
    
    elif "foreign currency account" in query_lower:
        return f"""
        MATCH (c:Chunk)
        WHERE toLower(c.text) CONTAINS 'foreign currency account'
        RETURN c.text as text, c.page_num as page, c.chunk_id as id
        ORDER BY c.page_num
        LIMIT {limit}
        """
    
    # Default: general text search
    escaped_query = query.replace("'", "\\'")
    return f"""
    MATCH (c:Chunk)
    WHERE toLower(c.text) CONTAINS toLower('{escaped_query}')
    RETURN c.text as text, c.page_num as page, c.chunk_id as id
    ORDER BY c.page_num
    LIMIT {limit}
    """

def execute_neo4j_query(query: str, limit: int = 10) -> Dict[str, Any]:
    """Execute query on Neo4j"""
    if not neo4j_available or not neo4j_driver:
        return {"error": "Neo4j not available"}
    
    try:
        # Convert natural language to Cypher
        cypher = natural_language_to_cypher(query, limit)
        sys.stderr.write(f"Executing Cypher: {cypher[:100]}...\n")
        
        with neo4j_driver.session() as session:
            result = session.run(cypher)
            records = list(result)
            
            return {
                "query": query,
                "cypher": cypher,
                "results": [dict(record) for record in records],
                "count": len(records)
            }
            
    except Exception as e:
        sys.stderr.write(f"Neo4j query error: {e}\n")
        return {"error": str(e)}

@mcp.tool()
async def search_knowledge(
    query: str, 
    search_type: str = "neo4j_cypher", 
    limit: int = 5,
    rerank: bool = True
) -> str:
    """
    Search the knowledge graph.
    
    Args:
        query: The search query
        search_type: Currently only 'neo4j_cypher' is supported
        limit: Maximum number of results to return
    
    Returns:
        Search results from the knowledge graph
    """
    try:
        # Force neo4j_cypher search type
        if search_type != "neo4j_cypher":
            return "⚠️ Only 'neo4j_cypher' search type is currently enabled."
        
        # Try direct Neo4j first
        if neo4j_available:
            result = execute_neo4j_query(query, limit)
            
            if "error" not in result:
                output = [f"**Query**: {query}"]
                output.append(f"**Type**: Direct Neo4j Query")
                output.append(f"**Results**: {result['count']} found\n")
                
                # Show the Cypher query for transparency
                output.append("**Generated Cypher**:")
                output.append(f"```cypher\n{result['cypher']}\n```\n")
                
                for i, record in enumerate(result['results'][:limit], 1):
                    output.append(f"### Result {i}")
                    output.append(f"**Page**: {record.get('page', 'N/A')}")
                    
                    text = record.get('text', '')
                    preview = text[:400] + "..." if len(text) > 400 else text
                    output.append(f"\n{preview}\n")
                    output.append("---")
                
                return "\n".join(output)
        
        # Fallback to text2cypher API
        sys.stderr.write("Using text2cypher API fallback\n")
        response = requests.post(
            f"{API_BASE_URL}/search",
            json={
                "query": query,
                "search_type": "text2cypher",
                "limit": limit,
                "rerank": False
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            output = [f"**Query**: {query}"]
            output.append(f"**Type**: Text2Cypher API (fallback)")
            output.append(f"**Results**: {len(data.get('results', []))} found\n")
            
            for i, res in enumerate(data.get('results', [])[:limit], 1):
                output.append(f"### Result {i}")
                output.append(f"**Document**: {res.get('document_id', 'Unknown')}")
                output.append(f"**Page**: {res.get('page_num', 'N/A')}")
                output.append(f"**Score**: {res.get('score', 0):.3f}")
                
                text = res.get('text', '')
                preview = text[:400] + "..." if len(text) > 400 else text
                output.append(f"\n{preview}\n")
                output.append("---")
            
            return "\n".join(output)
        else:
            return f"API Error: {response.status_code}"
            
    except requests.exceptions.ConnectionError:
        return "Error: Cannot connect to Knowledge Graph API at " + API_BASE_URL
    except Exception as e:
        sys.stderr.write(f"Error in search_knowledge: {e}\n")
        return f"Error: {str(e)}"

@mcp.tool()
async def execute_cypher(query: str) -> str:
    """
    Execute a raw Cypher query on Neo4j.
    
    Args:
        query: The Cypher query to execute
    
    Returns:
        Query results
    """
    if not neo4j_available:
        return "Error: Direct Cypher execution requires Neo4j connection"
    
    try:
        with neo4j_driver.session() as session:
            result = session.run(query)
            records = list(result)
            
            output = [f"**Cypher Query Executed**"]
            output.append(f"```cypher\n{query}\n```\n")
            output.append(f"**Results**: {len(records)} found\n")
            
            for i, record in enumerate(records[:10], 1):
                output.append(f"### Record {i}")
                for key, value in dict(record).items():
                    output.append(f"**{key}**: {value}")
                output.append("---")
            
            return "\n".join(output)
            
    except Exception as e:
        return f"Cypher Error: {str(e)}"

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
            result += f"- **Neo4j Direct**: {'✓ Connected' if neo4j_available else '✗ Not connected'}\n"
            
            return result
        else:
            return f"API Error: {response.status_code}"
            
    except Exception as e:
        return f"Error: {str(e)}"

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