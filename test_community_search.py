#!/usr/bin/env python3
"""
Test community-aware search functionality
"""

import requests
import json
from typing import List, Dict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_URL = "http://localhost:8000"


def test_community_stats():
    """Test community statistics endpoint"""
    logger.info("Testing community statistics...")
    
    response = requests.get(f"{API_URL}/community/stats")
    if response.status_code == 200:
        stats = response.json()
        logger.info(f"Community Statistics:")
        logger.info(f"  Total communities: {stats['total_communities']}")
        logger.info(f"  Entities with communities: {stats['entities_with_communities']}")
        logger.info(f"  Bridge nodes: {stats['bridge_nodes']}")
        logger.info(f"  Average community size: {stats['avg_community_size']:.2f}")
        return stats
    else:
        logger.error(f"Failed to get community stats: {response.status_code}")
        return None


def test_community_search(query: str, community_weight: float = 0.3):
    """Test community-aware search"""
    logger.info(f"\nTesting community search for: '{query}'")
    
    payload = {
        "query": query,
        "search_type": "community",
        "top_k": 5,
        "use_reranking": True,
        "community_weight": community_weight
    }
    
    response = requests.post(f"{API_URL}/search", json=payload)
    
    if response.status_code == 200:
        results = response.json()
        logger.info(f"Found {len(results)} results")
        
        for i, result in enumerate(results, 1):
            logger.info(f"\nResult {i}:")
            logger.info(f"  Document: {result['document']}, Page: {result['page_num']}")
            logger.info(f"  Score: {result['score']:.3f}")
            logger.info(f"  Text preview: {result['text'][:100]}...")
            if result.get('community_metrics'):
                logger.info(f"  Community metrics: {result['community_metrics']}")
        
        return results
    else:
        logger.error(f"Search failed: {response.status_code} - {response.text}")
        return []


def compare_search_types(query: str):
    """Compare different search types"""
    logger.info(f"\nComparing search types for: '{query}'")
    
    search_types = ["vector", "community"]
    all_results = {}
    
    for search_type in search_types:
        payload = {
            "query": query,
            "search_type": search_type,
            "top_k": 3,
            "use_reranking": True
        }
        
        response = requests.post(f"{API_URL}/search", json=payload)
        
        if response.status_code == 200:
            results = response.json()
            all_results[search_type] = results
            
            logger.info(f"\n{search_type.upper()} search results:")
            for i, result in enumerate(results, 1):
                logger.info(f"  {i}. {result['document']} (p.{result['page_num']}) - Score: {result['score']:.3f}")
        else:
            logger.error(f"{search_type} search failed: {response.status_code}")
    
    return all_results


def test_community_entities(community_id: int = 0):
    """Test getting entities from a specific community"""
    logger.info(f"\nGetting entities from community {community_id}...")
    
    response = requests.get(f"{API_URL}/community/{community_id}/entities")
    
    if response.status_code == 200:
        data = response.json()
        entities = data['entities']
        
        logger.info(f"Top entities in community {community_id}:")
        for entity in entities[:10]:
            logger.info(f"  - {entity['entity']} ({entity['type']}) - Centrality: {entity['centrality']:.3f}")
        
        return entities
    else:
        logger.error(f"Failed to get community entities: {response.status_code}")
        return []


def main():
    # Wait for API to be ready
    import time
    max_retries = 30
    for i in range(max_retries):
        try:
            response = requests.get(f"{API_URL}/health")
            if response.status_code == 200:
                logger.info("API is ready!")
                break
        except:
            pass
        
        if i < max_retries - 1:
            logger.info(f"Waiting for API to start... ({i+1}/{max_retries})")
            time.sleep(2)
        else:
            logger.error("API failed to start!")
            return
    
    # Test community statistics
    stats = test_community_stats()
    
    if stats and stats['total_communities'] > 0:
        # Test community-aware search with different queries
        test_queries = [
            "What are the tax implications for foreign residents?",
            "How do I open a bank account?",
            "What are the eligibility requirements for youth allowance?",
            "Tell me about superannuation withdrawal rules"
        ]
        
        for query in test_queries:
            # Test with different community weights
            test_community_search(query, community_weight=0.3)
            test_community_search(query, community_weight=0.7)
        
        # Compare search types
        compare_search_types("superannuation contribution limits")
        
        # Test getting entities from first few communities
        for comm_id in range(min(3, stats['total_communities'])):
            test_community_entities(comm_id)
    else:
        logger.warning("No community data found. Please run community detection first.")


if __name__ == "__main__":
    main()