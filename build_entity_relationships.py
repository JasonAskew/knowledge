#!/usr/bin/env python3
"""
Build RELATED_TO relationships between entities based on co-occurrence in chunks
"""

import os
import logging
from neo4j import GraphDatabase
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def build_entity_relationships(uri: str, user: str, password: str):
    """Build RELATED_TO relationships between entities that co-occur in chunks"""
    
    driver = GraphDatabase.driver(uri, auth=(user, password))
    
    try:
        with driver.session() as session:
            # First, let's check how many chunks have entities
            result = session.run("""
                MATCH (c:Chunk)-[:CONTAINS_ENTITY]->(e:Entity)
                RETURN COUNT(DISTINCT c) as chunks_with_entities,
                       COUNT(DISTINCT e) as total_entities
            """)
            stats = result.single()
            logger.info(f"Found {stats['chunks_with_entities']} chunks with {stats['total_entities']} entities")
            
            # Create RELATED_TO relationships based on co-occurrence
            logger.info("Building entity relationships based on co-occurrence...")
            
            # This query creates relationships between entities that appear in the same chunk
            # The strength is the number of chunks they co-occur in
            result = session.run("""
                MATCH (c:Chunk)-[:CONTAINS_ENTITY]->(e1:Entity)
                MATCH (c)-[:CONTAINS_ENTITY]->(e2:Entity)
                WHERE id(e1) < id(e2)  // Avoid duplicates and self-relationships
                WITH e1, e2, COUNT(DISTINCT c) as cooccurrence_count
                WHERE cooccurrence_count > 1  // Only create relationship if they co-occur in multiple chunks
                MERGE (e1)-[r:RELATED_TO]-(e2)
                SET r.strength = cooccurrence_count
                RETURN COUNT(r) as relationships_created
            """)
            
            rel_count = result.single()['relationships_created']
            logger.info(f"Created {rel_count} RELATED_TO relationships")
            
            # Add some statistics about the relationships
            result = session.run("""
                MATCH ()-[r:RELATED_TO]->()
                RETURN MIN(r.strength) as min_strength,
                       MAX(r.strength) as max_strength,
                       AVG(r.strength) as avg_strength,
                       COUNT(r) as total_relationships
            """)
            
            stats = result.single()
            logger.info(f"Relationship statistics:")
            logger.info(f"  Total relationships: {stats['total_relationships']}")
            logger.info(f"  Min strength: {stats['min_strength']}")
            logger.info(f"  Max strength: {stats['max_strength']}")
            logger.info(f"  Avg strength: {stats['avg_strength']:.2f}")
            
            # Create index on Entity.id for better performance
            logger.info("Creating index on Entity.id...")
            session.run("CREATE INDEX entity_id IF NOT EXISTS FOR (e:Entity) ON (e.id)")
            
    finally:
        driver.close()


def main():
    # Neo4j connection details
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "knowledge123")
    
    logger.info("Starting entity relationship building process...")
    start_time = datetime.now()
    
    build_entity_relationships(neo4j_uri, neo4j_user, neo4j_password)
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    logger.info(f"Entity relationship building completed in {duration:.2f} seconds")


if __name__ == "__main__":
    main()