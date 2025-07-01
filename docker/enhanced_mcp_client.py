"""
Enhanced MCP Neo4j Client with improved natural language to Cypher translation
"""

import re
import logging
from typing import Dict, List, Any, Optional, Tuple
from mcp_neo4j_client import MCPNeo4jClient

logger = logging.getLogger(__name__)

class EnhancedMCPNeo4jClient(MCPNeo4jClient):
    """Enhanced MCP client with better query understanding"""
    
    def __init__(self, mcp_server_name: str = "mcp-neo4j-cypher"):
        super().__init__(mcp_server_name)
        
        # Define query patterns and their Cypher templates
        self.query_patterns = [
            # Balance queries
            (r"minimum.*balance|balance.*minimum", self._balance_query),
            (r"account.*balance|balance.*requirement", self._balance_query),
            
            # Interest rate queries
            (r"interest.*rate|rate.*interest", self._interest_rate_query),
            (r"swap.*rate|irs.*rate", self._swap_rate_query),
            
            # Fee queries
            (r"fee|charge|cost", self._fee_query),
            (r"international.*transfer.*fee", self._international_fee_query),
            
            # Product queries
            (r"open.*account|account.*open", self._account_opening_query),
            (r"term.*deposit|deposit.*term", self._term_deposit_query),
            (r"loan.*eligibility|eligibility.*loan", self._loan_eligibility_query),
            
            # Document queries
            (r"foreign.*currency|fca|currency.*account", self._foreign_currency_query),
            
            # Process queries
            (r"how.*to|process|steps", self._process_query),
            (r"requirement|eligible|criteria", self._requirement_query),
        ]
    
    def _generate_cypher_from_natural_language(self, query: str) -> str:
        """Generate a more sophisticated Cypher query from natural language"""
        query_lower = query.lower()
        
        # Try to match query patterns
        for pattern, query_func in self.query_patterns:
            if re.search(pattern, query_lower):
                return query_func(query)
        
        # If no pattern matches, use advanced text search
        return self._advanced_text_search(query)
    
    def _balance_query(self, query: str) -> str:
        """Generate Cypher for balance-related queries"""
        return """
        MATCH (c:Chunk)-[:BELONGS_TO]->(d:Document)
        WHERE c.text =~ '(?i).*(minimum|initial|opening).*balance.*' 
           OR c.text =~ '(?i).*balance.*(requirement|minimum|maintain).*'
           OR c.text =~ '(?i).*\$[0-9,]+.*balance.*'
        WITH c, d, 
             CASE 
                WHEN c.text =~ '(?i).*minimum.*balance.*' THEN 2.0
                WHEN c.text =~ '(?i).*balance.*requirement.*' THEN 1.5
                ELSE 1.0
             END as relevance_boost
        RETURN c.text as text, 
               d.filename as document, 
               c.page_num as page, 
               c.chunk_id as chunk_id,
               c.semantic_density * relevance_boost as score
        ORDER BY score DESC
        LIMIT $limit
        """
    
    def _interest_rate_query(self, query: str) -> str:
        """Generate Cypher for interest rate queries"""
        return """
        MATCH (c:Chunk)-[:BELONGS_TO]->(d:Document)
        WHERE c.text =~ '(?i).*interest.*rate.*' 
           OR c.text =~ '(?i).*[0-9]+(\.[0-9]+)?%.*'
           OR c.text =~ '(?i).*(variable|fixed|floating).*rate.*'
        WITH c, d,
             CASE
                WHEN c.text =~ '(?i).*current.*interest.*rate.*' THEN 2.0
                WHEN c.text =~ '(?i).*[0-9]+(\.[0-9]+)?%.*per.*annum.*' THEN 1.8
                ELSE 1.0
             END as relevance_boost
        RETURN c.text as text, 
               d.filename as document, 
               c.page_num as page, 
               c.chunk_id as chunk_id,
               c.semantic_density * relevance_boost as score
        ORDER BY score DESC
        LIMIT $limit
        """
    
    def _swap_rate_query(self, query: str) -> str:
        """Generate Cypher for swap rate specific queries"""
        return """
        MATCH (c:Chunk)-[:BELONGS_TO]->(d:Document)
        WHERE (c.text =~ '(?i).*interest.*rate.*swap.*' OR c.text =~ '(?i).*IRS.*')
          AND (d.filename =~ '(?i).*swap.*' OR d.filename =~ '(?i).*irs.*')
        RETURN c.text as text, 
               d.filename as document, 
               c.page_num as page, 
               c.chunk_id as chunk_id,
               c.semantic_density * 1.5 as score
        ORDER BY score DESC
        LIMIT $limit
        """
    
    def _fee_query(self, query: str) -> str:
        """Generate Cypher for fee-related queries"""
        fee_type = "general"
        if "international" in query.lower():
            fee_type = "international"
        elif "account" in query.lower():
            fee_type = "account"
        elif "transaction" in query.lower():
            fee_type = "transaction"
        
        return f"""
        MATCH (c:Chunk)-[:BELONGS_TO]->(d:Document)
        WHERE c.text =~ '(?i).*(fee|charge|cost).*' 
           {'AND c.text =~ "(?i).*international.*"' if fee_type == 'international' else ''}
           {'AND c.text =~ "(?i).*account.*"' if fee_type == 'account' else ''}
           {'AND c.text =~ "(?i).*transaction.*"' if fee_type == 'transaction' else ''}
        WITH c, d,
             CASE
                WHEN c.text =~ '(?i).*\$[0-9]+.*' THEN 2.0
                WHEN d.filename =~ '(?i).*fee.*' THEN 1.5
                ELSE 1.0
             END as relevance_boost
        RETURN c.text as text, 
               d.filename as document, 
               c.page_num as page, 
               c.chunk_id as chunk_id,
               c.semantic_density * relevance_boost as score
        ORDER BY score DESC
        LIMIT $limit
        """
    
    def _international_fee_query(self, query: str) -> str:
        """Generate Cypher for international transfer fee queries"""
        return """
        MATCH (c:Chunk)-[:BELONGS_TO]->(d:Document)
        WHERE (c.text =~ '(?i).*international.*(transfer|payment|wire).*' 
               AND c.text =~ '(?i).*(fee|charge|cost).*')
           OR (c.text =~ '(?i).*foreign.*(transfer|payment).*fee.*')
           OR (c.text =~ '(?i).*swift.*fee.*')
        RETURN c.text as text, 
               d.filename as document, 
               c.page_num as page, 
               c.chunk_id as chunk_id,
               c.semantic_density * 1.5 as score
        ORDER BY score DESC
        LIMIT $limit
        """
    
    def _account_opening_query(self, query: str) -> str:
        """Generate Cypher for account opening queries"""
        return """
        MATCH (c:Chunk)-[:BELONGS_TO]->(d:Document)
        WHERE c.text =~ '(?i).*(open|opening).*(account|banking).*'
           OR c.text =~ '(?i).*(apply|application).*account.*'
           OR c.text =~ '(?i).*account.*(process|procedure|steps).*'
        WITH c, d,
             CASE
                WHEN c.chunk_type = 'procedure' THEN 2.0
                WHEN c.text =~ '(?i).*step.*[0-9]+.*' THEN 1.8
                WHEN c.has_lists THEN 1.5
                ELSE 1.0
             END as relevance_boost
        RETURN c.text as text, 
               d.filename as document, 
               c.page_num as page, 
               c.chunk_id as chunk_id,
               c.semantic_density * relevance_boost as score
        ORDER BY score DESC
        LIMIT $limit
        """
    
    def _term_deposit_query(self, query: str) -> str:
        """Generate Cypher for term deposit queries"""
        return """
        MATCH (c:Chunk)-[:BELONGS_TO]->(d:Document)
        WHERE (c.text =~ '(?i).*term.*deposit.*' OR c.text =~ '(?i).*TD.*')
          AND (c.text =~ '(?i).*(open|apply|process|rate|minimum).*'
               OR d.filename =~ '(?i).*term.*deposit.*')
        RETURN c.text as text, 
               d.filename as document, 
               c.page_num as page, 
               c.chunk_id as chunk_id,
               c.semantic_density as score
        ORDER BY score DESC
        LIMIT $limit
        """
    
    def _loan_eligibility_query(self, query: str) -> str:
        """Generate Cypher for loan eligibility queries"""
        loan_type = "general"
        if "business" in query.lower():
            loan_type = "business"
        elif "home" in query.lower() or "mortgage" in query.lower():
            loan_type = "home"
        elif "personal" in query.lower():
            loan_type = "personal"
        
        return f"""
        MATCH (c:Chunk)-[:BELONGS_TO]->(d:Document)
        WHERE c.text =~ '(?i).*(eligib|qualify|criteria|requirement).*loan.*'
           OR c.text =~ '(?i).*loan.*(eligib|qualify|criteria|requirement).*'
           {'AND c.text =~ "(?i).*business.*"' if loan_type == 'business' else ''}
           {'AND c.text =~ "(?i).*(home|mortgage|property).*"' if loan_type == 'home' else ''}
           {'AND c.text =~ "(?i).*personal.*"' if loan_type == 'personal' else ''}
        WITH c, d,
             CASE
                WHEN c.chunk_type = 'requirement' THEN 2.0
                WHEN c.has_lists THEN 1.5
                ELSE 1.0
             END as relevance_boost
        RETURN c.text as text, 
               d.filename as document, 
               c.page_num as page, 
               c.chunk_id as chunk_id,
               c.semantic_density * relevance_boost as score
        ORDER BY score DESC
        LIMIT $limit
        """
    
    def _foreign_currency_query(self, query: str) -> str:
        """Generate Cypher for foreign currency account queries"""
        return """
        MATCH (c:Chunk)-[:BELONGS_TO]->(d:Document)
        WHERE (c.text =~ '(?i).*(foreign|multi).*currency.*account.*' 
               OR c.text =~ '(?i).*FCA.*'
               OR c.text =~ '(?i).*currency.*account.*')
          AND (d.filename =~ '(?i).*foreign.*currency.*' 
               OR d.filename =~ '(?i).*fca.*'
               OR d.filename =~ '(?i).*currency.*account.*')
        RETURN c.text as text, 
               d.filename as document, 
               c.page_num as page, 
               c.chunk_id as chunk_id,
               c.semantic_density * 1.5 as score
        ORDER BY score DESC
        LIMIT $limit
        """
    
    def _process_query(self, query: str) -> str:
        """Generate Cypher for process/how-to queries"""
        process_keywords = re.findall(r'\b(open|apply|transfer|close|withdraw|deposit)\b', query.lower())
        keyword_conditions = " OR ".join([f"c.text =~ '(?i).*{kw}.*'" for kw in process_keywords])
        
        return f"""
        MATCH (c:Chunk)-[:BELONGS_TO]->(d:Document)
        WHERE (c.text =~ '(?i).*(how.*to|process|procedure|steps?).*'
               {f'AND ({keyword_conditions})' if keyword_conditions else ''})
           OR c.chunk_type = 'procedure'
        WITH c, d,
             CASE
                WHEN c.chunk_type = 'procedure' THEN 2.0
                WHEN c.text =~ '(?i).*step.*[0-9]+.*' THEN 1.8
                WHEN c.has_lists THEN 1.5
                ELSE 1.0
             END as relevance_boost
        RETURN c.text as text, 
               d.filename as document, 
               c.page_num as page, 
               c.chunk_id as chunk_id,
               c.semantic_density * relevance_boost as score
        ORDER BY score DESC
        LIMIT $limit
        """
    
    def _requirement_query(self, query: str) -> str:
        """Generate Cypher for requirement/eligibility queries"""
        return """
        MATCH (c:Chunk)-[:BELONGS_TO]->(d:Document)
        WHERE c.text =~ '(?i).*(requirement|eligib|criteria|qualify|need.*to).*'
           OR c.chunk_type = 'requirement'
        WITH c, d,
             CASE
                WHEN c.chunk_type = 'requirement' THEN 2.0
                WHEN c.has_lists THEN 1.5
                WHEN c.text =~ '(?i).*must.*' THEN 1.3
                ELSE 1.0
             END as relevance_boost
        RETURN c.text as text, 
               d.filename as document, 
               c.page_num as page, 
               c.chunk_id as chunk_id,
               c.semantic_density * relevance_boost as score
        ORDER BY score DESC
        LIMIT $limit
        """
    
    def _advanced_text_search(self, query: str) -> str:
        """Advanced text search with entity recognition"""
        # Extract key terms and entities
        important_terms = self._extract_important_terms(query)
        
        # Build search conditions
        conditions = []
        for term in important_terms:
            conditions.append(f"c.text =~ '(?i).*{re.escape(term)}.*'")
        
        condition_str = " OR ".join(conditions) if conditions else "c.text IS NOT NULL"
        
        return f"""
        MATCH (c:Chunk)-[:BELONGS_TO]->(d:Document)
        WHERE {condition_str}
        OPTIONAL MATCH (c)-[:HAS_ENTITY]->(e:Entity)
        WHERE e.name IN {important_terms}
        WITH c, d, COUNT(e) as entity_matches
        RETURN c.text as text, 
               d.filename as document, 
               c.page_num as page, 
               c.chunk_id as chunk_id,
               (c.semantic_density + entity_matches * 0.2) as score
        ORDER BY score DESC
        LIMIT $limit
        """
    
    def _extract_important_terms(self, query: str) -> List[str]:
        """Extract important terms from query"""
        # Remove common words
        stop_words = {'what', 'is', 'the', 'a', 'an', 'how', 'do', 'i', 'to', 'for', 'of', 'in', 'on', 'at'}
        
        # Extract words
        words = re.findall(r'\b\w+\b', query.lower())
        important_terms = [w for w in words if w not in stop_words and len(w) > 2]
        
        # Also extract phrases
        phrases = re.findall(r'\b(?:foreign currency|interest rate|term deposit|minimum balance)\b', query.lower())
        important_terms.extend(phrases)
        
        return list(set(important_terms))

# Update the get_mcp_neo4j_client function to use the enhanced client
def get_enhanced_mcp_client() -> EnhancedMCPNeo4jClient:
    """Get or create the enhanced MCP Neo4j client singleton"""
    global _enhanced_mcp_client
    if not hasattr(get_enhanced_mcp_client, '_client'):
        get_enhanced_mcp_client._client = EnhancedMCPNeo4jClient()
    return get_enhanced_mcp_client._client