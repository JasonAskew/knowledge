"""
Fixed search engine with corrected graph query and improved accuracy
"""

import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
import numpy as np
from sentence_transformers import SentenceTransformer
from neo4j import GraphDatabase
import spacy
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class SearchResult:
    chunk_id: str
    text: str
    score: float
    document_id: str
    page_num: int
    entities: List[Dict[str, str]]
    search_type: str
    metadata: Dict[str, Any]

class KnowledgeSearchEngine:
    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str):
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        
        # Load models
        logger.info("Loading search models...")
        self.embedder = SentenceTransformer('BAAI/bge-small-en-v1.5')
        self.nlp = spacy.load('en_core_web_sm')
    
    def _extract_query_entities(self, query: str) -> List[str]:
        """Extract entities from query using spaCy"""
        doc = self.nlp(query)
        entities = []
        
        # Extract named entities
        for ent in doc.ents:
            entities.append(ent.text.lower())
        
        # Extract important tokens (nouns and proper nouns)
        for token in doc:
            if token.pos_ in ['NOUN', 'PROPN'] and not token.is_stop:
                entities.append(token.text.lower())
        
        # Extract financial terms and acronyms
        financial_terms = re.findall(r'\b[A-Z]{2,}\b', query)  # Acronyms
        entities.extend([term.lower() for term in financial_terms])
        
        # Extract product names
        product_patterns = [
            r'\b(?:forward|swap|option|deposit|account|contract|rate|premium)\b',
            r'\b(?:FX|FXO|FCA|TD|PFC|BCF|EFC|DCI|WIBTD|TLD|IRS)\b'
        ]
        for pattern in product_patterns:
            matches = re.findall(pattern, query, re.IGNORECASE)
            entities.extend([m.lower() for m in matches])
        
        return list(set(entities))
    
    def vector_search(self, query: str, top_k: int = 10) -> List[SearchResult]:
        """Vector similarity search using embeddings"""
        logger.info(f"Performing vector search for: {query}")
        
        # Generate query embedding
        query_embedding = self.embedder.encode(query, normalize_embeddings=True)
        
        driver = GraphDatabase.driver(self.neo4j_uri,
                                    auth=(self.neo4j_user, self.neo4j_password))
        
        results = []
        
        try:
            with driver.session() as session:
                # Vector similarity search
                result = session.run("""
                    CALL db.index.vector.queryNodes(
                        'chunk-embeddings',
                        $k,
                        $embedding
                    ) YIELD node, score
                    MATCH (node)<-[:HAS_CHUNK]-(d:Document)
                    RETURN node.id as chunk_id,
                           node.text as text,
                           node.page_num as page_num,
                           d.id as document_id,
                           d.filename as filename,
                           score
                    ORDER BY score DESC
                """, k=top_k * 2, embedding=query_embedding.tolist())  # Get more results for better ranking
                
                for record in result:
                    entities = self._get_chunk_entities(session, record['chunk_id'])
                    
                    search_result = SearchResult(
                        chunk_id=record['chunk_id'],
                        text=record['text'],
                        score=record['score'],
                        document_id=record['document_id'],
                        page_num=record['page_num'],
                        entities=entities,
                        search_type='vector',
                        metadata={'filename': record['filename']}
                    )
                    results.append(search_result)
        
        finally:
            driver.close()
        
        return results[:top_k]
    
    def graph_search(self, query: str, top_k: int = 10) -> List[SearchResult]:
        """Graph-based search using entity relationships - FIXED"""
        logger.info(f"Performing graph search for: {query}")
        
        # Extract entities from query
        query_entities = self._extract_query_entities(query)
        
        if not query_entities:
            return []
        
        driver = GraphDatabase.driver(self.neo4j_uri,
                                    auth=(self.neo4j_user, self.neo4j_password))
        
        results = []
        
        try:
            with driver.session() as session:
                # Fixed query with proper aggregation
                for entity in query_entities:
                    result = session.run("""
                        MATCH (e:Entity)
                        WHERE toLower(e.text) CONTAINS $entity_text
                        MATCH (c:Chunk)-[:CONTAINS_ENTITY]->(e)
                        MATCH (c)<-[:HAS_CHUNK]-(d:Document)
                        WITH c, d, count(DISTINCT e) as matched_entities
                        OPTIONAL MATCH (c)-[:CONTAINS_ENTITY]->(other:Entity)
                        WITH c, d, matched_entities,
                             collect(DISTINCT {text: other.text, type: other.type}) as entities,
                             count(DISTINCT other) as total_entities
                        WITH c, d, entities,
                             matched_entities * 1.0 + (total_entities * 0.1) as score
                        RETURN c.id as chunk_id,
                               c.text as text,
                               c.page_num as page_num,
                               d.id as document_id,
                               d.filename as filename,
                               entities,
                               score
                        ORDER BY score DESC
                        LIMIT $k
                    """, entity_text=entity.lower(), k=top_k)
                    
                    for record in result:
                        entities = [{'text': e['text'], 'type': e['type']} 
                                  for e in record['entities']]
                        
                        search_result = SearchResult(
                            chunk_id=record['chunk_id'],
                            text=record['text'],
                            score=record['score'],
                            document_id=record['document_id'],
                            page_num=record['page_num'],
                            entities=entities,
                            search_type='graph',
                            metadata={'filename': record['filename']}
                        )
                        results.append(search_result)
        
        finally:
            driver.close()
        
        # Deduplicate and sort by score
        unique_results = []
        seen_chunks = set()
        
        for result in sorted(results, key=lambda x: x.score, reverse=True):
            if result.chunk_id not in seen_chunks:
                seen_chunks.add(result.chunk_id)
                unique_results.append(result)
                if len(unique_results) >= top_k:
                    break
        
        return unique_results
    
    def full_text_search(self, query: str, top_k: int = 10) -> List[SearchResult]:
        """Full-text search with enhanced keyword matching"""
        logger.info(f"Performing full-text search for: {query}")
        
        driver = GraphDatabase.driver(self.neo4j_uri,
                                    auth=(self.neo4j_user, self.neo4j_password))
        
        results = []
        
        try:
            with driver.session() as session:
                # Enhanced full-text search with fuzzy matching
                result = session.run("""
                    MATCH (c:Chunk)<-[:HAS_CHUNK]-(d:Document)
                    WHERE toLower(c.text) CONTAINS toLower($search_query)
                       OR ANY(word IN split(toLower($search_query), ' ') 
                             WHERE toLower(c.text) CONTAINS word)
                    WITH c, d, 
                         CASE 
                             WHEN toLower(c.text) CONTAINS toLower($search_query) THEN 2.0
                             ELSE 1.0
                         END as base_score
                    OPTIONAL MATCH (c)-[:CONTAINS_ENTITY]->(e:Entity)
                    WITH c, d, base_score,
                         collect(DISTINCT {text: e.text, type: e.type}) as entities
                    RETURN c.id as chunk_id,
                           c.text as text,
                           c.page_num as page_num,
                           d.id as document_id,
                           d.filename as filename,
                           entities,
                           base_score as score
                    ORDER BY score DESC
                    LIMIT $k
                """, search_query=query, k=top_k)
                
                for record in result:
                    entities = [{'text': e['text'], 'type': e['type']} 
                              for e in record['entities']]
                    
                    search_result = SearchResult(
                        chunk_id=record['chunk_id'],
                        text=record['text'],
                        score=record['score'],
                        document_id=record['document_id'],
                        page_num=record['page_num'],
                        entities=entities,
                        search_type='full_text',
                        metadata={'filename': record['filename']}
                    )
                    results.append(search_result)
        
        finally:
            driver.close()
        
        return results
    
    def hybrid_search(self, query: str, top_k: int = 10, 
                     weights: Dict[str, float] = None) -> List[SearchResult]:
        """Enhanced hybrid search combining vector, graph, and full-text search"""
        logger.info(f"Performing hybrid search for: {query}")
        
        if weights is None:
            weights = {
                'vector': 0.5,      # Increased weight for semantic similarity
                'graph': 0.3,       # Entity relationships
                'full_text': 0.2,   # Keyword matching
            }
        
        # Run all search methods
        vector_results = self.vector_search(query, top_k * 2)
        graph_results = self.graph_search(query, top_k * 2)
        full_text_results = self.full_text_search(query, top_k * 2)
        
        # Combine results with weighted scoring
        combined_results = {}
        
        # Process vector results
        for i, result in enumerate(vector_results):
            score = (1.0 - i / len(vector_results)) * weights['vector']
            combined_results[result.chunk_id] = {
                'result': result,
                'vector_score': score,
                'graph_score': 0,
                'full_text_score': 0,
                'total_score': score
            }
        
        # Process graph results
        for i, result in enumerate(graph_results):
            score = (1.0 - i / len(graph_results)) * weights['graph']
            if result.chunk_id in combined_results:
                combined_results[result.chunk_id]['graph_score'] = score
                combined_results[result.chunk_id]['total_score'] += score
            else:
                combined_results[result.chunk_id] = {
                    'result': result,
                    'vector_score': 0,
                    'graph_score': score,
                    'full_text_score': 0,
                    'total_score': score
                }
        
        # Process full-text results
        for i, result in enumerate(full_text_results):
            score = (1.0 - i / len(full_text_results)) * weights['full_text']
            if result.chunk_id in combined_results:
                combined_results[result.chunk_id]['full_text_score'] = score
                combined_results[result.chunk_id]['total_score'] += score
            else:
                combined_results[result.chunk_id] = {
                    'result': result,
                    'vector_score': 0,
                    'graph_score': 0,
                    'full_text_score': score,
                    'total_score': score
                }
        
        # Apply query-specific boosting
        query_lower = query.lower()
        for chunk_id, data in combined_results.items():
            result = data['result']
            text_lower = result.text.lower()
            
            # Boost exact matches
            if query_lower in text_lower:
                data['total_score'] *= 1.5
            
            # Boost question answering patterns
            if '?' in query and any(word in text_lower for word in ['yes', 'no', 'can', 'will', 'must']):
                data['total_score'] *= 1.2
            
            # Boost financial term matches
            financial_terms = ['premium', 'rate', 'deposit', 'account', 'contract', 'forward', 'option']
            matching_terms = sum(1 for term in financial_terms if term in query_lower and term in text_lower)
            if matching_terms > 0:
                data['total_score'] *= (1.0 + 0.1 * matching_terms)
        
        # Sort by total score and return top results
        sorted_results = sorted(combined_results.values(), 
                              key=lambda x: x['total_score'], 
                              reverse=True)
        
        final_results = []
        for item in sorted_results[:top_k]:
            result = item['result']
            result.score = item['total_score']
            result.search_type = 'hybrid'
            final_results.append(result)
        
        return final_results
    
    def graphrag_search(self, query: str, top_k: int = 10) -> List[SearchResult]:
        """GraphRAG search combining graph traversal with embeddings"""
        logger.info(f"Performing GraphRAG search for: {query}")
        
        # Get initial vector results
        vector_results = self.vector_search(query, top_k // 2)
        
        if not vector_results:
            return []
        
        driver = GraphDatabase.driver(self.neo4j_uri,
                                    auth=(self.neo4j_user, self.neo4j_password))
        
        enhanced_results = []
        
        try:
            with driver.session() as session:
                for result in vector_results:
                    # Traverse graph from high-scoring chunks
                    neighbors = session.run("""
                        MATCH (c:Chunk {id: $chunk_id})
                        MATCH (c)-[:CONTAINS_ENTITY]->(e:Entity)
                        MATCH (other:Chunk)-[:CONTAINS_ENTITY]->(e)
                        WHERE other.id <> c.id
                        WITH other, count(DISTINCT e) as shared_entities
                        MATCH (other)<-[:HAS_CHUNK]-(d:Document)
                        RETURN other.id as chunk_id,
                               other.text as text,
                               other.page_num as page_num,
                               d.id as document_id,
                               d.filename as filename,
                               shared_entities
                        ORDER BY shared_entities DESC
                        LIMIT 3
                    """, chunk_id=result.chunk_id)
                    
                    # Add original result
                    enhanced_results.append(result)
                    
                    # Add related chunks with adjusted scores
                    for record in neighbors:
                        entities = self._get_chunk_entities(session, record['chunk_id'])
                        
                        neighbor_result = SearchResult(
                            chunk_id=record['chunk_id'],
                            text=record['text'],
                            score=result.score * 0.8,  # Slightly lower score for neighbors
                            document_id=record['document_id'],
                            page_num=record['page_num'],
                            entities=entities,
                            search_type='graphrag',
                            metadata={'filename': record['filename']}
                        )
                        enhanced_results.append(neighbor_result)
        
        finally:
            driver.close()
        
        # Deduplicate and return top results
        unique_results = []
        seen_chunks = set()
        
        for result in sorted(enhanced_results, key=lambda x: x.score, reverse=True):
            if result.chunk_id not in seen_chunks:
                seen_chunks.add(result.chunk_id)
                unique_results.append(result)
                if len(unique_results) >= top_k:
                    break
        
        return unique_results
    
    def _get_chunk_entities(self, session, chunk_id: str) -> List[Dict[str, str]]:
        """Get entities for a chunk"""
        result = session.run("""
            MATCH (c:Chunk {id: $chunk_id})-[:CONTAINS_ENTITY]->(e:Entity)
            RETURN e.text as text, e.type as type
        """, chunk_id=chunk_id)
        
        return [{'text': record['text'], 'type': record['type']} 
                for record in result]