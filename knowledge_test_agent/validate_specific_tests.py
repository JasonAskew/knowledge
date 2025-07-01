#\!/usr/bin/env python3
"""Validate specific test cases to verify the fix"""

import csv

# Read test CSV
test_file = "/Users/jaskew/workspace/Skynet/claude/knowledge/knowledge_test_agent/test.csv"

# Document names we know exist in the system
known_docs = [
    "SGB-FgnCurrencyAccountTC",
    "WBC-TLDProductInformationStatement", 
    "WIBTD 24 April 2023",
    "WBC-ForeignExchangeOptionPDS"  # This should now work with normalization
]

print("Analyzing test cases that should now be valid with normalization:")
print("=" * 70)

with open(test_file, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    
    valid_count = 0
    should_be_valid = 0
    
    for row in reader:
        test_id = row.get('#', '')
        doc_name = row.get('Document Name', '')
        
        if not test_id or not test_id.isdigit():
            continue
            
        # Normalize document name
        doc_normalized = doc_name.lower()
        if doc_normalized.endswith('.pdf'):
            doc_normalized = doc_normalized[:-4]
            
        # Check if this should be valid
        for known in known_docs:
            if known.lower() == doc_normalized:
                should_be_valid += 1
                print(f"Test {test_id}: {doc_name} -> Should be VALID (matches {known})")
                break

print(f"\nTotal tests that should be valid with normalization: {should_be_valid}")
print("\nDocuments known to exist in the system:")
for doc in known_docs:
    print(f"  - {doc}")
