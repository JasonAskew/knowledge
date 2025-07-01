#!/usr/bin/env python3
"""
Enhanced MCP Server for Knowledge Graph System with Neo4j MCP Integration

This server provides MCP access to the knowledge graph API and internally
calls Neo4j MCP tools without requiring clients to configure them separately.
Includes streaming support for long responses.
"""

import json
import logging
import asyncio
import os
import requests
import sys
from typing import Any, Dict, List, Optional, AsyncIterator
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

from mcp.server import FastMCP

# Import our Neo4j proxy
try:
    from .neo4j_mcp_proxy import Neo4jMCPProxy
except ImportError:
    from neo4j_mcp_proxy import Neo4jMCPProxy

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add debugging
sys.stderr.write("Starting Enhanced Knowledge Graph MCP Server...\n")
sys.stderr.write(f"Python: {sys.executable}\n")
sys.stderr.write(f"API URL: {os.getenv('API_BASE_URL', 'http://localhost:8000')}\n")

# Create the MCP server
mcp = FastMCP("enhanced-knowledge-graph")

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

class SearchType(Enum):
    VECTOR = "vector"
    GRAPH = "graph"
    HYBRID = "hybrid"
    TEXT2CYPHER = "text2cypher"
    NEO4J_CYPHER = "neo4j_cypher"
    NEO4J_SCHEMA = "neo4j_schema"

@dataclass
class Neo4jConfig:
    """Configuration for Neo4j MCP integration"""
    uri: str = "bolt://localhost:7687"
    username: str = "neo4j"
    password: str = "password"
    database: str = "neo4j"

class Neo4jMCPClient:
    """Client for interacting with Neo4j through our proxy"""
    
    def __init__(self, config: Neo4jConfig):
        self.config = config
        self.proxy = None
        
    async def start(self):
        """Start the Neo4j connection"""
        try:
            self.proxy = Neo4jMCPProxy(
                uri=self.config.uri,
                username=self.config.username,
                password=self.config.password,
                database=self.config.database
            )
            
            connected = await self.proxy.connect()
            if connected:
                logger.info("Neo4j MCP proxy connected successfully")
                return True
            else:
                logger.error("Failed to connect to Neo4j")
                return False
                
        except ImportError:
            logger.warning("neo4j package not installed. Neo4j MCP features will be unavailable.")
            return False
        except Exception as e:
            logger.error(f"Failed to start Neo4j MCP proxy: {e}")
            return False
    
    async def stop(self):
        """Stop the Neo4j connection"""
        if self.proxy:
            await self.proxy.disconnect()
            logger.info("Neo4j MCP proxy disconnected")
    
    async def execute_cypher(self, query: str) -> Dict[str, Any]:
        """Execute a Cypher query through Neo4j proxy"""
        if not self.proxy:
            return {"error": "Neo4j MCP proxy not connected"}
        
        try:
            result = await self.proxy.execute_cypher(query)
            return result
            
        except Exception as e:
            logger.error(f"Error executing Cypher query: {e}")
            return {"error": str(e)}
    
    async def get_schema(self) -> Dict[str, Any]:
        """Get Neo4j database schema through proxy"""
        if not self.proxy:
            return {"error": "Neo4j MCP proxy not connected"}
        
        try:
            schema = await self.proxy.get_schema()
            return schema
            
        except Exception as e:
            logger.error(f"Error getting schema: {e}")
            return {"error": str(e)}

# Initialize Neo4j client
neo4j_config = Neo4jConfig(
    uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
    username=os.getenv("NEO4J_USERNAME", "neo4j"),
    password=os.getenv("NEO4J_PASSWORD", "password"),
    database=os.getenv("NEO4J_DATABASE", "neo4j")
)
neo4j_client = Neo4jMCPClient(neo4j_config)

# Helper formatting functions
def format_search_results(data: Dict[str, Any]) -> str:
    """Format search results"""
    results = []
    results.append(f"**Query**: {data.get('query', 'N/A')}")
    results.append(f"**Search Type**: {data.get('search_type', 'N/A')}")
    results.append(f"**Query Time**: {data.get('query_time', 0):.2f}s\n")
    
    for i, result in enumerate(data.get('results', []), 1):
        result_text = f"**Result {i}:**\n"
        result_text += f"Document: {result.get('document', 'Unknown')}\n"
        result_text += f"Page: {result.get('page_num', 'N/A')}\n"
        result_text += f"Score: {result.get('score', 0):.3f}\n"
        if result.get('rerank_score'):
            result_text += f"Rerank Score: {result['rerank_score']:.3f}\n"
        result_text += f"\n{result.get('text', '')}\n"
        result_text += "-" * 80 + "\n"
        results.append(result_text)
    
    return "\n".join(results)

def format_neo4j_results(result: Dict[str, Any]) -> str:
    """Format Neo4j query results"""
    if "error" in result:
        return f"**Neo4j Error**: {result['error']}"
    
    if not result.get("success", False):
        return f"**Neo4j Query Failed**: {result.get('error', 'Unknown error')}"
    
    formatted = "**Neo4j Query Results**\n\n"
    if isinstance(result, dict) and "records" in result:
        records = result["records"]
        formatted += f"Found {len(records)} records\n\n"
        for i, record in enumerate(records, 1):
            formatted += f"Record {i}:\n{json.dumps(record, indent=2)}\n\n"
        
        # Add summary if available
        if "summary" in result and "counters" in result["summary"]:
            formatted += "\n**Query Summary:**\n"
            formatted += json.dumps(result["summary"]["counters"], indent=2)
    else:
        formatted += json.dumps(result, indent=2)
    
    return formatted

def format_neo4j_schema(schema: Dict[str, Any]) -> str:
    """Format Neo4j schema information"""
    if "error" in schema:
        return f"**Neo4j Schema Error**: {schema['error']}"
    
    formatted = "**Neo4j Database Schema**\n\n"
    
    if "node_labels" in schema:
        formatted += "**Node Labels:**\n"
        for label in schema["node_labels"]:
            formatted += f"- {label}\n"
        formatted += "\n"
    
    if "relationship_types" in schema:
        formatted += "**Relationship Types:**\n"
        for rel_type in schema["relationship_types"]:
            formatted += f"- {rel_type}\n"
        formatted += "\n"
    
    if "properties" in schema:
        formatted += "**Properties:**\n"
        formatted += json.dumps(schema["properties"], indent=2)
    
    return formatted

def format_text2cypher_results(data: Dict[str, Any]) -> str:
    """Format text2cypher results"""
    results = []
    results.append(f"**Query**: {data.get('query', 'N/A')}")
    results.append(f"**Generated Cypher**: {data.get('cypher_query', 'N/A')}")
    results.append(f"**Query Time**: {data.get('query_time', 0):.2f}s\n")
    
    for i, result in enumerate(data.get('results', []), 1):
        result_text = f"**Result {i}:**\n"
        result_text += f"Document: {result.get('document', 'Unknown')}\n"
        result_text += f"Page: {result.get('page', 'N/A')}\n"
        result_text += f"\n{result.get('text', '')}\n"
        result_text += "-" * 80 + "\n"
        results.append(result_text)
    
    return "\n".join(results)

def format_stats(stats: Dict[str, Any]) -> str:
    """Format statistics"""
    result = "**Knowledge Base Statistics**\n\n"
    result += f"- Total Documents: {stats.get('total_documents', 0)}\n"
    result += f"- Total Chunks: {stats.get('total_chunks', 0)}\n"
    result += f"- Total Entities: {stats.get('total_entities', 0)}\n"
    result += f"- Total Relationships: {stats.get('total_relationships', 0)}\n"
    result += f"- Graph Store: {stats.get('graph_store', 'Unknown')}\n"
    result += f"- Vector Store: {stats.get('vector_store', 'Unknown')}\n"
    
    return result

# Initialize server components
logger.info("Initializing Enhanced Knowledge Graph MCP Server")

# Check API connectivity
try:
    response = requests.get(f"{API_BASE_URL}/stats", timeout=5)
    if response.status_code == 200:
        logger.info("Successfully connected to Knowledge Graph API")
    else:
        logger.warning(f"API returned status {response.status_code}")
except Exception as e:
    logger.error(f"Failed to connect to API: {e}")

# MCP Tools
@mcp.tool()
async def search_knowledge(
    query: str, 
    search_type: str = "hybrid", 
    limit: int = 5,
    rerank: bool = True
) -> str:
    """
    Search the knowledge graph using various search types including Neo4j MCP.
    
    Args:
        query: The search query
        search_type: One of 'vector', 'graph', 'hybrid', 'text2cypher', 'neo4j_cypher', or 'neo4j_schema'
        limit: Maximum number of results
        rerank: Whether to use reranking (not applicable to neo4j_* types)
    
    Returns:
        Search results from the knowledge graph
    """
    try:
        # Handle Neo4j MCP search types
        if search_type == "neo4j_cypher":
            # Use Neo4j MCP for direct Cypher execution
            result = await neo4j_client.execute_cypher(query)
            return format_neo4j_results(result)
        
        elif search_type == "neo4j_schema":
            # Get schema and search based on it
            schema = await neo4j_client.get_schema()
            return format_neo4j_schema(schema)
        
        else:
            # Use regular API for other search types
            response = requests.post(
                f"{API_BASE_URL}/search",
                json={
                    "query": query,
                    "search_type": search_type,
                    "limit": limit,
                    "rerank": rerank
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                return format_search_results(data)
            else:
                return f"API Error: {response.status_code} - {response.text}"
    
    except requests.exceptions.Timeout:
        return "Error: Request timed out"
    except requests.exceptions.ConnectionError:
        return f"Error: Could not connect to API at {API_BASE_URL}"
    except Exception as e:
        logger.error(f"Error in search_knowledge: {e}")
        return f"Error: {str(e)}"

@mcp.tool()
async def execute_cypher(query: str) -> str:
    """
    Execute a Cypher query directly on Neo4j through MCP.
    
    Args:
        query: The Cypher query to execute
    
    Returns:
        Query results from Neo4j
    """
    try:
        result = await neo4j_client.execute_cypher(query)
        return format_neo4j_results(result)
    except Exception as e:
        logger.error(f"Error in execute_cypher: {e}")
        return f"Error: {str(e)}"

@mcp.tool()
async def get_neo4j_schema() -> str:
    """
    Get the Neo4j database schema through MCP.
    
    Returns:
        Schema information from Neo4j database
    """
    try:
        schema = await neo4j_client.get_schema()
        return format_neo4j_schema(schema)
    except Exception as e:
        logger.error(f"Error in get_neo4j_schema: {e}")
        return f"Error: {str(e)}"

@mcp.tool()
async def text2cypher_search(query: str, limit: int = 5) -> str:
    """
    Search using natural language that gets converted to Cypher queries.
    
    Args:
        query: Natural language query
        limit: Maximum number of results
    
    Returns:
        Search results from text2cypher query generation
    """
    try:
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
            return format_text2cypher_results(data)
        else:
            return f"API Error: {response.status_code} - {response.text}"
    
    except requests.exceptions.Timeout:
        return "Error: Request timed out"
    except requests.exceptions.ConnectionError:
        return f"Error: Could not connect to API at {API_BASE_URL}"
    except Exception as e:
        logger.error(f"Error in text2cypher_search: {e}")
        return f"Error: {str(e)}"

@mcp.tool()
async def get_stats() -> str:
    """
    Get statistics about the knowledge base.
    
    Returns:
        Statistics including document count, chunks, entities, etc.
    """
    try:
        response = requests.get(f"{API_BASE_URL}/stats", timeout=10)
        
        if response.status_code == 200:
            stats = response.json()
            return format_stats(stats)
        else:
            return f"API Error: {response.status_code} - {response.text}"
    
    except requests.exceptions.Timeout:
        return "Error: Request timed out"
    except requests.exceptions.ConnectionError:
        return f"Error: Could not connect to API at {API_BASE_URL}"
    except Exception as e:
        logger.error(f"Error in get_stats: {e}")
        return f"Error: {str(e)}"

# Main function for entry point
def main():
    """Main entry point for the enhanced server"""
    mcp.run()

# Run the server
if __name__ == "__main__":
    main()