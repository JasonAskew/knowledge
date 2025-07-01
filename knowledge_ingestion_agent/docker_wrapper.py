#!/usr/bin/env python3
"""
Docker-safe wrapper for knowledge ingestion
Processes files sequentially to avoid multiprocessing issues in containers
"""

import os
import sys
import json
import logging
from knowledge_ingestion_agent import KnowledgeIngestionAgent

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def process_inventory_sequential(agent, inventory_file):
    """Process inventory sequentially for Docker compatibility"""
    logger.info(f"Processing inventory sequentially: {inventory_file}")
    
    # Load inventory
    with open(inventory_file, 'r') as f:
        inventory = json.load(f)
    
    total_files = len(inventory['files'])
    logger.info(f"Found {total_files} files to process")
    
    # Process each file sequentially
    processed = 0
    errors = 0
    
    for i, file_info in enumerate(inventory['files']):
        try:
            local_path = file_info['local_path']
            
            # Map Docker paths to actual paths
            if local_path.startswith('/data/pdfs/'):
                # In Docker, PDFs are mounted to /data/pdfs/
                if not os.path.exists(local_path):
                    logger.warning(f"File not found: {local_path}")
                    errors += 1
                    continue
            else:
                logger.warning(f"Unexpected path format: {local_path}")
                errors += 1
                continue
                
            logger.info(f"Processing [{i+1}/{total_files}]: {file_info['filename']}")
            
            # Process the single PDF
            agent.process_single_pdf(local_path, file_info)
            processed += 1
            
            logger.info(f"Successfully processed: {file_info['filename']}")
            
        except Exception as e:
            logger.error(f"Error processing {file_info.get('filename', 'unknown')}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            errors += 1
    
    logger.info(f"Processing complete: {processed} successful, {errors} errors")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Docker-safe Knowledge Ingestion')
    parser.add_argument('--inventory', required=True, help='Inventory JSON file')
    parser.add_argument('--neo4j-uri', default='bolt://neo4j:7687', help='Neo4j URI')
    parser.add_argument('--neo4j-user', default='neo4j', help='Neo4j username')
    parser.add_argument('--neo4j-password', default='knowledge123', help='Neo4j password')
    
    args = parser.parse_args()
    
    # Override Neo4j settings from environment
    neo4j_uri = os.getenv('NEO4J_URI', args.neo4j_uri)
    neo4j_user = os.getenv('NEO4J_USER', args.neo4j_user)
    neo4j_password = os.getenv('NEO4J_PASSWORD', args.neo4j_password)
    
    # Create agent with single worker
    agent = KnowledgeIngestionAgent(
        neo4j_uri=neo4j_uri,
        neo4j_user=neo4j_user,
        neo4j_password=neo4j_password,
        num_workers=1  # Single worker for Docker
    )
    
    # Process inventory sequentially
    process_inventory_sequential(agent, args.inventory)

if __name__ == "__main__":
    main()