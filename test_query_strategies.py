#!/usr/bin/env python3
"""Test a single query across all search strategies"""

import requests
import json
import time

query = 'Is there A minimum account balance in AUD to open a Foreign Currency Account?'
api_url = 'http://localhost:8000'

# Test each search strategy
strategies = ['vector', 'graph', 'hybrid', 'text2cypher']
results = {}

print('Testing query:', query)
print('=' * 80)

for strategy in strategies:
    print(f'\n### Testing {strategy.upper()} search')
    print('-' * 40)
    
    start_time = time.time()
    
    # Make request
    try:
        use_rerank = strategy != 'text2cypher'
        response = requests.post(
            f'{api_url}/search',
            json={
                'query': query,
                'search_type': strategy,
                'limit': 3,
                'rerank': use_rerank
            },
            timeout=30
        )
        
        query_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            results[strategy] = data
            
            print(f'✅ Success - Query time: {query_time:.2f}s')
            print(f'Results found: {len(data.get("results", []))}')
            
            # Show top 3 results
            for i, result in enumerate(data.get('results', [])[:3], 1):
                print(f'\nResult {i}:')
                print(f'  Document: {result.get("document_id", "Unknown")}')
                print(f'  Page: {result.get("page_num", "N/A")}')
                print(f'  Score: {result.get("score", 0):.3f}')
                if result.get('rerank_score'):
                    print(f'  Rerank Score: {result.get("rerank_score", 0):.3f}')
                print(f'  Text preview: {result.get("text", "")[:150]}...')
        else:
            print(f'❌ Error: {response.status_code}')
            
    except Exception as e:
        print(f'❌ Error: {str(e)}')

print('\n' + '=' * 80)
print('SUMMARY COMPARISON')
print('=' * 80)

# Expected document for this query
expected_doc = "SGB-FgnCurrencyAccountTC"

print(f"\nExpected document: {expected_doc}")
print("\nResults by strategy:")
print(f"{'Strategy':<15} {'Found Expected Doc?':<20} {'Top Doc':<30} {'Score':<10} {'Time':<10}")
print("-" * 85)

for strategy in strategies:
    if strategy in results and results[strategy].get('results'):
        top_result = results[strategy]['results'][0]
        top_doc = top_result.get('document_id', 'Unknown')
        score = top_result.get('score', 0)
        found_expected = expected_doc.lower() in top_doc.lower()
        query_time = results[strategy].get('query_time', 0)
        
        print(f"{strategy:<15} {'✅ YES' if found_expected else '❌ NO':<20} {top_doc:<30} {score:<10.3f} {query_time:<10.2f}s")
    else:
        print(f"{strategy:<15} {'❌ NO':<20} {'No results':<30} {0:<10.3f} {0:<10.2f}s")