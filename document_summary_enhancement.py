#!/usr/bin/env python3
"""
Design for document summary generation and graph integration
"""

import logging
from typing import Dict, List, Optional, Tuple
import json
from dataclasses import dataclass
from neo4j import GraphDatabase
from sentence_transformers import SentenceTransformer
import numpy as np

logger = logging.getLogger(__name__)

@dataclass
class DocumentSummary:
    document_id: str
    filename: str
    executive_summary: str      # 2-3 sentences
    key_topics: List[str]       # Main subjects covered
    main_entities: List[str]    # Most important entities
    document_type: str          # terms, guide, policy, etc.
    complexity_score: float    # Reading complexity 0-1
    page_summaries: List[str]   # Per-page summaries
    semantic_fingerprint: np.ndarray  # Summary embedding

class DocumentSummaryGenerator:
    """
    Generate multi-level document summaries for enhanced search performance
    
    Summary Levels:
    1. Executive Summary (document-level, 2-3 sentences)
    2. Section Summaries (for long documents)
    3. Page Summaries (per-page abstracts)
    4. Semantic Fingerprint (embedding of key concepts)
    """
    
    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str):
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        self.embedding_model = SentenceTransformer('BAAI/bge-small-en-v1.5')
        
        # Summary generation prompts
        self.summary_prompts = {
            "executive": """Summarize this banking document in 2-3 sentences, focusing on:
            - What service/product it covers
            - Key requirements or fees
            - Main customer actions described""",
            
            "page": """Summarize this page in 1-2 sentences covering:
            - Main topic
            - Key facts or requirements
            - Important numbers/fees if present""",
            
            "entities": """Extract the 5-10 most important banking terms, products, or concepts from this document."""
        }
    
    def generate_document_summaries(self, document_limit: Optional[int] = None) -> Dict:
        """Generate summaries for all documents in the graph"""
        logger.info("Starting document summary generation...")
        
        # Get all documents
        with self.driver.session() as session:
            query = """
                MATCH (d:Document)
                RETURN d.id as doc_id, d.filename as filename, d.total_pages as pages
            """
            if document_limit:
                query += f" LIMIT {document_limit}"
                
            result = session.run(query)
            documents = [dict(record) for record in result]
        
        summaries_generated = 0
        
        for doc in documents:
            try:
                summary = self._generate_single_document_summary(doc)
                self._store_summary_in_graph(summary)
                summaries_generated += 1
                
                if summaries_generated % 10 == 0:
                    logger.info(f"Generated {summaries_generated} summaries...")
                    
            except Exception as e:
                logger.error(f"Failed to generate summary for {doc['filename']}: {e}")
        
        # Create summary search indexes
        self._create_summary_indexes()
        
        return {
            "summaries_generated": summaries_generated,
            "total_documents": len(documents)
        }
    
    def _generate_single_document_summary(self, document: Dict) -> DocumentSummary:
        """Generate comprehensive summary for a single document"""
        doc_id = document['doc_id']
        filename = document['filename']
        
        # Get document text by chunks
        with self.driver.session() as session:
            result = session.run("""
                MATCH (d:Document {id: $doc_id})-[:HAS_CHUNK]->(c:Chunk)
                RETURN c.text as text, c.page_num as page
                ORDER BY c.chunk_index
            """, doc_id=doc_id)
            
            chunks = [dict(record) for record in result]
        
        # Aggregate text by page for page summaries
        page_texts = {}
        full_text = ""
        
        for chunk in chunks:
            page_num = chunk['page']
            text = chunk['text']
            
            if page_num not in page_texts:
                page_texts[page_num] = ""
            page_texts[page_num] += text + " "
            full_text += text + " "
        
        # Generate executive summary
        executive_summary = self._generate_executive_summary(full_text, filename)
        
        # Generate page summaries
        page_summaries = []
        for page_num in sorted(page_texts.keys()):
            page_summary = self._generate_page_summary(page_texts[page_num])
            page_summaries.append(page_summary)
        
        # Extract key topics and entities
        key_topics = self._extract_key_topics(full_text)
        main_entities = self._extract_main_entities(doc_id)
        
        # Determine document type
        document_type = self._classify_document_type(filename, executive_summary)
        
        # Calculate complexity score
        complexity_score = self._calculate_complexity_score(full_text)
        
        # Generate semantic fingerprint
        semantic_fingerprint = self._generate_semantic_fingerprint(
            executive_summary, key_topics, main_entities
        )
        
        return DocumentSummary(
            document_id=doc_id,
            filename=filename,
            executive_summary=executive_summary,
            key_topics=key_topics,
            main_entities=main_entities,
            document_type=document_type,
            complexity_score=complexity_score,
            page_summaries=page_summaries,
            semantic_fingerprint=semantic_fingerprint
        )
    
    def _generate_executive_summary(self, full_text: str, filename: str) -> str:
        """Generate 2-3 sentence executive summary"""
        # Simplified summary generation (in production, use LLM API)
        
        # Extract key sentences based on banking keywords
        banking_keywords = [
            'fee', 'charge', 'account', 'card', 'loan', 'transfer', 
            'minimum', 'balance', 'interest', 'rate', 'deposit', 'withdrawal'
        ]
        
        sentences = full_text.split('.')[:20]  # First 20 sentences
        important_sentences = []
        
        for sentence in sentences:
            score = sum(1 for kw in banking_keywords if kw.lower() in sentence.lower())
            if score >= 2:  # At least 2 banking keywords
                important_sentences.append((sentence.strip(), score))
        
        # Take top 3 sentences by keyword score
        important_sentences.sort(key=lambda x: x[1], reverse=True)
        top_sentences = [s[0] for s in important_sentences[:3]]
        
        if top_sentences:
            summary = ". ".join(top_sentences) + "."
        else:
            # Fallback: use first few sentences
            summary = ". ".join(sentences[:3]) + "."
        
        return summary[:500]  # Limit length
    
    def _generate_page_summary(self, page_text: str) -> str:
        """Generate 1-2 sentence page summary"""
        sentences = page_text.split('.')[:5]  # First 5 sentences of page
        
        # Look for key information patterns
        key_patterns = ['fee', 'charge', 'minimum', 'maximum', 'requirement', 'condition']
        
        important_sentences = []
        for sentence in sentences:
            if any(pattern in sentence.lower() for pattern in key_patterns):
                important_sentences.append(sentence.strip())
        
        if important_sentences:
            summary = ". ".join(important_sentences[:2]) + "."
        else:
            summary = ". ".join(sentences[:2]) + "."
        
        return summary[:200]
    
    def _extract_key_topics(self, full_text: str) -> List[str]:
        """Extract main topics/themes from document"""
        # Simplified topic extraction using keyword frequency
        
        banking_topics = {
            'accounts': ['account', 'savings', 'checking', 'deposit'],
            'cards': ['card', 'credit', 'debit', 'mastercard', 'visa'],
            'loans': ['loan', 'mortgage', 'credit', 'lending'],
            'transfers': ['transfer', 'wire', 'telegraphic', 'payment'],
            'fees': ['fee', 'charge', 'cost', 'pricing'],
            'international': ['international', 'foreign', 'currency', 'exchange'],
            'terms': ['terms', 'conditions', 'agreement', 'policy']
        }
        
        text_lower = full_text.lower()
        topic_scores = {}
        
        for topic, keywords in banking_topics.items():
            score = sum(text_lower.count(kw) for kw in keywords)
            if score > 0:
                topic_scores[topic] = score
        
        # Return top topics
        sorted_topics = sorted(topic_scores.items(), key=lambda x: x[1], reverse=True)
        return [topic for topic, score in sorted_topics[:5]]
    
    def _extract_main_entities(self, doc_id: str) -> List[str]:
        """Get most important entities from document"""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (d:Document {id: $doc_id})-[:HAS_CHUNK]->(c:Chunk)
                MATCH (c)-[:CONTAINS_ENTITY]->(e:Entity)
                WITH e, COUNT(c) as chunk_frequency
                ORDER BY chunk_frequency DESC
                LIMIT 10
                RETURN e.text as entity
            """, doc_id=doc_id)
            
            return [record['entity'] for record in result]
    
    def _classify_document_type(self, filename: str, summary: str) -> str:
        """Classify document type based on filename and content"""
        filename_lower = filename.lower()
        summary_lower = summary.lower()
        
        if 'terms' in filename_lower or 'conditions' in filename_lower:
            return 'terms_and_conditions'
        elif 'fee' in filename_lower or 'pricing' in filename_lower:
            return 'fee_schedule'
        elif 'guide' in filename_lower or 'how to' in summary_lower:
            return 'user_guide'
        elif 'policy' in filename_lower:
            return 'policy_document'
        elif 'application' in filename_lower or 'form' in filename_lower:
            return 'application_form'
        else:
            return 'general_document'
    
    def _calculate_complexity_score(self, text: str) -> float:
        """Calculate reading complexity score (0-1, higher = more complex)"""
        # Simplified complexity calculation
        sentences = text.split('.')
        words = text.split()
        
        if not sentences or not words:
            return 0.5
        
        avg_sentence_length = len(words) / len(sentences)
        long_words = sum(1 for word in words if len(word) > 6)
        long_word_ratio = long_words / len(words) if words else 0
        
        # Normalize to 0-1 scale
        complexity = min(1.0, (avg_sentence_length / 30) * 0.6 + long_word_ratio * 0.4)
        return complexity
    
    def _generate_semantic_fingerprint(self, summary: str, topics: List[str], 
                                     entities: List[str]) -> np.ndarray:
        """Generate semantic embedding representing document essence"""
        # Combine summary, topics, and key entities
        fingerprint_text = f"{summary} {' '.join(topics)} {' '.join(entities[:5])}"
        
        # Generate embedding
        embedding = self.embedding_model.encode(fingerprint_text)
        return embedding
    
    def _store_summary_in_graph(self, summary: DocumentSummary):
        """Store summary data in Neo4j graph"""
        with self.driver.session() as session:
            # Create Summary node
            session.run("""
                MATCH (d:Document {id: $doc_id})
                MERGE (s:Summary {document_id: $doc_id})
                SET s.executive_summary = $exec_summary,
                    s.key_topics = $topics,
                    s.main_entities = $entities,
                    s.document_type = $doc_type,
                    s.complexity_score = $complexity,
                    s.semantic_fingerprint = $fingerprint
                MERGE (d)-[:HAS_SUMMARY]->(s)
            """, 
                doc_id=summary.document_id,
                exec_summary=summary.executive_summary,
                topics=summary.key_topics,
                entities=summary.main_entities,
                doc_type=summary.document_type,
                complexity=summary.complexity_score,
                fingerprint=summary.semantic_fingerprint.tolist()
            )
            
            # Store page summaries
            for i, page_summary in enumerate(summary.page_summaries):
                session.run("""
                    MATCH (s:Summary {document_id: $doc_id})
                    MERGE (ps:PageSummary {document_id: $doc_id, page_number: $page_num})
                    SET ps.summary = $page_summary
                    MERGE (s)-[:HAS_PAGE_SUMMARY]->(ps)
                """, 
                    doc_id=summary.document_id,
                    page_num=i + 1,
                    page_summary=page_summary
                )
    
    def _create_summary_indexes(self):
        """Create indexes for efficient summary-based search"""
        with self.driver.session() as session:
            # Full-text index on executive summaries
            session.run("""
                CREATE FULLTEXT INDEX summary_fulltext IF NOT EXISTS
                FOR (s:Summary) ON EACH [s.executive_summary]
            """)
            
            # Index on document types
            session.run("""
                CREATE INDEX summary_doc_type IF NOT EXISTS
                FOR (s:Summary) ON (s.document_type)
            """)
            
            # Index on complexity for filtering
            session.run("""
                CREATE INDEX summary_complexity IF NOT EXISTS
                FOR (s:Summary) ON (s.complexity_score)
            """)


class SummaryEnhancedSearch:
    """Enhanced search using document summaries for faster initial screening"""
    
    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str):
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        self.embedding_model = SentenceTransformer('BAAI/bge-small-en-v1.5')
    
    def search_with_summaries(self, query: str, top_k: int = 10) -> List[Dict]:
        """
        Two-phase search using summaries:
        1. Fast summary-level screening to identify relevant documents
        2. Detailed chunk-level search within relevant documents only
        """
        
        # Phase 1: Summary-level screening
        relevant_docs = self._screen_documents_by_summary(query, top_k * 3)
        
        # Phase 2: Detailed search within relevant documents
        detailed_results = self._detailed_search_in_documents(
            query, [doc['doc_id'] for doc in relevant_docs], top_k
        )
        
        return detailed_results
    
    def _screen_documents_by_summary(self, query: str, limit: int) -> List[Dict]:
        """Fast document screening using summaries"""
        query_embedding = self.embedding_model.encode(query).tolist()
        
        with self.driver.session() as session:
            result = session.run("""
                MATCH (s:Summary)
                WITH s, 
                     reduce(similarity = 0.0, i IN range(0, size(s.semantic_fingerprint)-1) |
                        similarity + s.semantic_fingerprint[i] * $query_embedding[i]
                     ) as summary_similarity
                WHERE summary_similarity > 0.3
                MATCH (d:Document)-[:HAS_SUMMARY]->(s)
                RETURN d.id as doc_id, 
                       d.filename as filename,
                       s.executive_summary as summary,
                       s.document_type as doc_type,
                       summary_similarity
                ORDER BY summary_similarity DESC
                LIMIT $limit
            """, query_embedding=query_embedding, limit=limit)
            
            return [dict(record) for record in result]
    
    def _detailed_search_in_documents(self, query: str, doc_ids: List[str], 
                                    limit: int) -> List[Dict]:
        """Detailed chunk-level search within pre-screened documents"""
        if not doc_ids:
            return []
            
        query_embedding = self.embedding_model.encode(query).tolist()
        
        with self.driver.session() as session:
            result = session.run("""
                MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk)
                WHERE d.id IN $doc_ids
                WITH c, d,
                     reduce(similarity = 0.0, i IN range(0, size(c.embedding)-1) |
                        similarity + c.embedding[i] * $query_embedding[i]
                     ) as chunk_similarity
                ORDER BY chunk_similarity DESC
                LIMIT $limit
                RETURN c.id as chunk_id,
                       c.text as text,
                       c.page_num as page_num,
                       d.filename as document,
                       chunk_similarity as score
            """, doc_ids=doc_ids, query_embedding=query_embedding, limit=limit)
            
            return [dict(record) for record in result]


# Performance impact analysis
SUMMARY_PERFORMANCE_ANALYSIS = {
    "current_search": {
        "scope": "search_all_chunks",
        "chunks_to_search": 12709,
        "avg_query_time": "4-6s (vector search)",
        "memory_usage": "high (all embeddings loaded)"
    },
    "summary_enhanced_search": {
        "phase_1": {
            "scope": "search_summaries_only", 
            "summaries_to_search": 428,
            "estimated_time": "0.2-0.5s",
            "memory_usage": "low (summary embeddings only)"
        },
        "phase_2": {
            "scope": "search_relevant_chunks_only",
            "chunks_to_search": "~1000 (pre-filtered)",
            "estimated_time": "1-2s",
            "memory_usage": "medium (subset of embeddings)"
        },
        "total_estimated_time": "1.2-2.5s",
        "speedup_factor": "2-3x improvement",
        "additional_benefits": [
            "Better result relevance through document-level context",
            "Ability to filter by document type/complexity",
            "Executive summaries provide quick result preview",
            "Reduced computational load for large document sets"
        ]
    }
}

if __name__ == "__main__":
    print("Document Summary Enhancement Analysis")
    print("=" * 50)
    print(json.dumps(SUMMARY_PERFORMANCE_ANALYSIS, indent=2))