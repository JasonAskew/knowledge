#!/usr/bin/env python3
"""
Simple reranker to improve search accuracy without full re-indexing
"""

import pandas as pd
import requests
import json
import time
from sentence_transformers import CrossEncoder
import re

class SimpleReranker:
    def __init__(self):
        print("Loading cross-encoder for reranking...")
        self.cross_encoder = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
        
        # Query type patterns
        self.patterns = {
            'minimum': re.compile(r'minimum|requirement|eligible|qualify', re.I),
            'example': re.compile(r'example|show|demonstrate|how does', re.I),
            'risk': re.compile(r'risk|danger|downside', re.I),
            'process': re.compile(r'how to|how can|steps|process', re.I),
            'definition': re.compile(r'what is|what are|define', re.I)
        }
        
        # Document-specific keywords
        self.doc_keywords = {
            'foreign currency account': ['fca', 'foreign currency account', 'multi-currency'],
            'interest rate swap': ['irs', 'swap', 'fixed rate', 'floating rate'],
            'fx option': ['fxo', 'option premium', 'strike price'],
            'term deposit': ['td', 'wibtd', 'deposit', 'maturity'],
            'callable swap': ['callable', 'cs', 'terminate'],
            'dual currency': ['dci', 'dual currency investment']
        }
    
    def analyze_query_type(self, query):
        """Simple query type detection"""
        for q_type, pattern in self.patterns.items():
            if pattern.search(query):
                return q_type
        return 'general'
    
    def boost_by_keywords(self, query, text, filename):
        """Boost score based on keyword matches"""
        boost = 0.0
        query_lower = query.lower()
        text_lower = text.lower()
        
        # Check document-specific keywords
        for product, keywords in self.doc_keywords.items():
            if any(kw in query_lower for kw in keywords):
                if any(kw in text_lower for kw in keywords):
                    boost += 0.2
                if any(kw in filename.lower() for kw in keywords):
                    boost += 0.1
        
        return boost
    
    def rerank_results(self, query, results):
        """Rerank search results for better accuracy"""
        if not results:
            return results
        
        # Analyze query
        query_type = self.analyze_query_type(query)
        
        # Prepare for cross-encoder
        pairs = [[query, r['text']] for r in results]
        
        # Get cross-encoder scores
        ce_scores = self.cross_encoder.predict(pairs)
        
        # Calculate final scores
        for i, result in enumerate(results):
            # Base score from cross-encoder
            rerank_score = float(ce_scores[i])
            
            # Original score weight
            original_score = result['score']
            
            # Keyword boost
            keyword_boost = self.boost_by_keywords(
                query, 
                result['text'], 
                result['metadata']['filename']
            )
            
            # Query type boost
            type_boost = 0.0
            if query_type == 'minimum' and 'minimum' in result['text'].lower():
                type_boost = 0.15
            elif query_type == 'example' and 'example' in result['text'].lower():
                type_boost = 0.15
            
            # Calculate final score
            final_score = (
                rerank_score * 0.5 +      # Cross-encoder weight
                original_score * 0.3 +     # Original score weight  
                keyword_boost * 0.1 +      # Keyword weight
                type_boost * 0.1           # Query type weight
            )
            
            result['rerank_score'] = rerank_score
            result['final_score'] = final_score
            result['query_type'] = query_type
        
        # Sort by final score
        results.sort(key=lambda x: x['final_score'], reverse=True)
        
        return results

def test_with_reranking():
    """Test search with reranking"""
    print("Testing Search with Reranking")
    print("=" * 80)
    
    # Initialize reranker
    reranker = SimpleReranker()
    
    # Load test questions
    df = pd.read_csv('knowledge_test_agent/test.csv')
    
    results = []
    doc_matches = 0
    doc_matches_reranked = 0
    
    print(f"Running {len(df)} tests with reranking...")
    
    for idx, row in df.iterrows():
        question = row['Question']
        expected_doc = row['Document Name']
        
        print(f"\rProcessing test {idx+1}/{len(df)}...", end='', flush=True)
        
        try:
            # Get vector search results
            response = requests.post(
                'http://localhost:8000/search',
                json={
                    'query': question,
                    'search_type': 'vector',
                    'top_k': 10  # Get more candidates
                },
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if data['results']:
                    # Check original match
                    original_match = any(
                        expected_doc in r.get('metadata', {}).get('filename', '')
                        for r in data['results'][:5]
                    )
                    
                    # Rerank results
                    reranked = reranker.rerank_results(question, data['results'])
                    
                    # Check reranked match
                    reranked_match = any(
                        expected_doc in r.get('metadata', {}).get('filename', '')
                        for r in reranked[:5]
                    )
                    
                    if original_match:
                        doc_matches += 1
                    if reranked_match:
                        doc_matches_reranked += 1
                    
                    results.append({
                        'question': question,
                        'expected_doc': expected_doc,
                        'original_match': original_match,
                        'reranked_match': reranked_match,
                        'improved': reranked_match and not original_match,
                        'query_type': reranked[0].get('query_type', 'general')
                    })
                    
        except Exception as e:
            print(f"\nError on test {idx+1}: {e}")
    
    print(f"\n\nResults Summary:")
    print(f"{'='*60}")
    print(f"Total tests: {len(df)}")
    print(f"Original accuracy: {doc_matches}/{len(df)} = {doc_matches/len(df)*100:.1f}%")
    print(f"Reranked accuracy: {doc_matches_reranked}/{len(df)} = {doc_matches_reranked/len(df)*100:.1f}%")
    print(f"Improvement: {(doc_matches_reranked - doc_matches)} tests (+{(doc_matches_reranked/len(df) - doc_matches/len(df))*100:.1f} percentage points)")
    
    # Analyze improvements
    improvements = [r for r in results if r['improved']]
    if improvements:
        print(f"\nImproved {len(improvements)} test cases:")
        for imp in improvements[:5]:
            print(f"  - {imp['question'][:60]}... (type: {imp['query_type']})")
    
    # Save detailed results
    results_file = f"data/test_results/reranking_results_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(results_file, 'w') as f:
        json.dump({
            'summary': {
                'total_tests': len(df),
                'original_matches': doc_matches,
                'reranked_matches': doc_matches_reranked,
                'improvements': len(improvements),
                'original_accuracy': doc_matches/len(df),
                'reranked_accuracy': doc_matches_reranked/len(df)
            },
            'results': results
        }, f, indent=2)
    
    print(f"\nDetailed results saved to {results_file}")

if __name__ == "__main__":
    test_with_reranking()