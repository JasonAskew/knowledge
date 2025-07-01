#!/usr/bin/env python3
"""
Enhanced MCP Server with Neo4j MCP Proxy
Proxies neo4j_cypher queries to the actual mcp-neo4j-cypher tool
"""

import asyncio
import json
import os
import sys
import requests
import subprocess
from typing import Dict, Any, List, Optional

# Add debugging
sys.stderr.write("Starting Enhanced Knowledge Graph MCP Server with Neo4j Proxy...\n")
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

# Neo4j MCP subprocess
neo4j_process = None
neo4j_ready = False

def start_neo4j_mcp():
    """Start the mcp-neo4j-cypher subprocess"""
    global neo4j_process, neo4j_ready
    
    try:
        # Start mcp-neo4j-cypher as subprocess
        cmd = [
            "/Users/jaskew/.local/bin/uvx",
            "mcp-neo4j-cypher@0.2.3",
            "--transport", "stdio"
        ]
        
        env = os.environ.copy()
        env.update({
            "NEO4J_URI": NEO4J_URI,
            "NEO4J_USER": NEO4J_USERNAME,
            "NEO4J_PASSWORD": NEO4J_PASSWORD
        })
        
        neo4j_process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
            bufsize=0
        )
        
        sys.stderr.write("Started mcp-neo4j-cypher subprocess\n")
        neo4j_ready = True
        return True
        
    except Exception as e:
        sys.stderr.write(f"Failed to start mcp-neo4j-cypher: {e}\n")
        return False

def call_neo4j_mcp(method: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Call the Neo4j MCP subprocess"""
    if not neo4j_ready or not neo4j_process:
        return {"error": "Neo4j MCP not available"}
    
    try:
        # Create JSON-RPC request
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params
        }
        
        # Send request
        neo4j_process.stdin.write(json.dumps(request) + '\n')
        neo4j_process.stdin.flush()
        
        # Read response
        response_line = neo4j_process.stdout.readline()
        if response_line:
            response = json.loads(response_line)
            if "result" in response:
                return response["result"]
            elif "error" in response:
                return {"error": response["error"]}
        
        return {"error": "No response from Neo4j MCP"}
        
    except Exception as e:
        sys.stderr.write(f"Error calling Neo4j MCP: {e}\n")
        return {"error": str(e)}

def format_neo4j_results(results: Any) -> str:
    """Format Neo4j MCP results for display"""
    if isinstance(results, dict) and "error" in results:
        return f"❌ Error: {results['error']}"
    
    if isinstance(results, str):
        return results
    
    if isinstance(results, list):
        output = [f"**Found {len(results)} results**\n"]
        for i, item in enumerate(results[:10], 1):
            output.append(f"\n### Result {i}")
            if isinstance(item, dict):
                for key, value in item.items():
                    output.append(f"**{key}**: {value}")
            else:
                output.append(str(item))
            output.append("---")
        return "\n".join(output)
    
    return str(results)

# Start Neo4j MCP on server startup
start_neo4j_mcp()

@mcp.tool()
async def search_knowledge(
    query: str, 
    search_type: str = "neo4j_cypher", 
    limit: int = 5,
    rerank: bool = True
) -> str:
    """
    Search the knowledge graph using Neo4j MCP.
    
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
        
        # Call the Neo4j MCP tool
        sys.stderr.write(f"Proxying query to mcp-neo4j-cypher: {query}\n")
        
        result = call_neo4j_mcp("tools/call", {
            "name": "query",
            "arguments": {
                "cypher": query  # mcp-neo4j-cypher treats queries as Cypher
            }
        })
        
        if "error" in result:
            # Fallback to text2cypher API
            sys.stderr.write(f"Neo4j MCP error, falling back to text2cypher: {result['error']}\n")
            
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
                results = []
                results.append(f"**Query**: {query}")
                results.append(f"**Search Type**: neo4j_cypher (via text2cypher fallback)")
                results.append(f"**Total Results**: {len(data.get('results', []))}\n")
                
                for i, res in enumerate(data.get('results', [])[:limit], 1):
                    results.append(f"\n### Result {i}")
                    results.append(f"**Document**: {res.get('document_id', 'Unknown')}")
                    results.append(f"**Page**: {res.get('page_num', 'N/A')}")
                    results.append(f"**Score**: {res.get('score', 0):.3f}")
                    
                    text = res.get('text', '')
                    preview = text[:300] + "..." if len(text) > 300 else text
                    results.append(f"\n{preview}")
                    results.append("---")
                
                return "\n".join(results)
            else:
                return f"API Error: {response.status_code}"
        
        # Format and return Neo4j MCP results
        return format_neo4j_results(result)
            
    except Exception as e:
        sys.stderr.write(f"Error in search_knowledge: {e}\n")
        return f"Error: {str(e)}"

@mcp.tool()
async def execute_cypher(query: str, limit: int = 10) -> str:
    """
    Execute a Cypher query directly via Neo4j MCP.
    
    Args:
        query: The Cypher query to execute
        limit: Maximum number of results (may need to be included in query)
    
    Returns:
        Query results
    """
    try:
        # Add LIMIT if not present
        if "limit" not in query.lower():
            query = f"{query} LIMIT {limit}"
        
        result = call_neo4j_mcp("tools/call", {
            "name": "query",
            "arguments": {
                "cypher": query
            }
        })
        
        return format_neo4j_results(result)
        
    except Exception as e:
        return f"Error executing Cypher query: {str(e)}"

@mcp.tool()
async def get_neo4j_schema() -> str:
    """
    Get the Neo4j database schema via Neo4j MCP.
    
    Returns:
        Schema information including node labels, relationships, and properties
    """
    try:
        # Neo4j MCP might have a schema tool
        result = call_neo4j_mcp("tools/call", {
            "name": "get-schema",
            "arguments": {}
        })
        
        if "error" in result:
            # Fallback to basic schema
            return """**Neo4j Knowledge Graph Schema**

**Node Types:**
- Document: Represents PDF documents
- Chunk: Text chunks from documents
- Entity: Extracted entities

**Relationships:**
- (:Document)-[:HAS_CHUNK]->(:Chunk)
- (:Chunk)-[:CONTAINS_ENTITY]->(:Entity)
- (:Chunk)-[:NEXT_CHUNK]->(:Chunk)
- (:Entity)-[:RELATED_TO]->(:Entity)

Note: For detailed schema, Neo4j MCP connection required."""
        
        return format_neo4j_results(result)
        
    except Exception as e:
        return f"Error getting schema: {str(e)}"

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
            result += f"- **Neo4j MCP**: {'Connected' if neo4j_ready else 'Not connected'}\n"
            
            return result
        else:
            return f"API Error: {response.status_code}"
            
    except Exception as e:
        sys.stderr.write(f"Error in get_stats: {e}\n")
        return f"Error: {str(e)}"

# Cleanup on exit
import atexit

def cleanup():
    global neo4j_process
    if neo4j_process:
        neo4j_process.terminate()
        neo4j_process.wait()
        sys.stderr.write("Cleaned up Neo4j MCP subprocess\n")

atexit.register(cleanup)

# Run the server
if __name__ == "__main__":
    mcp.run()