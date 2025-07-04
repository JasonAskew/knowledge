"""
Community Detection for Knowledge Graph using Louvain Algorithm
Implements community detection, enrichment, and community-aware search
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


class CommunityDetector:
    """Detect and manage communities in the knowledge graph"""
    
    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        
    def close(self):
        self.driver.close()
        
    def run_louvain_detection(self, resolution: float = 1.0) -> Dict[str, int]:
        """
        Run Louvain community detection on the entity graph
        
        Args:
            resolution: Resolution parameter for community detection (higher = more communities)
            
        Returns:
            Dictionary mapping entity IDs to community IDs
        """
        logger.info("Starting Louvain community detection...")
        
        # Build NetworkX graph from Neo4j
        G = self._build_entity_graph()
        
        # Run Louvain algorithm
        communities = community_louvain.best_partition(G, resolution=resolution)
        
        logger.info(f"Detected {len(set(communities.values()))} communities")
        return communities
    
    def _build_entity_graph(self) -> nx.Graph:
        """Build NetworkX graph from Neo4j entity relationships"""
        G = nx.Graph()
        
        with self.driver.session() as session:
            # Get all entity relationships
            result = session.run("""
                MATCH (e1:Entity)-[r:RELATED_TO]->(e2:Entity)
                WHERE r.strength > 1
                RETURN id(e1) as source, id(e2) as target, r.strength as weight
            """)
            
            for record in result:
                G.add_edge(
                    record['source'], 
                    record['target'], 
                    weight=record['weight']
                )
        
        logger.info(f"Built graph with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges")
        return G
    
    def enrich_graph_with_communities(self, communities: Dict[str, int]):
        """Add community metadata to entities in Neo4j"""
        logger.info("Enriching graph with community metadata...")
        
        with self.driver.session() as session:
            # Calculate community statistics
            community_stats = self._calculate_community_stats(communities)
            
            # Update entities with community info
            batch_size = 1000
            entity_items = list(communities.items())
            
            for i in range(0, len(entity_items), batch_size):
                batch = entity_items[i:i + batch_size]
                
                session.run("""
                    UNWIND $updates as update
                    MATCH (e:Entity) 
                    WHERE id(e) = update.entity_id
                    SET e.community_id = update.community_id,
                        e.community_size = update.community_size
                """, updates=[
                    {
                        'entity_id': entity_id,
                        'community_id': comm_id,
                        'community_size': community_stats[comm_id]['size']
                    }
                    for entity_id, comm_id in batch
                ])
            
            # Calculate and set node centrality within communities
            self._calculate_community_centrality(session, communities)
            
            # Identify and mark bridge nodes
            self._identify_bridge_nodes(session)
            
        logger.info("Community enrichment complete")
    
    def _calculate_community_stats(self, communities: Dict[str, int]) -> Dict[int, Dict]:
        """Calculate statistics for each community"""
        stats = defaultdict(lambda: {'size': 0, 'entities': []})
        
        for entity_id, comm_id in communities.items():
            stats[comm_id]['size'] += 1
            stats[comm_id]['entities'].append(entity_id)
        
        return dict(stats)
    
    def _calculate_community_centrality(self, session, communities: Dict[str, int]):
        """Calculate centrality metrics within each community"""
        logger.info("Calculating community centrality metrics...")
        
        # Group entities by community
        communities_grouped = defaultdict(list)
        for entity_id, comm_id in communities.items():
            communities_grouped[comm_id].append(entity_id)
        
        for comm_id, entity_ids in communities_grouped.items():
            # Build subgraph for this community
            result = session.run("""
                MATCH (e1:Entity)-[r:RELATED_TO]->(e2:Entity)
                WHERE e1.community_id = $comm_id AND e2.community_id = $comm_id
                RETURN id(e1) as source, id(e2) as target, r.strength as weight
            """, comm_id=comm_id)
            
            # Build NetworkX subgraph
            G_comm = nx.Graph()
            for record in result:
                G_comm.add_edge(
                    record['source'],
                    record['target'],
                    weight=record['weight']
                )
            
            if G_comm.number_of_nodes() > 0:
                # Calculate centrality metrics
                degree_centrality = nx.degree_centrality(G_comm)
                betweenness_centrality = nx.betweenness_centrality(G_comm, weight='weight')
                
                # Update entities with centrality scores
                updates = []
                for node in G_comm.nodes():
                    updates.append({
                        'entity_id': node,
                        'degree_centrality': degree_centrality.get(node, 0),
                        'betweenness_centrality': betweenness_centrality.get(node, 0)
                    })
                
                if updates:
                    session.run("""
                        UNWIND $updates as update
                        MATCH (e:Entity)
                        WHERE id(e) = update.entity_id
                        SET e.community_degree_centrality = update.degree_centrality,
                            e.community_betweenness_centrality = update.betweenness_centrality
                    """, updates=updates)
    
    def _identify_bridge_nodes(self, session):
        """Identify nodes that connect different communities"""
        logger.info("Identifying bridge nodes...")
        
        # Find entities connected to multiple communities
        result = session.run("""
            MATCH (e:Entity)-[:RELATED_TO]-(neighbor:Entity)
            WHERE e.community_id <> neighbor.community_id
            WITH e, COUNT(DISTINCT neighbor.community_id) as connected_communities
            WHERE connected_communities > 1
            SET e.is_bridge_node = true,
                e.connected_communities = connected_communities
            RETURN COUNT(e) as bridge_count
        """)
        
        bridge_count = result.single()['bridge_count']
        logger.info(f"Identified {bridge_count} bridge nodes")
    
    def calculate_community_coherence(self):
        """Calculate coherence scores for each community"""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (e1:Entity)-[r:RELATED_TO]-(e2:Entity)
                WHERE e1.community_id = e2.community_id
                WITH e1.community_id as community_id,
                     AVG(r.strength) as avg_internal_strength,
                     COUNT(r) as internal_edges
                MATCH (e3:Entity {community_id: community_id})
                WITH community_id, avg_internal_strength, internal_edges,
                     COUNT(DISTINCT e3) as community_size
                SET e3.community_coherence = avg_internal_strength,
                    e3.community_density = toFloat(internal_edges) / 
                        (toFloat(community_size) * (community_size - 1))
                RETURN community_id, avg_internal_strength as coherence, 
                       toFloat(internal_edges) / (toFloat(community_size) * (community_size - 1)) as density
                ORDER BY coherence DESC
            """)
            
            coherence_scores = {}
            for record in result:
                coherence_scores[record['community_id']] = {
                    'coherence': record['coherence'],
                    'density': record['density']
                }
            
            return coherence_scores


class CommunityAwareSearch:
    """Implement two-phase search using community structure"""
    
    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
    
    def close(self):
        self.driver.close()
    
    def search(self, query_embedding: np.ndarray, query_entities: List[str], 
               top_k: int = 10, community_weight: float = 0.3) -> List[Dict]:
        """
        Two-phase community-aware search
        
        Phase 1: Search within relevant communities
        Phase 2: Search bridge nodes if needed
        """
        # Identify relevant communities based on query entities
        relevant_communities = self._identify_relevant_communities(query_entities)
        
        # Phase 1: Search within communities
        phase1_results = self._search_within_communities(
            query_embedding, relevant_communities, top_k * 2
        )
        
        # Phase 2: Search bridge nodes if we need more results
        if len(phase1_results) < top_k:
            bridge_results = self._search_bridge_nodes(
                query_embedding, relevant_communities, top_k
            )
            phase1_results.extend(bridge_results)
        
        # Rank results using community metrics
        ranked_results = self._rank_with_community_metrics(
            phase1_results, query_entities, community_weight
        )
        
        return ranked_results[:top_k]
    
    def _identify_relevant_communities(self, query_entities: List[str]) -> Set[int]:
        """Identify communities relevant to the query"""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (e:Entity)
                WHERE e.text IN $entities
                RETURN DISTINCT e.community_id as community_id
            """, entities=query_entities)
            
            return {record['community_id'] for record in result}
    
    def _search_within_communities(self, query_embedding: np.ndarray, 
                                  communities: Set[int], limit: int) -> List[Dict]:
        """Search for chunks within specific communities"""
        with self.driver.session() as session:
            # Convert embedding to list for Cypher
            embedding_list = query_embedding.tolist()
            
            result = session.run("""
                MATCH (c:Chunk)-[:CONTAINS_ENTITY]->(e:Entity)
                WHERE e.community_id IN $communities
                WITH c, COUNT(DISTINCT e.community_id) as community_coverage,
                     AVG(e.community_degree_centrality) as avg_centrality
                WITH c, community_coverage, avg_centrality,
                     reduce(similarity = 0.0, i IN range(0, size(c.embedding)-1) |
                        similarity + c.embedding[i] * $query_embedding[i]
                     ) as cosine_similarity
                MATCH (c)<-[:HAS_CHUNK]-(d:Document)
                RETURN c.id as chunk_id,
                       c.text as text,
                       c.page_num as page_num,
                       d.filename as document,
                       cosine_similarity,
                       community_coverage,
                       avg_centrality
                ORDER BY cosine_similarity DESC
                LIMIT $limit
            """, communities=list(communities), query_embedding=embedding_list, limit=limit)
            
            return [dict(record) for record in result]
    
    def _search_bridge_nodes(self, query_embedding: np.ndarray, 
                            relevant_communities: Set[int], limit: int) -> List[Dict]:
        """Search chunks connected to bridge nodes"""
        with self.driver.session() as session:
            embedding_list = query_embedding.tolist()
            
            result = session.run("""
                MATCH (c:Chunk)-[:CONTAINS_ENTITY]->(e:Entity)
                WHERE e.is_bridge_node = true
                  AND ANY(comm IN e.connected_communities WHERE comm IN $communities)
                WITH c, e.connected_communities as bridge_importance,
                     reduce(similarity = 0.0, i IN range(0, size(c.embedding)-1) |
                        similarity + c.embedding[i] * $query_embedding[i]
                     ) as cosine_similarity
                MATCH (c)<-[:HAS_CHUNK]-(d:Document)
                RETURN c.id as chunk_id,
                       c.text as text,
                       c.page_num as page_num,
                       d.filename as document,
                       cosine_similarity,
                       0 as community_coverage,
                       bridge_importance as avg_centrality
                ORDER BY cosine_similarity DESC
                LIMIT $limit
            """, communities=list(relevant_communities), 
                 query_embedding=embedding_list, limit=limit)
            
            return [dict(record) for record in result]
    
    def _rank_with_community_metrics(self, results: List[Dict], 
                                    query_entities: List[str], 
                                    community_weight: float) -> List[Dict]:
        """Rank results using community metrics"""
        # Calculate final scores
        for result in results:
            # Base score from cosine similarity
            base_score = result['cosine_similarity']
            
            # Community bonus based on coverage and centrality
            community_bonus = (
                result['community_coverage'] * 0.5 +
                result['avg_centrality'] * 0.5
            ) * community_weight
            
            # Final score
            result['final_score'] = base_score * (1 - community_weight) + community_bonus
            result['community_metrics'] = {
                'coverage': result['community_coverage'],
                'avg_centrality': result['avg_centrality']
            }
        
        # Sort by final score
        return sorted(results, key=lambda x: x['final_score'], reverse=True)


def create_community_search_index(uri: str, user: str, password: str):
    """Create indexes for efficient community-based search"""
    driver = GraphDatabase.driver(uri, auth=(user, password))
    
    with driver.session() as session:
        # Index for community-based queries
        session.run("""
            CREATE INDEX entity_community IF NOT EXISTS
            FOR (e:Entity) ON (e.community_id)
        """)
        
        # Index for bridge node queries
        session.run("""
            CREATE INDEX entity_bridge IF NOT EXISTS
            FOR (e:Entity) ON (e.is_bridge_node)
        """)
        
        # Composite index for community metrics
        session.run("""
            CREATE INDEX entity_centrality IF NOT EXISTS
            FOR (e:Entity) ON (e.community_degree_centrality)
        """)
    
    driver.close()
    logger.info("Created community search indexes")


if __name__ == "__main__":
    # Example usage
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    # Neo4j connection
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "knowledge123")
    
    # Run community detection
    detector = CommunityDetector(uri, user, password)
    
    try:
        # Detect communities
        communities = detector.run_louvain_detection(resolution=1.2)
        
        # Enrich graph
        detector.enrich_graph_with_communities(communities)
        
        # Calculate coherence
        coherence_scores = detector.calculate_community_coherence()
        
        print(f"Community coherence scores: {json.dumps(coherence_scores, indent=2)}")
        
        # Create indexes
        create_community_search_index(uri, user, password)
        
    finally:
        detector.close()