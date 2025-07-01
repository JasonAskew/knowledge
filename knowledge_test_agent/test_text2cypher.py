#!/usr/bin/env python3
"""
Test script for Text2CypherRetriever functionality
"""

import requests
import json
import time
import logging
from datetime import datetime
import pandas as pd
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Text2CypherTester:
    def __init__(self, api_url="http://localhost:8000"):
        self.api_url = api_url
        self.results = []
        
    def wait_for_api(self, max_attempts=30, delay=2):
        """Wait for API to be ready"""
        logger.info(f"Waiting for API at {self.api_url}...")
        
        for attempt in range(max_attempts):
            try:
                response = requests.get(f"{self.api_url}/stats")
                if response.status_code == 200:
                    stats = response.json()
                    if stats.get("documents", 0) > 0:
                        logger.info("✅ API is ready!")
                        return True
            except:
                pass
            
            if attempt < max_attempts - 1:
                logger.info(f"Attempt {attempt + 1}/{max_attempts}: API not ready yet. Waiting {delay}s...")
                time.sleep(delay)
        
        logger.error("❌ API failed to become ready")
        return False
    
    def test_direct_endpoint(self, query):
        """Test the /text2cypher endpoint directly"""
        try:
            response = requests.post(
                f"{self.api_url}/text2cypher",
                json={"query": query},
                timeout=30
            )
            return response.json()
        except Exception as e:
            logger.error(f"Error testing direct endpoint: {e}")
            return {"success": False, "error": str(e)}
    
    def test_search_endpoint(self, query):
        """Test text2cypher through the main search endpoint"""
        try:
            response = requests.post(
                f"{self.api_url}/search",
                json={
                    "query": query,
                    "search_type": "text2cypher",
                    "top_k": 5,
                    "use_reranking": False
                },
                timeout=30
            )
            return response.json()
        except Exception as e:
            logger.error(f"Error testing search endpoint: {e}")
            return {"error": str(e)}
    
    def run_test_suite(self):
        """Run comprehensive test suite for Text2CypherRetriever"""
        
        # Define test cases with expected outcomes
        test_cases = [
            {
                "query": "how many documents are there",
                "expected_type": "aggregation",
                "validate": lambda r: "total_documents" in str(r)
            },
            {
                "query": "find all documents about foreign currency account",
                "expected_type": "simple",
                "validate": lambda r: any("foreign" in str(item).lower() for item in r.get("results", []))
            },
            {
                "query": "what is the minimum amount for FCA",
                "expected_type": "simple",
                "validate": lambda r: "minimum" in str(r).lower() and "50" in str(r)
            },
            {
                "query": "show documents related to interest rate swaps",
                "expected_type": "path",
                "validate": lambda r: len(r.get("results", [])) > 0
            },
            {
                "query": "what entities are in WBC-ForeignExchangeOptionPDS.pdf",
                "expected_type": "aggregation",
                "validate": lambda r: "entity" in str(r) or "entities" in str(r)
            },
            {
                "query": "find documents with option premium",
                "expected_type": "simple",
                "validate": lambda r: "option" in str(r).lower() or "premium" in str(r).lower()
            },
            {
                "query": "show structure of SGB-FgnCurrencyAccountTC.pdf",
                "expected_type": "aggregation",
                "validate": lambda r: "chunk" in str(r) or "page" in str(r)
            },
            {
                "query": "what is the minimum balance for term deposit",
                "expected_type": "simple",
                "validate": lambda r: "minimum" in str(r).lower()
            },
            {
                "query": "find documents about fx options",
                "expected_type": "simple",
                "validate": lambda r: "option" in str(r).lower() or "fxo" in str(r).lower()
            },
            {
                "query": "show all documents with swap in the title",
                "expected_type": "simple",
                "validate": lambda r: "swap" in str(r).lower()
            }
        ]
        
        # Get example queries from API
        try:
            examples_response = requests.get(f"{self.api_url}/text2cypher/examples")
            if examples_response.status_code == 200:
                api_examples = examples_response.json().get("examples", [])
                logger.info(f"API provides {len(api_examples)} example queries")
        except:
            api_examples = []
        
        # Run tests
        logger.info(f"Running {len(test_cases)} test cases...")
        
        for i, test in enumerate(test_cases, 1):
            query = test["query"]
            logger.info(f"Test {i}/{len(test_cases)}: {query[:50]}...")
            
            start_time = time.time()
            
            # Test direct endpoint
            direct_result = self.test_direct_endpoint(query)
            direct_time = time.time() - start_time
            
            # Test search endpoint
            search_start = time.time()
            search_result = self.test_search_endpoint(query)
            search_time = time.time() - search_start
            
            # Validate results
            direct_valid = test["validate"](direct_result) if direct_result.get("success") else False
            search_valid = len(search_result.get("results", [])) > 0 if "error" not in search_result else False
            
            # Store results
            result = {
                "test_id": i,
                "query": query,
                "expected_type": test["expected_type"],
                
                # Direct endpoint results
                "direct_success": direct_result.get("success", False),
                "direct_valid": direct_valid,
                "direct_time": direct_time,
                "direct_result_count": direct_result.get("count", 0),
                "direct_query_type": direct_result.get("query_type", ""),
                "direct_cypher": direct_result.get("cypher", "")[:200] if direct_result.get("cypher") else "",
                
                # Search endpoint results
                "search_success": "error" not in search_result,
                "search_valid": search_valid,
                "search_time": search_time,
                "search_result_count": len(search_result.get("results", [])),
                
                # Sample results
                "sample_result": str(direct_result.get("results", [])[:1])[:200] if direct_result.get("results") else ""
            }
            
            self.results.append(result)
            
            # Brief pause between tests
            time.sleep(0.5)
        
        # Calculate summary statistics
        summary = {
            "total_tests": len(self.results),
            "direct_endpoint": {
                "success_count": sum(1 for r in self.results if r["direct_success"]),
                "valid_count": sum(1 for r in self.results if r["direct_valid"]),
                "avg_time": sum(r["direct_time"] for r in self.results) / len(self.results),
                "avg_results": sum(r["direct_result_count"] for r in self.results) / len(self.results)
            },
            "search_endpoint": {
                "success_count": sum(1 for r in self.results if r["search_success"]),
                "valid_count": sum(1 for r in self.results if r["search_valid"]),
                "avg_time": sum(r["search_time"] for r in self.results) / len(self.results),
                "avg_results": sum(r["search_result_count"] for r in self.results) / len(self.results)
            },
            "query_types": {}
        }
        
        # Count query types
        for r in self.results:
            qt = r["direct_query_type"]
            if qt:
                summary["query_types"][qt] = summary["query_types"].get(qt, 0) + 1
        
        return summary
    
    def save_results(self, summary):
        """Save test results"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"../data/test_results/text2cypher_test_results_{timestamp}.json"
        
        output = {
            "summary": summary,
            "results": self.results,
            "timestamp": datetime.now().isoformat()
        }
        
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, 'w') as f:
            json.dump(output, f, indent=2)
        
        logger.info(f"Results saved to {filename}")
        
        # Also save as CSV for easy viewing
        csv_filename = filename.replace('.json', '.csv')
        df = pd.DataFrame(self.results)
        df.to_csv(csv_filename, index=False)
        logger.info(f"CSV saved to {csv_filename}")

def main():
    """Main test execution"""
    tester = Text2CypherTester()
    
    # Wait for API
    if not tester.wait_for_api():
        logger.error("API not available, exiting")
        return
    
    # Run tests
    summary = tester.run_test_suite()
    
    # Print summary
    logger.info("\n" + "="*60)
    logger.info("Text2CypherRetriever Test Results Summary:")
    logger.info(f"  Total tests: {summary['total_tests']}")
    
    logger.info("\nDirect /text2cypher endpoint:")
    logger.info(f"  Success rate: {summary['direct_endpoint']['success_count']}/{summary['total_tests']} ({summary['direct_endpoint']['success_count']/summary['total_tests']*100:.1f}%)")
    logger.info(f"  Valid results: {summary['direct_endpoint']['valid_count']}/{summary['total_tests']} ({summary['direct_endpoint']['valid_count']/summary['total_tests']*100:.1f}%)")
    logger.info(f"  Avg response time: {summary['direct_endpoint']['avg_time']:.2f}s")
    logger.info(f"  Avg results per query: {summary['direct_endpoint']['avg_results']:.1f}")
    
    logger.info("\nSearch endpoint with text2cypher:")
    logger.info(f"  Success rate: {summary['search_endpoint']['success_count']}/{summary['total_tests']} ({summary['search_endpoint']['success_count']/summary['total_tests']*100:.1f}%)")
    logger.info(f"  Valid results: {summary['search_endpoint']['valid_count']}/{summary['total_tests']} ({summary['search_endpoint']['valid_count']/summary['total_tests']*100:.1f}%)")
    logger.info(f"  Avg response time: {summary['search_endpoint']['avg_time']:.2f}s")
    logger.info(f"  Avg results per query: {summary['search_endpoint']['avg_results']:.1f}")
    
    logger.info("\nQuery type distribution:")
    for qt, count in summary['query_types'].items():
        logger.info(f"  {qt}: {count}")
    
    # Save results
    tester.save_results(summary)

if __name__ == "__main__":
    main()