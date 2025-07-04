#!/usr/bin/env python3
"""
Cascading Filter API for Hierarchical Navigation
Provides endpoints for UI to implement cascading filters
"""

from fastapi import FastAPI, Query
from typing import Dict, List, Optional
from neo4j import GraphDatabase
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Hierarchical Filter API")

# Neo4j connection
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "knowledge123"

class HierarchicalFilterService:
    """Service for hierarchical filtering operations"""
    
    def __init__(self):
        self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    def get_divisions(self) -> List[Dict]:
        """Get all divisions with document counts"""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (d:Division)
                OPTIONAL MATCH (doc:Document)-[:BELONGS_TO_DIVISION]->(d)
                WITH d, count(DISTINCT doc) as doc_count
                ORDER BY d.name
                RETURN {
                    code: d.code,
                    name: d.name,
                    color: d.color,
                    document_count: doc_count
                } as division
            """)
            
            return [record['division'] for record in result]
    
    def get_categories(self, division_code: Optional[str] = None) -> List[Dict]:
        """Get categories, optionally filtered by division"""
        with self.driver.session() as session:
            if division_code:
                result = session.run("""
                    MATCH (d:Division {code: $division_code})-[:HAS_CATEGORY]->(c:Category)
                    OPTIONAL MATCH (doc:Document)-[:COVERS_CATEGORY]->(c)
                    WHERE doc.division = $division_code
                    WITH c, count(DISTINCT doc) as doc_count
                    ORDER BY c.name
                    RETURN {
                        name: c.name,
                        description: c.description,
                        division: $division_code,
                        document_count: doc_count
                    } as category
                """, division_code=division_code)
            else:
                result = session.run("""
                    MATCH (c:Category)
                    OPTIONAL MATCH (doc:Document)-[:COVERS_CATEGORY]->(c)
                    WITH c, count(DISTINCT doc) as doc_count
                    ORDER BY c.name
                    RETURN {
                        name: c.name,
                        description: c.description,
                        division: c.division,
                        document_count: doc_count
                    } as category
                """)
            
            return [record['category'] for record in result]
    
    def get_products(self, division_code: Optional[str] = None, 
                    category: Optional[str] = None) -> List[Dict]:
        """Get products, optionally filtered by division and/or category"""
        with self.driver.session() as session:
            params = {}
            conditions = []
            
            if division_code:
                conditions.append("EXISTS((p)<-[:HAS_PRODUCT]-(:Category)<-[:HAS_CATEGORY]-(:Division {code: $division_code}))")
                params['division_code'] = division_code
            
            if category:
                conditions.append("EXISTS((p)<-[:HAS_PRODUCT]-(:Category {name: $category}))")
                params['category'] = category
            
            where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
            
            result = session.run(f"""
                MATCH (p:Product)
                {where_clause}
                OPTIONAL MATCH (doc:Document)-[:COVERS_PRODUCT]->(p)
                WITH p, count(DISTINCT doc) as doc_count
                ORDER BY p.name
                RETURN {{
                    name: p.name,
                    category: p.category,
                    document_count: doc_count
                }} as product
            """, **params)
            
            return [record['product'] for record in result]
    
    def get_filter_state(self, division_code: Optional[str] = None,
                        category: Optional[str] = None,
                        product: Optional[str] = None) -> Dict:
        """Get complete filter state with counts"""
        with self.driver.session() as session:
            # Build filter conditions
            conditions = []
            params = {}
            
            if division_code:
                conditions.append("d.division = $division_code")
                params['division_code'] = division_code
            
            if category:
                conditions.append("d.category_hierarchy = $category")
                params['category'] = category
            
            if product:
                conditions.append("$product IN d.product_scope")
                params['product'] = product
            
            where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
            
            # Get matching documents count
            doc_count_result = session.run(f"""
                MATCH (d:Document)
                {where_clause}
                RETURN count(d) as total_documents
            """, **params)
            
            total_documents = doc_count_result.single()['total_documents']
            
            # Get available options at each level
            state = {
                'current_filters': {
                    'division': division_code,
                    'category': category,
                    'product': product
                },
                'total_documents': total_documents,
                'available_options': {
                    'divisions': self.get_divisions(),
                    'categories': self.get_categories(division_code) if division_code else [],
                    'products': self.get_products(division_code, category) if (division_code or category) else []
                }
            }
            
            return state
    
    def close(self):
        self.driver.close()

# Initialize service
filter_service = HierarchicalFilterService()

@app.get("/api/filters/divisions")
async def get_divisions():
    """Get all divisions with document counts"""
    return filter_service.get_divisions()

@app.get("/api/filters/categories")
async def get_categories(division: Optional[str] = Query(None)):
    """Get categories, optionally filtered by division"""
    return filter_service.get_categories(division)

@app.get("/api/filters/products")
async def get_products(division: Optional[str] = Query(None),
                      category: Optional[str] = Query(None)):
    """Get products, optionally filtered by division and/or category"""
    return filter_service.get_products(division, category)

@app.get("/api/filters/state")
async def get_filter_state(division: Optional[str] = Query(None),
                          category: Optional[str] = Query(None),
                          product: Optional[str] = Query(None)):
    """Get complete filter state with all available options and counts"""
    return filter_service.get_filter_state(division, category, product)

@app.get("/api/search/hierarchical")
async def hierarchical_search(
    query: str,
    division: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    product: Optional[str] = Query(None),
    limit: int = Query(10, le=50)
):
    """Search with hierarchical filters"""
    from hierarchical_search import HierarchicalSearch
    
    search = HierarchicalSearch(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    try:
        results = search.search_with_hierarchy(
            query=query,
            division=division,
            category=category,
            product=product,
            top_k=limit
        )
        return results
    finally:
        search.close()

@app.on_event("shutdown")
def shutdown_event():
    filter_service.close()

if __name__ == "__main__":
    import uvicorn
    
    # Test the API locally
    print("Testing Cascading Filter API...")
    
    # Test get divisions
    print("\nDivisions:")
    divisions = filter_service.get_divisions()
    for div in divisions:
        print(f"  - {div['name']} ({div['code']}): {div['document_count']} documents")
    
    # Test get categories for Retail
    print("\nRetail Banking Categories:")
    categories = filter_service.get_categories("RETAIL")
    for cat in categories:
        print(f"  - {cat['name']}: {cat['document_count']} documents")
    
    # Test filter state
    print("\nFilter State (Retail > Cards):")
    state = filter_service.get_filter_state(division_code="RETAIL", category="Cards")
    print(f"  Total matching documents: {state['total_documents']}")
    print(f"  Available products: {[p['name'] for p in state['available_options']['products']]}")
    
    filter_service.close()
    
    # Uncomment to run the API server
    # uvicorn.run(app, host="0.0.0.0", port=8001)