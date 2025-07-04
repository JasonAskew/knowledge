#!/usr/bin/env python3
"""
Performance Benchmarker - Analyzes speed vs accuracy trade-offs
Tracks performance trends and provides optimization recommendations
"""

import requests
import time
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
import logging
import statistics
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PerformanceBenchmarker:
    def __init__(self, api_url: str = "http://localhost:8000"):
        self.api_url = api_url
        self.benchmark_data = []
        
        # Performance thresholds based on current system requirements
        self.thresholds = {
            "excellent": {"accuracy": 0.90, "response_time": 200},  # ms
            "good": {"accuracy": 0.80, "response_time": 500},
            "acceptable": {"accuracy": 0.70, "response_time": 1000},
            "poor": {"accuracy": 0.60, "response_time": 2000}
        }
        
        # Test scenarios for different performance profiles
        self.test_scenarios = {
            "speed_optimized": {
                "search_types": ["optimized_keyword", "full_text"],
                "reranking": False,
                "description": "Fastest response, moderate accuracy"
            },
            "balanced": {
                "search_types": ["vector", "hybrid"],
                "reranking": True,
                "description": "Balanced speed and accuracy"
            },
            "accuracy_optimized": {
                "search_types": ["graph", "graphrag"],
                "reranking": True,
                "description": "Highest accuracy, slower response"
            }
        }
        
        # Sample queries categorized by complexity
        self.query_complexity_sets = {
            "simple": [
                "What is an FX Forward?",
                "What is the minimum deposit?",
                "Can I cancel a contract?",
                "What are the fees?",
                "Who can apply?"
            ],
            "moderate": [
                "What are the requirements for opening a Foreign Currency Account?",
                "How are interest rates calculated for Term Deposits?",
                "What documentation is needed for large transactions?",
                "What are the risks of currency hedging?",
                "How do I calculate option premiums?"
            ],
            "complex": [
                "Compare the benefits and risks of Participating Forward Contracts versus Range Forward Contracts",
                "What factors determine the premium calculation for FX Options and how can they be optimized?",
                "Explain the relationship between interest rate movements and swap valuations",
                "What are the regulatory requirements for cross-border financial products?",
                "How do market volatility and economic indicators affect derivative pricing?"
            ]
        }
    
    def measure_performance_profile(self, search_type: str, use_reranking: bool = True,
                                  iterations: int = 5) -> Dict[str, Any]:
        """Measure detailed performance profile for a search method"""
        logger.info(f"📊 Measuring performance profile: {search_type} (reranking={use_reranking})")
        
        profile_data = {
            "search_type": search_type,
            "use_reranking": use_reranking,
            "complexity_results": {},
            "overall_metrics": {}
        }
        
        all_response_times = []
        all_accuracies = []
        
        # Test across different query complexities
        for complexity, queries in self.query_complexity_sets.items():
            logger.info(f"  Testing {complexity} queries...")
            
            complexity_times = []
            complexity_accuracies = []
            
            for iteration in range(iterations):
                for query in queries:
                    try:
                        start_time = time.time()
                        
                        response = requests.post(
                            f"{self.api_url}/search",
                            json={
                                "query": query,
                                "search_type": search_type,
                                "top_k": 5,
                                "use_reranking": use_reranking
                            },
                            timeout=15
                        )
                        
                        response_time = (time.time() - start_time) * 1000  # ms
                        complexity_times.append(response_time)
                        all_response_times.append(response_time)
                        
                        # Simple accuracy check (has results)
                        if response.status_code == 200:
                            data = response.json()
                            has_results = len(data.get('results', [])) > 0
                            accuracy = 1.0 if has_results else 0.0
                        else:
                            accuracy = 0.0
                        
                        complexity_accuracies.append(accuracy)
                        all_accuracies.append(accuracy)
                        
                    except Exception as e:
                        logger.warning(f"Query failed: {e}")
                        complexity_times.append(5000)  # Penalty
                        complexity_accuracies.append(0.0)
                        all_response_times.append(5000)
                        all_accuracies.append(0.0)
            
            # Calculate complexity-specific metrics
            profile_data["complexity_results"][complexity] = {
                "avg_response_time": statistics.mean(complexity_times),
                "p95_response_time": statistics.quantiles(complexity_times, n=20)[18] if len(complexity_times) >= 20 else max(complexity_times),
                "accuracy": statistics.mean(complexity_accuracies),
                "queries_tested": len(queries) * iterations
            }
        
        # Calculate overall metrics
        profile_data["overall_metrics"] = {
            "avg_response_time": statistics.mean(all_response_times),
            "p50_response_time": statistics.median(all_response_times),
            "p95_response_time": statistics.quantiles(all_response_times, n=20)[18] if len(all_response_times) >= 20 else max(all_response_times),
            "p99_response_time": statistics.quantiles(all_response_times, n=100)[98] if len(all_response_times) >= 100 else max(all_response_times),
            "min_response_time": min(all_response_times),
            "max_response_time": max(all_response_times),
            "accuracy": statistics.mean(all_accuracies),
            "total_queries": len(all_response_times),
            "fast_queries_pct": len([t for t in all_response_times if t <= 500]) / len(all_response_times) * 100,
            "slow_queries_pct": len([t for t in all_response_times if t > 2000]) / len(all_response_times) * 100
        }
        
        # Determine performance tier
        metrics = profile_data["overall_metrics"]
        tier = self._classify_performance_tier(metrics["accuracy"], metrics["avg_response_time"])
        profile_data["performance_tier"] = tier
        
        return profile_data
    
    def run_speed_accuracy_analysis(self, search_methods: Optional[List[str]] = None) -> Dict[str, Any]:
        """Run comprehensive speed vs accuracy analysis"""
        if search_methods is None:
            search_methods = ["optimized_keyword", "vector", "hybrid", "graph", "graphrag"]
        
        logger.info("🚀 Starting Speed vs Accuracy Analysis")
        logger.info("=" * 60)
        
        analysis_results = {
            "timestamp": datetime.now().isoformat(),
            "search_methods": {},
            "scenario_analysis": {},
            "optimization_recommendations": {},
            "comparative_analysis": {}
        }
        
        # Test individual search methods
        for search_type in search_methods:
            logger.info(f"\n🔍 Analyzing {search_type}...")
            
            # Test with and without reranking
            with_reranking = self.measure_performance_profile(search_type, use_reranking=True)
            without_reranking = self.measure_performance_profile(search_type, use_reranking=False)
            
            analysis_results["search_methods"][search_type] = {
                "with_reranking": with_reranking,
                "without_reranking": without_reranking,
                "reranking_impact": self._calculate_reranking_impact(with_reranking, without_reranking)
            }
        
        # Test predefined scenarios
        for scenario_name, scenario_config in self.test_scenarios.items():
            logger.info(f"\n📋 Testing {scenario_name} scenario...")
            scenario_results = self._test_scenario(scenario_config)
            analysis_results["scenario_analysis"][scenario_name] = scenario_results
        
        # Generate comparative analysis
        analysis_results["comparative_analysis"] = self._generate_comparative_analysis(
            analysis_results["search_methods"]
        )
        
        # Generate optimization recommendations
        analysis_results["optimization_recommendations"] = self._generate_optimization_recommendations(
            analysis_results
        )
        
        return analysis_results
    
    def _classify_performance_tier(self, accuracy: float, response_time: float) -> str:
        """Classify performance into tiers"""
        if accuracy >= self.thresholds["excellent"]["accuracy"] and response_time <= self.thresholds["excellent"]["response_time"]:
            return "excellent"
        elif accuracy >= self.thresholds["good"]["accuracy"] and response_time <= self.thresholds["good"]["response_time"]:
            return "good"
        elif accuracy >= self.thresholds["acceptable"]["accuracy"] and response_time <= self.thresholds["acceptable"]["response_time"]:
            return "acceptable"
        else:
            return "poor"
    
    def _calculate_reranking_impact(self, with_reranking: Dict, without_reranking: Dict) -> Dict[str, Any]:
        """Calculate the impact of reranking on performance"""
        with_metrics = with_reranking["overall_metrics"]
        without_metrics = without_reranking["overall_metrics"]
        
        return {
            "accuracy_improvement": with_metrics["accuracy"] - without_metrics["accuracy"],
            "speed_impact_ms": with_metrics["avg_response_time"] - without_metrics["avg_response_time"],
            "speed_impact_pct": ((with_metrics["avg_response_time"] - without_metrics["avg_response_time"]) / without_metrics["avg_response_time"]) * 100,
            "worth_it": (with_metrics["accuracy"] - without_metrics["accuracy"]) > 0.05,  # 5% accuracy improvement threshold
            "recommendation": "enable" if (with_metrics["accuracy"] - without_metrics["accuracy"]) > 0.05 else "disable"
        }
    
    def _test_scenario(self, scenario_config: Dict[str, Any]) -> Dict[str, Any]:
        """Test a specific performance scenario"""
        scenario_results = []
        
        for search_type in scenario_config["search_types"]:
            profile = self.measure_performance_profile(
                search_type, 
                use_reranking=scenario_config["reranking"],
                iterations=2  # Fewer iterations for scenario testing
            )
            scenario_results.append(profile)
        
        # Calculate scenario average
        if scenario_results:
            avg_accuracy = statistics.mean([r["overall_metrics"]["accuracy"] for r in scenario_results])
            avg_response_time = statistics.mean([r["overall_metrics"]["avg_response_time"] for r in scenario_results])
            
            return {
                "description": scenario_config["description"],
                "search_types_tested": scenario_config["search_types"],
                "reranking_enabled": scenario_config["reranking"],
                "avg_accuracy": avg_accuracy,
                "avg_response_time": avg_response_time,
                "performance_tier": self._classify_performance_tier(avg_accuracy, avg_response_time),
                "individual_results": scenario_results
            }
        
        return {"error": "No results obtained"}
    
    def _generate_comparative_analysis(self, search_methods_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comparative analysis across search methods"""
        
        # Extract key metrics for comparison
        comparison_data = []
        
        for search_type, data in search_methods_data.items():
            with_reranking = data["with_reranking"]["overall_metrics"]
            without_reranking = data["without_reranking"]["overall_metrics"]
            
            comparison_data.append({
                "search_type": search_type,
                "best_accuracy": max(with_reranking["accuracy"], without_reranking["accuracy"]),
                "best_speed": min(with_reranking["avg_response_time"], without_reranking["avg_response_time"]),
                "balanced_accuracy": with_reranking["accuracy"],
                "balanced_speed": with_reranking["avg_response_time"],
                "reranking_worth_it": data["reranking_impact"]["worth_it"]
            })
        
        # Find optimal choices
        best_accuracy = max(comparison_data, key=lambda x: x["best_accuracy"])
        best_speed = min(comparison_data, key=lambda x: x["best_speed"])
        
        # Calculate efficiency score (accuracy / response_time)
        for item in comparison_data:
            item["efficiency_score"] = item["balanced_accuracy"] / (item["balanced_speed"] / 1000)  # accuracy per second
        
        best_efficiency = max(comparison_data, key=lambda x: x["efficiency_score"])
        
        return {
            "best_accuracy": best_accuracy,
            "best_speed": best_speed,
            "best_efficiency": best_efficiency,
            "all_methods": sorted(comparison_data, key=lambda x: x["efficiency_score"], reverse=True)
        }
    
    def _generate_optimization_recommendations(self, analysis_results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate optimization recommendations based on analysis"""
        
        comparative = analysis_results["comparative_analysis"]
        scenarios = analysis_results["scenario_analysis"]
        
        recommendations = {
            "use_case_recommendations": {},
            "general_optimizations": [],
            "configuration_suggestions": {}
        }
        
        # Use case specific recommendations
        recommendations["use_case_recommendations"] = {
            "real_time_applications": {
                "recommended_method": comparative["best_speed"]["search_type"],
                "avg_response_time": comparative["best_speed"]["best_speed"],
                "expected_accuracy": comparative["best_speed"]["best_accuracy"],
                "configuration": "Disable reranking for maximum speed"
            },
            "high_accuracy_applications": {
                "recommended_method": comparative["best_accuracy"]["search_type"],
                "avg_response_time": comparative["best_accuracy"]["balanced_speed"],
                "expected_accuracy": comparative["best_accuracy"]["best_accuracy"],
                "configuration": "Enable reranking for maximum accuracy"
            },
            "balanced_applications": {
                "recommended_method": comparative["best_efficiency"]["search_type"],
                "avg_response_time": comparative["best_efficiency"]["balanced_speed"],
                "expected_accuracy": comparative["best_efficiency"]["balanced_accuracy"],
                "configuration": "Use reranking based on accuracy requirements"
            }
        }
        
        # General optimization suggestions
        reranking_beneficial = len([m for m in comparative["all_methods"] if m["reranking_worth_it"]]) > len(comparative["all_methods"]) / 2
        
        if reranking_beneficial:
            recommendations["general_optimizations"].append("Enable reranking for most search methods - significant accuracy gains observed")
        else:
            recommendations["general_optimizations"].append("Consider disabling reranking for speed-critical applications - minimal accuracy impact")
        
        # Check for clear performance leaders
        top_performer = comparative["all_methods"][0]
        if top_performer["efficiency_score"] > comparative["all_methods"][1]["efficiency_score"] * 1.2:
            recommendations["general_optimizations"].append(f"Consider {top_performer['search_type']} as default - significantly better efficiency")
        
        # Configuration suggestions
        recommendations["configuration_suggestions"] = {
            "default_search_method": top_performer["search_type"],
            "enable_reranking_by_default": reranking_beneficial,
            "timeout_recommendations": {
                "fast_queries": f"{int(comparative['best_speed']['best_speed'] * 1.5)}ms",
                "normal_queries": f"{int(top_performer['balanced_speed'] * 1.5)}ms",
                "complex_queries": f"{int(max(m['balanced_speed'] for m in comparative['all_methods']) * 1.5)}ms"
            }
        }
        
        return recommendations
    
    def save_analysis_results(self, results: Dict[str, Any], 
                             filename: Optional[str] = None) -> str:
        """Save analysis results to JSON file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"../data/test_results/performance_analysis_{timestamp}.json"
        
        Path(filename).parent.mkdir(parents=True, exist_ok=True)
        
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        logger.info(f"📄 Analysis results saved to: {filename}")
        return filename
    
    def generate_performance_report(self, results: Dict[str, Any]) -> str:
        """Generate a formatted performance report"""
        
        report = f"""# Performance Benchmarking Report

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Executive Summary

This report analyzes the speed vs accuracy trade-offs across different search methods in the GraphRAG system.

### Key Findings

**🏆 Best Overall Performance**: {results['comparative_analysis']['best_efficiency']['search_type']}
- Efficiency Score: {results['comparative_analysis']['best_efficiency']['efficiency_score']:.2f}
- Accuracy: {results['comparative_analysis']['best_efficiency']['balanced_accuracy']*100:.1f}%
- Response Time: {results['comparative_analysis']['best_efficiency']['balanced_speed']:.0f}ms

**⚡ Fastest Method**: {results['comparative_analysis']['best_speed']['search_type']}
- Response Time: {results['comparative_analysis']['best_speed']['best_speed']:.0f}ms
- Accuracy: {results['comparative_analysis']['best_speed']['best_accuracy']*100:.1f}%

**🎯 Most Accurate Method**: {results['comparative_analysis']['best_accuracy']['search_type']}
- Accuracy: {results['comparative_analysis']['best_accuracy']['best_accuracy']*100:.1f}%
- Response Time: {results['comparative_analysis']['best_accuracy']['balanced_speed']:.0f}ms

## Performance Rankings

| Rank | Search Method | Efficiency Score | Accuracy | Avg Response Time | Reranking Worth It |
|------|---------------|------------------|----------|-------------------|-------------------|
"""
        
        for i, method in enumerate(results['comparative_analysis']['all_methods'], 1):
            report += f"| {i} | {method['search_type']} | {method['efficiency_score']:.2f} | {method['balanced_accuracy']*100:.1f}% | {method['balanced_speed']:.0f}ms | {'✅' if method['reranking_worth_it'] else '❌'} |\n"
        
        report += f"""
## Use Case Recommendations

### Real-Time Applications (Speed Priority)
- **Method**: {results['optimization_recommendations']['use_case_recommendations']['real_time_applications']['recommended_method']}
- **Expected Performance**: {results['optimization_recommendations']['use_case_recommendations']['real_time_applications']['expected_accuracy']*100:.1f}% accuracy in {results['optimization_recommendations']['use_case_recommendations']['real_time_applications']['avg_response_time']:.0f}ms
- **Configuration**: {results['optimization_recommendations']['use_case_recommendations']['real_time_applications']['configuration']}

### High-Accuracy Applications (Accuracy Priority)
- **Method**: {results['optimization_recommendations']['use_case_recommendations']['high_accuracy_applications']['recommended_method']}
- **Expected Performance**: {results['optimization_recommendations']['use_case_recommendations']['high_accuracy_applications']['expected_accuracy']*100:.1f}% accuracy in {results['optimization_recommendations']['use_case_recommendations']['high_accuracy_applications']['avg_response_time']:.0f}ms
- **Configuration**: {results['optimization_recommendations']['use_case_recommendations']['high_accuracy_applications']['configuration']}

### Balanced Applications (General Use)
- **Method**: {results['optimization_recommendations']['use_case_recommendations']['balanced_applications']['recommended_method']}
- **Expected Performance**: {results['optimization_recommendations']['use_case_recommendations']['balanced_applications']['expected_accuracy']*100:.1f}% accuracy in {results['optimization_recommendations']['use_case_recommendations']['balanced_applications']['avg_response_time']:.0f}ms
- **Configuration**: {results['optimization_recommendations']['use_case_recommendations']['balanced_applications']['configuration']}

## Configuration Recommendations

### Default Settings
- **Default Search Method**: {results['optimization_recommendations']['configuration_suggestions']['default_search_method']}
- **Enable Reranking**: {'Yes' if results['optimization_recommendations']['configuration_suggestions']['enable_reranking_by_default'] else 'No'}

### Timeout Configuration
- **Fast Queries**: {results['optimization_recommendations']['configuration_suggestions']['timeout_recommendations']['fast_queries']}
- **Normal Queries**: {results['optimization_recommendations']['configuration_suggestions']['timeout_recommendations']['normal_queries']}
- **Complex Queries**: {results['optimization_recommendations']['configuration_suggestions']['timeout_recommendations']['complex_queries']}

## Optimization Insights
"""
        
        for optimization in results['optimization_recommendations']['general_optimizations']:
            report += f"- {optimization}\n"
        
        report += f"""
## Testing Methodology

- **Search Methods Tested**: {len(results['search_methods'])}
- **Queries per Method**: {len(results['search_methods'][list(results['search_methods'].keys())[0]]['with_reranking']['complexity_results']) * 5} (across complexity levels)
- **Performance Tiers**: Excellent (≥90% accuracy, ≤200ms), Good (≥80% accuracy, ≤500ms), Acceptable (≥70% accuracy, ≤1000ms)

*This analysis provides data-driven recommendations for optimizing search performance based on specific use case requirements.*
"""
        
        return report
    
    def print_summary(self, results: Dict[str, Any]):
        """Print a concise summary of benchmark results"""
        logger.info("\n" + "=" * 80)
        logger.info("📊 PERFORMANCE BENCHMARKING SUMMARY")
        logger.info("=" * 80)
        
        best_efficiency = results['comparative_analysis']['best_efficiency']
        best_speed = results['comparative_analysis']['best_speed']
        best_accuracy = results['comparative_analysis']['best_accuracy']
        
        logger.info(f"🏆 **BEST OVERALL**: {best_efficiency['search_type']}")
        logger.info(f"   Efficiency: {best_efficiency['efficiency_score']:.2f} | Accuracy: {best_efficiency['balanced_accuracy']*100:.1f}% | Speed: {best_efficiency['balanced_speed']:.0f}ms")
        
        logger.info(f"\n⚡ **FASTEST**: {best_speed['search_type']} - {best_speed['best_speed']:.0f}ms")
        logger.info(f"🎯 **MOST ACCURATE**: {best_accuracy['search_type']} - {best_accuracy['best_accuracy']*100:.1f}%")
        
        logger.info(f"\n💡 **RECOMMENDATIONS**:")
        for rec in results['optimization_recommendations']['general_optimizations']:
            logger.info(f"   • {rec}")
        
        logger.info(f"\n⚙️  **DEFAULT CONFIG**: {results['optimization_recommendations']['configuration_suggestions']['default_search_method']} search with reranking {'enabled' if results['optimization_recommendations']['configuration_suggestions']['enable_reranking_by_default'] else 'disabled'}")
        logger.info("=" * 80)

def main():
    """Main execution function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Performance Benchmarker - Speed vs Accuracy Analysis")
    parser.add_argument("--api-url", default="http://localhost:8000",
                        help="API URL (default: http://localhost:8000)")
    parser.add_argument("--methods", nargs="+",
                        choices=["optimized_keyword", "vector", "hybrid", "graph", "graphrag", "full_text"],
                        help="Search methods to analyze (default: all)")
    parser.add_argument("--output", type=str,
                        help="Output file path for results")
    parser.add_argument("--report", type=str,
                        help="Output file path for markdown report")
    
    args = parser.parse_args()
    
    # Create benchmarker
    benchmarker = PerformanceBenchmarker(args.api_url)
    
    # Check API availability
    try:
        response = requests.get(f"{args.api_url}/stats", timeout=5)
        if response.status_code == 200:
            logger.info("✅ API is ready for benchmarking")
        else:
            logger.error("❌ API not responding correctly")
            return
    except Exception as e:
        logger.error(f"❌ Cannot connect to API: {e}")
        return
    
    # Run analysis
    results = benchmarker.run_speed_accuracy_analysis(args.methods)
    
    # Print summary
    benchmarker.print_summary(results)
    
    # Save results
    if args.output:
        benchmarker.save_analysis_results(results, args.output)
    else:
        default_file = benchmarker.save_analysis_results(results)
        logger.info(f"Results saved to: {default_file}")
    
    # Generate and save report
    if args.report:
        report = benchmarker.generate_performance_report(results)
        with open(args.report, 'w') as f:
            f.write(report)
        logger.info(f"📄 Performance report saved to: {args.report}")

if __name__ == "__main__":
    main()