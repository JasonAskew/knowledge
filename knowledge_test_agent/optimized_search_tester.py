#!/usr/bin/env python3
"""
Optimized Search Performance Tester
Tests current search methods with performance benchmarks based on measured system capabilities
"""

import requests
import time
import json
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional
import logging
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OptimizedSearchTester:
    def __init__(self, api_url: str = "http://localhost:8000"):
        self.api_url = api_url
        self.results = []
        
        # Current performance benchmarks based on measured system performance
        self.performance_benchmarks = {
            "optimized_keyword": {
                "accuracy_target": 0.90,
                "speed_target_ms": 200,
                "description": "Fast keyword search with high precision"
            },
            "vector": {
                "accuracy_target": 0.78,
                "speed_target_ms": 500,
                "description": "Semantic similarity search with embeddings"
            },
            "hybrid": {
                "accuracy_target": 0.73,
                "speed_target_ms": 1000,
                "description": "Combined search with reranking"
            },
            "graph": {
                "accuracy_target": 0.82,
                "speed_target_ms": 800,
                "description": "Entity-based graph traversal"
            },
            "graphrag": {
                "accuracy_target": 0.80,
                "speed_target_ms": 1500,
                "description": "Graph reasoning with community detection"
            },
            "full_text": {
                "accuracy_target": 0.75,
                "speed_target_ms": 300,
                "description": "Traditional text search"
            }
        }
        
        # Test questions representing different query types
        self.test_questions = [
            {
                "question": "What is the minimum balance for a Foreign Currency Account?",
                "expected_docs": ["SGB-FgnCurrencyAccountTC", "foreign currency"],
                "query_type": "requirement",
                "complexity": "simple"
            },
            {
                "question": "Can I reduce my Option Premium?",
                "expected_docs": ["ForeignExchangeOption", "option premium"],
                "query_type": "capability",
                "complexity": "simple"
            },
            {
                "question": "How are coupon payments calculated for Interest Rate Swaps?",
                "expected_docs": ["InterestRateSwap", "coupon payment"],
                "query_type": "procedure",
                "complexity": "complex"
            },
            {
                "question": "What are the requirements to open a Foreign Currency Account?",
                "expected_docs": ["SGB-FgnCurrencyAccountTC", "requirements"],
                "query_type": "requirement",
                "complexity": "moderate"
            },
            {
                "question": "What is a Participating Forward Contract?",
                "expected_docs": ["ParticipatingForward", "PFC"],
                "query_type": "definition",
                "complexity": "simple"
            }
        ]
    
    def test_search_method(self, search_type: str, use_reranking: bool = True, 
                          iterations: int = 3) -> Dict[str, Any]:
        """Test a specific search method with multiple iterations for stability"""
        logger.info(f"\n🔍 Testing {search_type} search (reranking={use_reranking})")
        logger.info("-" * 60)
        
        benchmark = self.performance_benchmarks.get(search_type, {
            "accuracy_target": 0.75,
            "speed_target_ms": 1000,
            "description": "Unknown search method"
        })
        
        results = {
            "search_type": search_type,
            "use_reranking": use_reranking,
            "benchmark": benchmark,
            "test_results": [],
            "performance_summary": {},
            "meets_targets": False
        }
        
        all_response_times = []
        all_accuracies = []
        
        # Run multiple iterations for each question
        for iteration in range(iterations):
            logger.info(f"  Iteration {iteration + 1}/{iterations}")
            
            for i, test_q in enumerate(self.test_questions):
                try:
                    start_time = time.time()
                    
                    # Prepare request
                    payload = {
                        "query": test_q["question"],
                        "search_type": search_type,
                        "top_k": 5,
                        "use_reranking": use_reranking
                    }
                    
                    # Make API request
                    response = requests.post(
                        f"{self.api_url}/search",
                        json=payload,
                        timeout=10
                    )
                    
                    response_time = (time.time() - start_time) * 1000  # Convert to ms
                    all_response_times.append(response_time)
                    
                    if response.status_code == 200:
                        data = response.json()
                        search_results = data.get('results', [])
                        
                        # Check document accuracy
                        found_docs = []
                        for result in search_results[:3]:  # Top 3 results
                            doc_id = result.get('document_id', '')
                            if doc_id:
                                found_docs.append(doc_id.lower())
                        
                        # Check if expected documents are found
                        is_accurate = any(
                            any(expected.lower() in found_doc for found_doc in found_docs)
                            for expected in test_q["expected_docs"]
                        )
                        
                        all_accuracies.append(1.0 if is_accurate else 0.0)
                        
                        test_result = {
                            "iteration": iteration + 1,
                            "question_id": i + 1,
                            "question": test_q["question"],
                            "query_type": test_q["query_type"],
                            "complexity": test_q["complexity"],
                            "response_time_ms": response_time,
                            "is_accurate": is_accurate,
                            "found_docs": found_docs[:2],  # Top 2 for brevity
                            "expected_docs": test_q["expected_docs"]
                        }
                        
                        results["test_results"].append(test_result)
                        
                        status = "✅" if is_accurate else "❌"
                        logger.info(f"    Q{i+1}: {status} {response_time:.0f}ms - {test_q['question'][:50]}...")
                        
                    else:
                        logger.error(f"    Q{i+1}: API Error {response.status_code}")
                        all_accuracies.append(0.0)
                        all_response_times.append(10000)  # Penalty for errors
                        
                except Exception as e:
                    logger.error(f"    Q{i+1}: Exception - {str(e)}")
                    all_accuracies.append(0.0)
                    all_response_times.append(10000)
                
                # Small delay between requests
                time.sleep(0.1)
        
        # Calculate performance summary
        accuracy = statistics.mean(all_accuracies) if all_accuracies else 0.0
        avg_response_time = statistics.mean(all_response_times) if all_response_times else 0.0
        p95_response_time = statistics.quantiles(all_response_times, n=20)[18] if len(all_response_times) >= 20 else max(all_response_times)
        
        results["performance_summary"] = {
            "accuracy": accuracy,
            "avg_response_time_ms": avg_response_time,
            "p95_response_time_ms": p95_response_time,
            "min_response_time_ms": min(all_response_times) if all_response_times else 0,
            "max_response_time_ms": max(all_response_times) if all_response_times else 0,
            "total_tests": len(all_accuracies),
            "accurate_results": sum(all_accuracies),
            "fast_queries": len([t for t in all_response_times if t <= 500]),
            "slow_queries": len([t for t in all_response_times if t > 2000])
        }
        
        # Check if meets performance targets
        meets_accuracy = accuracy >= benchmark["accuracy_target"]
        meets_speed = avg_response_time <= benchmark["speed_target_ms"]
        results["meets_targets"] = meets_accuracy and meets_speed
        
        # Performance grade
        if accuracy >= benchmark["accuracy_target"] + 0.05 and avg_response_time <= benchmark["speed_target_ms"] * 0.8:
            grade = "A+"
        elif meets_accuracy and meets_speed:
            grade = "A"
        elif meets_accuracy or meets_speed:
            grade = "B"
        else:
            grade = "C"
        
        results["performance_grade"] = grade
        
        # Log summary
        logger.info(f"\n📊 {search_type.upper()} RESULTS:")
        logger.info(f"  🎯 Accuracy: {accuracy*100:.1f}% (Target: {benchmark['accuracy_target']*100:.1f}%) {'✅' if meets_accuracy else '❌'}")
        logger.info(f"  ⚡ Avg Speed: {avg_response_time:.0f}ms (Target: {benchmark['speed_target_ms']}ms) {'✅' if meets_speed else '❌'}")
        logger.info(f"  📈 Grade: {grade}")
        logger.info(f"  🎯 Meets Targets: {'✅ YES' if results['meets_targets'] else '❌ NO'}")
        
        return results
    
    def run_comprehensive_test(self, search_methods: Optional[List[str]] = None, 
                             iterations: int = 3) -> Dict[str, Any]:
        """Run comprehensive testing across multiple search methods"""
        if search_methods is None:
            search_methods = list(self.performance_benchmarks.keys())
        
        logger.info("=" * 80)
        logger.info("🚀 COMPREHENSIVE SEARCH PERFORMANCE TEST")
        logger.info("=" * 80)
        logger.info(f"Testing {len(search_methods)} search methods with {iterations} iterations each")
        logger.info(f"Total tests: {len(search_methods) * len(self.test_questions) * iterations}")
        
        test_start_time = time.time()
        all_results = {}
        
        for search_type in search_methods:
            if search_type in self.performance_benchmarks:
                all_results[search_type] = self.test_search_method(
                    search_type, 
                    use_reranking=True,
                    iterations=iterations
                )
            else:
                logger.warning(f"Unknown search method: {search_type}")
        
        total_test_time = time.time() - test_start_time
        
        # Generate comparison report
        comparison = self._generate_comparison_report(all_results, total_test_time)
        
        return {
            "individual_results": all_results,
            "comparison": comparison,
            "test_metadata": {
                "total_test_time": total_test_time,
                "iterations_per_method": iterations,
                "questions_tested": len(self.test_questions),
                "timestamp": datetime.now().isoformat()
            }
        }
    
    def _generate_comparison_report(self, all_results: Dict[str, Any], 
                                  total_test_time: float) -> Dict[str, Any]:
        """Generate a comparison report across all tested methods"""
        
        # Extract key metrics for comparison
        comparison_data = []
        
        for search_type, results in all_results.items():
            if "performance_summary" in results:
                perf = results["performance_summary"]
                benchmark = results["benchmark"]
                
                comparison_data.append({
                    "search_type": search_type,
                    "accuracy": perf["accuracy"],
                    "accuracy_target": benchmark["accuracy_target"],
                    "avg_response_time_ms": perf["avg_response_time_ms"],
                    "speed_target_ms": benchmark["speed_target_ms"],
                    "grade": results.get("performance_grade", "F"),
                    "meets_targets": results.get("meets_targets", False),
                    "description": benchmark["description"]
                })
        
        # Sort by overall performance (accuracy + speed)
        comparison_data.sort(
            key=lambda x: (x["meets_targets"], x["accuracy"], -x["avg_response_time_ms"]),
            reverse=True
        )
        
        # Find best performers
        best_accuracy = max(comparison_data, key=lambda x: x["accuracy"]) if comparison_data else None
        best_speed = min(comparison_data, key=lambda x: x["avg_response_time_ms"]) if comparison_data else None
        best_overall = next((x for x in comparison_data if x["meets_targets"]), comparison_data[0] if comparison_data else None)
        
        # Generate recommendations
        recommendations = []
        
        if best_overall and best_overall["meets_targets"]:
            recommendations.append(f"✅ **Recommended**: {best_overall['search_type']} - {best_overall['description']}")
        
        if best_accuracy:
            recommendations.append(f"🎯 **Most Accurate**: {best_accuracy['search_type']} - {best_accuracy['accuracy']*100:.1f}% accuracy")
        
        if best_speed:
            recommendations.append(f"⚡ **Fastest**: {best_speed['search_type']} - {best_speed['avg_response_time_ms']:.0f}ms average")
        
        # Usage recommendations based on use case
        recommendations.extend([
            "",
            "**Use Case Recommendations:**",
            "- **Real-time queries**: optimized_keyword or vector search",
            "- **High accuracy needed**: graph or graphrag search", 
            "- **Balanced performance**: hybrid search with reranking",
            "- **Complex reasoning**: graphrag search"
        ])
        
        return {
            "summary": {
                "methods_tested": len(all_results),
                "methods_meeting_targets": len([r for r in comparison_data if r["meets_targets"]]),
                "total_test_time": total_test_time,
                "avg_accuracy": statistics.mean([r["accuracy"] for r in comparison_data]) if comparison_data else 0,
                "avg_response_time": statistics.mean([r["avg_response_time_ms"] for r in comparison_data]) if comparison_data else 0
            },
            "rankings": comparison_data,
            "best_performers": {
                "overall": best_overall,
                "accuracy": best_accuracy,
                "speed": best_speed
            },
            "recommendations": recommendations
        }
    
    def save_results(self, results: Dict[str, Any], filename: Optional[str] = None) -> str:
        """Save test results to JSON file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"../data/test_results/optimized_search_test_{timestamp}.json"
        
        import os
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        logger.info(f"📄 Results saved to: {filename}")
        return filename
    
    def print_summary_report(self, results: Dict[str, Any]):
        """Print a formatted summary report"""
        logger.info("\n" + "=" * 80)
        logger.info("📊 SEARCH PERFORMANCE SUMMARY REPORT")
        logger.info("=" * 80)
        
        comparison = results["comparison"]
        summary = comparison["summary"]
        
        logger.info(f"📈 Methods Tested: {summary['methods_tested']}")
        logger.info(f"🎯 Meeting Targets: {summary['methods_meeting_targets']}/{summary['methods_tested']}")
        logger.info(f"⏱️  Total Test Time: {summary['total_test_time']:.1f}s")
        logger.info(f"📊 Average Accuracy: {summary['avg_accuracy']*100:.1f}%")
        logger.info(f"⚡ Average Response Time: {summary['avg_response_time']:.0f}ms")
        
        logger.info("\n🏆 PERFORMANCE RANKINGS:")
        for i, method in enumerate(comparison["rankings"], 1):
            status = "✅" if method["meets_targets"] else "❌"
            logger.info(f"  {i}. {method['search_type']} {status} - Grade: {method['grade']}")
            logger.info(f"     Accuracy: {method['accuracy']*100:.1f}% | Speed: {method['avg_response_time_ms']:.0f}ms")
        
        logger.info("\n💡 RECOMMENDATIONS:")
        for rec in comparison["recommendations"]:
            if rec:  # Skip empty strings
                logger.info(f"  {rec}")
        
        logger.info("=" * 80)

def main():
    """Main execution function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Optimized Search Performance Tester")
    parser.add_argument("--api-url", default="http://localhost:8000",
                        help="API URL (default: http://localhost:8000)")
    parser.add_argument("--methods", nargs="+", 
                        choices=["optimized_keyword", "vector", "hybrid", "graph", "graphrag", "full_text"],
                        help="Search methods to test (default: all)")
    parser.add_argument("--iterations", type=int, default=3,
                        help="Number of iterations per method (default: 3)")
    parser.add_argument("--output", type=str,
                        help="Output JSON file path")
    
    args = parser.parse_args()
    
    # Create tester
    tester = OptimizedSearchTester(args.api_url)
    
    # Wait for API to be ready
    logger.info("🔄 Checking API availability...")
    try:
        response = requests.get(f"{args.api_url}/stats", timeout=5)
        if response.status_code == 200:
            stats = response.json()
            logger.info(f"✅ API ready - {stats.get('documents', 0)} documents indexed")
        else:
            logger.error("❌ API not responding correctly")
            return
    except Exception as e:
        logger.error(f"❌ Cannot connect to API: {e}")
        return
    
    # Run comprehensive test
    results = tester.run_comprehensive_test(
        search_methods=args.methods,
        iterations=args.iterations
    )
    
    # Print summary
    tester.print_summary_report(results)
    
    # Save results
    output_file = tester.save_results(results, args.output)
    logger.info(f"\n✅ Testing complete! Results saved to: {output_file}")

if __name__ == "__main__":
    main()