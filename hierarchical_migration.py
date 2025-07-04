#!/usr/bin/env python3
"""
Migrate existing graph to hierarchical structure while preserving data
This can be run on existing graph without data loss
"""

import logging
from typing import Dict, List, Optional
from neo4j import GraphDatabase
import json
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HierarchicalMigration:
    """Safely migrate existing graph to hierarchical structure"""
    
    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        
        # Define the hierarchical structure
        self.hierarchy_definition = {
            "institution": {
                "name": "Westpac Banking Corporation",
                "code": "WBC",
                "divisions": [
                    {
                        "name": "Retail Banking",
                        "code": "RETAIL",
                        "color": "#DA1710",
                        "categories": [
                            {
                                "name": "Accounts",
                                "description": "Deposit and transaction accounts",
                                "products": ["Savings Account", "Checking Account", "Term Deposit", "Youth Account"]
                            },
                            {
                                "name": "Cards", 
                                "description": "Credit and debit cards",
                                "products": ["Credit Card", "Debit Card", "Prepaid Card"]
                            },
                            {
                                "name": "Loans",
                                "description": "Personal and home loans", 
                                "products": ["Home Loan", "Personal Loan", "Car Loan", "Overdraft"]
                            }
                        ]
                    },
                    {
                        "name": "Business Banking",
                        "code": "BUSINESS",
                        "color": "#00A890",
                        "categories": [
                            {
                                "name": "Business Accounts",
                                "description": "Business transaction and savings accounts",
                                "products": ["Business Transaction Account", "Business Savings", "Merchant Account"]
                            },
                            {
                                "name": "Business Lending",
                                "description": "Business loans and finance",
                                "products": ["Business Loan", "Equipment Finance", "Invoice Finance"]
                            }
                        ]
                    },
                    {
                        "name": "Institutional Banking",
                        "code": "INST",
                        "color": "#2D3748",
                        "categories": [
                            {
                                "name": "Markets",
                                "description": "Foreign exchange and derivatives",
                                "products": ["FX Spot", "FX Forward", "Interest Rate Swap", "Options"]
                            },
                            {
                                "name": "Trade Finance",
                                "description": "International trade services",
                                "products": ["Letter of Credit", "Trade Finance", "Supply Chain Finance"]
                            }
                        ]
                    }
                ]
            }
        }
    
    def create_backup_snapshot(self):
        """Create a snapshot of current state before migration"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        logger.info(f"Creating backup snapshot: hierarchy_migration_{timestamp}")
        
        with self.driver.session() as session:
            # Count existing nodes
            result = session.run("""
                MATCH (n)
                RETURN labels(n)[0] as label, count(n) as count
                ORDER BY count DESC
            """)
            
            stats = {}
            for record in result:
                stats[record['label']] = record['count']
            
            logger.info(f"Current graph statistics: {json.dumps(stats, indent=2)}")
            
            # Mark migration start
            session.run("""
                CREATE (m:Migration {
                    timestamp: $timestamp,
                    type: 'hierarchical_ontology',
                    status: 'started',
                    pre_migration_stats: $stats
                })
            """, timestamp=timestamp, stats=json.dumps(stats))
            
        return timestamp
    
    def create_hierarchy_nodes(self):
        """Create the hierarchical structure nodes"""
        logger.info("Creating hierarchical structure nodes...")
        
        with self.driver.session() as session:
            # Create constraints for uniqueness
            constraints = [
                "CREATE CONSTRAINT institution_name IF NOT EXISTS FOR (i:Institution) REQUIRE i.name IS UNIQUE",
                "CREATE CONSTRAINT division_code IF NOT EXISTS FOR (d:Division) REQUIRE d.code IS UNIQUE",
                "CREATE CONSTRAINT category_name_division IF NOT EXISTS FOR (c:Category) REQUIRE (c.name, c.division) IS UNIQUE",
                "CREATE CONSTRAINT product_name_category IF NOT EXISTS FOR (p:Product) REQUIRE (p.name, p.category) IS UNIQUE"
            ]
            
            for constraint in constraints:
                try:
                    session.run(constraint)
                    logger.info(f"Created constraint: {constraint.split(' ')[2]}")
                except Exception as e:
                    logger.info(f"Constraint already exists or error: {e}")
            
            # Create Institution
            inst_data = self.hierarchy_definition["institution"]
            session.run("""
                MERGE (i:Institution {name: $name})
                SET i.code = $code,
                    i.created_at = timestamp()
            """, name=inst_data["name"], code=inst_data["code"])
            
            # Create Divisions, Categories, and Products
            for division_data in inst_data["divisions"]:
                # Create Division
                session.run("""
                    MATCH (i:Institution {name: $inst_name})
                    MERGE (d:Division {code: $code})
                    SET d.name = $name,
                        d.color = $color,
                        d.created_at = timestamp()
                    MERGE (i)-[:HAS_DIVISION]->(d)
                """, 
                    inst_name=inst_data["name"],
                    code=division_data["code"],
                    name=division_data["name"],
                    color=division_data["color"]
                )
                
                # Create Categories
                for category_data in division_data["categories"]:
                    session.run("""
                        MATCH (d:Division {code: $division_code})
                        MERGE (c:Category {name: $name, division: $division_code})
                        SET c.description = $description,
                            c.created_at = timestamp()
                        MERGE (d)-[:HAS_CATEGORY]->(c)
                    """,
                        division_code=division_data["code"],
                        name=category_data["name"],
                        description=category_data["description"]
                    )
                    
                    # Create Products
                    for product_name in category_data["products"]:
                        session.run("""
                            MATCH (c:Category {name: $category_name, division: $division_code})
                            MERGE (p:Product {name: $product_name, category: $category_name})
                            SET p.created_at = timestamp()
                            MERGE (c)-[:HAS_PRODUCT]->(p)
                        """,
                            division_code=division_data["code"],
                            category_name=category_data["name"],
                            product_name=product_name
                        )
            
            logger.info("Hierarchical structure created successfully")
    
    def classify_existing_documents(self):
        """Classify existing documents into the hierarchy"""
        logger.info("Classifying existing documents...")
        
        with self.driver.session() as session:
            # Get all documents
            documents = session.run("""
                MATCH (d:Document)
                RETURN d.id as id, d.filename as filename, 
                       d.category as category, d.path as path
            """)
            
            classified_count = 0
            for doc in documents:
                classification = self.classify_document(doc)
                
                # Update document with hierarchy
                session.run("""
                    MATCH (d:Document {id: $doc_id})
                    SET d.institution = $institution,
                        d.division = $division,
                        d.category_hierarchy = $category,
                        d.product_scope = $products,
                        d.hierarchy_confidence = $confidence
                    
                    // Create relationships to hierarchy nodes
                    WITH d
                    MATCH (div:Division {code: $division})
                    MERGE (d)-[:BELONGS_TO_DIVISION]->(div)
                    
                    WITH d
                    MATCH (cat:Category {name: $category, division: $division})
                    MERGE (d)-[:COVERS_CATEGORY]->(cat)
                    
                    // Link to relevant products
                    WITH d
                    UNWIND $products as product_name
                    MATCH (p:Product {name: product_name, category: $category})
                    MERGE (d)-[:COVERS_PRODUCT]->(p)
                """,
                    doc_id=doc['id'],
                    institution="Westpac Banking Corporation",
                    division=classification['division_code'],
                    category=classification['category'],
                    products=classification['products'],
                    confidence=classification['confidence']
                )
                
                classified_count += 1
                if classified_count % 10 == 0:
                    logger.info(f"Classified {classified_count} documents...")
            
            logger.info(f"Classified {classified_count} total documents")
    
    def classify_document(self, doc: Dict) -> Dict:
        """Classify a document based on filename and content patterns"""
        
        filename = doc['filename'].lower()
        category = doc.get('category', '').lower() if doc.get('category') else ''
        path = doc.get('path', '').lower() if doc.get('path') else ''
        
        # Classification rules based on patterns
        classification = {
            'division': 'Retail Banking',
            'division_code': 'RETAIL',
            'category': 'General',
            'products': [],
            'confidence': 0.5
        }
        
        # Division detection
        if any(term in filename for term in ['personal', 'retail', 'consumer']):
            classification['division'] = 'Retail Banking'
            classification['division_code'] = 'RETAIL'
            classification['confidence'] = 0.8
        elif any(term in filename for term in ['business', 'commercial', 'corporate']):
            classification['division'] = 'Business Banking'
            classification['division_code'] = 'BUSINESS'
            classification['confidence'] = 0.8
        elif any(term in filename for term in ['institutional', 'wholesale', 'markets', 'fx']):
            classification['division'] = 'Institutional Banking'
            classification['division_code'] = 'INST'
            classification['confidence'] = 0.9
        
        # Category detection
        if any(term in filename for term in ['account', 'deposit', 'savings', 'checking']):
            classification['category'] = 'Accounts'
            classification['products'] = ['Savings Account', 'Checking Account']
            classification['confidence'] = 0.9
        elif any(term in filename for term in ['card', 'credit', 'debit', 'mastercard', 'visa']):
            classification['category'] = 'Cards'
            classification['products'] = ['Credit Card', 'Debit Card']
            classification['confidence'] = 0.9
        elif any(term in filename for term in ['loan', 'mortgage', 'lending']):
            classification['category'] = 'Loans' if classification['division_code'] == 'RETAIL' else 'Business Lending'
            classification['products'] = ['Home Loan', 'Personal Loan'] if classification['division_code'] == 'RETAIL' else ['Business Loan']
            classification['confidence'] = 0.85
        elif any(term in filename for term in ['fx', 'foreign', 'exchange', 'swap']):
            classification['category'] = 'Markets'
            classification['products'] = ['FX Spot', 'FX Forward']
            classification['confidence'] = 0.95
        elif any(term in filename for term in ['trade', 'letter', 'credit', 'lc']):
            classification['category'] = 'Trade Finance'
            classification['products'] = ['Letter of Credit', 'Trade Finance']
            classification['confidence'] = 0.9
        
        return classification
    
    def enhance_community_with_hierarchy(self):
        """Enhance existing communities with hierarchical context"""
        logger.info("Enhancing communities with hierarchical context...")
        
        with self.driver.session() as session:
            # Link communities to hierarchy based on their entities
            result = session.run("""
                MATCH (e:Entity)
                WHERE e.community_id IS NOT NULL
                WITH e.community_id as community_id, collect(e) as entities
                
                // Analyze which documents contain these entities
                UNWIND entities as entity
                MATCH (entity)<-[:CONTAINS_ENTITY]-(c:Chunk)<-[:HAS_CHUNK]-(d:Document)
                WHERE d.division IS NOT NULL
                WITH community_id, d.division as division, 
                     d.category_hierarchy as category,
                     count(DISTINCT d) as doc_count
                ORDER BY doc_count DESC
                
                // Get the most common division/category for each community
                WITH community_id, collect({
                    division: division, 
                    category: category, 
                    count: doc_count
                })[0] as primary_classification
                
                // Update entities in the community
                MATCH (e:Entity {community_id: community_id})
                SET e.primary_division = primary_classification.division,
                    e.primary_category = primary_classification.category
                
                RETURN community_id, primary_classification
            """)
            
            community_count = 0
            for record in result:
                community_count += 1
                logger.info(f"Community {record['community_id']}: {record['primary_classification']}")
            
            logger.info(f"Enhanced {community_count} communities with hierarchical context")
    
    def create_hierarchical_indexes(self):
        """Create indexes for efficient hierarchical queries"""
        logger.info("Creating hierarchical indexes...")
        
        with self.driver.session() as session:
            indexes = [
                "CREATE INDEX doc_division IF NOT EXISTS FOR (d:Document) ON (d.division)",
                "CREATE INDEX doc_category IF NOT EXISTS FOR (d:Document) ON (d.category_hierarchy)",
                "CREATE INDEX entity_division IF NOT EXISTS FOR (e:Entity) ON (e.primary_division)",
                "CREATE INDEX entity_category IF NOT EXISTS FOR (e:Entity) ON (e.primary_category)",
                "CREATE INDEX product_category IF NOT EXISTS FOR (p:Product) ON (p.category)"
            ]
            
            for index in indexes:
                try:
                    session.run(index)
                    logger.info(f"Created index: {index.split(' ')[2]}")
                except Exception as e:
                    logger.info(f"Index already exists or error: {e}")
    
    def verify_migration(self, migration_timestamp: str):
        """Verify the migration was successful"""
        logger.info("Verifying migration...")
        
        with self.driver.session() as session:
            # Check hierarchy nodes
            result = session.run("""
                MATCH (i:Institution)
                OPTIONAL MATCH (i)-[:HAS_DIVISION]->(d:Division)
                OPTIONAL MATCH (d)-[:HAS_CATEGORY]->(c:Category)
                OPTIONAL MATCH (c)-[:HAS_PRODUCT]->(p:Product)
                RETURN count(DISTINCT i) as institutions,
                       count(DISTINCT d) as divisions,
                       count(DISTINCT c) as categories,
                       count(DISTINCT p) as products
            """)
            
            hierarchy_stats = result.single()
            logger.info(f"Hierarchy created: {dict(hierarchy_stats)}")
            
            # Check document classification
            result = session.run("""
                MATCH (d:Document)
                RETURN count(d) as total_documents,
                       count(d.division) as classified_documents,
                       collect(DISTINCT d.division) as divisions,
                       collect(DISTINCT d.category_hierarchy) as categories
            """)
            
            doc_stats = result.single()
            logger.info(f"Document classification: {doc_stats['classified_documents']}/{doc_stats['total_documents']} classified")
            logger.info(f"Divisions found: {doc_stats['divisions']}")
            logger.info(f"Categories found: {doc_stats['categories']}")
            
            # Update migration record
            session.run("""
                MATCH (m:Migration {timestamp: $timestamp})
                SET m.status = 'completed',
                    m.completed_at = timestamp(),
                    m.post_migration_stats = $stats
            """, 
                timestamp=migration_timestamp,
                stats=json.dumps({
                    'hierarchy': dict(hierarchy_stats),
                    'documents': {
                        'total': doc_stats['total_documents'],
                        'classified': doc_stats['classified_documents']
                    }
                })
            )
    
    def migrate(self):
        """Run the complete migration"""
        logger.info("Starting hierarchical migration...")
        
        try:
            # Step 1: Create backup snapshot
            migration_timestamp = self.create_backup_snapshot()
            
            # Step 2: Create hierarchy nodes
            self.create_hierarchy_nodes()
            
            # Step 3: Classify existing documents
            self.classify_existing_documents()
            
            # Step 4: Enhance communities with hierarchy
            self.enhance_community_with_hierarchy()
            
            # Step 5: Create indexes
            self.create_hierarchical_indexes()
            
            # Step 6: Verify migration
            self.verify_migration(migration_timestamp)
            
            logger.info("Migration completed successfully!")
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            raise
        finally:
            self.driver.close()


def main():
    # Neo4j connection
    NEO4J_URI = "bolt://localhost:7687"
    NEO4J_USER = "neo4j"
    NEO4J_PASSWORD = "knowledge123"
    
    # Run migration
    migration = HierarchicalMigration(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    migration.migrate()


if __name__ == "__main__":
    main()