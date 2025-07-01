#!/usr/bin/env python3
"""
Neo4j Knowledge Graph Export Script

This script exports the entire Neo4j database including:
- All nodes with properties and labels
- All relationships with properties and types
- Vector embeddings
- Metadata and timestamps

The export is saved in a JSON format that can be easily reimported.
"""

import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Any
import logging
from neo4j import GraphDatabase
import numpy as np

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class Neo4jExporter:
    def __init__(self, uri: str, user: str, password: str):
        """Initialize the Neo4j exporter with connection details."""
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.export_data = {
            "metadata": {
                "export_timestamp": datetime.now().isoformat(),
                "version": "1.0",
                "neo4j_uri": uri
            },
            "nodes": [],
            "relationships": [],
            "statistics": {}
        }
    
    def close(self):
        """Close the Neo4j driver connection."""
        self.driver.close()
    
    def _serialize_value(self, value: Any) -> Any:
        """Serialize values for JSON export, handling special types."""
        if isinstance(value, (list, tuple)) and len(value) > 0 and isinstance(value[0], (int, float)):
            # Handle vector embeddings
            return {
                "_type": "vector",
                "values": list(value),
                "dimension": len(value)
            }
        elif isinstance(value, datetime):
            return {
                "_type": "datetime",
                "value": value.isoformat()
            }
        elif isinstance(value, bytes):
            return {
                "_type": "bytes",
                "value": value.hex()
            }
        elif isinstance(value, (dict, list, tuple)):
            # Recursively serialize nested structures
            if isinstance(value, dict):
                return {k: self._serialize_value(v) for k, v in value.items()}
            else:
                return [self._serialize_value(v) for v in value]
        else:
            return value
    
    def export_nodes(self) -> int:
        """Export all nodes from the database."""
        logger.info("Exporting nodes...")
        
        query = """
        MATCH (n)
        RETURN n, labels(n) as labels, id(n) as node_id
        ORDER BY id(n)
        """
        
        count = 0
        with self.driver.session() as session:
            result = session.run(query)
            
            for record in result:
                node = record["n"]
                node_data = {
                    "id": record["node_id"],
                    "labels": record["labels"],
                    "properties": {}
                }
                
                # Serialize all properties
                for key, value in node.items():
                    node_data["properties"][key] = self._serialize_value(value)
                
                self.export_data["nodes"].append(node_data)
                count += 1
                
                if count % 1000 == 0:
                    logger.info(f"Exported {count} nodes...")
        
        logger.info(f"Total nodes exported: {count}")
        return count
    
    def export_relationships(self) -> int:
        """Export all relationships from the database."""
        logger.info("Exporting relationships...")
        
        query = """
        MATCH (a)-[r]->(b)
        RETURN id(r) as rel_id, type(r) as rel_type, 
               id(a) as start_id, id(b) as end_id, r
        ORDER BY id(r)
        """
        
        count = 0
        with self.driver.session() as session:
            result = session.run(query)
            
            for record in result:
                rel = record["r"]
                rel_data = {
                    "id": record["rel_id"],
                    "type": record["rel_type"],
                    "start_node_id": record["start_id"],
                    "end_node_id": record["end_id"],
                    "properties": {}
                }
                
                # Serialize all properties
                for key, value in rel.items():
                    rel_data["properties"][key] = self._serialize_value(value)
                
                self.export_data["relationships"].append(rel_data)
                count += 1
                
                if count % 1000 == 0:
                    logger.info(f"Exported {count} relationships...")
        
        logger.info(f"Total relationships exported: {count}")
        return count
    
    def collect_statistics(self):
        """Collect database statistics."""
        logger.info("Collecting database statistics...")
        
        stats_queries = {
            "node_count_by_label": """
                MATCH (n)
                RETURN labels(n)[0] as label, count(n) as count
                ORDER BY count DESC
            """,
            "relationship_count_by_type": """
                MATCH ()-[r]->()
                RETURN type(r) as rel_type, count(r) as count
                ORDER BY count DESC
            """,
            "total_nodes": "MATCH (n) RETURN count(n) as count",
            "total_relationships": "MATCH ()-[r]->() RETURN count(r) as count",
            "documents_with_embeddings": """
                MATCH (d:Document)
                WHERE d.embedding IS NOT NULL
                RETURN count(d) as count
            """,
            "chunks_with_embeddings": """
                MATCH (c:Chunk)
                WHERE c.embedding IS NOT NULL
                RETURN count(c) as count
            """
        }
        
        with self.driver.session() as session:
            for stat_name, query in stats_queries.items():
                try:
                    result = session.run(query)
                    if stat_name.endswith("_by_label") or stat_name.endswith("_by_type"):
                        self.export_data["statistics"][stat_name] = [
                            dict(record) for record in result
                        ]
                    else:
                        self.export_data["statistics"][stat_name] = result.single()["count"]
                except Exception as e:
                    logger.warning(f"Failed to collect statistic {stat_name}: {e}")
    
    def save_export(self, output_path: str):
        """Save the export data to a JSON file."""
        logger.info(f"Saving export to {output_path}")
        
        # Add final statistics
        self.export_data["statistics"]["exported_nodes"] = len(self.export_data["nodes"])
        self.export_data["statistics"]["exported_relationships"] = len(self.export_data["relationships"])
        
        # Save to file
        with open(output_path, 'w') as f:
            json.dump(self.export_data, f, indent=2)
        
        # Get file size
        file_size = os.path.getsize(output_path)
        logger.info(f"Export saved successfully. File size: {file_size / 1024 / 1024:.2f} MB")
    
    def export_to_file(self, output_path: str):
        """Main export method that orchestrates the entire export process."""
        try:
            logger.info("Starting Neo4j export...")
            
            # Export nodes
            node_count = self.export_nodes()
            
            # Export relationships
            rel_count = self.export_relationships()
            
            # Collect statistics
            self.collect_statistics()
            
            # Save to file
            self.save_export(output_path)
            
            logger.info(f"Export completed successfully!")
            logger.info(f"Exported {node_count} nodes and {rel_count} relationships")
            
        except Exception as e:
            logger.error(f"Export failed: {e}")
            raise


def main():
    """Main function to run the export."""
    # Get configuration from environment or use defaults
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "knowledge123")
    
    # Create backup directory if it doesn't exist
    backup_dir = "/data/backups"
    os.makedirs(backup_dir, exist_ok=True)
    
    # Generate output filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(backup_dir, f"neo4j_export_{timestamp}.json")
    
    # Create exporter and run export
    exporter = Neo4jExporter(neo4j_uri, neo4j_user, neo4j_password)
    
    try:
        exporter.export_to_file(output_file)
        
        # Create a symlink to the latest export
        latest_link = os.path.join(backup_dir, "latest_export.json")
        if os.path.exists(latest_link):
            os.remove(latest_link)
        os.symlink(output_file, latest_link)
        
        print(f"Export completed: {output_file}")
        print(f"Latest export link: {latest_link}")
        
    finally:
        exporter.close()


if __name__ == "__main__":
    main()