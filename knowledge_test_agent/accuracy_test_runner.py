#!/usr/bin/env python3
"""
Corrected test runner that measures document/citation accuracy
as the primary metric, which is what we were measuring before.
"""

import os
import sys
import json
import time
import logging
import argparse
import requests
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AccuracyTestRunner:
    def __init__(self, api_url: str = "http://localhost:8000"):
        self.api_url = api_url
        self.results = []
        
    def run_test_case(self, test_id: int, question: str, expected_doc: str,
                     search_type: str = "vector", use_reranking: bool = False,
                     timeout: int = 30) -> Dict[str, Any]:
        """Run a single test case"""
        
        # Build search request
        search_request = {
            "query": question,
            "search_type": search_type,
            "top_k": 5
        }
        
        if use_reranking:
            search_request["use_reranking"] = True
        
        # Make API request
        start_time = time.time()
        
        try:
            response = requests.post(
                f"{self.api_url}/search",
                json=search_request,
                timeout=timeout
            )
            query_time = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
                
                if results:
                    # Get top result
                    top_result = results[0]
                    
                    # Extract citations from all results
                    actual_citations = []
                    for r in results:
                        doc = r.get("document", "")
                        if doc and doc not in actual_citations:
                            actual_citations.append(doc)
                    
                    # Check document match - this is our primary accuracy metric
                    document_match = False
                    if expected_doc:
                        # Clean up expected doc name for comparison
                        expected_clean = expected_doc.lower().strip()
                        if expected_clean.endswith('.pdf'):
                            expected_clean = expected_clean[:-4]
                        
                        for citation in actual_citations:
                            citation_clean = citation.lower().strip()
                            if citation_clean.endswith('.pdf'):
                                citation_clean = citation_clean[:-4]
                            
                            if expected_clean in citation_clean or citation_clean in expected_clean:
                                document_match = True
                                break
                    
                    # Also check if answer contains key information
                    answer_quality = "low"
                    if top_result.get("score", 0) > 0.8:
                        answer_quality = "high"
                    elif top_result.get("score", 0) > 0.6:
                        answer_quality = "medium"
                    
                    return {
                        "test_id": test_id,
                        "question": question[:100] + "...",
                        "expected_doc": expected_doc,
                        "actual_citations": ", ".join(actual_citations[:3]),
                        "document_match": document_match,
                        "top_score": round(top_result.get("score", 0), 3),
                        "rerank_score": round(top_result.get("rerank_score", 0), 3) if top_result.get("rerank_score") else None,
                        "answer_quality": answer_quality,
                        "query_time": round(query_time, 2),
                        "search_type": search_type,
                        "reranking_used": use_reranking,
                        "status": "success"
                    }
                else:
                    return {
                        "test_id": test_id,
                        "question": question[:100] + "...",
                        "expected_doc": expected_doc,
                        "actual_citations": "",
                        "document_match": False,
                        "top_score": 0,
                        "rerank_score": None,
                        "answer_quality": "no_results",
                        "query_time": round(query_time, 2),
                        "search_type": search_type,
                        "reranking_used": use_reranking,
                        "status": "no_results"
                    }
            else:
                return {
                    "test_id": test_id,
                    "question": question[:100] + "...",
                    "status": "api_error",
                    "error": f"API returned {response.status_code}"
                }
                
        except Exception as e:
            return {
                "test_id": test_id,
                "question": question[:100] + "...",
                "status": "error",
                "error": str(e)
            }
    
    def run_all_tests(self, test_file: str = "test.csv", search_type: str = "vector",
                     use_reranking: bool = False, timeout: int = 30):
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
            test_id = idx + 1
            question = row['Question']
            expected_doc = row.get('Document Name', '')
            
            logger.info(f"Test {test_id}/{total_tests}: {question[:50]}...")
            
            result = self.run_test_case(
                test_id, question, expected_doc,
                search_type, use_reranking, timeout
            )
            
            self.results.append(result)
            
            # Small delay between tests
            time.sleep(0.1)
        
        total_time = time.time() - start_time
        
        # Calculate statistics
        successful = sum(1 for r in self.results if r.get("status") == "success")
        doc_matches = sum(1 for r in self.results if r.get("document_match", False))
        high_quality = sum(1 for r in self.results if r.get("answer_quality") == "high")
        med_quality = sum(1 for r in self.results if r.get("answer_quality") == "medium")
        
        # This is our primary accuracy metric - document match rate
        accuracy = doc_matches / total_tests * 100 if total_tests > 0 else 0
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Test Results Summary:")
        logger.info(f"  Total tests: {total_tests}")
        logger.info(f"  Successful queries: {successful}")
        logger.info(f"  Document matches: {doc_matches}")
        logger.info(f"  **ACCURACY: {accuracy:.1f}%**")
        logger.info(f"  High quality answers: {high_quality}")
        logger.info(f"  Medium quality answers: {med_quality}")
        logger.info(f"  Total time: {total_time:.1f}s")
        logger.info(f"  Avg time per query: {total_time/total_tests:.2f}s")
        
        # Save results
        search_type_suffix = f"_{search_type}"
        if use_reranking:
            search_type_suffix += "_reranked"
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        results_file = f"../data/test_results/accuracy_test{search_type_suffix}_{timestamp}.json"
        os.makedirs(os.path.dirname(results_file), exist_ok=True)
        
        with open(results_file, 'w') as f:
            json.dump({
                "summary": {
                    "total_tests": total_tests,
                    "successful_queries": successful,
                    "document_matches": doc_matches,
                    "accuracy": accuracy,
                    "high_quality_answers": high_quality,
                    "medium_quality_answers": med_quality,
                    "total_time": total_time,
                    "avg_query_time": total_time/total_tests,
                    "search_type": search_type,
                    "use_reranking": use_reranking,
                    "timestamp": datetime.now().isoformat()
                },
                "results": self.results
            }, f, indent=2)
        
        logger.info(f"Results saved to {results_file}")
        
        # Generate summary report
        summary_file = f"../data/test_results/accuracy_summary_{timestamp}.md"
        with open(summary_file, 'w') as f:
            f.write(f"# Accuracy Test Results\n\n")
            f.write(f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Search Type**: {search_type}\n")
            f.write(f"**Reranking**: {'Enabled' if use_reranking else 'Disabled'}\n\n")
            f.write(f"## Summary\n\n")
            f.write(f"| Metric | Value |\n")
            f.write(f"|--------|-------|\n")
            f.write(f"| **Document Match Accuracy** | **{accuracy:.1f}%** |\n")
            f.write(f"| Total Tests | {total_tests} |\n")
            f.write(f"| Successful Queries | {successful} |\n")
            f.write(f"| Document Matches | {doc_matches} |\n")
            f.write(f"| High Quality Answers | {high_quality} |\n")
            f.write(f"| Medium Quality Answers | {med_quality} |\n")
            f.write(f"| Avg Query Time | {total_time/total_tests:.2f}s |\n\n")
            
            f.write(f"## Failed Document Matches\n\n")
            failed = [r for r in self.results if not r.get("document_match", False) and r.get("status") == "success"]
            if failed:
                f.write("| Question | Expected Doc | Retrieved Docs |\n")
                f.write("|----------|--------------|----------------|\n")
                for r in failed[:10]:  # Show first 10
                    f.write(f"| {r['question'][:50]}... | {r['expected_doc']} | {r['actual_citations']} |\n")
        
        logger.info(f"Summary saved to {summary_file}")
        
        return accuracy

def main():
    parser = argparse.ArgumentParser(description='Run accuracy tests for Knowledge Graph API')
    parser.add_argument('--api-url', default='http://localhost:8000', help='API URL')
    parser.add_argument('--test-file', default='test.csv', help='Test CSV file')
    parser.add_argument('--search-type', choices=['vector', 'graph', 'hybrid', 'text2cypher'], 
                       default='vector', help='Search type to test')
    parser.add_argument('--use-reranking', action='store_true', help='Enable reranking')
    parser.add_argument('--timeout', type=int, default=30, help='Request timeout in seconds')
    
    args = parser.parse_args()
    
    # Wait for API
    logger.info(f"Waiting for API at {args.api_url}...")
    for i in range(30):
        try:
            response = requests.get(f"{args.api_url}/stats", timeout=5)
            if response.status_code == 200:
                logger.info("✅ API is ready!")
                break
        except:
            pass
        time.sleep(1)
    else:
        logger.error("❌ API is not responding")
        sys.exit(1)
    
    # Run tests
    runner = AccuracyTestRunner(args.api_url)
    accuracy = runner.run_all_tests(
        args.test_file,
        args.search_type,
        args.use_reranking,
        args.timeout
    )
    
    print(f"\n🎯 FINAL ACCURACY: {accuracy:.1f}%")

if __name__ == "__main__":
    main()