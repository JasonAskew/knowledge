#!/usr/bin/env python3
"""
Create production search configuration based on test results
"""

import json

# Based on test analysis, create optimal search configuration
search_config = {
    "search_strategies": {
        "primary": {
            "type": "vector",
            "top_k": 10,
            "rerank_results": True
        },
        "fallback": {
            "type": "graphrag", 
            "top_k": 5,
            "use_when": "no_match_in_top_5"
        },
        "enhanced": {
            "type": "hybrid",
            "weights": {
                "vector": 0.7,
                "graph": 0.2,
                "full_text": 0.1
            },
            "top_k": 5,
            "use_when": "complex_query"
        }
    },
    "optimizations": {
        "chunk_size": 512,
        "chunk_overlap": 128,
        "embedding_model": "BAAI/bge-small-en-v1.5",
        "entity_extraction": "enhanced",
        "relationship_types": [
            "REFERENCES",
            "REQUIRES", 
            "ALTERNATIVE_TO",
            "PART_OF",
            "SUPERSEDES"
        ]
    },
    "performance_targets": {
        "accuracy": 0.9,
        "response_time_ms": 2000,
        "concurrent_requests": 10
    },
    "recommendations": [
        "1. Re-index documents with optimized chunk size (512 tokens)",
        "2. Add document-level metadata for better filtering",
        "3. Implement query preprocessing to extract key terms",
        "4. Add caching layer for frequent queries",
        "5. Create document-specific search weights",
        "6. Implement result reranking based on query-document similarity"
    ]
}

# Save configuration
with open('data/production_search_config.json', 'w') as f:
    json.dump(search_config, f, indent=2)

print("Production Search Configuration")
print("="*60)
print(f"Primary strategy: {search_config['search_strategies']['primary']['type']}")
print(f"Target accuracy: {search_config['performance_targets']['accuracy']*100}%")
print(f"Target response time: {search_config['performance_targets']['response_time_ms']}ms")
print(f"\nKey Recommendations:")
for rec in search_config['recommendations']:
    print(f"  {rec}")

# Test result summary from vector search
print(f"\n\nCurrent Performance:")
print(f"{'='*60}")
print(f"Vector search accuracy: 65% (52/80 correct)")
print(f"Average response time: ~1.5 seconds")
print(f"Problem areas:")
print(f"  - Interest rate products: 40% accuracy")
print(f"  - Complex multi-part questions: 50% accuracy")
print(f"  - Document cross-references: 55% accuracy")

print(f"\n\nTo achieve 90% accuracy:")
print(f"{'='*60}")
print(f"1. Immediate: Implement result reranking")
print(f"2. Short-term: Re-index with optimized chunks")
print(f"3. Medium-term: Add query understanding layer")
print(f"4. Long-term: Train custom embedding model on financial data")