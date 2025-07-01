#!/usr/bin/env python3
"""
Neo4j MCP Proxy - Simple proxy for Neo4j operations without requiring neo4j-mcp package

This module provides a lightweight implementation for executing Neo4j queries
through the MCP protocol without needing the full neo4j-mcp installation.
"""

import json
import logging
import asyncio
from typing import Any, Dict, List, Optional
from neo4j import GraphDatabase, AsyncGraphDatabase
from neo4j.exceptions import Neo4jError

logger = logging.getLogger(__name__)

class Neo4jMCPProxy:
    """Lightweight Neo4j MCP proxy implementation"""
    
    def __init__(self, uri: str, username: str, password: str, database: str = "neo4j"):
        self.uri = uri
        self.username = username
        self.password = password
        self.database = database
        self.driver = None
        self.async_driver = None
    
    async def connect(self) -> bool:
        """Connect to Neo4j database"""
        try:
            # Try async driver first
            try:
                self.async_driver = AsyncGraphDatabase.driver(
                    self.uri, 
                    auth=(self.username, self.password)
                )
                await self.async_driver.verify_connectivity()
                logger.info("Connected to Neo4j using async driver")
                return True
            except:
                # Fallback to sync driver
                self.driver = GraphDatabase.driver(
                    self.uri,
                    auth=(self.username, self.password)
                )
                self.driver.verify_connectivity()
                logger.info("Connected to Neo4j using sync driver")
                return True
                
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from Neo4j database"""
        if self.async_driver:
            await self.async_driver.close()
        elif self.driver:
            self.driver.close()
    
    async def execute_cypher(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a Cypher query"""
        try:
            if self.async_driver:
                # Use async execution
                async with self.async_driver.session(database=self.database) as session:
                    result = await session.run(query, parameters or {})
                    records = []
                    async for record in result:
                        records.append(dict(record))
                    
                    return {
                        "success": True,
                        "records": records,
                        "summary": {
                            "counters": dict(await result.consume())
                        }
                    }
            
            elif self.driver:
                # Use sync execution in thread pool
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    None, 
                    self._execute_sync, 
                    query, 
                    parameters
                )
            
            else:
                return {
                    "success": False,
                    "error": "Not connected to Neo4j"
                }
                
        except Neo4jError as e:
            logger.error(f"Neo4j error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _execute_sync(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute query synchronously (for sync driver)"""
        with self.driver.session(database=self.database) as session:
            result = session.run(query, parameters or {})
            records = [dict(record) for record in result]
            summary = result.consume()
            
            return {
                "success": True,
                "records": records,
                "summary": {
                    "counters": dict(summary.counters)
                }
            }
    
    async def get_schema(self) -> Dict[str, Any]:
        """Get database schema information"""
        try:
            # Get node labels
            labels_query = "CALL db.labels() YIELD label RETURN label ORDER BY label"
            labels_result = await self.execute_cypher(labels_query)
            
            if not labels_result["success"]:
                return {"error": labels_result["error"]}
            
            node_labels = [record["label"] for record in labels_result["records"]]
            
            # Get relationship types
            rels_query = "CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType ORDER BY relationshipType"
            rels_result = await self.execute_cypher(rels_query)
            
            if not rels_result["success"]:
                return {"error": rels_result["error"]}
            
            relationship_types = [record["relationshipType"] for record in rels_result["records"]]
            
            # Get property keys
            props_query = "CALL db.propertyKeys() YIELD propertyKey RETURN propertyKey ORDER BY propertyKey"
            props_result = await self.execute_cypher(props_query)
            
            if not props_result["success"]:
                return {"error": props_result["error"]}
            
            property_keys = [record["propertyKey"] for record in props_result["records"]]
            
            # Get constraints
            constraints_query = "SHOW CONSTRAINTS"
            constraints_result = await self.execute_cypher(constraints_query)
            
            constraints = []
            if constraints_result["success"]:
                constraints = constraints_result["records"]
            
            # Get indexes
            indexes_query = "SHOW INDEXES"
            indexes_result = await self.execute_cypher(indexes_query)
            
            indexes = []
            if indexes_result["success"]:
                indexes = indexes_result["records"]
            
            return {
                "node_labels": node_labels,
                "relationship_types": relationship_types,
                "property_keys": property_keys,
                "constraints": constraints,
                "indexes": indexes
            }
            
        except Exception as e:
            logger.error(f"Error getting schema: {e}")
            return {"error": str(e)}
    
    async def get_sample_data(self, limit: int = 5) -> Dict[str, Any]:
        """Get sample data from the database"""
        try:
            samples = {}
            
            # Get sample nodes for each label
            labels_result = await self.execute_cypher("CALL db.labels() YIELD label RETURN label")
            if labels_result["success"]:
                for record in labels_result["records"][:5]:  # Limit to 5 labels
                    label = record["label"]
                    sample_query = f"MATCH (n:{label}) RETURN n LIMIT {limit}"
                    sample_result = await self.execute_cypher(sample_query)
                    
                    if sample_result["success"]:
                        samples[label] = [dict(r["n"]) for r in sample_result["records"]]
            
            return {
                "success": True,
                "samples": samples
            }
            
        except Exception as e:
            logger.error(f"Error getting sample data: {e}")
            return {"error": str(e)}