#!/usr/bin/env python3
"""
Wait for Neo4j to be ready before starting the application
"""

import time
import sys
from neo4j import GraphDatabase
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def wait_for_neo4j(uri, user, password, max_attempts=30, delay=2):
    """Wait for Neo4j to be ready"""
    logger.info(f"Waiting for Neo4j at {uri}...")
    
    for attempt in range(max_attempts):
        try:
            driver = GraphDatabase.driver(uri, auth=(user, password))
            driver.verify_connectivity()
            driver.close()
            logger.info("✅ Neo4j is ready!")
            return True
        except Exception as e:
            if attempt < max_attempts - 1:
                logger.info(f"Attempt {attempt + 1}/{max_attempts}: Neo4j not ready yet. Waiting {delay}s...")
                time.sleep(delay)
            else:
                logger.error(f"❌ Neo4j failed to start after {max_attempts} attempts")
                logger.error(f"Last error: {e}")
                return False
    
    return False

if __name__ == "__main__":
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "knowledge123")
    
    if wait_for_neo4j(neo4j_uri, neo4j_user, neo4j_password):
        sys.exit(0)
    else:
        sys.exit(1)