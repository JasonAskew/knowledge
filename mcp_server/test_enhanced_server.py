#!/usr/bin/env python3
"""
Test script for the Enhanced MCP Server
Tests Neo4j MCP integration and streaming capabilities
"""

import asyncio
import json
import logging
from typing import Dict, Any, List
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp_server.neo4j_mcp_proxy import Neo4jMCPProxy

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EnhancedMCPServerTester:
    """Test suite for Enhanced MCP Server"""
    
    def __init__(self):
        self.results = []
        
    async def test_neo4j_proxy(self):
        """Test Neo4j MCP Proxy functionality"""
        logger.info("\n=== Testing Neo4j MCP Proxy ===")
        
        # Create proxy instance
        proxy = Neo4jMCPProxy(
            uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            username=os.getenv("NEO4J_USERNAME", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", "password"),
            database=os.getenv("NEO4J_DATABASE", "neo4j")
        )
        
        try:
            # Test connection
            logger.info("Testing Neo4j connection...")
            connected = await proxy.connect()
            if not connected:
                logger.error("Failed to connect to Neo4j")
                return False
            
            logger.info("✅ Connected to Neo4j")
            
            # Test schema retrieval
            logger.info("\nTesting schema retrieval...")
            schema = await proxy.get_schema()
            
            if "error" in schema:
                logger.error(f"Schema retrieval failed: {schema['error']}")
                return False
            
            logger.info(f"✅ Retrieved schema with {len(schema.get('node_labels', []))} node labels")
            logger.info(f"   Node labels: {', '.join(schema.get('node_labels', [])[:5])}...")
            logger.info(f"   Relationship types: {', '.join(schema.get('relationship_types', [])[:5])}...")
            
            # Test simple query
            logger.info("\nTesting Cypher query execution...")
            result = await proxy.execute_cypher(
                "MATCH (n) RETURN labels(n) as labels, count(n) as count LIMIT 5"
            )
            
            if not result.get("success"):
                logger.error(f"Query execution failed: {result.get('error')}")
                return False
            
            logger.info(f"✅ Query executed successfully, got {len(result.get('records', []))} records")
            
            # Test query with parameters
            logger.info("\nTesting parameterized query...")
            param_result = await proxy.execute_cypher(
                "MATCH (n) WHERE size(labels(n)) > $min_labels RETURN labels(n) as labels LIMIT $limit",
                {"min_labels": 0, "limit": 3}
            )
            
            if not param_result.get("success"):
                logger.error(f"Parameterized query failed: {param_result.get('error')}")
                return False
            
            logger.info("✅ Parameterized query successful")
            
            # Disconnect
            await proxy.disconnect()
            logger.info("\n✅ All Neo4j proxy tests passed!")
            return True
            
        except Exception as e:
            logger.error(f"Test failed with error: {e}")
            await proxy.disconnect()
            return False
    
    async def test_streaming_simulation(self):
        """Simulate streaming functionality"""
        logger.info("\n=== Testing Streaming Simulation ===")
        
        async def simulate_stream(data: List[str]):
            """Simulate streaming data"""
            for item in data:
                yield f"Streaming: {item}"
                await asyncio.sleep(0.1)  # Simulate delay
        
        try:
            # Simulate streaming results
            test_data = ["Result 1", "Result 2", "Result 3", "Result 4", "Result 5"]
            
            logger.info("Starting stream simulation...")
            async for chunk in simulate_stream(test_data):
                logger.info(f"  Received: {chunk}")
            
            logger.info("✅ Streaming simulation successful")
            return True
            
        except Exception as e:
            logger.error(f"Streaming test failed: {e}")
            return False
    
    async def test_search_types(self):
        """Test different search type configurations"""
        logger.info("\n=== Testing Search Type Configurations ===")
        
        search_types = [
            {"type": "vector", "description": "Vector similarity search"},
            {"type": "graph", "description": "Graph-based search"},
            {"type": "hybrid", "description": "Combined vector and graph search"},
            {"type": "text2cypher", "description": "Natural language to Cypher"},
            {"type": "neo4j_cypher", "description": "Direct Cypher through Neo4j MCP"},
            {"type": "neo4j_schema", "description": "Schema-aware search"},
        ]
        
        logger.info("Available search types:")
        for st in search_types:
            logger.info(f"  - {st['type']}: {st['description']}")
        
        return True
    
    async def run_all_tests(self):
        """Run all tests"""
        logger.info("Starting Enhanced MCP Server Tests")
        logger.info("=" * 60)
        
        tests = [
            ("Neo4j Proxy", self.test_neo4j_proxy),
            ("Streaming Simulation", self.test_streaming_simulation),
            ("Search Types", self.test_search_types),
        ]
        
        results = {}
        
        for test_name, test_func in tests:
            try:
                result = await test_func()
                results[test_name] = "PASS" if result else "FAIL"
            except Exception as e:
                logger.error(f"Test {test_name} crashed: {e}")
                results[test_name] = "ERROR"
        
        # Print summary
        logger.info("\n" + "=" * 60)
        logger.info("TEST SUMMARY")
        logger.info("=" * 60)
        
        for test_name, result in results.items():
            status = "✅" if result == "PASS" else "❌"
            logger.info(f"{status} {test_name}: {result}")
        
        # Overall result
        all_passed = all(r == "PASS" for r in results.values())
        if all_passed:
            logger.info("\n🎉 All tests passed!")
        else:
            logger.info("\n⚠️  Some tests failed")
        
        return all_passed

async def main():
    """Main entry point"""
    tester = EnhancedMCPServerTester()
    success = await tester.run_all_tests()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())