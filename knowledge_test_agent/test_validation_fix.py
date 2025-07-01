import os
import re

def normalize_document_name(doc_name):
    """Normalize document name by stripping common file extensions"""
    if not doc_name:
        return ""
    
    # Common file extensions to strip
    extensions = ['.pdf', '.PDF', '.docx', '.DOCX', '.doc', '.DOC', 
                  '.txt', '.TXT', '.html', '.HTML', '.htm', '.HTM']
    
    normalized = doc_name
    for ext in extensions:
        if normalized.endswith(ext):
            normalized = normalized[:-len(ext)]
            break
    
    return normalized.lower()

# Test cases
test_docs = [
    ("WBC-ForeignExchangeOptionPDS.pdf", "WBC-ForeignExchangeOptionPDS"),
    ("SGB-FgnCurrencyAccountTC", "SGB-FgnCurrencyAccountTC"),
    ("wbc-interest-rate-cap-floors-collars_pis.pdf", "wbc-interest-rate-cap-floors-collars_pis"),
    ("WBC 11am Deposit 24 April 2023.pdf", "WBC 11am Deposit 24 April 2023"),
]

print("Testing document name normalization:")
print("-" * 60)
for expected, search_result in test_docs:
    norm_expected = normalize_document_name(expected)
    norm_result = normalize_document_name(search_result)
    
    # Check if normalized names match
    match = (norm_expected in norm_result or norm_result in norm_expected)
    
    print(f"\nOriginal: '{expected}' vs '{search_result}'")
    print(f"Normalized: '{norm_expected}' vs '{norm_result}'")
    print(f"Match: {match}")
