#!/usr/bin/env python3
"""
Evaluate Text2CypherRetriever against the standard test questions
"""

import pandas as pd
import requests
import json
import time
import logging
from datetime import datetime
import os
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Text2CypherEvaluator:
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
    
    def extract_document_from_answer(self, answer):
        """Extract document reference from expected answer"""
        # Look for .pdf filenames in the answer
        pdf_pattern = r'([A-Za-z0-9\-_]+\.pdf)'
        matches = re.findall(pdf_pattern, answer, re.IGNORECASE)
        
        if matches:
            return matches[0]
        
        # Look for specific document indicators
        doc_patterns = {
            "foreign currency account": "SGB-FgnCurrencyAccountTC.pdf",
            "fca": "SGB-FgnCurrencyAccountTC.pdf",
            "interest rate swap": "WBC-InterestRateSwapPIS.pdf",
            "irs": "WBC-InterestRateSwapPIS.pdf",
            "foreign exchange option": "WBC-ForeignExchangeOptionPDS.pdf",
            "fxo": "WBC-ForeignExchangeOptionPDS.pdf",
            "term deposit": "WBC-TermDepositPIS.pdf",
            "dual currency": "BSA-DualCurrencyInvestmentPIS.pdf",
            "dci": "BSA-DualCurrencyInvestmentPIS.pdf"
        }
        
        answer_lower = answer.lower()
        for key, doc in doc_patterns.items():
            if key in answer_lower:
                return doc
        
        return None
    
    def query_text2cypher(self, query, timeout=30):
        """Query using Text2CypherRetriever"""
        try:
            # Try direct endpoint first
            response = requests.post(
                f"{self.api_url}/text2cypher",
                json={"query": query},
                timeout=timeout
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                # Fallback to search endpoint
                response = requests.post(
                    f"{self.api_url}/search",
                    json={
                        "query": query,
                        "search_type": "text2cypher",
                        "top_k": 5,
                        "use_reranking": False
                    },
                    timeout=timeout
                )
                
                if response.status_code == 200:
                    search_result = response.json()
                    # Convert to text2cypher format
                    return {
                        "success": True,
                        "query": query,
                        "results": [
                            {
                                "document": r.get("document_id", ""),
                                "text": r.get("text", ""),
                                "page": r.get("page_num", 0)
                            }
                            for r in search_result.get("results", [])
                        ],
                        "count": len(search_result.get("results", []))
                    }
        except Exception as e:
            logger.error(f"Error querying: {e}")
            
        return {
            "success": False,
            "query": query,
            "error": "Failed to get response",
            "results": []
        }
    
    def evaluate_result(self, result, expected_doc):
        """Evaluate if the result matches expected document"""
        if not result.get("success") or not result.get("results"):
            return False
        
        # Check if expected document appears in results
        for res in result.get("results", []):
            doc = res.get("document", "")
            if expected_doc and expected_doc.lower() in doc.lower():
                return True
            
            # Also check in text content
            text = res.get("text", "")
            if expected_doc and expected_doc.lower() in text.lower():
                return True
        
        return False
    
    def run_evaluation(self, test_file="/app/test.csv"):
        """Run evaluation against test questions"""
        # Load test questions
        logger.info(f"Loading test cases from {test_file}")
        df = pd.read_csv(test_file)
        
        logger.info(f"Running {len(df)} test cases...")
        
        for idx, row in df.iterrows():
            question = row['Question']
            expected_answer = row['Acceptable answer\n(entered by business / humans)']
            
            # Extract expected document
            expected_doc = row.get('Document Name', '') or self.extract_document_from_answer(expected_answer)
            
            logger.info(f"Test {idx+1}/{len(df)}: {question[:50]}...")
            
            start_time = time.time()
            result = self.query_text2cypher(question)
            query_time = time.time() - start_time
            
            # Evaluate
            is_correct = self.evaluate_result(result, expected_doc)
            
            # Get top document
            top_doc = ""
            if result.get("results"):
                top_doc = result["results"][0].get("document", "")
            
            # Store result
            test_result = {
                "test_id": idx + 1,
                "question": question,
                "expected_doc": expected_doc,
                "success": result.get("success", False),
                "result_count": result.get("count", 0),
                "top_document": top_doc,
                "document_match": is_correct,
                "query_time": query_time,
                "cypher_query": result.get("cypher", "")[:200] if result.get("cypher") else "",
                "query_type": result.get("query_type", ""),
                "error": result.get("error", "")
            }
            
            self.results.append(test_result)
            
            # Small delay between queries
            time.sleep(0.2)
        
        # Calculate summary
        summary = {
            "total_tests": len(self.results),
            "successful_queries": sum(1 for r in self.results if r["success"]),
            "document_matches": sum(1 for r in self.results if r["document_match"]),
            "success_rate": sum(1 for r in self.results if r["success"]) / len(self.results),
            "accuracy_rate": sum(1 for r in self.results if r["document_match"]) / len(self.results),
            "avg_query_time": sum(r["query_time"] for r in self.results) / len(self.results),
            "avg_results": sum(r["result_count"] for r in self.results) / len(self.results),
            "query_types": {},
            "errors": sum(1 for r in self.results if r["error"])
        }
        
        # Count query types
        for r in self.results:
            qt = r["query_type"]
            if qt:
                summary["query_types"][qt] = summary["query_types"].get(qt, 0) + 1
        
        return summary
    
    def save_results(self, summary):
        """Save evaluation results"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"../data/test_results/text2cypher_evaluation_{timestamp}.json"
        
        output = {
            "summary": summary,
            "results": self.results,
            "timestamp": datetime.now().isoformat(),
            "test_type": "text2cypher_evaluation"
        }
        
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, 'w') as f:
            json.dump(output, f, indent=2)
        
        logger.info(f"Results saved to {filename}")
        
        # Save detailed CSV
        csv_filename = filename.replace('.json', '.csv')
        df = pd.DataFrame(self.results)
        df.to_csv(csv_filename, index=False)
        logger.info(f"CSV saved to {csv_filename}")
        
        # Save failed cases
        failed_df = df[df['document_match'] == False]
        if len(failed_df) > 0:
            failed_csv = filename.replace('.json', '_failed.csv')
            failed_df.to_csv(failed_csv, index=False)
            logger.info(f"Failed cases saved to {failed_csv}")

def main():
    """Main evaluation"""
    evaluator = Text2CypherEvaluator()
    
    # Wait for API
    if not evaluator.wait_for_api():
        logger.error("API not available, exiting")
        return
    
    # Run evaluation
    summary = evaluator.run_evaluation()
    
    # Print results
    logger.info("\n" + "="*60)
    logger.info("Text2CypherRetriever Evaluation Results:")
    logger.info(f"  Total tests: {summary['total_tests']}")
    logger.info(f"  Successful queries: {summary['successful_queries']} ({summary['success_rate']*100:.1f}%)")
    logger.info(f"  Document matches: {summary['document_matches']} ({summary['accuracy_rate']*100:.1f}%)")
    logger.info(f"  Errors: {summary['errors']}")
    logger.info(f"  Avg query time: {summary['avg_query_time']:.2f}s")
    logger.info(f"  Avg results per query: {summary['avg_results']:.1f}")
    
    logger.info("\nQuery type distribution:")
    for qt, count in summary.get('query_types', {}).items():
        logger.info(f"  {qt}: {count}")
    
    logger.info("\nComparison to other methods:")
    logger.info("  Vector search + reranking: 73.8% accuracy")
    logger.info(f"  Text2CypherRetriever: {summary['accuracy_rate']*100:.1f}% accuracy")
    
    # Save results
    evaluator.save_results(summary)

if __name__ == "__main__":
    main()