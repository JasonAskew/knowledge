#!/usr/bin/env python3
"""
Design for hierarchical ontology enhancement to existing community detection
"""

import logging
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict
import numpy as np
from neo4j import GraphDatabase
import networkx as nx
from community import community_louvain
import json

logger = logging.getLogger(__name__)

class HierarchicalOntologyEnhancer:
    """
    Enhance existing community detection with hierarchical ontology layers
    
    Current: 42 flat communities with bridge nodes
    Enhancement: Add domain/subdomain hierarchy + semantic relationships
    """
    
    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        
        # Banking domain ontology structure
        self.domain_hierarchy = {
            "BANKING_OPERATIONS": {
                "ACCOUNTS": ["savings", "checking", "current", "deposit", "withdrawal"],
                "PAYMENTS": ["transfer", "wire", "telegraphic", "international", "domestic"],
                "CARDS": ["credit", "debit", "lost", "stolen", "replacement", "activation"],
                "LOANS": ["home", "personal", "business", "mortgage", "refinance"],
                "FEES": ["charges", "costs", "pricing", "tariff", "schedule"]
            },
            "COMPLIANCE": {
                "TERMS_CONDITIONS": ["agreement", "contract", "policy", "procedure"],
                "REGULATORY": ["compliance", "requirement", "legislation", "mandate"],
                "DOCUMENTATION": ["form", "application", "verification", "proof"]
            },
            "CUSTOMER_SERVICE": {
                "SUPPORT": ["help", "assistance", "contact", "inquiry"],
                "PROCESSES": ["opening", "closing", "changing", "updating"],
                "PROBLEMS": ["issue", "complaint", "dispute", "resolution"]
            }
        }
    
    def create_hierarchical_structure(self):
        """Create hierarchical domain structure overlaying communities"""
        logger.info("Creating hierarchical ontology structure...")
        
        with self.driver.session() as session:
            # Step 1: Create domain and subdomain nodes
            self._create_domain_nodes(session)
            
            # Step 2: Classify existing communities into domains
            self._classify_communities_to_domains(session)
            
            # Step 3: Create semantic relationships between entities
            self._create_semantic_relationships(session)
            
            # Step 4: Add hierarchical search paths
            self._create_hierarchical_search_paths(session)
    
    def _create_domain_nodes(self, session):
        """Create domain and subdomain nodes"""
        logger.info("Creating domain hierarchy nodes...")
        
        for domain, subdomains in self.domain_hierarchy.items():
            # Create domain node
            session.run("""
                MERGE (d:Domain {name: $domain})
                SET d.level = 1, d.type = 'domain'
            """, domain=domain)
            
            for subdomain, keywords in subdomains.items():
                # Create subdomain node
                session.run("""
                    MERGE (d:Domain {name: $domain})
                    MERGE (sd:Subdomain {name: $subdomain})
                    MERGE (d)-[:HAS_SUBDOMAIN]->(sd)
                    SET sd.level = 2, sd.type = 'subdomain',
                        sd.keywords = $keywords
                """, domain=domain, subdomain=subdomain, keywords=keywords)
    
    def _classify_communities_to_domains(self, session):
        """Classify existing communities into domain hierarchy"""
        logger.info("Classifying communities into domains...")
        
        # Get community statistics with entity text analysis
        result = session.run("""
            MATCH (e:Entity)
            WHERE e.community_id IS NOT NULL
            WITH e.community_id as community_id, 
                 collect(toLower(e.text)) as entity_texts
            RETURN community_id, entity_texts
        """)
        
        community_classifications = {}
        
        for record in result:
            comm_id = record['community_id']
            entity_texts = record['entity_texts']
            
            # Score community against each subdomain
            best_match = self._score_community_against_domains(entity_texts)
            community_classifications[comm_id] = best_match
            
            if best_match:
                # Create relationship between community and subdomain
                session.run("""
                    MATCH (e:Entity {community_id: $comm_id})
                    MATCH (sd:Subdomain {name: $subdomain})
                    WITH e, sd
                    LIMIT 1
                    MERGE (sd)-[:CONTAINS_COMMUNITY {community_id: $comm_id}]->(e)
                """, comm_id=comm_id, subdomain=best_match['subdomain'])
        
        logger.info(f"Classified {len(community_classifications)} communities")
        return community_classifications
    
    def _score_community_against_domains(self, entity_texts: List[str]) -> Optional[Dict]:
        """Score a community's entities against domain keywords"""
        best_score = 0
        best_match = None
        
        for domain, subdomains in self.domain_hierarchy.items():
            for subdomain, keywords in subdomains.items():
                # Calculate keyword overlap score
                matches = 0
                for text in entity_texts:
                    for keyword in keywords:
                        if keyword in text:
                            matches += 1
                
                score = matches / len(entity_texts) if entity_texts else 0
                
                if score > best_score and score > 0.1:  # Minimum threshold
                    best_score = score
                    best_match = {
                        'domain': domain,
                        'subdomain': subdomain,
                        'score': score,
                        'matches': matches
                    }
        
        return best_match
    
    def _create_semantic_relationships(self, session):
        """Create semantic relationships between entities based on hierarchy"""
        logger.info("Creating semantic relationships...")
        
        # Create SEMANTIC_PARENT relationships within domains
        session.run("""
            MATCH (e1:Entity)-[:RELATED_TO]-(e2:Entity)
            MATCH (sd1:Subdomain)-[:CONTAINS_COMMUNITY {community_id: e1.community_id}]->()
            MATCH (sd2:Subdomain)-[:CONTAINS_COMMUNITY {community_id: e2.community_id}]->()
            MATCH (d:Domain)-[:HAS_SUBDOMAIN]->(sd1)
            MATCH (d)-[:HAS_SUBDOMAIN]->(sd2)
            WHERE e1.community_id <> e2.community_id
            MERGE (e1)-[:SEMANTIC_SIBLING {domain: d.name}]->(e2)
        """)
        
        # Create hierarchical paths for search
        session.run("""
            MATCH (d:Domain)-[:HAS_SUBDOMAIN]->(sd:Subdomain)
            MATCH (sd)-[:CONTAINS_COMMUNITY]->(e:Entity)
            MERGE (d)-[:HIERARCHICAL_CONTAINS]->(e)
            SET e.domain = d.name, e.subdomain = sd.name
        """)
    
    def _create_hierarchical_search_paths(self, session):
        """Create indexed paths for efficient hierarchical search"""
        logger.info("Creating hierarchical search indexes...")
        
        # Index for domain-based search
        session.run("""
            CREATE INDEX entity_domain_search IF NOT EXISTS
            FOR (e:Entity) ON (e.domain, e.subdomain)
        """)
        
        # Create search views for each domain
        for domain in self.domain_hierarchy.keys():
            session.run("""
                MATCH (e:Entity {domain: $domain})-[:CONTAINS_ENTITY]-(c:Chunk)
                SET c.domain = $domain
            """, domain=domain)


class HierarchicalSearch:
    """Enhanced search using hierarchical ontology + communities"""
    
    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
    
    def hierarchical_search(self, query: str, query_embedding: np.ndarray, 
                          top_k: int = 10) -> List[Dict]:
        """
        Multi-level hierarchical search:
        1. Domain classification of query
        2. Subdomain refinement
        3. Community-level search
        4. Cross-hierarchy bridge exploration
        """
        
        # Step 1: Classify query into domain/subdomain
        query_classification = self._classify_query(query)
        
        # Step 2: Search within classified domain/subdomain
        domain_results = self._search_within_domain(
            query_embedding, query_classification, top_k * 2
        )
        
        # Step 3: Expand to semantic siblings if needed
        if len(domain_results) < top_k:
            sibling_results = self._search_semantic_siblings(
                query_embedding, query_classification, top_k
            )
            domain_results.extend(sibling_results)
        
        # Step 4: Bridge to other domains if still needed
        if len(domain_results) < top_k:
            bridge_results = self._search_cross_domain_bridges(
                query_embedding, query_classification, top_k
            )
            domain_results.extend(bridge_results)
        
        return self._rank_hierarchical_results(domain_results, query_classification)[:top_k]
    
    def _classify_query(self, query: str) -> Dict:
        """Classify query into domain/subdomain"""
        # Implementation for query classification
        # Could use embeddings or keyword matching
        pass
    
    def _search_within_domain(self, query_embedding: np.ndarray, 
                             classification: Dict, limit: int) -> List[Dict]:
        """Search within classified domain"""
        pass
    
    def _search_semantic_siblings(self, query_embedding: np.ndarray,
                                 classification: Dict, limit: int) -> List[Dict]:
        """Search semantic siblings in same domain"""
        pass
    
    def _search_cross_domain_bridges(self, query_embedding: np.ndarray,
                                    classification: Dict, limit: int) -> List[Dict]:
        """Search across domain boundaries via bridge entities"""
        pass
    
    def _rank_hierarchical_results(self, results: List[Dict], 
                                  classification: Dict) -> List[Dict]:
        """Rank results using hierarchical metrics"""
        pass


# Performance comparison analysis
HIERARCHY_VS_FLAT_ANALYSIS = {
    "current_system": {
        "communities": 42,
        "entities": 10150,
        "structure": "flat_communities_with_bridges",
        "search_complexity": "O(n) within community",
        "accuracy": "80%+ keyword, 88.8% hybrid"
    },
    "hierarchical_enhancement": {
        "estimated_domains": 3,
        "estimated_subdomains": 15,
        "structure": "3_level_hierarchy_over_communities", 
        "search_complexity": "O(log n) domain classification + O(m) subdomain",
        "expected_benefits": [
            "Faster query routing to relevant domains",
            "Better semantic understanding", 
            "Reduced search space for domain-specific queries",
            "Improved precision for banking terminology"
        ],
        "implementation_effort": "medium_complexity",
        "performance_impact": "minimal_overhead_significant_gains"
    }
}

if __name__ == "__main__":
    print("Hierarchical Ontology Design Analysis")
    print("=" * 50)
    print(json.dumps(HIERARCHY_VS_FLAT_ANALYSIS, indent=2))