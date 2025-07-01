#!/usr/bin/env python3
"""
Enhanced MCP Server that proxies to mcp-neo4j-cypher
"""

import asyncio
import json
import os
import sys
import requests
import subprocess
from typing import Dict, Any, Optional
import threading
import queue

# Add debugging
sys.stderr.write("Starting Enhanced Knowledge Graph MCP Server with Neo4j Proxy...\n")
sys.stderr.write(f"Python: {sys.executable}\n")

from mcp.server import FastMCP

# Create the MCP server
mcp = FastMCP("enhanced-knowledge-graph")

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "knowledge123")

# Neo4j MCP subprocess management
neo4j_process = None
response_queue = queue.Queue()
request_id = 0

def read_neo4j_output(proc):
    """Read output from Neo4j MCP subprocess"""
    while True:
        try:
            line = proc.stdout.readline()
            if not line:
                break
            
            # Try to parse as JSON
            try:
                data = json.loads(line.strip())
                response_queue.put(data)
            except json.JSONDecodeError:
                # Not JSON, might be debug output
                sys.stderr.write(f"Neo4j MCP output: {line}")
                
        except Exception as e:
            sys.stderr.write(f"Error reading Neo4j output: {e}\n")
            break

def start_neo4j_mcp():
    """Start the mcp-neo4j-cypher subprocess"""
    global neo4j_process
    
    try:
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
            bufsize=1
        )
        
        # Start reader thread
        reader_thread = threading.Thread(target=read_neo4j_output, args=(neo4j_process,))
        reader_thread.daemon = True
        reader_thread.start()
        
        # Send initialization
        init_request = {
            "jsonrpc": "2.0",
            "id": 0,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "enhanced-knowledge-graph",
                    "version": "1.0.0"
                }
            }
        }
        
        neo4j_process.stdin.write(json.dumps(init_request) + '\n')
        neo4j_process.stdin.flush()
        
        # Wait for initialization response
        timeout = 5
        start_time = asyncio.get_event_loop().time()
        while (asyncio.get_event_loop().time() - start_time) < timeout:
            try:
                response = response_queue.get(timeout=0.1)
                if response.get("id") == 0:
                    sys.stderr.write("Neo4j MCP initialized successfully\n")
                    return True
            except queue.Empty:
                continue
                
        sys.stderr.write("Neo4j MCP initialization timeout\n")
        return False
        
    except Exception as e:
        sys.stderr.write(f"Failed to start Neo4j MCP: {e}\n")
        return False

def query_neo4j_mcp(query: str) -> Dict[str, Any]:
    """Query Neo4j via MCP"""
    global request_id
    
    if not neo4j_process:
        return {"error": "Neo4j MCP not running"}
    
    try:
        request_id += 1
        
        # Call the query tool
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {
                "name": "query",
                "arguments": {
                    "cypher": query
                }
            }
        }
        
        neo4j_process.stdin.write(json.dumps(request) + '\n')
        neo4j_process.stdin.flush()
        
        # Wait for response
        timeout = 10
        start_time = asyncio.get_event_loop().time()
        while (asyncio.get_event_loop().time() - start_time) < timeout:
            try:
                response = response_queue.get(timeout=0.1)
                if response.get("id") == request_id:
                    if "result" in response:
                        return response["result"]
                    elif "error" in response:
                        return {"error": response["error"]}
            except queue.Empty:
                continue
                
        return {"error": "Timeout waiting for Neo4j response"}
        
    except Exception as e:
        return {"error": str(e)}

# Try to start Neo4j MCP
neo4j_available = start_neo4j_mcp()

@mcp.tool()
async def search_knowledge(
    query: str, 
    search_type: str = "neo4j_cypher", 
    limit: int = 5,
    rerank: bool = True
) -> str:
    """
    Search using mcp-neo4j-cypher tool.
    
    Args:
        query: Natural language or Cypher query
        search_type: Only 'neo4j_cypher' supported
        limit: Maximum results
    
    Returns:
        Search results from Neo4j
    """
    if search_type != "neo4j_cypher":
        return "⚠️ Only 'neo4j_cypher' search type is currently enabled."
    
    # If Neo4j MCP is available, use it
    if neo4j_available:
        sys.stderr.write(f"Querying Neo4j MCP: {query}\n")
        result = query_neo4j_mcp(query)
        
        if "error" not in result:
            # Format results
            if isinstance(result, list):
                output = [f"**Neo4j Query Results** ({len(result)} found)\n"]
                for i, item in enumerate(result[:limit], 1):
                    output.append(f"\n### Result {i}")
                    if isinstance(item, dict):
                        for k, v in item.items():
                            output.append(f"**{k}**: {v}")
                    else:
                        output.append(str(item))
                    output.append("---")
                return "\n".join(output)
            else:
                return str(result)
    
    # Fallback to text2cypher API
    sys.stderr.write("Falling back to text2cypher API\n")
    try:
        response = requests.post(
            f"{API_BASE_URL}/search",
            json={
                "query": query,
                "search_type": "text2cypher",
                "limit": limit
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            output = [f"**Query**: {query}"]
            output.append(f"**Results**: {len(data.get('results', []))} found\n")
            
            for i, res in enumerate(data.get('results', [])[:limit], 1):
                output.append(f"\n### Result {i}")
                output.append(f"**Document**: {res.get('document_id', 'Unknown')}")
                output.append(f"**Page**: {res.get('page_num', 'N/A')}")
                text = res.get('text', '')[:300]
                output.append(f"\n{text}...")
                output.append("---")
            
            return "\n".join(output)
            
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
async def get_knowledge_stats() -> str:
    """Get knowledge base statistics"""
    try:
        response = requests.get(f"{API_BASE_URL}/stats", timeout=10)
        if response.status_code == 200:
            stats = response.json()
            return f"""**Knowledge Base Statistics**

- Documents: {stats.get('documents', 0)}
- Chunks: {stats.get('chunks', 0)}
- Entities: {stats.get('entities', 0)}
- Neo4j MCP: {'Connected' if neo4j_available else 'Not connected'}"""
    except Exception as e:
        return f"Error: {str(e)}"

# Cleanup
import atexit

def cleanup():
    if neo4j_process:
        neo4j_process.terminate()
        sys.stderr.write("Cleaned up Neo4j MCP\n")

atexit.register(cleanup)

if __name__ == "__main__":
    mcp.run()