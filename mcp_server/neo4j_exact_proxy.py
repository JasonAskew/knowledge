#!/usr/bin/env python3
"""
Neo4j Exact Proxy MCP Server
Exposes exactly the same tools as mcp-neo4j-cypher:
- read-neo4j-cypher
- write-neo4j-cypher
- get-neo4j-schema
"""

import sys
import os
import json
from typing import Dict, Any, Optional

sys.stderr.write("Starting Neo4j Exact Proxy MCP Server...\n")

from mcp.server import FastMCP

# Create the MCP server
mcp = FastMCP("knowledge-graph")

# Configuration
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "knowledge123")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

# Import Neo4j driver
neo4j_driver = None
try:
    from neo4j import GraphDatabase
    neo4j_driver = GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
    )
    neo4j_driver.verify_connectivity()
    sys.stderr.write(f"✓ Neo4j connection established to {NEO4J_URI}\n")
except Exception as e:
    sys.stderr.write(f"⚠️ Neo4j connection failed: {e}\n")

@mcp.tool()
async def read_neo4j_cypher(query: str, params: Optional[Dict[str, Any]] = None) -> str:
    """
    Execute a Cypher read query against Neo4j database.
    
    Args:
        query: Cypher read query
        params: Optional query parameters
    
    Returns:
        Query results as JSON
    """
    if not neo4j_driver:
        return json.dumps({"error": "Neo4j connection not available"})
    
    try:
        records = []
        with neo4j_driver.session(database=NEO4J_DATABASE) as session:
            result = session.run(query, params or {})
            for record in result:
                # Convert record to dict, handling Neo4j types
                record_dict = {}
                for key, value in dict(record).items():
                    if hasattr(value, '__dict__'):
                        # Handle node/relationship objects
                        record_dict[key] = dict(value)
                    else:
                        record_dict[key] = value
                records.append(record_dict)
        
        return json.dumps({
            "success": True,
            "records": records,
            "count": len(records)
        }, indent=2)
        
    except Exception as e:
        sys.stderr.write(f"Read query error: {e}\n")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, indent=2)

@mcp.tool()
async def write_neo4j_cypher(query: str, params: Optional[Dict[str, Any]] = None) -> str:
    """
    Execute a Cypher write/update query against Neo4j database.
    
    Args:
        query: Cypher update query
        params: Optional query parameters
    
    Returns:
        Summary of changes made
    """
    if not neo4j_driver:
        return json.dumps({"error": "Neo4j connection not available"})
    
    try:
        with neo4j_driver.session(database=NEO4J_DATABASE) as session:
            result = session.run(query, params or {})
            summary = result.consume()
            
            # Extract counters
            counters = summary.counters
            
            return json.dumps({
                "success": True,
                "summary": {
                    "nodes_created": counters.nodes_created,
                    "nodes_deleted": counters.nodes_deleted,
                    "relationships_created": counters.relationships_created,
                    "relationships_deleted": counters.relationships_deleted,
                    "properties_set": counters.properties_set,
                    "labels_added": counters.labels_added,
                    "labels_removed": counters.labels_removed
                }
            }, indent=2)
            
    except Exception as e:
        sys.stderr.write(f"Write query error: {e}\n")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, indent=2)

@mcp.tool()
async def get_neo4j_schema() -> str:
    """
    Get the schema of the Neo4j database including node labels, 
    relationships, and properties.
    
    Returns:
        Database schema as JSON
    """
    if not neo4j_driver:
        return json.dumps({"error": "Neo4j connection not available"})
    
    try:
        schema = {
            "node_labels": [],
            "relationships": [],
            "constraints": [],
            "indexes": []
        }
        
        with neo4j_driver.session(database=NEO4J_DATABASE) as session:
            # Get node labels
            result = session.run("CALL db.labels()")
            schema["node_labels"] = [record["label"] for record in result]
            
            # Get relationship types
            result = session.run("CALL db.relationshipTypes()")
            schema["relationships"] = [record["relationshipType"] for record in result]
            
            # Get constraints
            result = session.run("SHOW CONSTRAINTS")
            for record in result:
                schema["constraints"].append({
                    "name": record.get("name"),
                    "type": record.get("type"),
                    "entity_type": record.get("entityType"),
                    "properties": record.get("properties", [])
                })
            
            # Get indexes
            result = session.run("SHOW INDEXES")
            for record in result:
                schema["indexes"].append({
                    "name": record.get("name"),
                    "type": record.get("type"),
                    "entity_type": record.get("entityType"),
                    "properties": record.get("properties", [])
                })
            
            # Get sample properties for each node label
            schema["node_properties"] = {}
            for label in schema["node_labels"]:
                query = f"MATCH (n:{label}) RETURN n LIMIT 5"
                result = session.run(query)
                properties = set()
                for record in result:
                    node = record["n"]
                    properties.update(node.keys())
                schema["node_properties"][label] = list(properties)
            
            # Get sample properties for relationships
            schema["relationship_properties"] = {}
            for rel_type in schema["relationships"]:
                query = f"MATCH ()-[r:{rel_type}]->() RETURN r LIMIT 5"
                result = session.run(query)
                properties = set()
                for record in result:
                    rel = record["r"]
                    properties.update(rel.keys())
                schema["relationship_properties"][rel_type] = list(properties)
        
        return json.dumps(schema, indent=2)
        
    except Exception as e:
        sys.stderr.write(f"Schema query error: {e}\n")
        return json.dumps({
            "error": str(e)
        }, indent=2)

# Cleanup
import atexit

def cleanup():
    if neo4j_driver:
        neo4j_driver.close()
        sys.stderr.write("Closed Neo4j connection\n")

atexit.register(cleanup)

# Run the server
if __name__ == "__main__":
    mcp.run()