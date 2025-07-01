"""
Enhanced search engine with query preprocessing and result reranking
"""

import logging
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass
import numpy as np
from sentence_transformers import SentenceTransformer, CrossEncoder
from neo4j import GraphDatabase
import spacy
import re
from collections import defaultdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class QueryIntent:
    """Analyzed query intent"""
    query_type: str  # definition, example, comparison, requirement, procedure
    target_products: List[str]
    key_terms: List[str]
    requires_multiple_docs: bool
    complexity_score: float

@dataclass
class EnhancedSearchResult:
    chunk_id: str
    text: str
    score: float
    document_id: str
    document_title: str
    page_num: int
    entities: List[Dict[str, str]]
    search_type: str
    metadata: Dict[str, Any]
    
    # Enhanced fields
    relevance_score: float = 0.0
    keyword_matches: List[str] = None
    semantic_similarity: float = 0.0
    rerank_score: float = 0.0
    explanation: str = ""

class QueryPreprocessor:
    """Preprocess and analyze queries for better search"""
    
    def __init__(self):
        self.nlp = spacy.load('en_core_web_sm')
        
        # Query patterns
        self.patterns = {
            'definition': re.compile(r'what is|what are|define|definition', re.I),
            'example': re.compile(r'example|show me|demonstrate|how does.*work', re.I),
            'comparison': re.compile(r'difference|compare|versus|vs|between', re.I),
            'requirement': re.compile(r'requirement|minimum|maximum|need|must|eligible', re.I),
            'procedure': re.compile(r'how to|how can|steps|process|procedure', re.I),
            'risk': re.compile(r'risk|danger|downside|disadvantage', re.I),
            'benefit': re.compile(r'benefit|advantage|upside|why should', re.I)
        }
        
        # Financial product names and abbreviations
        self.product_map = {
            'fx': 'foreign exchange',
            'fxo': 'foreign exchange option',
            'irs': 'interest rate swap',
            'fca': 'foreign currency account',
            'td': 'term deposit',
            'wibtd': 'wib term deposit',
            'dci': 'dual currency investment',
            'bcf': 'bonus forward contract',
            'pfc': 'participating forward contract',
            'rfc': 'range forward contract',
            'tfc': 'target forward contract'
        }
    
    def analyze_query(self, query: str) -> QueryIntent:
        """Analyze query to understand intent"""
        query_lower = query.lower()
        
        # Determine query type
        query_type = 'general'
        for pattern_type, pattern in self.patterns.items():
            if pattern.search(query):
                query_type = pattern_type
                break
        
        # Extract products
        target_products = []
        for abbrev, full_name in self.product_map.items():
            if abbrev in query_lower or full_name in query_lower:
                target_products.append(full_name)
        
        # Extract key terms using NLP
        doc = self.nlp(query)
        key_terms = []
        
        # Get noun phrases
        for chunk in doc.noun_chunks:
            if len(chunk.text) > 3:
                key_terms.append(chunk.text.lower())
        
        # Get important individual terms
        for token in doc:
            if token.pos_ in ['NOUN', 'VERB'] and not token.is_stop and len(token.text) > 3:
                key_terms.append(token.text.lower())
        
        # Determine if multiple documents needed
        requires_multiple_docs = (
            query_type == 'comparison' or
            len(target_products) > 1 or
            'and' in query_lower and any(p in query_lower for p in self.product_map.values())
        )
        
        # Calculate complexity
        complexity_score = (
            len(key_terms) * 0.1 +
            len(target_products) * 0.2 +
            (0.3 if requires_multiple_docs else 0) +
            (0.2 if query_type in ['comparison', 'procedure'] else 0)
        )
        
        return QueryIntent(
            query_type=query_type,
            target_products=target_products,
            key_terms=list(set(key_terms)),
            requires_multiple_docs=requires_multiple_docs,
            complexity_score=min(1.0, complexity_score)
        )
    
    def expand_query(self, query: str, intent: QueryIntent) -> str:
        """Expand query with synonyms and related terms"""
        expanded_terms = [query]
        
        # Add product expansions
        for product in intent.target_products:
            # Add abbreviations
            for abbrev, full_name in self.product_map.items():
                if full_name == product:
                    expanded_terms.append(abbrev.upper())
        
        # Add query type specific terms
        if intent.query_type == 'requirement':
            expanded_terms.extend(['minimum', 'eligibility', 'qualify'])
        elif intent.query_type == 'risk':
            expanded_terms.extend(['risk', 'exposure', 'downside'])
        elif intent.query_type == 'example':
            expanded_terms.extend(['example', 'scenario', 'illustration'])
        
        return ' '.join(expanded_terms)

class ResultReranker:
    """Rerank search results for better accuracy"""
    
    def __init__(self):
        # Load cross-encoder for reranking
        self.cross_encoder = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
        self.embedder = SentenceTransformer('BAAI/bge-small-en-v1.5')
    
    def calculate_keyword_overlap(self, query: str, text: str) -> Tuple[float, List[str]]:
        """Calculate keyword overlap between query and text"""
        query_words = set(query.lower().split())
        text_words = set(text.lower().split())
        
        # Remove stopwords (simple approach)
        stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'is', 'are', 'was', 'were'}
        query_words = query_words - stopwords
        text_words = text_words - stopwords
        
        matches = query_words.intersection(text_words)
        
        if not query_words:
            return 0.0, []
        
        overlap_score = len(matches) / len(query_words)
        return overlap_score, list(matches)
    
    def rerank_results(self, query: str, results: List[EnhancedSearchResult], 
                      intent: QueryIntent) -> List[EnhancedSearchResult]:
        """Rerank results based on multiple factors"""
        
        if not results:
            return results
        
        # Prepare query-document pairs for cross-encoder
        pairs = [[query, result.text] for result in results]
        
        # Get cross-encoder scores
        try:
            cross_scores = self.cross_encoder.predict(pairs)
        except:
            cross_scores = [0.5] * len(results)
        
        # Calculate additional features for each result
        for i, result in enumerate(results):
            # Cross-encoder score
            result.rerank_score = float(cross_scores[i])
            
            # Keyword overlap
            overlap_score, matches = self.calculate_keyword_overlap(query, result.text)
            result.keyword_matches = matches
            
            # Intent-specific scoring
            intent_boost = 0.0
            
            if intent.query_type == 'definition' and result.metadata.get('has_definitions'):
                intent_boost += 0.2
            elif intent.query_type == 'example' and result.metadata.get('has_examples'):
                intent_boost += 0.2
            elif intent.query_type == 'requirement':
                if any(term in result.text.lower() for term in ['minimum', 'requirement', 'eligible']):
                    intent_boost += 0.15
            
            # Product-specific boost
            if intent.target_products:
                for product in intent.target_products:
                    if product in result.text.lower():
                        intent_boost += 0.1
            
            # Semantic density bonus
            density_boost = result.metadata.get('semantic_density', 0) * 0.1
            
            # Calculate final relevance score
            result.relevance_score = (
                result.rerank_score * 0.4 +          # Cross-encoder score
                result.score * 0.2 +                 # Original search score
                overlap_score * 0.2 +                # Keyword overlap
                intent_boost * 0.1 +                 # Intent matching
                density_boost * 0.1                  # Semantic density
            )
            
            # Add explanation
            explanations = []
            if result.rerank_score > 0.7:
                explanations.append("High semantic match")
            if len(matches) >= 3:
                explanations.append(f"Keywords: {', '.join(matches[:3])}")
            if intent_boost > 0:
                explanations.append(f"Matches {intent.query_type} intent")
            
            result.explanation = "; ".join(explanations)
        
        # Sort by relevance score
        results.sort(key=lambda x: x.relevance_score, reverse=True)
        
        return results

class EnhancedKnowledgeSearchEngine:
    """Enhanced search engine with preprocessing and reranking"""
    
    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str):
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        
        # Initialize components
        logger.info("Loading enhanced search models...")
        self.embedder = SentenceTransformer('BAAI/bge-small-en-v1.5')
        self.preprocessor = QueryPreprocessor()
        self.reranker = ResultReranker()
        
        # Cache for frequently accessed data
        self.document_cache = {}
    
    def search(self, query: str, search_type: str = "enhanced", 
               top_k: int = 10) -> List[EnhancedSearchResult]:
        """Main search method with enhancement pipeline"""
        
        # Step 1: Analyze query intent
        intent = self.preprocessor.analyze_query(query)
        logger.info(f"Query intent: {intent.query_type}, Products: {intent.target_products}")
        
        # Step 2: Expand query if needed
        expanded_query = self.preprocessor.expand_query(query, intent)
        
        # Step 3: Perform initial search (get more candidates for reranking)
        candidates = self._vector_search(expanded_query, top_k * 2)
        
        # Step 4: Enhance with graph search if needed
        if intent.requires_multiple_docs or intent.complexity_score > 0.5:
            graph_results = self._graph_search(expanded_query, intent, top_k)
            # Merge results
            seen_ids = {r.chunk_id for r in candidates}
            for result in graph_results:
                if result.chunk_id not in seen_ids:
                    candidates.append(result)
        
        # Step 5: Load additional metadata
        self._load_result_metadata(candidates)
        
        # Step 6: Rerank results
        reranked_results = self.reranker.rerank_results(query, candidates, intent)
        
        # Step 7: Apply document diversity if multiple docs expected
        if intent.requires_multiple_docs:
            reranked_results = self._ensure_document_diversity(reranked_results, top_k)
        
        return reranked_results[:top_k]
    
    def _vector_search(self, query: str, top_k: int) -> List[EnhancedSearchResult]:
        """Enhanced vector search"""
        query_embedding = self.embedder.encode(query, normalize_embeddings=True)
        
        driver = GraphDatabase.driver(self.neo4j_uri,
                                    auth=(self.neo4j_user, self.neo4j_password))
        
        results = []
        
        try:
            with driver.session() as session:
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
                           node.chunk_type as chunk_type,
                           node.semantic_density as semantic_density,
                           node.has_definitions as has_definitions,
                           node.has_examples as has_examples,
                           node.keywords as keywords,
                           d.id as document_id,
                           d.title as document_title,
                           d.filename as filename,
                           score
                    ORDER BY score DESC
                """, k=top_k, embedding=query_embedding.tolist())
                
                for record in result:
                    search_result = EnhancedSearchResult(
                        chunk_id=record['chunk_id'],
                        text=record['text'],
                        score=record['score'],
                        document_id=record['document_id'],
                        document_title=record['document_title'],
                        page_num=record['page_num'],
                        entities=[],
                        search_type='vector',
                        metadata={
                            'filename': record['filename'],
                            'chunk_type': record['chunk_type'],
                            'semantic_density': record['semantic_density'],
                            'has_definitions': record['has_definitions'],
                            'has_examples': record['has_examples'],
                            'keywords': record['keywords']
                        },
                        semantic_similarity=record['score']
                    )
                    results.append(search_result)
        
        finally:
            driver.close()
        
        return results
    
    def _graph_search(self, query: str, intent: QueryIntent, 
                     top_k: int) -> List[EnhancedSearchResult]:
        """Enhanced graph search focusing on intent"""
        driver = GraphDatabase.driver(self.neo4j_uri,
                                    auth=(self.neo4j_user, self.neo4j_password))
        
        results = []
        
        try:
            with driver.session() as session:
                # Search based on intent
                if intent.query_type == 'comparison' and len(intent.target_products) >= 2:
                    # Find chunks that mention multiple products
                    result = session.run("""
                        MATCH (c:Chunk)<-[:HAS_CHUNK]-(d:Document)
                        WHERE $product1 IN c.keywords AND $product2 IN c.keywords
                        RETURN c, d
                        LIMIT $k
                    """, product1=intent.target_products[0], 
                        product2=intent.target_products[1], 
                        k=top_k)
                
                elif intent.target_products:
                    # Find chunks related to specific products
                    for product in intent.target_products:
                        result = session.run("""
                            MATCH (c:Chunk)<-[:HAS_CHUNK]-(d:Document)
                            WHERE $product IN c.keywords
                            OPTIONAL MATCH (c)-[:SIMILAR_TO]-(related:Chunk)
                            RETURN c, d, collect(related) as related_chunks
                            LIMIT $k
                        """, product=product, k=top_k // len(intent.target_products))
                        
                        for record in result:
                            chunk = record['c']
                            doc = record['d']
                            
                            search_result = EnhancedSearchResult(
                                chunk_id=chunk['id'],
                                text=chunk['text'],
                                score=0.7,  # Base score for graph results
                                document_id=doc['id'],
                                document_title=doc['title'],
                                page_num=chunk['page_num'],
                                entities=[],
                                search_type='graph',
                                metadata={
                                    'filename': doc['filename'],
                                    'chunk_type': chunk.get('chunk_type', 'content'),
                                    'semantic_density': chunk.get('semantic_density', 0),
                                    'has_definitions': chunk.get('has_definitions', False),
                                    'has_examples': chunk.get('has_examples', False),
                                    'keywords': chunk.get('keywords', [])
                                }
                            )
                            results.append(search_result)
        
        finally:
            driver.close()
        
        return results
    
    def _load_result_metadata(self, results: List[EnhancedSearchResult]):
        """Load additional metadata for results"""
        driver = GraphDatabase.driver(self.neo4j_uri,
                                    auth=(self.neo4j_user, self.neo4j_password))
        
        try:
            with driver.session() as session:
                for result in results:
                    # Load entities
                    entities = session.run("""
                        MATCH (c:Chunk {id: $chunk_id})-[:CONTAINS_ENTITY]->(e:Entity)
                        RETURN e.text as text, e.type as type
                    """, chunk_id=result.chunk_id)
                    
                    result.entities = [{'text': record['text'], 'type': record['type']} 
                                     for record in entities]
        
        finally:
            driver.close()
    
    def _ensure_document_diversity(self, results: List[EnhancedSearchResult], 
                                  top_k: int) -> List[EnhancedSearchResult]:
        """Ensure results come from diverse documents"""
        diverse_results = []
        seen_docs = set()
        
        # First pass: get best result from each document
        for result in results:
            if result.document_id not in seen_docs:
                diverse_results.append(result)
                seen_docs.add(result.document_id)
                if len(diverse_results) >= top_k:
                    break
        
        # Second pass: fill remaining slots
        if len(diverse_results) < top_k:
            for result in results:
                if result not in diverse_results:
                    diverse_results.append(result)
                    if len(diverse_results) >= top_k:
                        break
        
        return diverse_results