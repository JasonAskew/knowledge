#!/usr/bin/env python3
"""
Final success rate measurement with corrected document matching
"""

import requests
import json
import time
from datetime import datetime

API_URL = "http://localhost:8000"

# Test questions with corrected expected document names
TEST_QUESTIONS = [
    {
        "question": "What are the fees for international wire transfers?",
        "expected_docs": ["international-service-fees", "international service fees"]
    },
    {
        "question": "What is the minimum balance for a savings account?", 
        "expected_docs": ["personalaccounts", "personal accounts", "tandc"]
    },
    {
        "question": "How do I report a lost credit card?",
        "expected_docs": ["credit-card", "creditcard", "terms-and-conditions", "credit card"]
    },
    {
        "question": "What are the overdraft fees?",
        "expected_docs": ["overdraft", "fees", "charges"]
    },
    {
        "question": "How do I transfer money internationally?",
        "expected_docs": ["international", "transfer", "telegraphic"]
    }
]

def normalize_doc_name(doc_name):
    """Normalize document name for comparison"""
    return doc_name.lower().replace('.pdf', '').replace(' ', '').replace('-', '').replace('_', '')

def check_document_match(found_docs, expected_patterns):
    """Check if any expected pattern matches found documents"""
    normalized_found = [normalize_doc_name(doc) for doc in found_docs if doc]
    
    for pattern in expected_patterns:
        normalized_pattern = normalize_doc_name(pattern)
        for found in normalized_found:
            if normalized_pattern in found or found in normalized_pattern:
                return True, found, pattern
    return False, None, None

def test_search_method(search_type, use_reranking=False):
    """Test a specific search method"""
    print(f"\n🔍 Testing: {search_type} (reranking={use_reranking})")
    print("-" * 50)
    
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
                response = requests.post(f"{API_URL}/text2cypher", json=payload, timeout=15)
            else:
                response = requests.post(f"{API_URL}/search", json=payload, timeout=15)
            
            elapsed = time.time() - start
            total_time += elapsed
            
            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])
                
                # Extract document names from top 3 results
                found_docs = []
                for r in results[:3]:
                    doc_name = r.get('metadata', {}).get('filename', '') or r.get('document', '')
                    if doc_name:
                        found_docs.append(doc_name)
                
                # Check for matches
                is_correct, matched_doc, matched_pattern = check_document_match(found_docs, q['expected_docs'])
                
                if is_correct:
                    correct += 1
                    print(f"  ✅ Q{i+1}: Found '{matched_doc}' (matched pattern: {matched_pattern})")
                else:
                    print(f"  ❌ Q{i+1}: No match found")
                    print(f"     Found: {found_docs[:2]}")
                    print(f"     Expected patterns: {q['expected_docs']}")
                
                details.append({
                    'question': q['question'][:60] + "...",
                    'correct': is_correct,
                    'found': found_docs[:2],
                    'expected': q['expected_docs'],
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
        'avg_time': avg_time,
        'details': details
    }
    
    print(f"  📊 Result: {accuracy:.1f}% ({correct}/{len(TEST_QUESTIONS)}) - Avg: {avg_time:.2f}s")
    return result

def main():
    print("🎯 FINAL SUCCESS RATE MEASUREMENT")
    print("=" * 50)
    print(f"Testing with {len(TEST_QUESTIONS)} questions")
    
    # Check API availability
    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
        print("✅ API is available")
    except:
        print("❌ API not available - cannot run tests")
        return
    
    # Test different methods
    methods_to_test = [
        ("vector", False),
        ("vector", True), 
        ("hybrid", False),
        ("hybrid", True),
        ("text2cypher", False),
        ("graph", False),
        ("full_text", False)
    ]
    
    results = []
    for search_type, use_reranking in methods_to_test:
        try:
            result = test_search_method(search_type, use_reranking)
            results.append(result)
        except Exception as e:
            print(f"⚠️  Skipped {search_type}: {e}")
    
    # Print summary
    if results:
        print("\n" + "=" * 80)
        print("📈 SUCCESS RATE COMPARISON")
        print("=" * 80)
        
        # Sort by accuracy
        results.sort(key=lambda x: x['accuracy'], reverse=True)
        
        print(f"{'Method':<20} {'Accuracy':<12} {'Avg Time':<12}")
        print("-" * 50)
        
        for r in results:
            method_name = r['method'].replace('_', ' ').title()
            print(f"{method_name:<20} {r['accuracy']:>6.1f}% ({r['correct']}/{r['total']}) {r['avg_time']:>8.2f}s")
        
        # Save detailed results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"final_success_rates_{timestamp}.json"
        with open(filename, 'w') as f:
            json.dump({
                'timestamp': timestamp,
                'test_questions': len(TEST_QUESTIONS),
                'results': results
            }, f, indent=2)
        
        print(f"\n💾 Detailed results saved to: {filename}")
        
        # Show top performer details
        if results:
            top_result = results[0]
            print(f"\n🏆 Best Method: {top_result['method']} ({top_result['accuracy']:.1f}%)")
    else:
        print("❌ No results to display")

if __name__ == "__main__":
    main()