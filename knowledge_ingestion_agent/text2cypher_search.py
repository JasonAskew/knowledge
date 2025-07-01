"""
Neo4j Text2Cypher search implementation for natural language queries
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import re
from neo4j import GraphDatabase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class CypherQuery:
    """Represents a Cypher query with metadata"""
    query: str
    description: str
    parameters: Dict[str, Any]
    query_type: str  # simple, aggregation, path, relationship

class Text2CypherRetriever:
    """Convert natural language queries to Cypher queries"""
    
    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str):
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        
        # Query patterns and templates
        self.query_templates = {
            'find_documents': {
                'patterns': [
                    r'(?:find|show|get|list)\s+(?:all\s+)?documents?\s+(?:about|on|regarding|with)\s+(.+)',
                    r'(?:what|which)\s+documents?\s+(?:discuss|mention|contain|have)\s+(.+)',
                ],
                'template': """
                    MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk)
                    WHERE toLower(c.text) CONTAINS toLower($keyword)
                    RETURN DISTINCT d.filename as document, d.title as title
                    ORDER BY d.filename
                    LIMIT 10
                """,
                'type': 'simple'
            },
            
            'find_entities': {
                'patterns': [
                    r'(?:find|show|list)\s+(?:all\s+)?(?:entities|products|terms)\s+(?:in|from)\s+(.+)',
                    r'what\s+(?:entities|products|terms)\s+are\s+in\s+(.+)',
                ],
                'template': """
                    MATCH (d:Document {filename: $filename})-[:HAS_CHUNK]->(c:Chunk)-[:CONTAINS_ENTITY]->(e:Entity)
                    RETURN DISTINCT e.text as entity, e.type as type, count(c) as mentions
                    ORDER BY mentions DESC
                    LIMIT 20
                """,
                'type': 'aggregation'
            },
            
            'find_related': {
                'patterns': [
                    r'(?:find|show)\s+(?:documents?\s+)?related\s+to\s+(.+)',
                    r'what\s+is\s+related\s+to\s+(.+)',
                ],
                'template': """
                    MATCH (c1:Chunk)-[:CONTAINS_ENTITY]->(e:Entity)<-[:CONTAINS_ENTITY]-(c2:Chunk)
                    WHERE toLower(e.text) CONTAINS toLower($entity)
                    MATCH (c2)<-[:HAS_CHUNK]-(d:Document)
                    WHERE c1 <> c2
                    RETURN DISTINCT d.filename as document, 
                           count(DISTINCT e) as shared_entities,
                           collect(DISTINCT e.text)[..5] as example_entities
                    ORDER BY shared_entities DESC
                    LIMIT 10
                """,
                'type': 'path'
            },
            
            'minimum_amount': {
                'patterns': [
                    r'(?:what\s+is\s+the\s+)?minimum\s+(?:amount|balance|requirement)\s+(?:for|to|of)\s+(.+)',
                ],
                'template': """
                    MATCH (c:Chunk)<-[:HAS_CHUNK]-(d:Document)
                    WHERE toLower(c.text) CONTAINS 'minimum'
                    AND toLower(c.text) CONTAINS toLower($product)
                    AND (toLower(c.text) CONTAINS 'amount' OR toLower(c.text) CONTAINS 'balance')
                    RETURN d.filename as document, 
                           c.text as text,
                           c.page_num as page
                    ORDER BY c.page_num
                    LIMIT 5
                """,
                'type': 'simple'
            },
            
            'count_documents': {
                'patterns': [
                    r'how\s+many\s+documents?\s*(?:are\s+there)?',
                    r'count\s+(?:of\s+)?documents?',
                ],
                'template': """
                    MATCH (d:Document)
                    RETURN count(d) as total_documents
                """,
                'type': 'aggregation'
            },
            
            'document_structure': {
                'patterns': [
                    r'(?:show|what\s+is)\s+(?:the\s+)?structure\s+of\s+(.+)',
                    r'how\s+many\s+(?:pages|chunks)\s+(?:in|does)\s+(.+)\s+have',
                ],
                'template': """
                    MATCH (d:Document {filename: $filename})-[:HAS_CHUNK]->(c:Chunk)
                    WITH d, count(c) as chunk_count, max(c.page_num) as max_page
                    OPTIONAL MATCH (d)-[:HAS_CHUNK]->(c2:Chunk)-[:CONTAINS_ENTITY]->(e:Entity)
                    RETURN d.filename as document,
                           d.title as title,
                           chunk_count,
                           max_page as pages,
                           count(DISTINCT e) as unique_entities
                """,
                'type': 'aggregation'
            }
        }
        
        # Product name mappings
        self.product_mappings = {
            'fca': 'foreign currency account',
            'fx': 'foreign exchange',
            'fxo': 'foreign exchange option',
            'irs': 'interest rate swap',
            'td': 'term deposit',
            'wibtd': 'wib term deposit',
            'dci': 'dual currency investment'
        }
    
    def parse_query(self, natural_query: str) -> Optional[CypherQuery]:
        """Parse natural language query and return Cypher query"""
        query_lower = natural_query.lower().strip()
        
        # Try each template
        for template_name, template_info in self.query_templates.items():
            for pattern in template_info['patterns']:
                match = re.match(pattern, query_lower, re.IGNORECASE)
                if match:
                    # Extract parameters
                    params = {}
                    
                    if template_name == 'find_documents':
                        keyword = match.group(1)
                        # Expand product abbreviations
                        for abbrev, full in self.product_mappings.items():
                            if abbrev in keyword:
                                keyword = keyword.replace(abbrev, full)
                        params['keyword'] = keyword
                        
                    elif template_name in ['find_entities', 'document_structure']:
                        filename = match.group(1).strip()
                        # Add .pdf if not present
                        if not filename.endswith('.pdf'):
                            filename += '.pdf'
                        params['filename'] = filename
                        
                    elif template_name == 'find_related':
                        params['entity'] = match.group(1)
                        
                    elif template_name == 'minimum_amount':
                        product = match.group(1)
                        # Expand abbreviations
                        for abbrev, full in self.product_mappings.items():
                            if abbrev in product:
                                product = product.replace(abbrev, full)
                        params['product'] = product
                    
                    return CypherQuery(
                        query=template_info['template'].strip(),
                        description=f"Query type: {template_name}",
                        parameters=params,
                        query_type=template_info['type']
                    )
        
        # If no template matches, try a generic search
        return self._generic_search(natural_query)
    
    def _generic_search(self, query: str) -> CypherQuery:
        """Generic search when no specific pattern matches"""
        # Extract potential keywords
        keywords = []
        for word in query.split():
            if len(word) > 3 and word not in ['what', 'where', 'when', 'which', 'find', 'show']:
                keywords.append(word)
        
        if not keywords:
            keywords = [query]
        
        cypher = """
            MATCH (c:Chunk)<-[:HAS_CHUNK]-(d:Document)
            WHERE """ + " OR ".join([f"toLower(c.text) CONTAINS toLower('{kw}')" for kw in keywords]) + """
            WITH d, c, 
                 CASE 
                    WHEN """ + " AND ".join([f"toLower(c.text) CONTAINS toLower('{kw}')" for kw in keywords]) + """ THEN 2.0
                    ELSE 1.0
                 END as score
            RETURN d.filename as document,
                   c.text as text,
                   c.page_num as page,
                   score
            ORDER BY score DESC, c.page_num
            LIMIT 10
        """
        
        return CypherQuery(
            query=cypher,
            description="Generic keyword search",
            parameters={},
            query_type='simple'
        )
    
    def execute_natural_query(self, natural_query: str) -> Dict[str, Any]:
        """Execute a natural language query"""
        logger.info(f"Processing natural language query: {natural_query}")
        
        # Parse to Cypher
        cypher_query = self.parse_query(natural_query)
        
        if not cypher_query:
            return {
                'success': False,
                'error': 'Could not parse query',
                'query': natural_query
            }
        
        # Execute Cypher
        driver = GraphDatabase.driver(self.neo4j_uri, 
                                    auth=(self.neo4j_user, self.neo4j_password))
        
        results = []
        
        try:
            with driver.session() as session:
                logger.info(f"Executing Cypher: {cypher_query.query[:100]}...")
                result = session.run(cypher_query.query, **cypher_query.parameters)
                
                for record in result:
                    results.append(dict(record))
            
            return {
                'success': True,
                'query': natural_query,
                'cypher': cypher_query.query,
                'parameters': cypher_query.parameters,
                'query_type': cypher_query.query_type,
                'results': results,
                'count': len(results)
            }
            
        except Exception as e:
            logger.error(f"Error executing Cypher: {e}")
            return {
                'success': False,
                'error': str(e),
                'query': natural_query,
                'cypher': cypher_query.query
            }
        
        finally:
            driver.close()
    
    def suggest_queries(self) -> List[str]:
        """Return example queries that can be processed"""
        return [
            "find all documents about foreign currency account",
            "what is the minimum amount for FCA",
            "show documents related to interest rate swaps",
            "what entities are in WBC-ForeignExchangeOptionPDS.pdf",
            "how many documents are there",
            "find documents with option premium",
            "show structure of SGB-FgnCurrencyAccountTC.pdf",
            "what products are mentioned in term deposits"
        ]