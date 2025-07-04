#!/usr/bin/env python3
"""
Simple success rate measurement using direct API calls on a small test set
"""

import requests
import json
import time
from datetime import datetime

API_URL = "http://localhost:8000"

# Sample test questions with known expected documents
TEST_QUESTIONS = [
    {
        "question": "What are the fees for international wire transfers?",
        "expected_doc": "international-service-fees"
    },
    {
        "question": "What is the minimum balance for a savings account?", 
        "expected_doc": "personalaccounts-tandc"
    },
    {
        "question": "How do I report a lost credit card?",
        "expected_doc": "westpac-credit-card-terms-and-conditions"
    }
]

def normalize_doc_name(doc_name):
    """Normalize document name for comparison"""
    return doc_name.lower().replace('.pdf', '').replace(' ', '').replace('-', '').replace('_', '')

def test_search_method(search_type, use_reranking=False):
    """Test a specific search method"""
    print(f"\nTesting: {search_type} (reranking={use_reranking})")
    print("-" * 40)
    
    correct = 0
    total_time = 0
    details = []
    
    for i, q in enumerate(TEST_QUESTIONS):
        try:
            start = time.time()
            
            payload = {
                "query": q["question"],
                "search_type": search_type,
                "limit": 5,
                "rerank": use_reranking
            }
            
            if search_type == "text2cypher":
                response = requests.post(f"{API_URL}/text2cypher", json=payload, timeout=10)
            else:
                response = requests.post(f"{API_URL}/search", json=payload, timeout=10)
            
            elapsed = time.time() - start
            total_time += elapsed
            
            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])
                
                # Check if expected document pattern is found
                found_docs = []
                for r in results[:3]:
                    doc_name = r.get('metadata', {}).get('filename', '') or r.get('document', '')
                    if doc_name:
                        found_docs.append(normalize_doc_name(doc_name))
                
                expected_pattern = normalize_doc_name(q['expected_doc'])
                is_correct = any(expected_pattern in doc or doc in expected_pattern for doc in found_docs)
                
                if is_correct:
                    correct += 1
                    print(f"  ✅ Q{i+1}: Found relevant document")
                else:
                    print(f"  ❌ Q{i+1}: No match found")
                
                details.append({
                    'question': q['question'][:50] + "...",
                    'correct': is_correct,
                    'found': found_docs[:2],
                    'expected': expected_pattern,
                    'time': elapsed
                })
            else:
                print(f"  ❌ Q{i+1}: API Error {response.status_code}")
                
        except Exception as e:
            print(f"  ❌ Q{i+1}: Exception - {str(e)}")
    
    accuracy = (correct / len(TEST_QUESTIONS)) * 100
    avg_time = total_time / len(TEST_QUESTIONS)
    
    result = {
        'method': f"{search_type}{'_rerank' if use_reranking else ''}",
        'accuracy': accuracy,
        'correct': correct,
        'total': len(TEST_QUESTIONS),
        'avg_time': avg_time
    }
    
    print(f"  📊 Result: {accuracy:.1f}% ({correct}/{len(TEST_QUESTIONS)}) - Avg: {avg_time:.2f}s")
    return result

def main():
    print("🎯 MEASURING SUCCESS RATES")
    print("=" * 50)
    print(f"Testing with {len(TEST_QUESTIONS)} sample questions")
    
    # Check if API is available
    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
        print("✅ API is available")
    except:
        print("❌ API not available - cannot run tests")
        return
    
    # Test different methods (reduced set for speed)
    results = []
    
    try:
        results.append(test_search_method("vector", False))
        results.append(test_search_method("hybrid", True))
        results.append(test_search_method("text2cypher", False))
    except Exception as e:
        print(f"Error running tests: {e}")
    
    # Print summary
    if results:
        print("\n" + "=" * 60)
        print("📈 SUCCESS RATE SUMMARY")
        print("=" * 60)
        
        # Sort by accuracy
        results.sort(key=lambda x: x['accuracy'], reverse=True)
        
        print(f"{'Method':<20} {'Accuracy':<12} {'Avg Time':<12}")
        print("-" * 50)
        
        for r in results:
            method_name = r['method'].replace('_', ' ').title()
            print(f"{method_name:<20} {r['accuracy']:>6.1f}% ({r['correct']}/{r['total']}) {r['avg_time']:>8.2f}s")
        
        # Save results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"success_rates_{timestamp}.json"
        with open(filename, 'w') as f:
            json.dump({
                'timestamp': timestamp,
                'test_questions': len(TEST_QUESTIONS),
                'results': results
            }, f, indent=2)
        
        print(f"\n💾 Results saved to: {filename}")
    else:
        print("❌ No results to display")

if __name__ == "__main__":
    main()