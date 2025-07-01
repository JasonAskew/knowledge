#!/usr/bin/env python3
"""
Test script for Neo4j MCP Proxy
"""

import json
import asyncio
import subprocess
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

async def test_proxy():
    """Test the Neo4j proxy server"""
    
    print("Starting Neo4j proxy test...")
    
    # Start the proxy server
    proxy_process = subprocess.Popen(
        [sys.executable, "neo4j_proxy_simple.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=Path(__file__).parent,
        env={
            **os.environ,
            "NEO4J_URI": os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            "NEO4J_USER": os.getenv("NEO4J_USER", "neo4j"),
            "NEO4J_PASSWORD": os.getenv("NEO4J_PASSWORD", "knowledge123")
        }
    )
    
    try:
        # Initialize
        init_request = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "0.1.0",
                "capabilities": {},
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                }
            },
            "id": 1
        }
        
        proxy_process.stdin.write((json.dumps(init_request) + "\n").encode())
        proxy_process.stdin.flush()
        
        # Read response
        response_line = proxy_process.stdout.readline()
        init_response = json.loads(response_line.decode())
        print(f"Initialize response: {json.dumps(init_response, indent=2)}")
        
        # List tools
        list_tools_request = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "params": {},
            "id": 2
        }
        
        proxy_process.stdin.write((json.dumps(list_tools_request) + "\n").encode())
        proxy_process.stdin.flush()
        
        response_line = proxy_process.stdout.readline()
        tools_response = json.loads(response_line.decode())
        print(f"\nTools response: {json.dumps(tools_response, indent=2)}")
        
        # Test a simple query
        test_query_request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "neo4j_cypher",
                "arguments": {
                    "query": "MATCH (n) RETURN count(n) as node_count LIMIT 1"
                }
            },
            "id": 3
        }
        
        proxy_process.stdin.write((json.dumps(test_query_request) + "\n").encode())
        proxy_process.stdin.flush()
        
        response_line = proxy_process.stdout.readline()
        query_response = json.loads(response_line.decode())
        print(f"\nQuery response: {json.dumps(query_response, indent=2)}")
        
        # Test a more complex query
        complex_query_request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "neo4j_cypher",
                "arguments": {
                    "query": "MATCH (d:Document) RETURN d.filename as filename, d.total_pages as pages LIMIT 5"
                }
            },
            "id": 4
        }
        
        proxy_process.stdin.write((json.dumps(complex_query_request) + "\n").encode())
        proxy_process.stdin.flush()
        
        response_line = proxy_process.stdout.readline()
        complex_response = json.loads(response_line.decode())
        print(f"\nComplex query response: {json.dumps(complex_response, indent=2)}")
        
    finally:
        # Cleanup
        proxy_process.terminate()
        proxy_process.wait()
        print("\nTest completed!")

async def test_direct_connection():
    """Test direct Neo4j connection"""
    print("\nTesting direct Neo4j connection...")
    
    try:
        from neo4j import GraphDatabase
        
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "knowledge123")
        
        driver = GraphDatabase.driver(uri, auth=(user, password))
        
        with driver.session() as session:
            result = session.run("MATCH (n) RETURN count(n) as node_count LIMIT 1")
            record = result.single()
            print(f"Direct connection test: {dict(record)}")
        
        driver.close()
        print("Direct connection successful!")
        
    except Exception as e:
        print(f"Direct connection failed: {e}")

if __name__ == "__main__":
    # Test direct connection first
    asyncio.run(test_direct_connection())
    
    # Then test the proxy
    asyncio.run(test_proxy())