#!/usr/bin/env python3
"""
Simple MCP Server for Knowledge Graph
"""

import asyncio
import json
import os
import sys
import requests

# Add debugging
sys.stderr.write("Starting Knowledge Graph MCP Server...\n")
sys.stderr.write(f"Python: {sys.executable}\n")
sys.stderr.write(f"API URL: {os.getenv('API_BASE_URL', 'http://localhost:8000')}\n")

from mcp.server import FastMCP

# Create the MCP server
mcp = FastMCP("knowledge-graph")

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

@mcp.tool()
async def search_knowledge(query: str, search_type: str = "hybrid", limit: int = 5) -> str:
    """
    Search the knowledge graph using various search types.
    
    Args:
        query: The search query
        search_type: One of 'vector', 'graph', 'hybrid', or 'text2cypher'
        limit: Maximum number of results to return
    
    Returns:
        Search results from the knowledge graph
    """
    try:
        response = requests.post(
            f"{API_BASE_URL}/search",
            json={
                "query": query,
                "search_type": search_type,
                "limit": limit,
                "rerank": True
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            results = []
            
            results.append(f"**Query**: {query}")
            results.append(f"**Search Type**: {search_type}")
            results.append(f"**Total Results**: {len(data.get('results', []))}\n")
            
            for i, result in enumerate(data.get('results', [])[:limit], 1):
                results.append(f"\n### Result {i}")
                results.append(f"**Document**: {result.get('document_id', 'Unknown')}")
                results.append(f"**Page**: {result.get('page_num', 'N/A')}")
                results.append(f"**Score**: {result.get('score', 0):.3f}")
                if result.get('rerank_score'):
                    results.append(f"**Rerank Score**: {result.get('rerank_score'):.3f}")
                results.append(f"\n{result.get('text', '')[:300]}...")
                results.append("---")
            
            return "\n".join(results)
        else:
            return f"API Error: {response.status_code} - {response.text}"
            
    except requests.exceptions.ConnectionError:
        return "Error: Cannot connect to Knowledge Graph API. Make sure it's running at " + API_BASE_URL
    except Exception as e:
        sys.stderr.write(f"Error in search_knowledge: {e}\n")
        return f"Error: {str(e)}"

@mcp.tool()
async def get_knowledge_stats() -> str:
    """
    Get statistics about the knowledge base.
    
    Returns:
        JSON formatted statistics including document count, chunks, entities, etc.
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
    return await search_knowledge(query, "text2cypher", limit)

# Main function for entry point
def main():
    """Main entry point for the simple server"""
    mcp.run()

# Run the server
if __name__ == "__main__":
    main()