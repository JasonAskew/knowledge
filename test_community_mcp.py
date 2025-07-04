#!/usr/bin/env python3
"""
Test the 80-question test set using only the Neo4j MCP tool with community-aware search
This simulates how Claude Desktop would use the proxied Neo4j Cypher tool
"""

import csv
import json
import logging
from datetime import datetime
from typing import Dict, List, Tuple
import numpy as np
from sentence_transformers import SentenceTransformer
from neo4j import GraphDatabase
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Neo4j connection
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "knowledge123")

class CommunityMCPTester:
    """Test harness using only Neo4j Cypher queries (MCP-compatible)"""
    
    def __init__(self):
        self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        self.model = SentenceTransformer('BAAI/bge-small-en-v1.5')
        
    def close(self):
        self.driver.close()
        
    def search_with_community(self, query: str, top_k: int = 10, community_weight: float = 0.3) -> List[Dict]:
        """
        Perform community-aware search using only Cypher queries
        This simulates what Claude Desktop would do via MCP
        """
        # Step 1: Generate query embedding
        query_embedding = self.model.encode(query).tolist()
        
        with self.driver.session() as session:
            # Step 2: Extract entities from query (simple keyword matching)
            words = query.lower().split()
            
            # Find entities matching query words
            entity_result = session.run("""
                MATCH (e:Entity)
                WHERE ANY(word IN $words WHERE toLower(e.text) CONTAINS word)
                RETURN e.text as entity, e.community_id as community_id
                LIMIT 10
            """, words=words)
            
            query_entities = []
            relevant_communities = set()
            for record in entity_result:
                query_entities.append(record['entity'])
                if record['community_id'] is not None:
                    relevant_communities.add(record['community_id'])
            
            logger.debug(f"Query entities: {query_entities}")
            logger.debug(f"Relevant communities: {relevant_communities}")
            
            # Step 3: Phase 1 - Search within relevant communities
            if relevant_communities:
                phase1_result = session.run("""
                    MATCH (c:Chunk)-[:CONTAINS_ENTITY]->(e:Entity)
                    WHERE e.community_id IN $communities
                    WITH c, COUNT(DISTINCT e.community_id) as community_coverage,
                         AVG(COALESCE(e.community_degree_centrality, 0)) as avg_centrality
                    WITH c, community_coverage, avg_centrality,
                         reduce(similarity = 0.0, i IN range(0, size(c.embedding)-1) |
                            similarity + c.embedding[i] * $query_embedding[i]
                         ) as cosine_similarity
                    MATCH (c)<-[:HAS_CHUNK]-(d:Document)
                    RETURN c.id as chunk_id,
                           c.text as text,
                           c.page_num as page_num,
                           d.filename as document,
                           cosine_similarity,
                           community_coverage,
                           avg_centrality
                    ORDER BY cosine_similarity DESC
                    LIMIT $limit
                """, communities=list(relevant_communities), 
                     query_embedding=query_embedding, 
                     limit=top_k * 2)
                
                phase1_results = [dict(record) for record in phase1_result]
            else:
                phase1_results = []
            
            # Step 4: Phase 2 - Search bridge nodes if needed
            if len(phase1_results) < top_k:
                remaining_needed = top_k - len(phase1_results)
                
                # Fall back to general vector search
                phase2_result = session.run("""
                    MATCH (c:Chunk)
                    WITH c, reduce(similarity = 0.0, i IN range(0, size(c.embedding)-1) |
                        similarity + c.embedding[i] * $query_embedding[i]
                    ) as cosine_similarity
                    ORDER BY cosine_similarity DESC
                    LIMIT $limit
                    MATCH (c)<-[:HAS_CHUNK]-(d:Document)
                    OPTIONAL MATCH (c)-[:CONTAINS_ENTITY]->(e:Entity)
                    WHERE e.is_bridge_node = true
                    WITH c, d, cosine_similarity, COUNT(e) as bridge_count
                    RETURN c.id as chunk_id,
                           c.text as text,
                           c.page_num as page_num,
                           d.filename as document,
                           cosine_similarity,
                           0 as community_coverage,
                           bridge_count as avg_centrality
                    ORDER BY cosine_similarity DESC
                    LIMIT $limit
                """, query_embedding=query_embedding, limit=remaining_needed)
                
                phase2_results = [dict(record) for record in phase2_result]
                phase1_results.extend(phase2_results)
            
            # Step 5: Apply community-aware ranking
            for result in phase1_results:
                # Calculate final score
                base_score = result['cosine_similarity']
                community_bonus = (
                    result['community_coverage'] * 0.5 +
                    result['avg_centrality'] * 0.5
                ) * community_weight
                
                result['final_score'] = base_score * (1 - community_weight) + community_bonus
                result['community_metrics'] = {
                    'coverage': result['community_coverage'],
                    'avg_centrality': result['avg_centrality'],
                    'community_weight': community_weight
                }
            
            # Sort by final score
            phase1_results.sort(key=lambda x: x['final_score'], reverse=True)
            
            return phase1_results[:top_k]
    
    def normalize_document_name(self, doc_name: str) -> str:
        """Normalize document name for comparison"""
        if '.' in doc_name:
            doc_name = doc_name.rsplit('.', 1)[0]
        return doc_name.lower().strip()
    
    def run_test_set(self, test_csv_path: str, output_dir: str):
        """Run the 80-question test set"""
        logger.info("Starting community-aware MCP test run...")
        
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
            
            # Search with community awareness
            search_results = self.search_with_community(
                test_case['question'], 
                top_k=5,
                community_weight=0.3
            )
            
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
                'top_score': search_results[0]['final_score'] if search_results else 0,
                'community_metrics': search_results[0].get('community_metrics', {}) if search_results else {},
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
        json_path = os.path.join(output_dir, f"community_mcp_test_results_{timestamp}.json")
        with open(json_path, 'w') as f:
            json.dump({
                'test_info': {
                    'timestamp': timestamp,
                    'total_tests': len(test_cases),
                    'passed': passed,
                    'failed': len(test_cases) - passed,
                    'accuracy': accuracy,
                    'search_method': 'community_aware_mcp',
                    'community_weight': 0.3
                },
                'results': results
            }, f, indent=2)
        
        # Save summary CSV
        csv_path = os.path.join(output_dir, f"community_mcp_test_summary_{timestamp}.csv")
        with open(csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Test ID', 'Status', 'Question', 'Expected Doc', 'Found Doc', 'Position', 'Score', 'Community Coverage'])
            
            for result in results:
                writer.writerow([
                    result['test_id'],
                    result['status'],
                    result['question'][:50] + '...',
                    result['expected_doc'],
                    result['top_result'],
                    result['position'] if result['position'] > 0 else 'Not found',
                    f"{result['top_score']:.3f}",
                    result['community_metrics'].get('coverage', 0) if result['community_metrics'] else 0
                ])
        
        # Print summary
        logger.info("="*80)
        logger.info("TEST RESULTS SUMMARY")
        logger.info("="*80)
        logger.info(f"Total Tests: {len(test_cases)}")
        logger.info(f"Passed: {passed}")
        logger.info(f"Failed: {len(test_cases) - passed}")
        logger.info(f"Accuracy: {accuracy:.2%}")
        logger.info(f"Search Method: Community-Aware MCP (Cypher-only)")
        logger.info(f"Community Weight: 0.3")
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
    """Run the community-aware MCP test"""
    tester = CommunityMCPTester()
    
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