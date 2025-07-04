#!/usr/bin/env python3
"""
Run community detection on the knowledge graph
"""

import os
import sys
import logging
from datetime import datetime

# Add the knowledge_ingestion_agent directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'knowledge_ingestion_agent'))

from community_detection import CommunityDetector, create_community_search_index

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    # Neo4j connection details
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "knowledge123")
    
    logger.info("Starting community detection process...")
    start_time = datetime.now()
    
    # Create detector
    detector = CommunityDetector(neo4j_uri, neo4j_user, neo4j_password)
    
    try:
        # Step 1: Run Louvain detection with different resolutions
        logger.info("Testing different resolution parameters...")
        
        # Try resolution 1.0 (default - balanced communities)
        communities_10 = detector.run_louvain_detection(resolution=1.0)
        num_communities_10 = len(set(communities_10.values()))
        logger.info(f"Resolution 1.0: {num_communities_10} communities detected")
        
        # Try resolution 0.5 (fewer, larger communities)
        communities_05 = detector.run_louvain_detection(resolution=0.5)
        num_communities_05 = len(set(communities_05.values()))
        logger.info(f"Resolution 0.5: {num_communities_05} communities detected")
        
        # Try resolution 1.5 (more, smaller communities)
        communities_15 = detector.run_louvain_detection(resolution=1.5)
        num_communities_15 = len(set(communities_15.values()))
        logger.info(f"Resolution 1.5: {num_communities_15} communities detected")
        
        # Use resolution 1.0 as the default
        logger.info("Using resolution 1.0 for final community assignment")
        communities = communities_10
        
        # Step 2: Enrich graph with community metadata
        logger.info("Enriching graph with community metadata...")
        detector.enrich_graph_with_communities(communities)
        
        # Step 3: Calculate community coherence
        logger.info("Calculating community coherence scores...")
        coherence_scores = detector.calculate_community_coherence()
        
        # Print summary statistics
        logger.info("\n=== Community Detection Summary ===")
        logger.info(f"Total communities: {len(set(communities.values()))}")
        logger.info(f"Total entities processed: {len(communities)}")
        
        # Show top 10 most coherent communities
        if coherence_scores:
            sorted_communities = sorted(
                coherence_scores.items(), 
                key=lambda x: x[1]['coherence'] if x[1]['coherence'] else 0, 
                reverse=True
            )[:10]
            
            logger.info("\nTop 10 most coherent communities:")
            for comm_id, scores in sorted_communities:
                logger.info(f"  Community {comm_id}: coherence={scores['coherence']:.3f}, density={scores['density']:.3f}")
        
        # Step 4: Create indexes for efficient search
        logger.info("\nCreating community search indexes...")
        create_community_search_index(neo4j_uri, neo4j_user, neo4j_password)
        
        # Calculate processing time
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(f"\nCommunity detection completed in {duration:.2f} seconds")
        
        # Verify the enrichment
        with detector.driver.session() as session:
            result = session.run("""
                MATCH (e:Entity)
                WHERE e.community_id IS NOT NULL
                RETURN COUNT(e) as enriched_count
            """)
            enriched_count = result.single()['enriched_count']
            
            result = session.run("""
                MATCH (e:Entity)
                WHERE e.is_bridge_node = true
                RETURN COUNT(e) as bridge_count
            """)
            bridge_count = result.single()['bridge_count']
            
            logger.info(f"\nEnrichment verification:")
            logger.info(f"  Entities with community assignment: {enriched_count}")
            logger.info(f"  Bridge nodes identified: {bridge_count}")
        
    except Exception as e:
        logger.error(f"Error during community detection: {str(e)}")
        raise
    finally:
        detector.close()


if __name__ == "__main__":
    main()