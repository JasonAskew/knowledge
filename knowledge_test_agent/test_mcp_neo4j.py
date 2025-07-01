#!/usr/bin/env python3
"""
Test script for MCP Neo4j integration
Compares results between our custom retrievers and MCP Neo4j queries
"""

import requests
import json
import time
from datetime import datetime
import argparse
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MCPNeo4jTester:
    def __init__(self, api_url="http://localhost:8000"):
        self.api_url = api_url
        
    def test_mcp_status(self):
        """Test MCP Neo4j connection status"""
        logger.info("Testing MCP Neo4j connection...")
        
        try:
            response = requests.get(f"{self.api_url}/mcp/status")
            if response.status_code == 200:
                status = response.json()
                logger.info(f"MCP Status: {json.dumps(status, indent=2)}")
                return status.get("status") == "connected"
            else:
                logger.error(f"MCP status check failed: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Error checking MCP status: {e}")
            return False
    
    def test_direct_cypher(self, query: str, parameters=None):
        """Test direct Cypher query execution through MCP"""
        logger.info(f"Executing Cypher query: {query}")
        
        try:
            response = requests.post(
                f"{self.api_url}/mcp/cypher",
                json={"query": query, "parameters": parameters}
            )
            
            if response.status_code == 200:
                result = response.json()
                if result["success"]:
                    logger.info(f"Query successful. Found {len(result['results'])} results")
                    return result
                else:
                    logger.error(f"Query failed: {result.get('error')}")
                    return None
            else:
                logger.error(f"API error: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error executing Cypher query: {e}")
            return None
    
    def compare_search_types(self, query: str, search_types=None):
        """Compare results across different search types"""
        if search_types is None:
            search_types = ["vector", "hybrid", "text2cypher", "mcp_cypher"]
        
        logger.info(f"\nComparing search results for query: '{query}'")
        logger.info("=" * 80)
        
        results = {}
        
        for search_type in search_types:
            logger.info(f"\nTesting {search_type}...")
            start_time = time.time()
            
            try:
                response = requests.post(
                    f"{self.api_url}/search",
                    json={
                        "query": query,
                        "search_type": search_type,
                        "top_k": 5,
                        "use_reranking": True
                    },
                    timeout=30
                )
                
                if response.status_code == 200:
                    result = response.json()
                    elapsed = time.time() - start_time
                    
                    results[search_type] = {
                        "total_results": result["total_results"],
                        "elapsed_time": elapsed,
                        "top_results": result["results"][:3] if result["results"] else []
                    }
                    
                    logger.info(f"✅ {search_type}: {result['total_results']} results in {elapsed:.2f}s")
                    
                    # Show top result
                    if result["results"]:
                        top = result["results"][0]
                        logger.info(f"   Top result: {top['text'][:150]}...")
                        logger.info(f"   Document: {top.get('metadata', {}).get('filename', top.get('document_id'))}")
                        logger.info(f"   Score: {top['score']:.3f}")
                else:
                    logger.error(f"❌ {search_type}: API error {response.status_code}")
                    results[search_type] = {"error": f"API error {response.status_code}"}
                    
            except Exception as e:
                logger.error(f"❌ {search_type}: {str(e)}")
                results[search_type] = {"error": str(e)}
        
        return results
    
    def run_test_queries(self):
        """Run a set of test queries comparing different search methods"""
        test_queries = [
            "What is the minimum balance for a Foreign Currency Account?",
            "interest rate swap requirements",
            "fees for international transfers",
            "How do I open a term deposit?",
            "What are the eligibility criteria for a business loan?"
        ]
        
        all_results = {}
        
        for query in test_queries:
            results = self.compare_search_types(query)
            all_results[query] = results
            time.sleep(1)  # Brief pause between queries
        
        # Save results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = f"mcp_comparison_results_{timestamp}.json"
        
        with open(results_file, 'w') as f:
            json.dump(all_results, f, indent=2)
        
        logger.info(f"\nResults saved to {results_file}")
        
        # Print summary
        self.print_summary(all_results)
    
    def print_summary(self, all_results):
        """Print a summary of the comparison results"""
        logger.info("\n" + "=" * 80)
        logger.info("COMPARISON SUMMARY")
        logger.info("=" * 80)
        
        # Calculate average performance
        search_types = set()
        for query_results in all_results.values():
            search_types.update(query_results.keys())
        
        avg_times = {st: [] for st in search_types}
        success_counts = {st: 0 for st in search_types}
        
        for query, results in all_results.items():
            for search_type, result in results.items():
                if "error" not in result:
                    avg_times[search_type].append(result["elapsed_time"])
                    success_counts[search_type] += 1
        
        logger.info("\nAverage response times:")
        for search_type in sorted(search_types):
            if avg_times[search_type]:
                avg = sum(avg_times[search_type]) / len(avg_times[search_type])
                logger.info(f"  {search_type}: {avg:.2f}s (success rate: {success_counts[search_type]}/{len(all_results)})")
            else:
                logger.info(f"  {search_type}: No successful queries")

def main():
    parser = argparse.ArgumentParser(description="Test MCP Neo4j integration")
    parser.add_argument("--api-url", default="http://localhost:8000", help="API URL")
    parser.add_argument("--query", help="Single query to test")
    parser.add_argument("--cypher", help="Direct Cypher query to execute")
    parser.add_argument("--full-test", action="store_true", help="Run full test suite")
    
    args = parser.parse_args()
    
    tester = MCPNeo4jTester(args.api_url)
    
    # Check MCP status first
    if not tester.test_mcp_status():
        logger.error("MCP Neo4j connection failed!")
        return
    
    if args.cypher:
        # Test direct Cypher query
        result = tester.test_direct_cypher(args.cypher)
        if result and result["results"]:
            logger.info(f"\nResults:\n{json.dumps(result['results'], indent=2)}")
    elif args.query:
        # Test single query across search types
        tester.compare_search_types(args.query)
    elif args.full_test:
        # Run full test suite
        tester.run_test_queries()
    else:
        # Run a simple comparison test
        tester.compare_search_types("What is the minimum balance requirement?")

if __name__ == "__main__":
    main()