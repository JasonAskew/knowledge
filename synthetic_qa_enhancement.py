#!/usr/bin/env python3
"""
Design for synthetic Q&A pair generation and graph integration
"""

import logging
from typing import Dict, List, Optional, Tuple, Set
import json
from dataclasses import dataclass
from neo4j import GraphDatabase
from sentence_transformers import SentenceTransformer
import numpy as np
import re

logger = logging.getLogger(__name__)

@dataclass
class QAPair:
    question: str
    answer: str
    chunk_id: str
    document_id: str
    page_number: int
    question_type: str      # factual, procedural, calculation, etc.
    difficulty: str         # basic, intermediate, advanced
    entities_involved: List[str]
    confidence_score: float  # 0-1, how confident we are in this Q&A
    question_embedding: np.ndarray
    answer_embedding: np.ndarray

class SyntheticQAGenerator:
    """
    Generate synthetic Q&A pairs from document content to improve search performance
    
    Strategy:
    1. Pattern-based Q&A generation for banking domain
    2. Entity-focused questions (fees, requirements, procedures)
    3. Multi-chunk reasoning questions
    4. Variation generation for training data
    """
    
    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str):
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        self.embedding_model = SentenceTransformer('BAAI/bge-small-en-v1.5')
        
        # Banking domain question patterns
        self.question_patterns = {
            "fees": [
                "What is the fee for {service}?",
                "How much does {service} cost?",
                "What are the charges for {service}?",
                "Is there a fee for {service}?",
                "What does {service} cost?"
            ],
            "requirements": [
                "What are the requirements for {service}?",
                "What do I need to {action}?", 
                "How do I qualify for {service}?",
                "What documents are needed for {service}?",
                "What are the eligibility criteria for {service}?"
            ],
            "procedures": [
                "How do I {action}?",
                "What is the process to {action}?", 
                "How can I {action}?",
                "What steps are needed to {action}?",
                "How do I go about {action}?"
            ],
            "limits": [
                "What is the minimum {amount} for {service}?",
                "What is the maximum {amount} for {service}?",
                "Are there limits on {service}?",
                "What are the {service} limits?",
                "How much can I {action}?"
            ],
            "timeframes": [
                "How long does {service} take?",
                "When will my {service} be processed?",
                "What is the processing time for {service}?",
                "How quickly can I {action}?",
                "When is {service} available?"
            ]
        }
        
        # Banking entities and actions for pattern substitution
        self.banking_entities = {
            "services": [
                "wire transfers", "international transfers", "account opening",
                "credit card application", "loan application", "term deposits"
            ],
            "actions": [
                "transfer money internationally", "open an account", "apply for a credit card",
                "report a lost card", "close my account", "make a deposit"
            ],
            "amounts": ["balance", "deposit", "withdrawal", "transfer amount", "payment"],
        }
    
    def generate_qa_pairs_for_corpus(self, document_limit: Optional[int] = None) -> Dict:
        """Generate Q&A pairs for entire document corpus"""
        logger.info("Starting synthetic Q&A generation...")
        
        # Get all chunks with their context
        chunks = self._get_chunks_with_context(document_limit)
        
        total_qa_pairs = 0
        generation_stats = {
            "factual": 0,
            "procedural": 0, 
            "calculation": 0,
            "comparison": 0
        }
        
        for chunk in chunks:
            try:
                qa_pairs = self._generate_qa_for_chunk(chunk)
                
                # Store Q&A pairs in graph
                for qa_pair in qa_pairs:
                    self._store_qa_pair(qa_pair)
                    generation_stats[qa_pair.question_type] += 1
                    
                total_qa_pairs += len(qa_pairs)
                
                if total_qa_pairs % 100 == 0:
                    logger.info(f"Generated {total_qa_pairs} Q&A pairs...")
                    
            except Exception as e:
                logger.error(f"Failed to generate Q&A for chunk {chunk['chunk_id']}: {e}")
        
        # Create Q&A search indexes
        self._create_qa_indexes()
        
        return {
            "total_qa_pairs": total_qa_pairs,
            "generation_stats": generation_stats,
            "chunks_processed": len(chunks)
        }
    
    def _get_chunks_with_context(self, document_limit: Optional[int]) -> List[Dict]:
        """Get chunks with document and entity context"""
        with self.driver.session() as session:
            query = """
                MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk)
                OPTIONAL MATCH (c)-[:CONTAINS_ENTITY]->(e:Entity)
                WITH d, c, collect(e.text) as entities
                RETURN c.id as chunk_id,
                       c.text as text,
                       c.page_num as page_num,
                       d.id as document_id,
                       d.filename as filename,
                       entities
                ORDER BY d.filename, c.chunk_index
            """
            
            if document_limit:
                # Limit by number of documents, not chunks
                query = f"""
                    MATCH (d:Document)
                    WITH d LIMIT {document_limit}
                    MATCH (d)-[:HAS_CHUNK]->(c:Chunk)
                    OPTIONAL MATCH (c)-[:CONTAINS_ENTITY]->(e:Entity)
                    WITH d, c, collect(e.text) as entities
                    RETURN c.id as chunk_id,
                           c.text as text,
                           c.page_num as page_num,
                           d.id as document_id,
                           d.filename as filename,
                           entities
                    ORDER BY d.filename, c.chunk_index
                """
            
            result = session.run(query)
            return [dict(record) for record in result]
    
    def _generate_qa_for_chunk(self, chunk: Dict) -> List[QAPair]:
        """Generate multiple Q&A pairs for a single chunk"""
        text = chunk['text']
        entities = chunk['entities']
        
        qa_pairs = []
        
        # 1. Pattern-based Q&A generation
        pattern_qas = self._generate_pattern_based_qa(text, entities, chunk)
        qa_pairs.extend(pattern_qas)
        
        # 2. Entity-focused Q&A generation  
        entity_qas = self._generate_entity_focused_qa(text, entities, chunk)
        qa_pairs.extend(entity_qas)
        
        # 3. Factual extraction Q&A
        factual_qas = self._generate_factual_qa(text, chunk)
        qa_pairs.extend(factual_qas)
        
        return qa_pairs
    
    def _generate_pattern_based_qa(self, text: str, entities: List[str], 
                                  chunk: Dict) -> List[QAPair]:
        """Generate Q&A using predefined banking patterns"""
        qa_pairs = []
        text_lower = text.lower()
        
        # Fee-related Q&A
        if any(word in text_lower for word in ['fee', 'charge', 'cost', '$']):
            # Extract fee information
            fee_info = self._extract_fee_information(text)
            if fee_info:
                for service, fee in fee_info.items():
                    question = f"What is the fee for {service}?"
                    answer = f"The fee for {service} is {fee}."
                    
                    qa_pair = self._create_qa_pair(
                        question, answer, "factual", "basic", chunk, entities
                    )
                    qa_pairs.append(qa_pair)
        
        # Requirement-related Q&A
        if any(word in text_lower for word in ['minimum', 'maximum', 'requirement', 'must']):
            requirements = self._extract_requirements(text)
            for req_type, requirement in requirements.items():
                question = f"What is the {req_type} requirement?"
                answer = f"The {req_type} requirement is {requirement}."
                
                qa_pair = self._create_qa_pair(
                    question, answer, "factual", "basic", chunk, entities
                )
                qa_pairs.append(qa_pair)
        
        # Procedural Q&A
        if any(word in text_lower for word in ['how', 'process', 'step', 'procedure']):
            procedures = self._extract_procedures(text)
            for action, procedure in procedures.items():
                question = f"How do I {action}?"
                answer = procedure
                
                qa_pair = self._create_qa_pair(
                    question, answer, "procedural", "intermediate", chunk, entities
                )
                qa_pairs.append(qa_pair)
        
        return qa_pairs
    
    def _generate_entity_focused_qa(self, text: str, entities: List[str], 
                                   chunk: Dict) -> List[QAPair]:
        """Generate Q&A focused on entities mentioned in the chunk"""
        qa_pairs = []
        
        for entity in entities[:3]:  # Limit to top 3 entities per chunk
            entity_lower = entity.lower()
            
            # Generate definition questions
            if entity_lower in text.lower():
                context_sentence = self._get_entity_context(text, entity)
                if context_sentence:
                    question = f"What is {entity}?"
                    answer = context_sentence
                    
                    qa_pair = self._create_qa_pair(
                        question, answer, "factual", "basic", chunk, [entity]
                    )
                    qa_pairs.append(qa_pair)
        
        return qa_pairs
    
    def _generate_factual_qa(self, text: str, chunk: Dict) -> List[QAPair]:
        """Generate factual Q&A from explicit facts in text"""
        qa_pairs = []
        
        # Extract numerical facts
        numerical_facts = self._extract_numerical_facts(text)
        for fact in numerical_facts:
            question = f"What is the {fact['type']}?"
            answer = f"The {fact['type']} is {fact['value']}."
            
            qa_pair = self._create_qa_pair(
                question, answer, "factual", "basic", chunk, []
            )
            qa_pairs.append(qa_pair)
        
        return qa_pairs
    
    def _create_qa_pair(self, question: str, answer: str, question_type: str,
                       difficulty: str, chunk: Dict, entities: List[str]) -> QAPair:
        """Create QAPair object with embeddings"""
        
        # Generate embeddings
        question_embedding = self.embedding_model.encode(question)
        answer_embedding = self.embedding_model.encode(answer)
        
        # Calculate confidence based on answer quality
        confidence = self._calculate_qa_confidence(question, answer, chunk['text'])
        
        return QAPair(
            question=question,
            answer=answer,
            chunk_id=chunk['chunk_id'],
            document_id=chunk['document_id'],
            page_number=chunk['page_num'],
            question_type=question_type,
            difficulty=difficulty,
            entities_involved=entities,
            confidence_score=confidence,
            question_embedding=question_embedding,
            answer_embedding=answer_embedding
        )
    
    def _extract_fee_information(self, text: str) -> Dict[str, str]:
        """Extract fee information from text"""
        fees = {}
        
        # Pattern for fees: service + fee amount
        fee_patterns = [
            r'(\w+(?:\s+\w+)*)\s+(?:fee|charge|cost)(?:s)?\s*(?:is|:)?\s*\$?(\d+(?:\.\d{2})?)',
            r'\$(\d+(?:\.\d{2})?)\s+(?:for|per)\s+(\w+(?:\s+\w+)*)',
        ]
        
        for pattern in fee_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                if len(match.groups()) == 2:
                    service = match.group(1).strip()
                    amount = match.group(2).strip()
                    fees[service] = f"${amount}"
        
        return fees
    
    def _extract_requirements(self, text: str) -> Dict[str, str]:
        """Extract requirement information from text"""
        requirements = {}
        
        # Pattern for requirements
        req_patterns = [
            r'minimum\s+(\w+(?:\s+\w+)*)\s+(?:is|of)\s+\$?(\d+(?:,\d{3})*(?:\.\d{2})?)',
            r'maximum\s+(\w+(?:\s+\w+)*)\s+(?:is|of)\s+\$?(\d+(?:,\d{3})*(?:\.\d{2})?)',
        ]
        
        for pattern in req_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                req_type = f"minimum/maximum {match.group(1)}"
                amount = match.group(2)
                requirements[req_type] = f"${amount}"
        
        return requirements
    
    def _extract_procedures(self, text: str) -> Dict[str, str]:
        """Extract procedural information from text"""
        procedures = {}
        
        # Look for step-by-step procedures
        sentences = text.split('.')
        for sentence in sentences:
            if any(word in sentence.lower() for word in ['step', 'first', 'then', 'next']):
                # This is likely a procedure
                action = "complete this process"
                procedures[action] = sentence.strip()
                break
        
        return procedures
    
    def _extract_numerical_facts(self, text: str) -> List[Dict]:
        """Extract numerical facts from text"""
        facts = []
        
        # Pattern for numerical facts
        patterns = [
            r'(\d+(?:\.\d+)?)\s*%\s*(?:interest|rate)',
            r'\$(\d+(?:,\d{3})*(?:\.\d{2})?)\s+(?:minimum|maximum|limit)',
            r'(\d+)\s+(?:days|business days|working days)',
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                if 'interest' in pattern or 'rate' in pattern:
                    fact_type = "interest rate"
                    value = f"{match.group(1)}%"
                elif 'days' in pattern:
                    fact_type = "processing time"
                    value = f"{match.group(1)} days"
                else:
                    fact_type = "amount limit"
                    value = f"${match.group(1)}"
                
                facts.append({"type": fact_type, "value": value})
        
        return facts
    
    def _get_entity_context(self, text: str, entity: str) -> Optional[str]:
        """Get contextual sentence that defines or describes an entity"""
        sentences = text.split('.')
        
        for sentence in sentences:
            if entity.lower() in sentence.lower():
                # Check if this sentence provides definition/context
                if any(word in sentence.lower() for word in ['is', 'means', 'refers to', 'includes']):
                    return sentence.strip()
        
        return None
    
    def _calculate_qa_confidence(self, question: str, answer: str, source_text: str) -> float:
        """Calculate confidence score for Q&A pair quality"""
        confidence = 0.5  # Base confidence
        
        # Higher confidence if answer is directly from source
        if answer.lower().replace('.', '') in source_text.lower():
            confidence += 0.3
        
        # Higher confidence for specific question types
        if any(word in question.lower() for word in ['what is', 'how much', 'when']):
            confidence += 0.1
        
        # Lower confidence for very short answers
        if len(answer.split()) < 5:
            confidence -= 0.1
        
        # Higher confidence if answer contains numbers (more specific)
        if re.search(r'\d+', answer):
            confidence += 0.1
        
        return min(1.0, max(0.1, confidence))
    
    def _store_qa_pair(self, qa_pair: QAPair):
        """Store Q&A pair in Neo4j graph"""
        with self.driver.session() as session:
            session.run("""
                MATCH (c:Chunk {id: $chunk_id})
                MERGE (qa:QAPair {
                    question: $question,
                    chunk_id: $chunk_id
                })
                SET qa.answer = $answer,
                    qa.question_type = $question_type,
                    qa.difficulty = $difficulty,
                    qa.entities_involved = $entities,
                    qa.confidence_score = $confidence,
                    qa.question_embedding = $q_embedding,
                    qa.answer_embedding = $a_embedding
                MERGE (c)-[:HAS_QA_PAIR]->(qa)
            """,
                chunk_id=qa_pair.chunk_id,
                question=qa_pair.question,
                answer=qa_pair.answer,
                question_type=qa_pair.question_type,
                difficulty=qa_pair.difficulty,
                entities=qa_pair.entities_involved,
                confidence=qa_pair.confidence_score,
                q_embedding=qa_pair.question_embedding.tolist(),
                a_embedding=qa_pair.answer_embedding.tolist()
            )
    
    def _create_qa_indexes(self):
        """Create indexes for Q&A search"""
        with self.driver.session() as session:
            # Full-text index on questions
            session.run("""
                CREATE FULLTEXT INDEX qa_questions_fulltext IF NOT EXISTS
                FOR (qa:QAPair) ON EACH [qa.question, qa.answer]
            """)
            
            # Index on question types
            session.run("""
                CREATE INDEX qa_question_type IF NOT EXISTS
                FOR (qa:QAPair) ON (qa.question_type)
            """)
            
            # Index on confidence scores
            session.run("""
                CREATE INDEX qa_confidence IF NOT EXISTS
                FOR (qa:QAPair) ON (qa.confidence_score)
            """)


class QAEnhancedSearch:
    """Search enhancement using synthetic Q&A pairs"""
    
    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str):
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        self.embedding_model = SentenceTransformer('BAAI/bge-small-en-v1.5')
    
    def search_with_qa_enhancement(self, query: str, top_k: int = 10) -> List[Dict]:
        """
        Enhanced search using Q&A pairs:
        1. Match against synthetic questions for better intent understanding
        2. Use Q&A pairs to improve result ranking
        3. Provide direct answers when available
        """
        
        # Phase 1: Direct Q&A matching
        qa_matches = self._find_matching_qa_pairs(query, top_k // 2)
        
        # Phase 2: Regular chunk search enhanced with Q&A context
        chunk_results = self._search_chunks_with_qa_context(query, top_k)
        
        # Phase 3: Combine and rank results
        combined_results = self._combine_qa_and_chunk_results(qa_matches, chunk_results)
        
        return combined_results[:top_k]
    
    def _find_matching_qa_pairs(self, query: str, limit: int) -> List[Dict]:
        """Find Q&A pairs that match the query intent"""
        query_embedding = self.embedding_model.encode(query).tolist()
        
        with self.driver.session() as session:
            result = session.run("""
                MATCH (qa:QAPair)
                WHERE qa.confidence_score > 0.6
                WITH qa,
                     reduce(similarity = 0.0, i IN range(0, size(qa.question_embedding)-1) |
                        similarity + qa.question_embedding[i] * $query_embedding[i]
                     ) as question_similarity
                WHERE question_similarity > 0.7
                MATCH (qa)<-[:HAS_QA_PAIR]-(c:Chunk)<-[:HAS_CHUNK]-(d:Document)
                RETURN qa.question as question,
                       qa.answer as answer,
                       qa.confidence_score as confidence,
                       c.page_num as page_num,
                       d.filename as document,
                       question_similarity as score,
                       'qa_pair' as result_type
                ORDER BY question_similarity DESC
                LIMIT $limit
            """, query_embedding=query_embedding, limit=limit)
            
            return [dict(record) for record in result]
    
    def _search_chunks_with_qa_context(self, query: str, limit: int) -> List[Dict]:
        """Search chunks but boost ranking based on Q&A pair presence"""
        query_embedding = self.embedding_model.encode(query).tolist()
        
        with self.driver.session() as session:
            result = session.run("""
                MATCH (c:Chunk)
                WITH c,
                     reduce(similarity = 0.0, i IN range(0, size(c.embedding)-1) |
                        similarity + c.embedding[i] * $query_embedding[i]
                     ) as chunk_similarity
                OPTIONAL MATCH (c)-[:HAS_QA_PAIR]->(qa:QAPair)
                WITH c, chunk_similarity,
                     CASE WHEN qa IS NOT NULL THEN 0.1 ELSE 0.0 END as qa_boost
                MATCH (c)<-[:HAS_CHUNK]-(d:Document)
                RETURN c.id as chunk_id,
                       c.text as text,
                       c.page_num as page_num,
                       d.filename as document,
                       (chunk_similarity + qa_boost) as score,
                       'chunk' as result_type
                ORDER BY score DESC
                LIMIT $limit
            """, query_embedding=query_embedding, limit=limit)
            
            return [dict(record) for record in result]
    
    def _combine_qa_and_chunk_results(self, qa_results: List[Dict], 
                                     chunk_results: List[Dict]) -> List[Dict]:
        """Combine Q&A and chunk results with appropriate ranking"""
        combined = []
        
        # Add Q&A results with slight score boost
        for qa_result in qa_results:
            qa_result['final_score'] = qa_result['score'] * 1.1  # Boost Q&A matches
            combined.append(qa_result)
        
        # Add chunk results
        for chunk_result in chunk_results:
            chunk_result['final_score'] = chunk_result['score']
            combined.append(chunk_result)
        
        # Sort by final score
        combined.sort(key=lambda x: x['final_score'], reverse=True)
        
        return combined


# Performance impact analysis
QA_PERFORMANCE_ANALYSIS = {
    "estimated_qa_pairs": {
        "total_chunks": 12709,
        "qa_pairs_per_chunk": "1-3 (average 2)",
        "total_estimated_qa_pairs": "20,000-25,000",
        "storage_overhead": "~50MB (embeddings + text)"
    },
    "search_improvements": {
        "intent_understanding": {
            "current": "keyword/semantic matching only",
            "enhanced": "question pattern matching + intent recognition",
            "benefit": "Better understanding of what user is asking"
        },
        "direct_answers": {
            "current": "chunk text returned",
            "enhanced": "direct answers when available + supporting chunks",
            "benefit": "Immediate answers for common questions"
        },
        "ranking_improvement": {
            "current": "semantic similarity only",
            "enhanced": "semantic similarity + Q&A context boost",
            "benefit": "Chunks with Q&A pairs ranked higher (more informative)"
        }
    },
    "expected_performance_gains": {
        "accuracy_improvement": "5-10% for factual questions",
        "response_time": "similar (slight overhead from Q&A matching)",
        "user_experience": "significantly better (direct answers)",
        "training_data": "20K+ synthetic Q&A pairs for future model training"
    }
}

if __name__ == "__main__":
    print("Synthetic Q&A Enhancement Analysis")
    print("=" * 50)
    print(json.dumps(QA_PERFORMANCE_ANALYSIS, indent=2))