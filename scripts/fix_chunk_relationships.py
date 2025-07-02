#!/usr/bin/env python3
"""
Fix Chunk Relationships Script

This script ensures all chunks are properly connected to their documents
after a bootstrap operation. It handles various chunk ID patterns and
creates missing HAS_CHUNK relationships.
"""

import os
import logging
from neo4j import GraphDatabase

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def fix_chunk_relationships(driver):
    """Fix missing HAS_CHUNK relationships between documents and chunks."""
    
    with driver.session() as session:
        # First, check how many orphaned chunks exist
        result = session.run("""
            MATCH (c:Chunk) 
            WHERE NOT (c)<-[:HAS_CHUNK]-(:Document)
            RETURN count(c) as orphaned_count
        """)
        orphaned_count = result.single()["orphaned_count"]
        
        if orphaned_count == 0:
            logger.info("No orphaned chunks found. All chunks are properly connected.")
            return
        
        logger.info(f"Found {orphaned_count} orphaned chunks. Fixing relationships...")
        
        # Strategy 1: Match chunks where chunk.id starts with document.id + '_p'
        result = session.run("""
            MATCH (c:Chunk) 
            WHERE c.id IS NOT NULL AND NOT (c)<-[:HAS_CHUNK]-(:Document)
            WITH c
            MATCH (d:Document)
            WHERE c.id STARTS WITH d.id + '_p'
            CREATE (d)-[:HAS_CHUNK]->(c)
            RETURN count(*) as fixed_count
        """)
        fixed_count = result.single()["fixed_count"]
        logger.info(f"Fixed {fixed_count} chunks using exact ID match")
        
        # Strategy 2: Match chunks by extracting document ID from chunk ID (split by '_p')
        result = session.run("""
            MATCH (c:Chunk) 
            WHERE c.id IS NOT NULL AND NOT (c)<-[:HAS_CHUNK]-(:Document)
            WITH c, split(c.id, '_p')[0] as doc_id_prefix
            MATCH (d:Document) 
            WHERE d.id = doc_id_prefix
            CREATE (d)-[:HAS_CHUNK]->(c)
            RETURN count(*) as fixed_count
        """)
        fixed_count = result.single()["fixed_count"]
        logger.info(f"Fixed {fixed_count} chunks using '_p' split pattern")
        
        # Strategy 3: Match chunks by extracting document ID from chunk ID (split by '_')
        result = session.run("""
            MATCH (c:Chunk) 
            WHERE c.id IS NOT NULL AND NOT (c)<-[:HAS_CHUNK]-(:Document)
            WITH c, split(c.id, '_')[0] as doc_id_prefix
            MATCH (d:Document) 
            WHERE d.id = doc_id_prefix
            CREATE (d)-[:HAS_CHUNK]->(c)
            RETURN count(*) as fixed_count
        """)
        fixed_count = result.single()["fixed_count"]
        logger.info(f"Fixed {fixed_count} chunks using '_' split pattern")
        
        # Final check
        result = session.run("""
            MATCH (c:Chunk) 
            WHERE NOT (c)<-[:HAS_CHUNK]-(:Document)
            RETURN count(c) as remaining_orphaned
        """)
        remaining = result.single()["remaining_orphaned"]
        
        if remaining > 0:
            logger.warning(f"Still have {remaining} orphaned chunks after fix attempts")
            
            # Log some examples
            result = session.run("""
                MATCH (c:Chunk) 
                WHERE c.id IS NOT NULL AND NOT (c)<-[:HAS_CHUNK]-(:Document)
                RETURN c.id as chunk_id
                LIMIT 10
            """)
            logger.warning("Example orphaned chunk IDs:")
            for record in result:
                logger.warning(f"  - {record['chunk_id']}")
        else:
            logger.info("All chunks successfully connected to documents!")

def update_chunk_counts(driver):
    """Update chunk_count property on all documents."""
    logger.info("Updating chunk counts on documents...")
    
    with driver.session() as session:
        result = session.run("""
            MATCH (d:Document)
            OPTIONAL MATCH (d)-[:HAS_CHUNK]->(c:Chunk)
            WITH d, count(c) as chunk_count
            SET d.chunk_count = chunk_count
            RETURN count(d) as documents_updated
        """)
        count = result.single()["documents_updated"]
        logger.info(f"Updated chunk counts for {count} documents")

def verify_relationships(driver):
    """Verify the state of chunk relationships."""
    logger.info("Verifying chunk relationships...")
    
    with driver.session() as session:
        # Get statistics
        result = session.run("""
            MATCH (d:Document)
            OPTIONAL MATCH (d)-[:HAS_CHUNK]->(c:Chunk)
            WITH d, count(c) as chunk_count
            RETURN 
                count(d) as total_documents,
                sum(chunk_count) as total_chunks,
                count(CASE WHEN chunk_count > 0 THEN 1 END) as docs_with_chunks,
                count(CASE WHEN chunk_count = 0 THEN 1 END) as docs_without_chunks
        """)
        stats = result.single()
        
        logger.info("Verification Results:")
        logger.info(f"  Total documents: {stats['total_documents']}")
        logger.info(f"  Total chunks: {stats['total_chunks']}")
        logger.info(f"  Documents with chunks: {stats['docs_with_chunks']}")
        logger.info(f"  Documents without chunks: {stats['docs_without_chunks']}")
        
        # Check total chunk count
        result = session.run("MATCH (c:Chunk) RETURN count(c) as total_chunks")
        total_chunks_in_db = result.single()["total_chunks"]
        logger.info(f"  Total chunks in database: {total_chunks_in_db}")
        
        # Check relationships
        result = session.run("MATCH ()-[r:HAS_CHUNK]->() RETURN count(r) as rel_count")
        rel_count = result.single()["rel_count"]
        logger.info(f"  HAS_CHUNK relationships: {rel_count}")

def main():
    """Main function to fix chunk relationships."""
    # Get configuration from environment or use defaults
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "knowledge123")
    
    # Create driver
    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
    
    try:
        # Fix relationships
        fix_chunk_relationships(driver)
        
        # Update chunk counts
        update_chunk_counts(driver)
        
        # Verify results
        verify_relationships(driver)
        
    finally:
        driver.close()

if __name__ == "__main__":
    main()