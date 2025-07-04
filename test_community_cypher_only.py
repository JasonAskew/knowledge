#!/usr/bin/env python3
"""
Test the 80-question test set using ONLY Cypher queries 
This exactly simulates how Claude Desktop would use the MCP server
"""

import csv
import json
import logging
from datetime import datetime
from typing import Dict, List
import os
from neo4j import GraphDatabase

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CypherOnlyTester:
    """Test using only Cypher queries - no Python ML models"""
    
    def __init__(self):
        # Neo4j connection
        self.driver = GraphDatabase.driver(
            "bolt://localhost:7687", 
            auth=("neo4j", "knowledge123")
        )
        
    def close(self):
        self.driver.close()
        
    def search_community_cypher(self, query: str, top_k: int = 10) -> List[Dict]:
        """
        Search using ONLY Cypher - simulating MCP tool usage
        No embeddings, just keyword matching and community structure
        """
        with self.driver.session() as session:
            # Extract keywords from query (simple tokenization)
            keywords = [w.lower() for w in query.split() if len(w) > 3]
            
            # Step 1: Find entities matching keywords and their communities
            entity_result = session.run("""
                MATCH (e:Entity)
                WHERE ANY(keyword IN $keywords WHERE toLower(e.text) CONTAINS keyword)
                RETURN e.text as entity, 
                       e.community_id as community_id,
                       e.community_degree_centrality as centrality
                ORDER BY e.occurrences DESC
                LIMIT 20
            """, keywords=keywords)
            
            entities = []
            communities = set()
            for record in entity_result:
                entities.append(record['entity'])
                if record['community_id'] is not None:
                    communities.add(record['community_id'])
            
            logger.debug(f"Found entities: {entities[:5]}...")
            logger.debug(f"Communities: {communities}")
            
            # Step 2: Search chunks in relevant communities
            if communities:
                # Search within communities first
                result = session.run("""
                    MATCH (c:Chunk)-[:CONTAINS_ENTITY]->(e:Entity)
                    WHERE e.community_id IN $communities
                    WITH c, COUNT(DISTINCT e) as entity_count,
                         COUNT(DISTINCT e.community_id) as community_coverage,
                         AVG(COALESCE(e.community_degree_centrality, 0)) as avg_centrality,
                         COLLECT(DISTINCT e.text) as entities_in_chunk
                    WHERE ANY(keyword IN $keywords WHERE toLower(c.text) CONTAINS keyword)
                    MATCH (c)<-[:HAS_CHUNK]-(d:Document)
                    RETURN c.id as chunk_id,
                           c.text as text,
                           c.page_num as page_num,
                           d.filename as document,
                           entity_count,
                           community_coverage,
                           avg_centrality,
                           entities_in_chunk,
                           SIZE([keyword IN $keywords WHERE toLower(c.text) CONTAINS keyword]) as keyword_matches
                    ORDER BY keyword_matches DESC, community_coverage DESC, avg_centrality DESC
                    LIMIT $limit
                """, communities=list(communities), keywords=keywords, limit=top_k)
                
                results = []
                for record in result:
                    results.append({
                        'chunk_id': record['chunk_id'],
                        'text': record['text'],
                        'page_num': record['page_num'],
                        'document': record['document'],
                        'score': float(record['keyword_matches']) + 
                                 (float(record['community_coverage']) * 0.3) + 
                                 (float(record['avg_centrality']) * 0.2),
                        'keyword_matches': record['keyword_matches'],
                        'community_coverage': record['community_coverage'],
                        'entities': record['entities_in_chunk'][:5]  # First 5 entities
                    })
                
                # If not enough results, search more broadly
                if len(results) < top_k:
                    broader_result = session.run("""
                        MATCH (c:Chunk)
                        WHERE ANY(keyword IN $keywords WHERE toLower(c.text) CONTAINS keyword)
                        MATCH (c)<-[:HAS_CHUNK]-(d:Document)
                        OPTIONAL MATCH (c)-[:CONTAINS_ENTITY]->(e:Entity)
                        WITH c, d, 
                             SIZE([keyword IN $keywords WHERE toLower(c.text) CONTAINS keyword]) as keyword_matches,
                             COUNT(e) as entity_count
                        RETURN c.id as chunk_id,
                               c.text as text,
                               c.page_num as page_num,
                               d.filename as document,
                               keyword_matches,
                               entity_count
                        ORDER BY keyword_matches DESC, entity_count DESC
                        LIMIT $limit
                    """, keywords=keywords, limit=top_k - len(results))
                    
                    for record in broader_result:
                        if not any(r['chunk_id'] == record['chunk_id'] for r in results):
                            results.append({
                                'chunk_id': record['chunk_id'],
                                'text': record['text'],
                                'page_num': record['page_num'],
                                'document': record['document'],
                                'score': float(record['keyword_matches']),
                                'keyword_matches': record['keyword_matches'],
                                'community_coverage': 0,
                                'entities': []
                            })
                
                return results[:top_k]
            else:
                # No communities found, do keyword search
                result = session.run("""
                    MATCH (c:Chunk)
                    WHERE ANY(keyword IN $keywords WHERE toLower(c.text) CONTAINS keyword)
                    MATCH (c)<-[:HAS_CHUNK]-(d:Document)
                    WITH c, d, SIZE([keyword IN $keywords WHERE toLower(c.text) CONTAINS keyword]) as keyword_matches
                    RETURN c.id as chunk_id,
                           c.text as text,
                           c.page_num as page_num,
                           d.filename as document,
                           keyword_matches as score,
                           keyword_matches,
                           0 as community_coverage
                    ORDER BY keyword_matches DESC
                    LIMIT $limit
                """, keywords=keywords, limit=top_k)
                
                return [dict(record) for record in result]
    
    def normalize_document_name(self, doc_name: str) -> str:
        """Normalize document name for comparison"""
        if '.' in doc_name:
            doc_name = doc_name.rsplit('.', 1)[0]
        return doc_name.lower().strip()
    
    def run_test_set(self, test_csv_path: str, output_dir: str):
        """Run the 80-question test set"""
        logger.info("Starting Cypher-only community test (MCP simulation)...")
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Read test cases
        test_cases = []
        with open(test_csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('#') and row.get('Question'):
                    test_cases.append({
                        'id': row['#'],
                        'question': row['Question'],
                        'expected_doc': row['Document Name'],
                        'expected_answer': row.get('Acceptable answer\n(entered by business / humans)', ''),
                        'document_type': row.get('Document Type\n\n(Product / Policy / Proceedure, PDS)', ''),
                        'brand': row.get('Brand\n(Westpac / SGB / BOM, BSA)', ''),
                        'product_category': row.get('Product Category', ''),
                        'product': row.get('Product', '')
                    })
        
        logger.info(f"Loaded {len(test_cases)} test cases")
        
        # Run tests
        results = []
        passed = 0
        
        for i, test_case in enumerate(test_cases, 1):
            logger.info(f"Test {i}/{len(test_cases)}: {test_case['question'][:50]}...")
            
            # Search using Cypher only
            search_results = self.search_community_cypher(test_case['question'], top_k=5)
            
            # Check if expected document is in results
            expected_doc_normalized = self.normalize_document_name(test_case['expected_doc'])
            found = False
            position = -1
            
            for idx, result in enumerate(search_results):
                result_doc_normalized = self.normalize_document_name(result['document'])
                if expected_doc_normalized in result_doc_normalized or result_doc_normalized in expected_doc_normalized:
                    found = True
                    position = idx + 1
                    break
            
            if found:
                passed += 1
                status = "PASS"
            else:
                status = "FAIL"
            
            result_entry = {
                'test_id': test_case['id'],
                'question': test_case['question'],
                'expected_doc': test_case['expected_doc'],
                'found': found,
                'position': position,
                'status': status,
                'top_result': search_results[0]['document'] if search_results else 'No results',
                'top_score': search_results[0]['score'] if search_results else 0,
                'keyword_matches': search_results[0].get('keyword_matches', 0) if search_results else 0,
                'community_coverage': search_results[0].get('community_coverage', 0) if search_results else 0,
                'search_results': search_results[:3]  # Keep top 3 for analysis
            }
            
            results.append(result_entry)
            
            # Log progress
            if i % 10 == 0:
                logger.info(f"Progress: {i}/{len(test_cases)} - Current accuracy: {passed/i:.2%}")
        
        # Calculate final statistics
        accuracy = passed / len(test_cases)
        
        # Save results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save detailed JSON results
        json_path = os.path.join(output_dir, f"cypher_only_test_results_{timestamp}.json")
        with open(json_path, 'w') as f:
            json.dump({
                'test_info': {
                    'timestamp': timestamp,
                    'total_tests': len(test_cases),
                    'passed': passed,
                    'failed': len(test_cases) - passed,
                    'accuracy': accuracy,
                    'search_method': 'cypher_only_community',
                    'description': 'Uses only Cypher queries accessible via MCP tools'
                },
                'results': results
            }, f, indent=2)
        
        # Save summary CSV
        csv_path = os.path.join(output_dir, f"cypher_only_test_summary_{timestamp}.csv")
        with open(csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Test ID', 'Status', 'Question', 'Expected Doc', 'Found Doc', 'Position', 'Score', 'Keyword Matches', 'Community Coverage'])
            
            for result in results:
                writer.writerow([
                    result['test_id'],
                    result['status'],
                    result['question'][:50] + '...',
                    result['expected_doc'],
                    result['top_result'],
                    result['position'] if result['position'] > 0 else 'Not found',
                    f"{result['top_score']:.2f}",
                    result['keyword_matches'],
                    result['community_coverage']
                ])
        
        # Print summary
        logger.info("="*80)
        logger.info("CYPHER-ONLY TEST RESULTS (MCP SIMULATION)")
        logger.info("="*80)
        logger.info(f"Total Tests: {len(test_cases)}")
        logger.info(f"Passed: {passed}")
        logger.info(f"Failed: {len(test_cases) - passed}")
        logger.info(f"Accuracy: {accuracy:.2%}")
        logger.info(f"Search Method: Cypher-only with Community Awareness")
        logger.info("="*80)
        
        # Analyze failures
        failures = [r for r in results if not r['found']]
        if failures:
            logger.info("\nFAILED TESTS:")
            for f in failures[:10]:  # Show first 10 failures
                logger.info(f"- Test {f['test_id']}: {f['question'][:50]}...")
                logger.info(f"  Expected: {f['expected_doc']}")
                logger.info(f"  Got: {f['top_result']}")
        
        return {
            'accuracy': accuracy,
            'passed': passed,
            'total': len(test_cases),
            'results_file': json_path
        }


def main():
    """Run the Cypher-only test"""
    # Use Docker network for connection
    tester = CypherOnlyTester()
    
    try:
        # Verify community data exists
        with tester.driver.session() as session:
            result = session.run("""
                MATCH (e:Entity)
                WHERE e.community_id IS NOT NULL
                RETURN COUNT(e) as count
            """)
            count = result.single()['count']
            
            if count == 0:
                logger.error("No community data found! Please run community detection first.")
                return
            
            logger.info(f"Found {count} entities with community assignments")
            
            # Check relationship count
            result = session.run("""
                MATCH ()-[r:RELATED_TO]->()
                RETURN COUNT(r) as count
            """)
            rel_count = result.single()['count']
            logger.info(f"Found {rel_count} RELATED_TO relationships")
        
        # Run test set
        results = tester.run_test_set(
            test_csv_path='knowledge_test_agent/test.csv',
            output_dir='data/test_results'
        )
        
        logger.info(f"\nResults saved to: {results['results_file']}")
        
    finally:
        tester.close()


if __name__ == "__main__":
    main()