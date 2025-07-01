"""
MCP Neo4j Client for executing Cypher queries through MCP protocol
"""

import json
import logging
import asyncio
from typing import Dict, List, Any, Optional
import aiohttp
import subprocess
import sys

logger = logging.getLogger(__name__)

class MCPNeo4jClient:
    """Client for interacting with Neo4j through MCP protocol"""
    
    def __init__(self, mcp_server_name: str = "mcp-neo4j-cypher"):
        self.mcp_server_name = mcp_server_name
        self.base_url = "http://localhost:8080"  # MCP server endpoint
        
    async def execute_cypher_query(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a Cypher query through MCP protocol"""
        try:
            # The MCP Neo4j server expects a tool call with the cypher query
            tool_call = {
                "tool": "execute_cypher",
                "arguments": {
                    "query": query
                }
            }
            
            if parameters:
                tool_call["arguments"]["parameters"] = parameters
            
            # In a real MCP implementation, we would use the MCP protocol
            # For now, we'll simulate the MCP call by directly executing the query
            # This is a placeholder that should be replaced with actual MCP client code
            
            # Import Neo4j driver for direct execution (temporary)
            from neo4j import GraphDatabase
            import os
            
            driver = GraphDatabase.driver(
                os.getenv("NEO4J_URI", "bolt://localhost:7687"),
                auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "knowledge123"))
            )
            
            results = []
            with driver.session() as session:
                result = session.run(query, parameters or {})
                for record in result:
                    results.append(dict(record))
            
            driver.close()
            
            return {
                "success": True,
                "results": results,
                "query": query,
                "parameters": parameters
            }
            
        except Exception as e:
            logger.error(f"MCP Neo4j query error: {e}")
            return {
                "success": False,
                "error": str(e),
                "query": query,
                "parameters": parameters
            }
    
    async def search_knowledge(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search for knowledge using natural language through MCP"""
        try:
            # Generate a Cypher query based on the natural language query
            cypher_query = self._generate_cypher_from_natural_language(query)
            
            # Execute the Cypher query
            result = await self.execute_cypher_query(cypher_query, {"limit": limit})
            
            if result["success"]:
                return self._format_search_results(result["results"], query)
            else:
                logger.error(f"MCP search failed: {result.get('error')}")
                return []
                
        except Exception as e:
            logger.error(f"MCP search error: {e}")
            return []
    
    def _generate_cypher_from_natural_language(self, query: str) -> str:
        """Generate a Cypher query from natural language (simple implementation)"""
        query_lower = query.lower()
        
        # Basic pattern matching for common queries
        if "minimum balance" in query_lower:
            return """
            MATCH (c:Chunk)-[:BELONGS_TO]->(d:Document)
            WHERE c.text =~ '(?i).*minimum.*balance.*'
            RETURN c.text as text, d.filename as document, c.page_num as page, c.chunk_id as chunk_id
            ORDER BY c.semantic_density DESC
            LIMIT $limit
            """
        elif "interest rate" in query_lower:
            return """
            MATCH (c:Chunk)-[:BELONGS_TO]->(d:Document)
            WHERE c.text =~ '(?i).*interest.*rate.*'
            RETURN c.text as text, d.filename as document, c.page_num as page, c.chunk_id as chunk_id
            ORDER BY c.semantic_density DESC
            LIMIT $limit
            """
        elif "fees" in query_lower or "charges" in query_lower:
            return """
            MATCH (c:Chunk)-[:BELONGS_TO]->(d:Document)
            WHERE c.text =~ '(?i).*(fee|charge).*'
            RETURN c.text as text, d.filename as document, c.page_num as page, c.chunk_id as chunk_id
            ORDER BY c.semantic_density DESC
            LIMIT $limit
            """
        else:
            # Generic text search
            search_terms = query.replace("'", "\\'")
            return f"""
            MATCH (c:Chunk)-[:BELONGS_TO]->(d:Document)
            WHERE c.text CONTAINS '{search_terms}'
            RETURN c.text as text, d.filename as document, c.page_num as page, c.chunk_id as chunk_id
            ORDER BY c.semantic_density DESC
            LIMIT $limit
            """
    
    def _format_search_results(self, results: List[Dict[str, Any]], original_query: str) -> List[Dict[str, Any]]:
        """Format MCP results to match the API response structure"""
        formatted_results = []
        
        for i, result in enumerate(results):
            formatted_result = {
                "chunk_id": result.get("chunk_id", f"mcp_{i}"),
                "text": result.get("text", ""),
                "score": 1.0 - (i * 0.1),  # Simple scoring based on order
                "document_id": result.get("document", "unknown"),
                "page_num": result.get("page", 0),
                "entities": [],
                "search_type": "mcp_cypher",
                "metadata": {
                    "source": "mcp_neo4j",
                    "original_query": original_query,
                    **result
                }
            }
            formatted_results.append(formatted_result)
        
        return formatted_results

# Singleton instance
_mcp_client = None

def get_mcp_neo4j_client() -> MCPNeo4jClient:
    """Get or create the MCP Neo4j client singleton"""
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPNeo4jClient()
    return _mcp_client