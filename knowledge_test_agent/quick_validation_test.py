#\!/usr/bin/env python3
"""Quick test of validation fix for document name normalization"""

import requests
import json

# Test cases with different document name formats
test_cases = [
    {
        "test_id": 1,
        "question": "Can I reduce my Option Premium?",
        "expected_doc": "WBC-ForeignExchangeOptionPDS.pdf",
        "search_type": "vector"
    },
    {
        "test_id": 2,
        "question": "Is there A minimum account balance in AUD to open a Foreign Currency Account?",
        "expected_doc": "SGB-FgnCurrencyAccountTC",
        "search_type": "vector"
    }
]

def normalize_document_name(doc_name):
    """Normalize document name by stripping common file extensions"""
    if not doc_name:
        return ""
    
    extensions = ['.pdf', '.PDF', '.docx', '.DOCX', '.doc', '.DOC', 
                  '.txt', '.TXT', '.html', '.HTML', '.htm', '.HTM']
    
    normalized = doc_name
    for ext in extensions:
        if normalized.endswith(ext):
            normalized = normalized[:-len(ext)]
            break
    
    return normalized.lower()

print("Testing Document Name Normalization in Validation")
print("=" * 60)

api_url = "http://localhost:8000"

for test in test_cases:
    print(f"\nTest {test['test_id']}: {test['question'][:50]}...")
    print(f"Expected doc: {test['expected_doc']}")
    
    # Search for the question
    response = requests.post(
        f"{api_url}/search",
        json={
            "query": test["question"],
            "search_type": test["search_type"],
            "limit": 5,
            "rerank": False
        }
    )
    
    if response.status_code == 200:
        results = response.json()["results"]
        
        # Normalize expected doc name
        expected_normalized = normalize_document_name(test["expected_doc"])
        print(f"Expected (normalized): {expected_normalized}")
        
        # Check results
        doc_found = False
        for result in results[:3]:  # Check top 3
            result_doc = result.get("document_id", "")
            result_normalized = normalize_document_name(result_doc)
            
            print(f"  Result doc: {result_doc} -> {result_normalized}")
            
            # Check if normalized names match
            if expected_normalized in result_normalized or result_normalized in expected_normalized:
                doc_found = True
                print(f"  ✅ MATCH FOUND\!")
                break
        
        if not doc_found:
            print(f"  ❌ No match found")
    else:
        print(f"  Error: {response.status_code}")

print("\n" + "=" * 60)
print("With normalization, .pdf extensions should no longer cause mismatches\!")
