#!/usr/bin/env python3
"""
Citation Query Examples for Knowledge Graph

This file demonstrates how to query the knowledge graph
to get results with complete citation information.
"""

# Example Cypher queries for citation-ready results

# 1. Basic text search with citations
BASIC_SEARCH_WITH_CITATIONS = """
MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk)
WHERE toLower(c.text) CONTAINS toLower($query)
RETURN 
  d.filename as source_document,
  d.id as document_id,
  d.total_pages as total_pages,
  d.category as document_category,
  c.page_num as page_number,
  c.chunk_index as chunk_position,
  c.id as chunk_id,
  c.text as full_text,
  substring(c.text, 0, 500) as excerpt
ORDER BY c.page_num, c.chunk_index
LIMIT $limit
"""

# 2. Vector similarity search with citations
VECTOR_SEARCH_WITH_CITATIONS = """
MATCH (c:Chunk)
WHERE c.embedding IS NOT NULL
WITH c, gds.similarity.cosine(c.embedding, $query_embedding) as similarity
WHERE similarity > $threshold
MATCH (d:Document)-[:HAS_CHUNK]->(c)
RETURN 
  d.filename as source_document,
  d.id as document_id,
  d.total_pages as total_pages,
  c.page_num as page_number,
  c.chunk_index as chunk_position,
  c.id as chunk_id,
  similarity as relevance_score,
  substring(c.text, 0, 500) as excerpt
ORDER BY similarity DESC
LIMIT $limit
"""

# 3. Entity-based search with citations
ENTITY_SEARCH_WITH_CITATIONS = """
MATCH (e:Entity {name: $entity_name})-[:APPEARS_IN]->(c:Chunk)
MATCH (d:Document)-[:HAS_CHUNK]->(c)
RETURN DISTINCT
  d.filename as source_document,
  d.id as document_id,
  c.page_num as page_number,
  c.chunk_index as chunk_position,
  c.id as chunk_id,
  e.name as entity_mentioned,
  e.type as entity_type,
  substring(c.text, 0, 500) as excerpt
ORDER BY c.page_num
LIMIT $limit
"""

# 4. Multi-hop graph search with citations
GRAPH_SEARCH_WITH_CITATIONS = """
// Find chunks mentioning an entity and related entities
MATCH (e1:Entity)-[:APPEARS_IN]->(c1:Chunk)
WHERE toLower(e1.name) CONTAINS toLower($query)
MATCH (c1)-[:CONTAINS_ENTITY]->(e2:Entity)
WHERE e1 <> e2
MATCH (e2)-[:APPEARS_IN]->(c2:Chunk)
MATCH (d1:Document)-[:HAS_CHUNK]->(c1)
MATCH (d2:Document)-[:HAS_CHUNK]->(c2)
RETURN 
  d1.filename as primary_document,
  c1.page_num as primary_page,
  c1.id as primary_chunk_id,
  substring(c1.text, 0, 300) as primary_excerpt,
  e2.name as related_entity,
  d2.filename as related_document,
  c2.page_num as related_page,
  c2.id as related_chunk_id,
  substring(c2.text, 0, 300) as related_excerpt
LIMIT $limit
"""

# 5. Aggregated citation summary
CITATION_SUMMARY = """
// Get citation summary for a topic
MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk)
WHERE toLower(c.text) CONTAINS toLower($query)
WITH d, count(c) as mention_count, collect(DISTINCT c.page_num) as pages
RETURN 
  d.filename as source_document,
  d.id as document_id,
  d.total_pages as total_pages,
  mention_count,
  pages[0..10] as sample_pages,
  size(pages) as pages_with_mentions
ORDER BY mention_count DESC
LIMIT $limit
"""

# Python function to format results with citations
def format_search_results_with_citations(results):
    """
    Format Neo4j query results with proper citations.
    
    Args:
        results: List of Neo4j result records
    
    Returns:
        List of formatted results with citations
    """
    formatted_results = []
    
    for record in results:
        result = dict(record)
        
        # Create citation string
        citation = f"{result['source_document']}, p. {result['page_number']}"
        
        # Add formatted citation to result
        result['citation'] = citation
        result['citation_details'] = {
            'document': result['source_document'],
            'page': result['page_number'],
            'chunk_id': result['chunk_id'],
            'chunk_position': result.get('chunk_position', None)
        }
        
        formatted_results.append(result)
    
    return formatted_results


# Example of how to use in an API endpoint
def search_with_citations(driver, query, search_type='text', limit=10):
    """
    Execute a search and return results with full citation information.
    
    Args:
        driver: Neo4j driver instance
        query: Search query
        search_type: Type of search ('text', 'vector', 'entity', 'graph')
        limit: Maximum results
    
    Returns:
        List of results with citation information
    """
    with driver.session() as session:
        if search_type == 'text':
            result = session.run(
                BASIC_SEARCH_WITH_CITATIONS,
                query=query,
                limit=limit
            )
        # Add other search types as needed
        
        # Format results with citations
        results = format_search_results_with_citations(result)
        
        return {
            'query': query,
            'total_results': len(results),
            'results': results,
            'citation_format': 'Document Name, p. Page Number'
        }


# Example response structure
EXAMPLE_API_RESPONSE = {
    "query": "minimum balance requirements",
    "total_results": 3,
    "results": [
        {
            "source_document": "WBC-ForeignCurrencyAccountPDS.pdf",
            "document_id": "WBC-ForeignCurrencyAccountPDS",
            "page_number": 12,
            "chunk_position": 15,
            "chunk_id": "WBC-ForeignCurrencyAccountPDS_p12_c15",
            "excerpt": "The minimum balance requirement for foreign currency accounts...",
            "citation": "WBC-ForeignCurrencyAccountPDS.pdf, p. 12",
            "citation_details": {
                "document": "WBC-ForeignCurrencyAccountPDS.pdf",
                "page": 12,
                "chunk_id": "WBC-ForeignCurrencyAccountPDS_p12_c15",
                "chunk_position": 15
            }
        }
    ],
    "citation_format": "Document Name, p. Page Number"
}