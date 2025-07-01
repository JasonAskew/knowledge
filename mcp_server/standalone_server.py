#!/usr/bin/env python3
"""
Standalone MCP Server for Knowledge Graph System

This server provides MCP access to the knowledge graph API without requiring
direct imports of the knowledge system components.
"""

import json
import logging
import asyncio
import os
import requests
from typing import Any, Dict, List, Optional
from pathlib import Path

from mcp.server import Server
from mcp.server.models import InitializeRequest, InitializeResponse
from mcp.types import Resource, Tool, TextContent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class KnowledgeGraphMCPServer:
    """MCP Server that connects to Knowledge Graph API"""
    
    def __init__(self):
        self.server = Server("knowledge-graph")
        self.api_base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
        self._setup_handlers()
        
    def _setup_handlers(self):
        """Set up MCP protocol handlers"""
        
        @self.server.request_handler
        async def handle_initialize(request: InitializeRequest) -> InitializeResponse:
            """Initialize the server"""
            logger.info("Initializing Knowledge Graph MCP Server")
            
            # Check API connectivity
            try:
                response = requests.get(f"{self.api_base_url}/stats", timeout=5)
                if response.status_code == 200:
                    logger.info("Successfully connected to Knowledge Graph API")
                else:
                    logger.warning(f"API returned status {response.status_code}")
            except Exception as e:
                logger.error(f"Failed to connect to API: {e}")
            
            return InitializeResponse(
                protocolVersion="1.0",
                capabilities={
                    "tools": True,
                    "resources": True,
                },
                serverInfo={
                    "name": "knowledge-graph",
                    "version": "1.0.0",
                    "description": "Knowledge Graph System with GraphRAG capabilities"
                }
            )
        
        @self.server.tool_handler
        async def handle_list_tools() -> List[Tool]:
            """List available tools"""
            return [
                Tool(
                    name="search_knowledge",
                    description="Search the knowledge graph using vector, graph, hybrid, or text2cypher search",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The search query"
                            },
                            "search_type": {
                                "type": "string",
                                "enum": ["vector", "graph", "hybrid", "text2cypher"],
                                "description": "Type of search to perform",
                                "default": "hybrid"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results",
                                "default": 5
                            },
                            "rerank": {
                                "type": "boolean",
                                "description": "Whether to use reranking",
                                "default": True
                            }
                        },
                        "required": ["query"]
                    }
                ),
                Tool(
                    name="text2cypher_search",
                    description="Search using natural language that gets converted to Cypher queries",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Natural language query"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results",
                                "default": 5
                            }
                        },
                        "required": ["query"]
                    }
                ),
                Tool(
                    name="get_stats",
                    description="Get statistics about the knowledge base",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                )
            ]
        
        @self.server.tool_handler
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Handle tool calls"""
            
            try:
                if name == "search_knowledge":
                    # Call search API
                    response = requests.post(
                        f"{self.api_base_url}/search",
                        json={
                            "query": arguments["query"],
                            "search_type": arguments.get("search_type", "hybrid"),
                            "limit": arguments.get("limit", 5),
                            "rerank": arguments.get("rerank", True)
                        },
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        # Format results
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
                        
                        return [TextContent(text="\n".join(results))]
                    else:
                        return [TextContent(text=f"API Error: {response.status_code} - {response.text}")]
                
                elif name == "text2cypher_search":
                    # Call text2cypher API
                    response = requests.post(
                        f"{self.api_base_url}/text2cypher",
                        json={
                            "query": arguments["query"],
                            "limit": arguments.get("limit", 5)
                        },
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        # Format results
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
                        
                        return [TextContent(text="\n".join(results))]
                    else:
                        return [TextContent(text=f"API Error: {response.status_code} - {response.text}")]
                
                elif name == "get_stats":
                    # Get statistics
                    response = requests.get(f"{self.api_base_url}/stats", timeout=10)
                    
                    if response.status_code == 200:
                        stats = response.json()
                        
                        result = "**Knowledge Base Statistics**\n\n"
                        result += f"- Total Documents: {stats.get('total_documents', 0)}\n"
                        result += f"- Total Chunks: {stats.get('total_chunks', 0)}\n"
                        result += f"- Total Entities: {stats.get('total_entities', 0)}\n"
                        result += f"- Total Relationships: {stats.get('total_relationships', 0)}\n"
                        result += f"- Graph Store: {stats.get('graph_store', 'Unknown')}\n"
                        result += f"- Vector Store: {stats.get('vector_store', 'Unknown')}\n"
                        
                        return [TextContent(text=result)]
                    else:
                        return [TextContent(text=f"API Error: {response.status_code} - {response.text}")]
                
                else:
                    return [TextContent(text=f"Unknown tool: {name}")]
                    
            except requests.exceptions.Timeout:
                return [TextContent(text="Error: Request timed out")]
            except requests.exceptions.ConnectionError:
                return [TextContent(text=f"Error: Could not connect to API at {self.api_base_url}")]
            except Exception as e:
                logger.error(f"Error executing tool {name}: {e}")
                return [TextContent(text=f"Error: {str(e)}")]
        
        @self.server.resource_handler
        async def handle_list_resources() -> List[Resource]:
            """List available resources"""
            try:
                # Get stats to show available documents
                response = requests.get(f"{self.api_base_url}/stats", timeout=10)
                if response.status_code == 200:
                    stats = response.json()
                    
                    return [
                        Resource(
                            uri="knowledge://stats",
                            name="Knowledge Base Statistics",
                            description=f"Statistics: {stats.get('total_documents', 0)} documents, {stats.get('total_chunks', 0)} chunks",
                            mimeType="application/json"
                        )
                    ]
            except Exception as e:
                logger.error(f"Error listing resources: {e}")
            
            return []
        
        @self.server.resource_handler
        async def handle_read_resource(uri: str) -> TextContent:
            """Read a specific resource"""
            try:
                if uri == "knowledge://stats":
                    response = requests.get(f"{self.api_base_url}/stats", timeout=10)
                    if response.status_code == 200:
                        return TextContent(text=json.dumps(response.json(), indent=2))
                    else:
                        return TextContent(text=f"Error fetching stats: {response.status_code}")
                else:
                    return TextContent(text=f"Unknown resource: {uri}")
            except Exception as e:
                return TextContent(text=f"Error: {str(e)}")
    
    async def run(self):
        """Run the MCP server"""
        logger.info(f"Starting MCP server, connecting to API at {self.api_base_url}")
        await self.server.run()

async def main():
    """Main entry point"""
    server = KnowledgeGraphMCPServer()
    await server.run()

if __name__ == "__main__":
    asyncio.run(main())