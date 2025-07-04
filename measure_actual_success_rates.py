#!/usr/bin/env python3
"""
Get actual success rates for each search approach using a subset of test questions
"""

import csv
import json
import time
import requests
from datetime import datetime
from neo4j import GraphDatabase

# Configuration
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "knowledge123"
API_URL = "http://localhost:8000"

class SuccessRateMeasurer:
    def __init__(self):
        self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        self.test_questions = []
        
    def load_test_questions(self, limit=30):
        """Load a subset of test questions"""
        print(f"Loading {limit} test questions...")
        
        with open('knowledge_test_agent/test.csv', 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Parse the CSV manually due to complex formatting
        lines = content.strip().split('\n')
        header = lines[0]
        
        for i, line in enumerate(lines[1:limit+1]):
            # Split by comma but handle quoted fields
            parts = []
            current = ""
            in_quotes = False
            
            for char in line:
                if char == '"':
                    in_quotes = not in_quotes
                elif char == ',' and not in_quotes:
                    parts.append(current.strip('"').strip())
                    current = ""
                    continue
                current += char
            parts.append(current.strip('"').strip())
            
            if len(parts) >= 8:
                self.test_questions.append({
                    'id': i + 1,
                    'question': parts[7],  # Question column
                    'expected_document': parts[3],  # Document Name column
                    'acceptable_answer': parts[8] if len(parts) > 8 else ""
                })
        
        print(f"Loaded {len(self.test_questions)} questions")
        return self.test_questions
    
    def normalize_doc_name(self, doc_name):
        """Normalize document name for comparison"""
        return doc_name.lower().replace('.pdf', '').strip()
    
    def test_api_method(self, search_type, use_reranking=False):
        """Test using API endpoints"""
        print(f"\n🔍 Testing API: {search_type} (reranking={use_reranking})")
        print("-" * 50)
        
        correct = 0
        total_time = 0
        errors = 0
        results = []
        
        for q in self.test_questions:
            try:
                start = time.time()
                
                payload = {
                    "query": q['question'],
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
                    search_results = data.get('results', [])
                    
                    # Check if expected document is found
                    found_docs = []
                    for r in search_results[:3]:
                        doc_name = r.get('metadata', {}).get('filename', '') or r.get('document', '')
                        found_docs.append(self.normalize_doc_name(doc_name))
                    
                    expected = self.normalize_doc_name(q['expected_document'])
                    is_correct = any(expected in doc or doc in expected for doc in found_docs if doc)
                    
                    if is_correct:
                        correct += 1
                    
                    results.append({
                        'question_id': q['id'],
                        'correct': is_correct,
                        'found_docs': found_docs,
                        'expected': expected,
                        'time': elapsed
                    })
                    
                else:
                    errors += 1
                    print(f"  ❌ API Error {response.status_code} on Q{q['id']}")
                    
            except Exception as e:
                errors += 1
                print(f"  ❌ Exception on Q{q['id']}: {str(e)}")
        
        accuracy = (correct / len(self.test_questions)) * 100
        avg_time = total_time / len(self.test_questions)
        
        print(f"  ✅ Accuracy: {accuracy:.1f}% ({correct}/{len(self.test_questions)})")
        print(f"  ⏱️  Avg time: {avg_time:.2f}s")
        print(f"  ❌ Errors: {errors}")
        
        return {
            'method': f"{search_type}{'_rerank' if use_reranking else ''}",
            'accuracy': accuracy,
            'correct': correct,
            'total': len(self.test_questions),
            'avg_time': avg_time,
            'errors': errors,
            'details': results
        }
    
    def test_cypher_keyword_simple(self):
        """Test simple OR keyword search (simulating optimized MCP)"""
        print(f"\n🔍 Testing Direct Cypher: Simple Keyword (OR)")
        print("-" * 50)
        
        correct = 0
        total_time = 0
        results = []
        
        with self.driver.session() as session:
            for q in self.test_questions:
                try:
                    start = time.time()
                    
                    # Extract keywords (similar to optimized MCP)
                    words = [w.lower() for w in q['question'].split() 
                            if len(w) > 2 and w.lower() not in ['the', 'for', 'and', 'are', 'what', 'how', 'can', 'do']]
                    
                    if words:
                        or_conditions = " OR ".join([f"toLower(c.text) CONTAINS '{word}'" for word in words])
                        
                        result = session.run(f"""
                            MATCH (c:Chunk)<-[:HAS_CHUNK]-(d:Document)
                            WHERE {or_conditions}
                            RETURN DISTINCT d.filename as document
                            LIMIT 5
                        """)
                        
                        found_docs = [self.normalize_doc_name(r['document']) for r in result]
                        expected = self.normalize_doc_name(q['expected_document'])
                        is_correct = any(expected in doc or doc in expected for doc in found_docs if doc)
                        
                        if is_correct:
                            correct += 1
                        
                        elapsed = time.time() - start
                        total_time += elapsed
                        
                        results.append({
                            'question_id': q['id'],
                            'correct': is_correct,
                            'found_docs': found_docs,
                            'expected': expected,
                            'time': elapsed
                        })
                    
                except Exception as e:
                    print(f"  ❌ Error on Q{q['id']}: {str(e)}")
        
        accuracy = (correct / len(self.test_questions)) * 100
        avg_time = total_time / len(self.test_questions)
        
        print(f"  ✅ Accuracy: {accuracy:.1f}% ({correct}/{len(self.test_questions)})")
        print(f"  ⏱️  Avg time: {avg_time:.2f}s")
        
        return {
            'method': 'cypher_keyword_or',
            'accuracy': accuracy,
            'correct': correct,
            'total': len(self.test_questions),
            'avg_time': avg_time,
            'errors': 0,
            'details': results
        }
    
    def test_cypher_pattern_and(self):
        """Test pattern search with AND logic"""
        print(f"\n🔍 Testing Direct Cypher: Pattern (AND)")
        print("-" * 50)
        
        correct = 0
        total_time = 0
        results = []
        
        with self.driver.session() as session:
            for q in self.test_questions:
                try:
                    start = time.time()
                    
                    # Extract key words for AND matching
                    words = [w.lower() for w in q['question'].split() 
                            if len(w) > 3 and w.lower() not in ['what', 'how', 'when', 'where', 'which', 'the', 'for', 'and', 'are']]
                    
                    if len(words) >= 2:
                        # Use top 3 words for AND matching
                        key_words = words[:3]
                        and_conditions = " AND ".join([f"toLower(c.text) CONTAINS '{word}'" for word in key_words])
                        
                        result = session.run(f"""
                            MATCH (c:Chunk)<-[:HAS_CHUNK]-(d:Document)
                            WHERE {and_conditions}
                            RETURN DISTINCT d.filename as document
                            LIMIT 5
                        """)
                        
                        found_docs = [self.normalize_doc_name(r['document']) for r in result]
                        expected = self.normalize_doc_name(q['expected_document'])
                        is_correct = any(expected in doc or doc in expected for doc in found_docs if doc)
                        
                        if is_correct:
                            correct += 1
                        
                        elapsed = time.time() - start
                        total_time += elapsed
                        
                        results.append({
                            'question_id': q['id'],
                            'correct': is_correct,
                            'found_docs': found_docs,
                            'expected': expected,
                            'time': elapsed,
                            'keywords_used': key_words
                        })
                    
                except Exception as e:
                    print(f"  ❌ Error on Q{q['id']}: {str(e)}")
        
        accuracy = (correct / len(self.test_questions)) * 100
        avg_time = total_time / len(self.test_questions)
        
        print(f"  ✅ Accuracy: {accuracy:.1f}% ({correct}/{len(self.test_questions)})")
        print(f"  ⏱️  Avg time: {avg_time:.2f}s")
        
        return {
            'method': 'cypher_pattern_and',
            'accuracy': accuracy,
            'correct': correct,
            'total': len(self.test_questions),
            'avg_time': avg_time,
            'errors': 0,
            'details': results
        }
    
    def run_all_tests(self):
        """Run all test methods"""
        print("📊 MEASURING ACTUAL SUCCESS RATES")
        print("=" * 60)
        
        # Load test questions
        self.load_test_questions(limit=25)  # Use 25 questions for faster testing
        
        all_results = []
        
        # Test different approaches
        try:
            # API-based tests (if API is running)
            all_results.append(self.test_api_method("vector", False))
            all_results.append(self.test_api_method("vector", True))
            all_results.append(self.test_api_method("hybrid", False))
            all_results.append(self.test_api_method("hybrid", True))
            all_results.append(self.test_api_method("text2cypher", False))
        except Exception as e:
            print(f"⚠️  API tests skipped: {e}")
        
        # Direct Cypher tests
        all_results.append(self.test_cypher_keyword_simple())
        all_results.append(self.test_cypher_pattern_and())
        
        # Print summary
        self.print_summary(all_results)
        
        # Save results
        self.save_results(all_results)
        
        return all_results
    
    def print_summary(self, results):
        """Print comparison summary"""
        print("\n" + "=" * 70)
        print("📈 SUCCESS RATE COMPARISON")
        print("=" * 70)
        
        # Sort by accuracy
        results.sort(key=lambda x: x['accuracy'], reverse=True)
        
        print(f"{'Method':<25} {'Accuracy':<12} {'Avg Time':<12} {'Errors':<8}")
        print("-" * 70)
        
        for r in results:
            method_name = r['method'].replace('_', ' ').title()
            print(f"{method_name:<25} {r['accuracy']:>6.1f}% ({r['correct']:>2}/{r['total']:<2}) {r['avg_time']:>8.2f}s {r['errors']:>5}")
        
        print(f"\nTested on {results[0]['total']} questions")
    
    def save_results(self, results):
        """Save results to file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"data/actual_success_rates_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump({
                'timestamp': timestamp,
                'num_questions': len(self.test_questions),
                'results': results
            }, f, indent=2)
        
        print(f"\n💾 Results saved to: {filename}")
    
    def cleanup(self):
        if self.driver:
            self.driver.close()

def main():
    measurer = SuccessRateMeasurer()
    try:
        measurer.run_all_tests()
    finally:
        measurer.cleanup()

if __name__ == "__main__":
    main()