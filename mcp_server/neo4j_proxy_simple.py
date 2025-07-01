#!/usr/bin/env python3
"""
Simple Neo4j MCP Proxy Server

This server acts as a simple proxy to the mcp-neo4j-cypher MCP server.
It spawns mcp-neo4j-cypher as a subprocess and forwards all communication.
"""

import json
import logging
import asyncio
import subprocess
import sys
import os
from typing import Any, Dict, List, Optional
from pathlib import Path
import threading
import queue

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from mcp.server import Server
from mcp.server.models import InitializeRequest
from mcp.types import Tool, TextContent, ServerCapabilities
from mcp.server.stdio import stdio_server

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SimpleNeo4jProxy:
    """Simple MCP Server that proxies to mcp-neo4j-cypher"""
    
    def __init__(self):
        self.app = Server("neo4j-proxy")
        self.neo4j_process = None
        self.response_queue = queue.Queue()
        self.request_id = 0
        self._setup_handlers()
        
    def _setup_handlers(self):
        """Set up MCP protocol handlers"""
        
        @self.app.list_tools()
        async def handle_list_tools() -> List[Tool]:
            """List available tools"""
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
                                "description": "Optional parameters for the query"
                            }
                        },
                        "required": ["query"]
                    }
                )
            ]
        
        @self.app.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Handle tool calls"""
            
            if name != "neo4j_cypher":
                return [TextContent(
                    type="text",
                    text=f"Unknown tool: {name}"
                )]
            
            try:
                # Get query and parameters
                query = arguments.get("query")
                parameters = arguments.get("parameters", {})
                
                if not query:
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "success": False,
                            "error": "Query is required"
                        }, indent=2)
                    )]
                
                # Execute through subprocess or direct connection
                result = await self._execute_query(query, parameters)
                
                return [TextContent(
                    type="text",
                    text=json.dumps(result, indent=2)
                )]
                
            except Exception as e:
                logger.error(f"Error executing neo4j_cypher: {e}")
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "success": False,
                        "error": str(e)
                    }, indent=2)
                )]
    
    async def _execute_query(self, query: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute query using subprocess or direct connection"""
        
        # Try subprocess first
        if self.neo4j_process and self.neo4j_process.poll() is None:
            try:
                return await self._execute_via_subprocess(query, parameters)
            except Exception as e:
                logger.warning(f"Subprocess execution failed: {e}, falling back to direct connection")
        
        # Fallback to direct connection
        return await self._execute_direct(query, parameters)
    
    async def _execute_via_subprocess(self, query: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute query through subprocess"""
        self.request_id += 1
        
        # Create request
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
            "id": self.request_id
        }
        
        # Send request
        request_str = json.dumps(request) + "\n"
        self.neo4j_process.stdin.write(request_str.encode())
        self.neo4j_process.stdin.flush()
        
        # Wait for response (with timeout)
        try:
            response = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None, self.response_queue.get
                ),
                timeout=30.0
            )
            
            # Parse response
            if "result" in response and response["result"]:
                content = response["result"][0].get("text", "{}")
                return json.loads(content)
            elif "error" in response:
                return {
                    "success": False,
                    "error": response["error"].get("message", "Unknown error")
                }
            else:
                return {
                    "success": False,
                    "error": "Invalid response format"
                }
                
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": "Query timeout"
            }
    
    async def _execute_direct(self, query: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute query directly using Neo4j driver"""
        try:
            from neo4j import GraphDatabase
            
            uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
            user = os.getenv("NEO4J_USER", "neo4j")
            password = os.getenv("NEO4J_PASSWORD", "knowledge123")
            
            driver = GraphDatabase.driver(uri, auth=(user, password))
            
            records = []
            summary_data = {}
            
            with driver.session() as session:
                result = session.run(query, parameters)
                for record in result:
                    records.append(dict(record))
                summary = result.consume()
                summary_data = {
                    "counters": dict(summary.counters)
                }
            
            driver.close()
            
            return {
                "success": True,
                "records": records,
                "summary": summary_data
            }
            
        except Exception as e:
            logger.error(f"Direct query execution failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _start_subprocess(self):
        """Start the mcp-neo4j-cypher subprocess"""
        try:
            # Command to start mcp-neo4j-cypher
            cmd = [
                "/Users/jaskew/.local/bin/uvx",
                "mcp-neo4j-cypher@0.2.3",
                "--transport", "stdio"
            ]
            
            # Set up environment
            env = os.environ.copy()
            env.update({
                "NEO4J_URI": os.getenv("NEO4J_URI", "bolt://localhost:7687"),
                "NEO4J_USER": os.getenv("NEO4J_USER", "neo4j"),
                "NEO4J_PASSWORD": os.getenv("NEO4J_PASSWORD", "knowledge123")
            })
            
            # Start subprocess
            self.neo4j_process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=False
            )
            
            # Start reader thread
            reader_thread = threading.Thread(
                target=self._read_subprocess_output,
                daemon=True
            )
            reader_thread.start()
            
            # Initialize subprocess
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
            
            self.neo4j_process.stdin.write((json.dumps(init_request) + "\n").encode())
            self.neo4j_process.stdin.flush()
            
            logger.info("Started mcp-neo4j-cypher subprocess")
            
        except Exception as e:
            logger.error(f"Failed to start subprocess: {e}")
            self.neo4j_process = None
    
    def _read_subprocess_output(self):
        """Read output from subprocess"""
        while self.neo4j_process and self.neo4j_process.poll() is None:
            try:
                line = self.neo4j_process.stdout.readline()
                if line:
                    try:
                        response = json.loads(line.decode())
                        self.response_queue.put(response)
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON from subprocess: {line}")
            except Exception as e:
                logger.error(f"Error reading subprocess output: {e}")
                break
    
    async def initialize(self):
        """Initialize the proxy"""
        # Try to start subprocess
        self._start_subprocess()
        
        # Give it time to initialize
        await asyncio.sleep(1)
    
    async def cleanup(self):
        """Clean up resources"""
        if self.neo4j_process:
            self.neo4j_process.terminate()
            try:
                self.neo4j_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.neo4j_process.kill()
            self.neo4j_process = None

async def main():
    """Main entry point"""
    proxy = SimpleNeo4jProxy()
    
    # Initialize
    await proxy.initialize()
    
    try:
        # Run the server
        async with stdio_server() as (read_stream, write_stream):
            await proxy.app.run(
                read_stream,
                write_stream,
                InitializeRequest(
                    protocol_version="0.1.0",
                    capabilities=ServerCapabilities(),
                    client_info={
                        "name": "claude-desktop",
                        "version": "1.0.0"
                    }
                ),
            )
    finally:
        # Cleanup
        await proxy.cleanup()

if __name__ == "__main__":
    asyncio.run(main())