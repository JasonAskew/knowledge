#!/usr/bin/env python3
"""
MCP Neo4j Proxy Server

This server acts as a transparent proxy to the mcp-neo4j-cypher MCP server.
It implements the MCP client protocol to communicate with mcp-neo4j-cypher
and exposes the same neo4j_cypher tool to Claude Desktop.
"""

import json
import logging
import asyncio
import subprocess
import sys
import os
from typing import Any, Dict, List, Optional, AsyncIterator
from pathlib import Path
from contextlib import asynccontextmanager

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

import mcp.types as types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.server import Server
from mcp.server.models import InitializeRequest
from mcp.server.stdio import stdio_server

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MCPNeo4jProxyServer:
    """MCP Server that acts as a proxy to mcp-neo4j-cypher"""
    
    def __init__(self):
        self.app = Server("neo4j-proxy")
        self.neo4j_session: Optional[ClientSession] = None
        self._setup_handlers()
        
    def _setup_handlers(self):
        """Set up MCP protocol handlers"""
        
        @self.app.list_tools()
        async def handle_list_tools() -> List[types.Tool]:
            """List available tools - proxy from neo4j server"""
            if not self.neo4j_session:
                logger.warning("Neo4j session not initialized")
                return []
            
            try:
                # Get tools from the neo4j server
                tools_list = await self.neo4j_session.list_tools()
                return tools_list.tools
            except Exception as e:
                logger.error(f"Error listing tools: {e}")
                return []
        
        @self.app.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[types.TextContent]:
            """Handle tool calls by proxying to mcp-neo4j-cypher"""
            
            if not self.neo4j_session:
                return [types.TextContent(
                    type="text",
                    text=json.dumps({
                        "success": False,
                        "error": "Neo4j session not initialized"
                    }, indent=2)
                )]
            
            try:
                # Call the tool on the neo4j server
                result = await self.neo4j_session.call_tool(name, arguments)
                
                # Return the result directly
                return result.content
                
            except Exception as e:
                logger.error(f"Error calling tool {name}: {e}")
                return [types.TextContent(
                    type="text",
                    text=json.dumps({
                        "success": False,
                        "error": str(e)
                    }, indent=2)
                )]
        
        @self.app.list_resources()
        async def handle_list_resources() -> List[types.Resource]:
            """List available resources from neo4j server"""
            if not self.neo4j_session:
                return []
            
            try:
                resources_list = await self.neo4j_session.list_resources()
                return resources_list.resources
            except Exception as e:
                logger.error(f"Error listing resources: {e}")
                return []
        
        @self.app.read_resource()
        async def handle_read_resource(uri: str) -> str:
            """Read a resource from neo4j server"""
            if not self.neo4j_session:
                return "Error: Neo4j session not initialized"
            
            try:
                resource_content = await self.neo4j_session.read_resource(uri)
                return resource_content.contents[0].text if resource_content.contents else ""
            except Exception as e:
                logger.error(f"Error reading resource {uri}: {e}")
                return f"Error: {str(e)}"
    
    async def initialize_neo4j_client(self):
        """Initialize the connection to mcp-neo4j-cypher"""
        try:
            # Server parameters for mcp-neo4j-cypher
            server_params = StdioServerParameters(
                command="/Users/jaskew/.local/bin/uvx",
                args=["mcp-neo4j-cypher@0.2.3", "--transport", "stdio"],
                env={
                    **os.environ,
                    "NEO4J_URI": os.getenv("NEO4J_URI", "bolt://localhost:7687"),
                    "NEO4J_USER": os.getenv("NEO4J_USER", "neo4j"),
                    "NEO4J_PASSWORD": os.getenv("NEO4J_PASSWORD", "knowledge123")
                }
            )
            
            # Create client session
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    self.neo4j_session = session
                    
                    # Initialize the session
                    await session.initialize()
                    
                    logger.info("Connected to mcp-neo4j-cypher successfully")
                    
                    # Keep the session alive while the proxy server runs
                    while True:
                        await asyncio.sleep(1)
                        
        except Exception as e:
            logger.error(f"Failed to connect to mcp-neo4j-cypher: {e}")
            self.neo4j_session = None

async def run_proxy_server():
    """Run the proxy server"""
    proxy = MCPNeo4jProxyServer()
    
    # Start the neo4j client in the background
    neo4j_task = asyncio.create_task(proxy.initialize_neo4j_client())
    
    # Give the neo4j client time to initialize
    await asyncio.sleep(2)
    
    try:
        # Run the proxy server
        async with stdio_server() as (read_stream, write_stream):
            await proxy.app.run(
                read_stream,
                write_stream,
                InitializeRequest(
                    protocol_version="0.1.0",
                    capabilities={},
                    client_info={
                        "name": "claude-desktop",
                        "version": "1.0.0"
                    }
                ),
            )
    finally:
        # Cancel the neo4j client task
        neo4j_task.cancel()
        try:
            await neo4j_task
        except asyncio.CancelledError:
            pass

if __name__ == "__main__":
    asyncio.run(run_proxy_server())