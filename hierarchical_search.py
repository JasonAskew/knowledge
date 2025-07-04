#!/usr/bin/env python3
"""
Hierarchical Search Implementation
Provides cascading search with division/category filtering
"""

import logging
from typing import Dict, List, Optional, Tuple
from neo4j import GraphDatabase
import json
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HierarchicalSearch:
    """Enhanced search with hierarchical filtering"""
    
    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
    
    def search_with_hierarchy(self, query: str, 
                            division: Optional[str] = None,
                            category: Optional[str] = None,
                            product: Optional[str] = None,
                            top_k: int = 10) -> Dict:
        """
        Search with hierarchical filtering
        
        Args:
            query: Search query text
            division: Optional division filter (RETAIL, BUSINESS, INST)
            category: Optional category filter
            product: Optional product filter
            top_k: Number of results to return
            
        Returns:
            Dict with results and metadata
        """
        logger.info(f"Hierarchical search: query='{query}', division={division}, category={category}")
        
        with self.driver.session() as session:
            # Build the filter conditions
            filter_conditions = []
            params = {'search_query': query, 'top_k': top_k}
            
            if division:
                filter_conditions.append("d.division = $division")
                params['division'] = division
            
            if category:
                filter_conditions.append("d.category_hierarchy = $category")
                params['category'] = category
                
            if product:
                filter_conditions.append("$product IN d.product_scope")
                params['product'] = product
            
            where_clause = " AND " + " AND ".join(filter_conditions) if filter_conditions else ""
            
            # Execute hierarchical search
            start_time = datetime.now()
            
            cypher_query = f"""
                // Text search on chunks with hierarchical filtering
                MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk)
                WHERE toLower(c.text) CONTAINS toLower($search_query)
                {where_clause if where_clause else ''}
                
                // Get additional context
                OPTIONAL MATCH (c)-[:CONTAINS_ENTITY]->(e:Entity)
                OPTIONAL MATCH (d)-[:BELONGS_TO_DIVISION]->(div:Division)
                OPTIONAL MATCH (d)-[:COVERS_CATEGORY]->(cat:Category)
                
                WITH d, c, div, cat,
                     collect(DISTINCT e.text) as entities,
                     CASE 
                         WHEN toLower(c.text) CONTAINS toLower($search_query) THEN 1.0
                         ELSE 0.5
                     END as score
                
                ORDER BY score DESC
                LIMIT $top_k
                
                RETURN 
                    d.filename as filename,
                    d.id as doc_id,
                    d.division as division,
                    d.category_hierarchy as category,
                    d.product_scope as products,
                    d.hierarchy_confidence as confidence,
                    div.name as division_name,
                    div.color as division_color,
                    cat.description as category_desc,
                    c.text as chunk_text,
                    c.page_num as page_num,
                    c.id as chunk_id,
                    score,
                    entities
            """
            
            result = session.run(cypher_query, **params)
            
            results = []
            divisions_found = set()
            categories_found = set()
            
            for record in result:
                results.append({
                    'document': {
                        'filename': record['filename'],
                        'id': record['doc_id'],
                        'division': record['division'],
                        'division_name': record['division_name'],
                        'division_color': record['division_color'],
                        'category': record['category'],
                        'category_desc': record['category_desc'],
                        'products': record['products'],
                        'confidence': record['confidence']
                    },
                    'chunk': {
                        'text': record['chunk_text'],
                        'page_num': record['page_num'],
                        'id': record['chunk_id']
                    },
                    'score': record['score'],
                    'entities': record['entities']
                })
                
                if record['division']:
                    divisions_found.add(record['division'])
                if record['category']:
                    categories_found.add(record['category'])
            
            search_time = (datetime.now() - start_time).total_seconds()
            
            # Get hierarchy statistics
            hierarchy_stats = self._get_hierarchy_stats(session)
            
            return {
                'query': query,
                'filters': {
                    'division': division,
                    'category': category,
                    'product': product
                },
                'results': results,
                'total_results': len(results),
                'search_time': search_time,
                'divisions_found': list(divisions_found),
                'categories_found': list(categories_found),
                'hierarchy_stats': hierarchy_stats
            }
    
    def get_hierarchy_structure(self) -> Dict:
        """Get the complete hierarchy structure"""
        
        with self.driver.session() as session:
            result = session.run("""
                MATCH (i:Institution)-[:HAS_DIVISION]->(d:Division)
                OPTIONAL MATCH (d)-[:HAS_CATEGORY]->(c:Category)
                OPTIONAL MATCH (c)-[:HAS_PRODUCT]->(p:Product)
                
                WITH i, d, c, collect(DISTINCT p.name) as products
                ORDER BY d.name, c.name
                
                WITH i, d, collect(DISTINCT {
                    name: c.name,
                    description: c.description,
                    products: products
                }) as categories
                
                WITH i, collect(DISTINCT {
                    name: d.name,
                    code: d.code,
                    color: d.color,
                    categories: categories
                }) as divisions
                
                RETURN {
                    institution: i.name,
                    code: i.code,
                    divisions: divisions
                } as hierarchy
            """)
            
            return result.single()['hierarchy']
    
    def get_division_documents(self, division_code: str) -> List[Dict]:
        """Get all documents in a division"""
        
        with self.driver.session() as session:
            result = session.run("""
                MATCH (d:Document)-[:BELONGS_TO_DIVISION]->(div:Division {code: $division_code})
                RETURN d.filename as filename,
                       d.id as id,
                       d.category_hierarchy as category,
                       d.product_scope as products,
                       d.total_pages as pages
                ORDER BY d.category_hierarchy, d.filename
            """, division_code=division_code)
            
            return [dict(record) for record in result]
    
    def get_category_documents(self, division_code: str, category: str) -> List[Dict]:
        """Get all documents in a specific category"""
        
        with self.driver.session() as session:
            result = session.run("""
                MATCH (d:Document)
                WHERE d.division_code = $division_code 
                  AND d.category_hierarchy = $category
                RETURN d.filename as filename,
                       d.id as id,
                       d.product_scope as products,
                       d.total_pages as pages
                ORDER BY d.filename
            """, division_code=division_code, category=category)
            
            return [dict(record) for record in result]
    
    def _get_hierarchy_stats(self, session) -> Dict:
        """Get statistics about the hierarchy"""
        
        stats = session.run("""
            MATCH (i:Institution)
            OPTIONAL MATCH (i)-[:HAS_DIVISION]->(d:Division)
            OPTIONAL MATCH (d)-[:HAS_CATEGORY]->(c:Category)
            OPTIONAL MATCH (c)-[:HAS_PRODUCT]->(p:Product)
            OPTIONAL MATCH (doc:Document)
            
            RETURN 
                count(DISTINCT i) as institutions,
                count(DISTINCT d) as divisions,
                count(DISTINCT c) as categories,
                count(DISTINCT p) as products,
                count(DISTINCT doc) as documents
        """).single()
        
        return dict(stats)
    
    def close(self):
        self.driver.close()


def demo_hierarchical_search():
    """Demo the hierarchical search capabilities"""
    
    # Neo4j connection
    NEO4J_URI = "bolt://localhost:7687"
    NEO4J_USER = "neo4j"
    NEO4J_PASSWORD = "knowledge123"
    
    search = HierarchicalSearch(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    
    try:
        # 1. Get hierarchy structure
        print("\n" + "="*80)
        print("HIERARCHY STRUCTURE")
        print("="*80)
        
        hierarchy = search.get_hierarchy_structure()
        print(json.dumps(hierarchy, indent=2))
        
        # 2. Search without filters
        print("\n" + "="*80)
        print("SEARCH: 'interest rate' (no filters)")
        print("="*80)
        
        results = search.search_with_hierarchy("interest rate", top_k=5)
        print(f"Found {results['total_results']} results in {results['search_time']:.2f}s")
        print(f"Divisions: {', '.join(results['divisions_found'])}")
        print(f"Categories: {', '.join(results['categories_found'])}")
        
        for i, result in enumerate(results['results'][:3]):
            print(f"\n{i+1}. {result['document']['filename']} (p. {result['chunk']['page_num']})")
            print(f"   Division: {result['document']['division_name']}")
            print(f"   Category: {result['document']['category']}")
            print(f"   Score: {result['score']:.3f}")
        
        # 3. Search with division filter
        print("\n" + "="*80)
        print("SEARCH: 'interest rate' (Retail Banking only)")
        print("="*80)
        
        results = search.search_with_hierarchy("interest rate", division="RETAIL", top_k=5)
        print(f"Found {results['total_results']} results in {results['search_time']:.2f}s")
        
        for i, result in enumerate(results['results'][:3]):
            print(f"\n{i+1}. {result['document']['filename']} (p. {result['chunk']['page_num']})")
            print(f"   Category: {result['document']['category']}")
            print(f"   Products: {', '.join(result['document']['products'] or [])}")
        
        # 4. Search with category filter
        print("\n" + "="*80)
        print("SEARCH: 'fees' (Retail Banking > Cards)")
        print("="*80)
        
        results = search.search_with_hierarchy("fees", division="RETAIL", category="Cards", top_k=5)
        print(f"Found {results['total_results']} results in {results['search_time']:.2f}s")
        
        for i, result in enumerate(results['results'][:3]):
            print(f"\n{i+1}. {result['document']['filename']} (p. {result['chunk']['page_num']})")
            print(f"   Products: {', '.join(result['document']['products'] or [])}")
            print(f"   Preview: {result['chunk']['text'][:100]}...")
        
        # 5. Get division statistics
        print("\n" + "="*80)
        print("DIVISION STATISTICS")
        print("="*80)
        
        for division_code in ["RETAIL", "BUSINESS", "INST"]:
            docs = search.get_division_documents(division_code)
            print(f"\n{division_code}: {len(docs)} documents")
            
            # Group by category
            categories = {}
            for doc in docs:
                cat = doc['category'] or 'General'
                if cat not in categories:
                    categories[cat] = 0
                categories[cat] += 1
            
            for cat, count in sorted(categories.items()):
                print(f"  - {cat}: {count} documents")
        
    finally:
        search.close()


if __name__ == "__main__":
    demo_hierarchical_search()