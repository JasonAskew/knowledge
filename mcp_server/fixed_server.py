#!/usr/bin/env python3
"""
Fixed MCP Server for Knowledge Graph System
"""

import asyncio
import json
import os
import sys
import requests
from typing import Any, Dict, List

# Simple MCP server implementation that works with current MCP version
from mcp.server import Server
from mcp import Tool

# Print to stderr for debugging
print("Starting Knowledge Graph MCP Server...", file=sys.stderr)
print(f"Python version: {sys.version}", file=sys.stderr)
print(f"API URL: {os.getenv('API_BASE_URL', 'http://localhost:8000')}", file=sys.stderr)

class KnowledgeGraphServer:
    def __init__(self):
        self.server = Server("knowledge-graph")
        self.api_url = os.getenv("API_BASE_URL", "http://localhost:8000")
        
    async def search_knowledge(self, query: str, search_type: str = "hybrid", limit: int = 5) -> str:
        """Search the knowledge graph"""
        try:
            response = requests.post(
                f"{self.api_url}/search",
                json={"query": query, "search_type": search_type, "limit": limit},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                results = []
                
                results.append(f"Query: {query}")
                results.append(f"Search Type: {search_type}")
                results.append(f"Results: {len(data.get('results', []))}\n")
                
                for i, result in enumerate(data.get('results', [])[:limit], 1):
                    results.append(f"\n--- Result {i} ---")
                    results.append(f"Document: {result.get('document_id', 'Unknown')}")
                    results.append(f"Page: {result.get('page_num', 'N/A')}")
                    results.append(f"Score: {result.get('score', 0):.3f}")
                    results.append(f"Text: {result.get('text', '')[:200]}...")
                
                return "\n".join(results)
            else:
                return f"API Error: {response.status_code}"
                
        except Exception as e:
            print(f"Error in search_knowledge: {e}", file=sys.stderr)
            return f"Error: {str(e)}"
    
    async def get_stats(self) -> str:
        """Get knowledge base statistics"""
        try:
            response = requests.get(f"{self.api_url}/stats", timeout=10)
            
            if response.status_code == 200:
                stats = response.json()
                return json.dumps(stats, indent=2)
            else:
                return f"API Error: {response.status_code}"
                
        except Exception as e:
            print(f"Error in get_stats: {e}", file=sys.stderr)
            return f"Error: {str(e)}"
    
    def setup_handlers(self):
        """Set up the tool handlers"""
        
        @self.server.tool()
        async def search_knowledge(query: str, search_type: str = "hybrid", limit: int = 5) -> str:
            """Search the knowledge graph using vector, graph, hybrid, or text2cypher search"""
            return await self.search_knowledge(query, search_type, limit)
        
        @self.server.tool()
        async def get_knowledge_stats() -> str:
            """Get statistics about the knowledge base"""
            return await self.get_stats()
        
        @self.server.tool()
        async def text2cypher_search(query: str, limit: int = 5) -> str:
            """Search using natural language that gets converted to Cypher queries"""
            return await self.search_knowledge(query, "text2cypher", limit)
    
    async def run(self):
        """Run the server"""
        self.setup_handlers()
        await self.server.run()

async def main():
    print("Initializing Knowledge Graph MCP Server...", file=sys.stderr)
    server = KnowledgeGraphServer()
    await server.run()

if __name__ == "__main__":
    asyncio.run(main())