#!/usr/bin/env python3
"""
Neo4j Knowledge Graph Bootstrap Script

This script imports a previously exported Neo4j database from JSON format.
It can be used to quickly bootstrap a new instance with existing data.

Features:
- Imports nodes with all properties and labels
- Imports relationships with all properties
- Preserves vector embeddings
- Validates data integrity
- Optional mode to skip if database already contains data
"""

import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional
import logging
from neo4j import GraphDatabase
import numpy as np

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class Neo4jBootstrapper:
    def __init__(self, uri: str, user: str, password: str):
        """Initialize the Neo4j bootstrapper with connection details."""
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.node_id_mapping = {}  # Maps old IDs to new IDs
        self.import_stats = {
            "nodes_imported": 0,
            "relationships_imported": 0,
            "errors": []
        }
    
    def close(self):
        """Close the Neo4j driver connection."""
        self.driver.close()
    
    def _deserialize_value(self, value: Any) -> Any:
        """Deserialize values from JSON export, handling special types."""
        if isinstance(value, dict) and "_type" in value:
            value_type = value["_type"]
            
            if value_type == "vector":
                # Restore vector embeddings
                return value["values"]
            elif value_type == "datetime":
                # Restore datetime objects
                return datetime.fromisoformat(value["value"])
            elif value_type == "bytes":
                # Restore bytes objects
                return bytes.fromhex(value["value"])
        
        elif isinstance(value, dict):
            # Recursively deserialize nested dicts
            return {k: self._deserialize_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            # Recursively deserialize lists
            return [self._deserialize_value(v) for v in value]
        
        return value
    
    def check_database_empty(self) -> bool:
        """Check if the database is empty."""
        with self.driver.session() as session:
            result = session.run("MATCH (n) RETURN count(n) as count LIMIT 1")
            count = result.single()["count"]
            return count == 0
    
    def clear_database(self):
        """Clear all data from the database."""
        logger.warning("Clearing existing database...")
        
        with self.driver.session() as session:
            # Delete all relationships first
            session.run("MATCH ()-[r]->() DELETE r")
            # Then delete all nodes
            session.run("MATCH (n) DELETE n")
        
        logger.info("Database cleared")
    
    def create_indexes(self):
        """Create necessary indexes for performance."""
        logger.info("Creating indexes...")
        
        indexes = [
            # Document indexes
            "CREATE INDEX IF NOT EXISTS FOR (d:Document) ON (d.file_path)",
            "CREATE INDEX IF NOT EXISTS FOR (d:Document) ON (d.title)",
            
            # Chunk indexes
            "CREATE INDEX IF NOT EXISTS FOR (c:Chunk) ON (c.chunk_id)",
            
            # Entity indexes
            "CREATE INDEX IF NOT EXISTS FOR (e:Entity) ON (e.name)",
            "CREATE INDEX IF NOT EXISTS FOR (e:Entity) ON (e.type)",
            
            # Topic indexes
            "CREATE INDEX IF NOT EXISTS FOR (t:Topic) ON (t.name)",
            
            # Concept indexes
            "CREATE INDEX IF NOT EXISTS FOR (c:Concept) ON (c.name)"
        ]
        
        with self.driver.session() as session:
            for index_query in indexes:
                try:
                    session.run(index_query)
                    logger.debug(f"Created index: {index_query}")
                except Exception as e:
                    logger.warning(f"Failed to create index: {e}")
    
    def import_nodes(self, nodes: List[Dict]) -> int:
        """Import nodes from the export data."""
        logger.info(f"Importing {len(nodes)} nodes...")
        
        batch_size = 100
        imported = 0
        
        with self.driver.session() as session:
            for i in range(0, len(nodes), batch_size):
                batch = nodes[i:i + batch_size]
                
                try:
                    # Build batch import query
                    for node_data in batch:
                        labels = ":".join(node_data["labels"])
                        properties = {}
                        
                        # Deserialize properties
                        for key, value in node_data["properties"].items():
                            properties[key] = self._deserialize_value(value)
                        
                        # Create node
                        query = f"""
                        CREATE (n:{labels})
                        SET n = $properties
                        RETURN id(n) as new_id
                        """
                        
                        result = session.run(query, properties=properties)
                        new_id = result.single()["new_id"]
                        
                        # Store ID mapping
                        self.node_id_mapping[node_data["id"]] = new_id
                        imported += 1
                        
                except Exception as e:
                    logger.error(f"Failed to import node batch: {e}")
                    self.import_stats["errors"].append(str(e))
                
                if imported % 1000 == 0:
                    logger.info(f"Imported {imported} nodes...")
        
        self.import_stats["nodes_imported"] = imported
        logger.info(f"Total nodes imported: {imported}")
        return imported
    
    def import_relationships(self, relationships: List[Dict]) -> int:
        """Import relationships from the export data."""
        logger.info(f"Importing {len(relationships)} relationships...")
        
        batch_size = 100
        imported = 0
        skipped = 0
        
        with self.driver.session() as session:
            for i in range(0, len(relationships), batch_size):
                batch = relationships[i:i + batch_size]
                
                for rel_data in batch:
                    try:
                        # Get mapped node IDs
                        start_id = self.node_id_mapping.get(rel_data["start_node_id"])
                        end_id = self.node_id_mapping.get(rel_data["end_node_id"])
                        
                        if start_id is None or end_id is None:
                            logger.warning(f"Skipping relationship - missing node mapping")
                            skipped += 1
                            continue
                        
                        # Deserialize properties
                        properties = {}
                        for key, value in rel_data["properties"].items():
                            properties[key] = self._deserialize_value(value)
                        
                        # Create relationship
                        query = f"""
                        MATCH (a), (b)
                        WHERE id(a) = $start_id AND id(b) = $end_id
                        CREATE (a)-[r:{rel_data["type"]}]->(b)
                        SET r = $properties
                        """
                        
                        session.run(query, start_id=start_id, end_id=end_id, properties=properties)
                        imported += 1
                        
                    except Exception as e:
                        logger.error(f"Failed to import relationship: {e}")
                        self.import_stats["errors"].append(str(e))
                
                if imported % 1000 == 0:
                    logger.info(f"Imported {imported} relationships...")
        
        self.import_stats["relationships_imported"] = imported
        logger.info(f"Total relationships imported: {imported} (skipped: {skipped})")
        return imported
    
    def verify_import(self, export_data: Dict):
        """Verify the import by comparing statistics."""
        logger.info("Verifying import...")
        
        with self.driver.session() as session:
            # Count nodes
            result = session.run("MATCH (n) RETURN count(n) as count")
            actual_nodes = result.single()["count"]
            
            # Count relationships
            result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
            actual_rels = result.single()["count"]
            
            expected_nodes = len(export_data["nodes"])
            expected_rels = len(export_data["relationships"])
            
            logger.info(f"Nodes - Expected: {expected_nodes}, Actual: {actual_nodes}")
            logger.info(f"Relationships - Expected: {expected_rels}, Actual: {actual_rels}")
            
            if actual_nodes != expected_nodes or actual_rels != expected_rels:
                logger.warning("Import verification failed - counts don't match!")
                return False
            
            return True
    
    def _fix_chunk_relationships(self):
        """Fix missing HAS_CHUNK relationships between documents and chunks."""
        with self.driver.session() as session:
            # Check for orphaned chunks
            result = session.run("""
                MATCH (c:Chunk) 
                WHERE NOT (c)<-[:HAS_CHUNK]-(:Document)
                RETURN count(c) as orphaned_count
            """)
            orphaned_count = result.single()["orphaned_count"]
            
            if orphaned_count == 0:
                logger.info("No orphaned chunks found.")
                return
            
            logger.info(f"Found {orphaned_count} orphaned chunks. Fixing...")
            
            # Fix using multiple strategies
            strategies = [
                # Strategy 1: Exact match with document.id + '_p'
                """
                MATCH (c:Chunk) 
                WHERE c.id IS NOT NULL AND NOT (c)<-[:HAS_CHUNK]-(:Document)
                WITH c
                MATCH (d:Document)
                WHERE c.id STARTS WITH d.id + '_p'
                CREATE (d)-[:HAS_CHUNK]->(c)
                RETURN count(*) as fixed_count
                """,
                # Strategy 2: Split by '_p'
                """
                MATCH (c:Chunk) 
                WHERE c.id IS NOT NULL AND NOT (c)<-[:HAS_CHUNK]-(:Document)
                WITH c, split(c.id, '_p')[0] as doc_id_prefix
                MATCH (d:Document) 
                WHERE d.id = doc_id_prefix
                CREATE (d)-[:HAS_CHUNK]->(c)
                RETURN count(*) as fixed_count
                """,
                # Strategy 3: Split by '_' for remaining
                """
                MATCH (c:Chunk) 
                WHERE c.id IS NOT NULL AND NOT (c)<-[:HAS_CHUNK]-(:Document)
                WITH c, split(c.id, '_')[0] as doc_id_prefix
                MATCH (d:Document) 
                WHERE d.id = doc_id_prefix
                CREATE (d)-[:HAS_CHUNK]->(c)
                RETURN count(*) as fixed_count
                """
            ]
            
            total_fixed = 0
            for i, strategy in enumerate(strategies, 1):
                result = session.run(strategy)
                fixed = result.single()["fixed_count"]
                if fixed > 0:
                    logger.info(f"Strategy {i} fixed {fixed} chunks")
                    total_fixed += fixed
            
            # Update chunk counts
            session.run("""
                MATCH (d:Document)
                OPTIONAL MATCH (d)-[:HAS_CHUNK]->(c:Chunk)
                WITH d, count(c) as chunk_count
                SET d.chunk_count = chunk_count
            """)
            
            logger.info(f"Fixed {total_fixed} chunk relationships total")
    
    def bootstrap_from_file(self, import_file: str, force: bool = False) -> bool:
        """Main bootstrap method that orchestrates the import process."""
        try:
            logger.info(f"Starting Neo4j bootstrap from {import_file}")
            
            # Check if database is empty
            if not self.check_database_empty():
                if force:
                    logger.warning("Database contains data but force mode is enabled")
                    # Check for environment variable to skip prompt
                    if os.getenv("BOOTSTRAP_FORCE") == "yes":
                        logger.info("Force mode confirmed via environment variable")
                        self.clear_database()
                    else:
                        response = input("Are you sure you want to clear the existing database? (yes/no): ")
                        if response.lower() != "yes":
                            logger.info("Bootstrap cancelled")
                            return False
                        self.clear_database()
                else:
                    logger.warning("Database already contains data. Use --force to overwrite.")
                    return False
            
            # Load export data
            logger.info("Loading export data...")
            with open(import_file, 'r') as f:
                export_data = json.load(f)
            
            logger.info(f"Export metadata: {export_data['metadata']}")
            
            # Create indexes first
            self.create_indexes()
            
            # Import nodes
            self.import_nodes(export_data["nodes"])
            
            # Import relationships
            self.import_relationships(export_data["relationships"])
            
            # Verify import
            if self.verify_import(export_data):
                logger.info("Import verification passed!")
            else:
                logger.warning("Import verification failed!")
            
            # Fix chunk relationships if needed
            logger.info("Checking and fixing chunk relationships...")
            self._fix_chunk_relationships()
            
            # Print summary
            logger.info("\nImport Summary:")
            logger.info(f"- Nodes imported: {self.import_stats['nodes_imported']}")
            logger.info(f"- Relationships imported: {self.import_stats['relationships_imported']}")
            logger.info(f"- Errors: {len(self.import_stats['errors'])}")
            
            if self.import_stats['errors']:
                logger.warning(f"First 5 errors: {self.import_stats['errors'][:5]}")
            
            return True
            
        except Exception as e:
            logger.error(f"Bootstrap failed: {e}")
            raise


def main():
    """Main function to run the bootstrap."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Bootstrap Neo4j from export file")
    parser.add_argument("--file", type=str, help="Path to export file (default: latest)")
    parser.add_argument("--force", action="store_true", help="Force bootstrap even if database has data")
    args = parser.parse_args()
    
    # Get configuration from environment or use defaults
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "knowledge123")
    
    # Determine import file
    backup_dir = "/data/backups"
    if args.file:
        import_file = args.file
    else:
        # Use latest export
        latest_link = os.path.join(backup_dir, "latest_export.json")
        if os.path.exists(latest_link):
            import_file = latest_link
        else:
            logger.error("No export file found. Please run export first or specify --file")
            sys.exit(1)
    
    if not os.path.exists(import_file):
        logger.error(f"Import file not found: {import_file}")
        sys.exit(1)
    
    # Create bootstrapper and run import
    bootstrapper = Neo4jBootstrapper(neo4j_uri, neo4j_user, neo4j_password)
    
    try:
        success = bootstrapper.bootstrap_from_file(import_file, force=args.force)
        sys.exit(0 if success else 1)
    finally:
        bootstrapper.close()


if __name__ == "__main__":
    main()