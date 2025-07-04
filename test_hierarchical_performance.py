#!/usr/bin/env python3
"""
Test hierarchical search performance
Compare unfiltered vs filtered search times
"""

import time
import statistics
from typing import List, Tuple
from neo4j import GraphDatabase
from hierarchical_search import HierarchicalSearch
import json

# Test queries representing different use cases
TEST_QUERIES = [
    "interest rate",
    "savings account",
    "credit card fees",
    "foreign exchange",
    "business loan requirements",
    "term deposit minimum",
    "transaction fees",
    "overdraft facility"
]

def run_performance_test(search: HierarchicalSearch, 
                        query: str, 
                        division: str = None,
                        category: str = None,
                        runs: int = 3) -> Tuple[float, int]:
    """Run a search multiple times and return average time and result count"""
    times = []
    result_count = 0
    
    for _ in range(runs):
        start = time.time()
        results = search.search_with_hierarchy(
            query=query,
            division=division,
            category=category,
            top_k=20
        )
        elapsed = time.time() - start
        times.append(elapsed)
        result_count = results['total_results']
    
    avg_time = statistics.mean(times)
    return avg_time, result_count

def main():
    # Neo4j connection
    NEO4J_URI = "bolt://localhost:7687"
    NEO4J_USER = "neo4j"
    NEO4J_PASSWORD = "knowledge123"
    
    search = HierarchicalSearch(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    
    print("Hierarchical Search Performance Test")
    print("=" * 80)
    
    # Get statistics
    with search.driver.session() as session:
        stats = session.run("""
            MATCH (d:Document)
            WITH count(d) as total_docs,
                 count(CASE WHEN d.division = 'RETAIL' THEN 1 END) as retail_docs,
                 count(CASE WHEN d.division = 'BUSINESS' THEN 1 END) as business_docs,
                 count(CASE WHEN d.division = 'INST' THEN 1 END) as inst_docs
            MATCH (c:Chunk)
            WITH total_docs, retail_docs, business_docs, inst_docs, count(c) as total_chunks
            RETURN total_docs, retail_docs, business_docs, inst_docs, total_chunks
        """).single()
        
        print(f"\nDataset Statistics:")
        print(f"Total Documents: {stats['total_docs']}")
        print(f"Total Chunks: {stats['total_chunks']}")
        print(f"Retail Banking: {stats['retail_docs']} docs ({stats['retail_docs']/stats['total_docs']*100:.1f}%)")
        print(f"Business Banking: {stats['business_docs']} docs ({stats['business_docs']/stats['total_docs']*100:.1f}%)")
        print(f"Institutional Banking: {stats['inst_docs']} docs ({stats['inst_docs']/stats['total_docs']*100:.1f}%)")
    
    # Performance comparison table
    print("\nPerformance Comparison")
    print("-" * 80)
    print(f"{'Query':<30} {'Type':<20} {'Time (s)':<12} {'Results':<10} {'Speedup':<10}")
    print("-" * 80)
    
    overall_results = {
        'unfiltered': [],
        'division_filtered': [],
        'category_filtered': []
    }
    
    for query in TEST_QUERIES:
        # Test 1: Unfiltered search
        unfiltered_time, unfiltered_count = run_performance_test(search, query)
        overall_results['unfiltered'].append(unfiltered_time)
        
        # Test 2: Division-filtered search (Retail)
        retail_time, retail_count = run_performance_test(search, query, division="RETAIL")
        overall_results['division_filtered'].append(retail_time)
        
        # Test 3: Category-filtered search (pick appropriate category)
        category = None
        if "savings" in query or "account" in query:
            category = "Accounts"
        elif "card" in query:
            category = "Cards"
        elif "loan" in query:
            category = "Loans"
        
        if category:
            cat_time, cat_count = run_performance_test(
                search, query, division="RETAIL", category=category
            )
            overall_results['category_filtered'].append(cat_time)
            cat_speedup = unfiltered_time / cat_time if cat_time > 0 else 0
            cat_info = f"{cat_time:.3f}"
            cat_count_info = str(cat_count)
            cat_speedup_info = f"{cat_speedup:.1f}x"
        else:
            cat_info = "N/A"
            cat_count_info = "N/A"
            cat_speedup_info = "N/A"
        
        # Calculate speedups
        retail_speedup = unfiltered_time / retail_time if retail_time > 0 else 0
        
        # Print results for this query
        print(f"{query:<30} {'Unfiltered':<20} {unfiltered_time:.3f} {' '*8} {unfiltered_count:<10}")
        print(f"{' '*30} {'Retail Only':<20} {retail_time:.3f} {' '*8} {retail_count:<10} {retail_speedup:.1f}x")
        if category:
            print(f"{' '*30} {f'Retail > {category}':<20} {cat_info:<12} {cat_count_info:<10} {cat_speedup_info}")
        print()
    
    # Summary statistics
    print("\nSummary Statistics")
    print("-" * 80)
    
    avg_unfiltered = statistics.mean(overall_results['unfiltered'])
    avg_division = statistics.mean(overall_results['division_filtered'])
    avg_category = statistics.mean([t for t in overall_results['category_filtered'] if t > 0]) if overall_results['category_filtered'] else 0
    
    print(f"Average unfiltered search time: {avg_unfiltered:.3f}s")
    print(f"Average division-filtered time: {avg_division:.3f}s ({avg_unfiltered/avg_division:.1f}x speedup)")
    if avg_category > 0:
        print(f"Average category-filtered time: {avg_category:.3f}s ({avg_unfiltered/avg_category:.1f}x speedup)")
    
    # Test cascading performance
    print("\nCascading Filter Performance")
    print("-" * 80)
    
    # Simulate cascading user journey
    journey_start = time.time()
    
    # Step 1: User selects Retail Banking
    retail_results = search.get_division_documents("RETAIL")
    step1_time = time.time() - journey_start
    
    # Step 2: User selects Cards category
    cards_results = search.get_category_documents("RETAIL", "Cards")
    step2_time = time.time() - journey_start - step1_time
    
    # Step 3: User searches within Cards
    search_results = search.search_with_hierarchy(
        "annual fee", division="RETAIL", category="Cards"
    )
    step3_time = time.time() - journey_start - step1_time - step2_time
    
    total_journey = time.time() - journey_start
    
    print(f"User Journey: Browse Retail → Cards → Search 'annual fee'")
    print(f"Step 1 - Get Retail documents: {step1_time:.3f}s ({len(retail_results)} docs)")
    print(f"Step 2 - Get Cards documents: {step2_time:.3f}s ({len(cards_results)} docs)")
    print(f"Step 3 - Search in Cards: {step3_time:.3f}s ({search_results['total_results']} results)")
    print(f"Total journey time: {total_journey:.3f}s")
    
    search.close()
    
    print("\nPerformance test completed!")

if __name__ == "__main__":
    main()