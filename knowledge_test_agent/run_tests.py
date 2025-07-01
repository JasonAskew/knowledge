#!/usr/bin/env python3
"""
Run tests against the knowledge graph API
"""

import pandas as pd
import requests
import json
import time
from datetime import datetime
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class KnowledgeTestRunner:
    def __init__(self, api_url: str = "http://knowledge-api:8000"):
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
    
    def run_test_case(self, row, search_type="vector", use_reranking=False, timeout=30):
        """Run a single test case"""
        question = row['Question']
        expected_answer = row['Acceptable answer\n(entered by business / humans)']
        document_ref = row['Document Name']
        
        # Build search request
        search_request = {
            "query": question,
            "search_type": search_type,
            "top_k": 5
        }
        
        # Add reranking if specified
        if use_reranking:
            search_request["use_reranking"] = True
        
        try:
            response = requests.post(
                f"{self.api_url}/search",
                json=search_request,
                timeout=timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Extract top result
                if result["results"]:
                    top_result = result["results"][0]
                    
                    # Check if correct document was found
                    doc_match = any(
                        document_ref in r.get("metadata", {}).get("filename", "")
                        for r in result["results"]
                    )
                    
                    return {
                        "question": question,
                        "expected_answer": expected_answer,
                        "retrieved_text": top_result["text"][:500],
                        "score": top_result["score"],
                        "rerank_score": top_result.get("rerank_score", None),
                        "final_score": top_result.get("final_score", top_result["score"]),
                        "document_match": doc_match,
                        "document_ref": document_ref,
                        "search_type": search_type,
                        "use_reranking": use_reranking,
                        "status": "success"
                    }
                else:
                    return {
                        "question": question,
                        "expected_answer": expected_answer,
                        "retrieved_text": "No results found",
                        "score": 0.0,
                        "document_match": False,
                        "document_ref": document_ref,
                        "search_type": search_type,
                        "use_reranking": use_reranking,
                        "status": "no_results"
                    }
            else:
                return {
                    "question": question,
                    "status": "api_error",
                    "error": f"API returned {response.status_code}"
                }
                
        except requests.exceptions.Timeout:
            return {
                "question": question,
                "status": "timeout",
                "error": f"Request timed out after {timeout}s"
            }
        except Exception as e:
            return {
                "question": question,
                "status": "error",
                "error": str(e)
            }
    
    def run_all_tests(self, test_file: str = "test.csv", search_type="vector", use_reranking=False, timeout=30):
        """Run all tests from CSV file"""
        logger.info(f"Loading test cases from {test_file}")
        
        # Load test cases
        df = pd.read_csv(test_file)
        total_tests = len(df)
        
        logger.info(f"Running {total_tests} test cases...")
        logger.info(f"  Search type: {search_type}")
        logger.info(f"  Reranking: {'Enabled' if use_reranking else 'Disabled'}")
        logger.info(f"  Timeout: {timeout}s")
        
        start_time = time.time()
        
        # Run each test
        for idx, row in df.iterrows():
            logger.info(f"Test {idx + 1}/{total_tests}: {row['Question'][:50]}...")
            result = self.run_test_case(row, search_type=search_type, use_reranking=use_reranking, timeout=timeout)
            result["test_id"] = idx + 1
            self.results.append(result)
            
            # Brief pause between tests to avoid overwhelming the API
            time.sleep(0.5)
        
        total_time = time.time() - start_time
        
        # Calculate statistics
        successful = sum(1 for r in self.results if r.get("status") == "success")
        doc_matches = sum(1 for r in self.results if r.get("document_match", False))
        timeouts = sum(1 for r in self.results if r.get("status") == "timeout")
        errors = sum(1 for r in self.results if r.get("status") in ["error", "api_error"])
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Test Results Summary:")
        logger.info(f"  Total tests: {total_tests}")
        logger.info(f"  Successful queries: {successful}")
        logger.info(f"  Document matches: {doc_matches}")
        logger.info(f"  Timeouts: {timeouts}")
        logger.info(f"  Errors: {errors}")
        logger.info(f"  Success rate: {successful/total_tests*100:.1f}%")
        logger.info(f"  Document match rate: {doc_matches/total_tests*100:.1f}%")
        logger.info(f"  Total time: {total_time:.1f}s")
        logger.info(f"  Avg time per query: {total_time/total_tests:.2f}s")
        
        # Save results
        search_type_suffix = f"_{search_type}"
        if use_reranking:
            search_type_suffix += "_reranked"
        
        results_file = f"../data/test_results/test_results{search_type_suffix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        os.makedirs(os.path.dirname(results_file), exist_ok=True)
        
        with open(results_file, 'w') as f:
            json.dump({
                "summary": {
                    "total_tests": total_tests,
                    "successful_queries": successful,
                    "document_matches": doc_matches,
                    "success_rate": successful/total_tests,
                    "document_match_rate": doc_matches/total_tests,
                    "timeouts": timeouts,
                    "errors": errors,
                    "total_time": total_time,
                    "avg_query_time": total_time/total_tests,
                    "search_type": search_type,
                    "use_reranking": use_reranking,
                    "timestamp": datetime.now().isoformat()
                },
                "results": self.results
            }, f, indent=2)
        
        logger.info(f"Results saved to {results_file}")
        
        return self.results

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Run knowledge graph tests")
    parser.add_argument("--api-url", default=os.getenv("API_URL", "http://localhost:8000"), 
                        help="API URL (default: http://localhost:8000)")
    parser.add_argument("--search-type", default="vector", 
                        choices=["vector", "hybrid", "graph", "full_text", "graphrag", "text2cypher", "mcp_cypher", "neo4j_mcp"],
                        help="Search type to test (default: vector)")
    parser.add_argument("--use-reranking", action="store_true",
                        help="Enable reranking for supported search types")
    parser.add_argument("--timeout", type=int, default=30,
                        help="Request timeout in seconds (default: 30)")
    parser.add_argument("--test-file", default="test.csv",
                        help="Test CSV file (default: test.csv)")
    
    args = parser.parse_args()
    
    # Create test runner
    runner = KnowledgeTestRunner(args.api_url)
    
    # Wait for API to be ready
    if not runner.wait_for_api():
        logger.error("API not available, exiting")
        return
    
    # Run tests
    runner.run_all_tests(
        test_file=args.test_file,
        search_type=args.search_type,
        use_reranking=args.use_reranking,
        timeout=args.timeout
    )

if __name__ == "__main__":
    main()