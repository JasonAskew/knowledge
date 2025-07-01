#!/usr/bin/env python3
"""
Neo4j MCP Proxy Server

This server acts as an MCP proxy to the mcp-neo4j-cypher MCP tool.
It forwards all neo4j_cypher queries to the actual Neo4j MCP server
and returns the responses transparently.
"""

import json
import logging
import asyncio
import subprocess
import sys
import os
from typing import Any, Dict, List, Optional
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from mcp.server import Server
from mcp.server.models import InitializeRequest
from mcp.types import Resource, Tool, TextContent, ServerCapabilities
from mcp.server.stdio import stdio_server

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Neo4jMCPProxy:
    """MCP Server that proxies to mcp-neo4j-cypher"""
    
    def __init__(self):
        self.app = Server("neo4j-proxy")
        self._setup_handlers()
        self.neo4j_process = None
        self.neo4j_client = None
        
    def _setup_handlers(self):
        """Set up MCP protocol handlers"""
        
        @self.app.list_tools()
        async def handle_list_tools() -> List[Tool]:
            """List available tools - proxy the neo4j_cypher tool"""
            return [
                Tool(
                    name="neo4j_cypher",
                    description="Execute a Cypher query on the Neo4j database",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The Cypher query to execute"
                            },
                            "parameters": {
                                "type": "object",
                                "description": "Optional parameters for the query",
                                "default": {}
                            }
                        },
                        "required": ["query"]
                    }
                )
            ]
        
        @self.app.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Handle tool calls by proxying to mcp-neo4j-cypher"""
            
            if name != "neo4j_cypher":
                return [TextContent(text=f"Unknown tool: {name}")]
            
            try:
                # Execute the query using the Neo4j MCP client
                result = await self._execute_neo4j_query(
                    arguments.get("query"),
                    arguments.get("parameters", {})
                )
                
                # Format the response
                if result.get("success", False):
                    response_text = json.dumps({
                        "success": True,
                        "records": result.get("records", []),
                        "summary": result.get("summary", {})
                    }, indent=2)
                else:
                    response_text = json.dumps({
                        "success": False,
                        "error": result.get("error", "Unknown error")
                    }, indent=2)
                
                return [TextContent(text=response_text)]
                
            except Exception as e:
                logger.error(f"Error executing neo4j_cypher: {e}")
                return [TextContent(text=json.dumps({
                    "success": False,
                    "error": str(e)
                }, indent=2))]
    
    async def _execute_neo4j_query(self, query: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a query through the mcp-neo4j-cypher subprocess"""
        try:
            # Start the mcp-neo4j-cypher process if not already running
            if self.neo4j_process is None:
                await self._start_neo4j_mcp()
            
            # Create the MCP request
            request = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "neo4j_cypher",
                    "arguments": {
                        "query": query,
                        "parameters": parameters
                    }
                },
                "id": 1
            }
            
            # Send request to the subprocess
            self.neo4j_process.stdin.write(json.dumps(request).encode() + b'\n')
            self.neo4j_process.stdin.flush()
            
            # Read response
            response_line = await asyncio.get_event_loop().run_in_executor(
                None, self.neo4j_process.stdout.readline
            )
            
            if not response_line:
                raise Exception("No response from mcp-neo4j-cypher")
            
            response = json.loads(response_line.decode())
            
            # Extract the result from the MCP response
            if "result" in response:
                # Parse the text content from the MCP response
                content = response["result"][0]["text"]
                return json.loads(content)
            elif "error" in response:
                return {
                    "success": False,
                    "error": response["error"]["message"]
                }
            else:
                return {
                    "success": False,
                    "error": "Invalid response format"
                }
                
        except Exception as e:
            logger.error(f"Error communicating with mcp-neo4j-cypher: {e}")
            # Fallback to direct Neo4j connection
            return await self._direct_neo4j_query(query, parameters)
    
    async def _start_neo4j_mcp(self):
        """Start the mcp-neo4j-cypher subprocess"""
        try:
            # Command to start mcp-neo4j-cypher
            cmd = [
                "/Users/jaskew/.local/bin/uvx",
                "mcp-neo4j-cypher@0.2.3",
                "--transport", "stdio"
            ]
            
            # Set up environment variables
            env = os.environ.copy()
            # Ensure Neo4j credentials are available
            if "NEO4J_URI" not in env:
                env["NEO4J_URI"] = "bolt://localhost:7687"
            if "NEO4J_USER" not in env:
                env["NEO4J_USER"] = "neo4j"
            if "NEO4J_PASSWORD" not in env:
                env["NEO4J_PASSWORD"] = "knowledge123"
            
            # Start the subprocess
            self.neo4j_process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env
            )
            
            # Send initialization
            init_request = {
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "0.1.0",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "neo4j-proxy",
                        "version": "1.0.0"
                    }
                },
                "id": 0
            }
            
            self.neo4j_process.stdin.write(json.dumps(init_request).encode() + b'\n')
            self.neo4j_process.stdin.flush()
            
            # Read initialization response
            init_response = await asyncio.get_event_loop().run_in_executor(
                None, self.neo4j_process.stdout.readline
            )
            
            if init_response:
                logger.info("mcp-neo4j-cypher subprocess started successfully")
            else:
                raise Exception("Failed to initialize mcp-neo4j-cypher")
                
        except Exception as e:
            logger.error(f"Failed to start mcp-neo4j-cypher: {e}")
            self.neo4j_process = None
            raise
    
    async def _direct_neo4j_query(self, query: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback to direct Neo4j query if subprocess fails"""
        try:
            from neo4j import GraphDatabase
            
            uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
            user = os.getenv("NEO4J_USER", "neo4j")
            password = os.getenv("NEO4J_PASSWORD", "knowledge123")
            
            driver = GraphDatabase.driver(uri, auth=(user, password))
            
            records = []
            with driver.session() as session:
                result = session.run(query, parameters)
                for record in result:
                    records.append(dict(record))
                summary = result.consume()
            
            driver.close()
            
            return {
                "success": True,
                "records": records,
                "summary": {
                    "counters": dict(summary.counters)
                }
            }
            
        except Exception as e:
            logger.error(f"Direct Neo4j query failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def cleanup(self):
        """Clean up resources"""
        if self.neo4j_process:
            self.neo4j_process.terminate()
            self.neo4j_process.wait()
            self.neo4j_process = None

async def main():
    """Main entry point"""
    proxy = Neo4jMCPProxy()
    
    # Run the server
    async with stdio_server() as (read_stream, write_stream):
        await proxy.app.run(
            read_stream,
            write_stream,
            InitializeRequest(
                protocol_version="0.1.0",
                capabilities=ServerCapabilities(),
                client_info={"name": "neo4j-proxy", "version": "1.0.0"}
            ),
        )
    
    # Cleanup
    await proxy.cleanup()

if __name__ == "__main__":
    asyncio.run(main())