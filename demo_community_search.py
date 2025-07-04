#!/usr/bin/env python3
"""
Demonstrate community-aware search functionality
"""

import os
import sys
import numpy as np
from neo4j import GraphDatabase
import logging
from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add the knowledge_ingestion_agent directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'knowledge_ingestion_agent'))
from community_detection import CommunityAwareSearch

# Neo4j connection
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "knowledge123")


def extract_entities_from_text(text: str, driver) -> List[str]:
    """Extract entities that exist in our graph"""
    with driver.session() as session:
        # Simple approach: find entities that match words in the query
        words = text.lower().split()
        
        result = session.run("""
            MATCH (e:Entity)
            WHERE ANY(word IN $words WHERE toLower(e.text) CONTAINS word)
            RETURN DISTINCT e.text as entity
            LIMIT 10
        """, words=words)
        
        return [record['entity'] for record in result]


def demonstrate_community_search():
    """Demonstrate the community-aware search functionality"""
    
    # Initialize components
    logger.info("Initializing community-aware search demo...")
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    community_search = CommunityAwareSearch(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    
    # Load embedding model
    logger.info("Loading embedding model...")
    model = SentenceTransformer('BAAI/bge-small-en-v1.5')
    
    # Test queries
    queries = [
        "What are the tax implications for foreign residents in Australia?",
        "How can I apply for youth allowance benefits?",
        "What are the superannuation contribution limits?",
        "Tell me about Medicare eligibility requirements"
    ]
    
    try:
        # First, show community statistics
        with driver.session() as session:
            result = session.run("""
                MATCH (e:Entity)
                WHERE e.community_id IS NOT NULL
                WITH e.community_id as community, COUNT(e) as size
                ORDER BY size DESC
                LIMIT 5
                RETURN collect({community: community, size: size}) as top_communities
            """)
            
            top_communities = result.single()['top_communities']
            logger.info("\nTop 5 communities by size:")
            for comm in top_communities:
                logger.info(f"  Community {comm['community']}: {comm['size']} entities")
        
        # Demonstrate search for each query
        for query in queries:
            logger.info(f"\n{'='*80}")
            logger.info(f"QUERY: {query}")
            logger.info(f"{'='*80}")
            
            # Generate query embedding
            query_embedding = model.encode(query)
            
            # Extract entities from query
            query_entities = extract_entities_from_text(query, driver)
            logger.info(f"Identified entities in query: {query_entities}")
            
            # Perform community-aware search
            results = community_search.search(
                query_embedding=query_embedding,
                query_entities=query_entities,
                top_k=3,
                community_weight=0.3
            )
            
            # Display results
            for i, result in enumerate(results, 1):
                logger.info(f"\nResult {i}:")
                logger.info(f"  Document: {result['document']}")
                logger.info(f"  Page: {result['page_num']}")
                logger.info(f"  Score: {result['final_score']:.3f}")
                logger.info(f"  Community metrics: {result.get('community_metrics', {})}")
                logger.info(f"  Text preview: {result['text'][:150]}...")
            
            # Compare with standard vector search
            logger.info("\nComparing with standard vector search:")
            with driver.session() as session:
                embedding_list = query_embedding.tolist()
                
                result = session.run("""
                    MATCH (c:Chunk)
                    WITH c, reduce(similarity = 0.0, i IN range(0, size(c.embedding)-1) |
                        similarity + c.embedding[i] * $query_embedding[i]
                    ) as cosine_similarity
                    ORDER BY cosine_similarity DESC
                    LIMIT 3
                    MATCH (c)<-[:HAS_CHUNK]-(d:Document)
                    RETURN c.text as text, d.filename as document, 
                           c.page_num as page_num, cosine_similarity as score
                """, query_embedding=embedding_list)
                
                for i, record in enumerate(result, 1):
                    logger.info(f"  {i}. {record['document']} (p.{record['page_num']}) - Score: {record['score']:.3f}")
        
        # Demonstrate bridge node search
        logger.info(f"\n{'='*80}")
        logger.info("BRIDGE NODE ANALYSIS")
        logger.info(f"{'='*80}")
        
        with driver.session() as session:
            result = session.run("""
                MATCH (e:Entity)
                WHERE e.is_bridge_node = true
                RETURN e.text as entity, 
                       e.connected_communities as num_communities,
                       e.type as entity_type
                ORDER BY num_communities DESC
                LIMIT 10
            """)
            
            logger.info("Top bridge nodes connecting multiple communities:")
            for record in result:
                logger.info(f"  - {record['entity']} ({record['entity_type']}) - Connects {record['num_communities']} communities")
        
    finally:
        driver.close()
        community_search.close()
        logger.info("\nDemo complete!")


if __name__ == "__main__":
    from typing import List
    demonstrate_community_search()