#!/usr/bin/env python3
"""
MCP Server for Knowledge Graph System

This server provides MCP (Model Context Protocol) access to the knowledge graph system,
allowing Claude Desktop and other MCP clients to query the knowledge base.
"""

import json
import logging
import asyncio
from typing import Any, Dict, List, Optional
from pathlib import Path
import sys

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from mcp.server import Server, Request, Response
from mcp.server.models import InitializeRequest, InitializeResponse
from mcp.types import Resource, Tool, TextContent

# Import our knowledge system components
from docker.api import KnowledgeSearchEngine, SearchRequest, SearchResponse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class KnowledgeGraphMCPServer:
    """MCP Server wrapper for Knowledge Graph System"""
    
    def __init__(self):
        self.server = Server("knowledge-graph")
        self.search_engine = None
        self._setup_handlers()
        
    def _setup_handlers(self):
        """Set up MCP protocol handlers"""
        
        @self.server.request_handler
        async def handle_initialize(request: InitializeRequest) -> InitializeResponse:
            """Initialize the server and load the knowledge engine"""
            try:
                # Initialize the search engine
                self.search_engine = KnowledgeSearchEngine()
                logger.info("Knowledge search engine initialized successfully")
                
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
            except Exception as e:
                logger.error(f"Failed to initialize: {e}")
                raise
        
        @self.server.tool_handler
        async def handle_list_tools() -> List[Tool]:
            """List available tools"""
            return [
                Tool(
                    name="search_knowledge",
                    description="Search the knowledge graph using vector, graph, or hybrid search",
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
                    name="query_cypher",
                    description="Execute a Cypher query directly on the knowledge graph",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The Cypher query to execute"
                            }
                        },
                        "required": ["query"]
                    }
                ),
                Tool(
                    name="get_document_info",
                    description="Get information about a specific document",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "document_name": {
                                "type": "string",
                                "description": "Name of the document to retrieve info for"
                            }
                        },
                        "required": ["document_name"]
                    }
                ),
                Tool(
                    name="list_documents",
                    description="List all documents in the knowledge base",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of documents to return",
                                "default": 50
                            }
                        }
                    }
                )
            ]
        
        @self.server.tool_handler
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Handle tool calls"""
            
            if not self.search_engine:
                return [TextContent(text="Error: Knowledge engine not initialized")]
            
            try:
                if name == "search_knowledge":
                    # Perform search
                    request = SearchRequest(
                        query=arguments["query"],
                        search_type=arguments.get("search_type", "hybrid"),
                        limit=arguments.get("limit", 5),
                        rerank=arguments.get("rerank", True)
                    )
                    
                    response = await self._async_search(request)
                    
                    # Format results
                    results = []
                    for i, result in enumerate(response.results, 1):
                        result_text = f"**Result {i}:**\n"
                        result_text += f"Document: {result.document}\n"
                        result_text += f"Page: {result.page_num}\n"
                        result_text += f"Score: {result.score:.3f}\n"
                        if hasattr(result, 'rerank_score') and result.rerank_score:
                            result_text += f"Rerank Score: {result.rerank_score:.3f}\n"
                        result_text += f"\n{result.text}\n"
                        result_text += "-" * 80 + "\n"
                        results.append(result_text)
                    
                    return [TextContent(text="\n".join(results))]
                
                elif name == "query_cypher":
                    # Execute Cypher query
                    results = self.search_engine.graph_store.execute_query(arguments["query"])
                    return [TextContent(text=json.dumps(results, indent=2))]
                
                elif name == "get_document_info":
                    # Get document information
                    doc_name = arguments["document_name"]
                    query = f"""
                    MATCH (d:Document {{filename: '{doc_name}'}})
                    OPTIONAL MATCH (d)-[:HAS_CHUNK]->(c:Chunk)
                    RETURN d.filename as filename, 
                           d.file_path as path,
                           d.total_pages as pages,
                           count(c) as chunks,
                           d.created_at as created
                    """
                    results = self.search_engine.graph_store.execute_query(query)
                    return [TextContent(text=json.dumps(results, indent=2))]
                
                elif name == "list_documents":
                    # List documents
                    limit = arguments.get("limit", 50)
                    query = f"""
                    MATCH (d:Document)
                    RETURN d.filename as filename, 
                           d.total_pages as pages,
                           d.created_at as created
                    ORDER BY d.created_at DESC
                    LIMIT {limit}
                    """
                    results = self.search_engine.graph_store.execute_query(query)
                    return [TextContent(text=json.dumps(results, indent=2))]
                
                else:
                    return [TextContent(text=f"Unknown tool: {name}")]
                    
            except Exception as e:
                logger.error(f"Error executing tool {name}: {e}")
                return [TextContent(text=f"Error: {str(e)}")]
        
        @self.server.resource_handler
        async def handle_list_resources() -> List[Resource]:
            """List available resources"""
            if not self.search_engine:
                return []
            
            try:
                # Get document list
                query = """
                MATCH (d:Document)
                RETURN d.filename as filename, d.file_path as path
                LIMIT 100
                """
                documents = self.search_engine.graph_store.execute_query(query)
                
                resources = []
                for doc in documents:
                    resources.append(Resource(
                        uri=f"knowledge://{doc['filename']}",
                        name=doc['filename'],
                        description=f"Document: {doc['filename']}",
                        mimeType="application/pdf"
                    ))
                
                return resources
            except Exception as e:
                logger.error(f"Error listing resources: {e}")
                return []
        
        @self.server.resource_handler
        async def handle_read_resource(uri: str) -> TextContent:
            """Read a specific resource"""
            if not self.search_engine:
                return TextContent(text="Error: Knowledge engine not initialized")
            
            try:
                # Extract document name from URI
                if uri.startswith("knowledge://"):
                    doc_name = uri[12:]  # Remove "knowledge://" prefix
                    
                    # Get document content
                    query = f"""
                    MATCH (d:Document {{filename: '{doc_name}'}})-[:HAS_CHUNK]->(c:Chunk)
                    RETURN c.text as text, c.page_num as page
                    ORDER BY c.page_num, c.chunk_index
                    """
                    chunks = self.search_engine.graph_store.execute_query(query)
                    
                    # Combine chunks
                    content = f"# {doc_name}\n\n"
                    current_page = None
                    for chunk in chunks:
                        if chunk['page'] != current_page:
                            current_page = chunk['page']
                            content += f"\n## Page {current_page}\n\n"
                        content += chunk['text'] + "\n\n"
                    
                    return TextContent(text=content)
                else:
                    return TextContent(text=f"Unknown resource URI: {uri}")
                    
            except Exception as e:
                logger.error(f"Error reading resource {uri}: {e}")
                return TextContent(text=f"Error: {str(e)}")
    
    async def _async_search(self, request: SearchRequest) -> SearchResponse:
        """Perform search asynchronously"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.search_engine.search, request)
    
    async def run(self):
        """Run the MCP server"""
        await self.server.run()

async def main():
    """Main entry point"""
    server = KnowledgeGraphMCPServer()
    await server.run()

if __name__ == "__main__":
    asyncio.run(main())