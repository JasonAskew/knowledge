#!/usr/bin/env python3
"""
Enhanced GraphRAG Query System
- Vector similarity search with BGE-small
- Multi-path retrieval
- Multi-chunk answer aggregation
- Confidence scoring
"""

import numpy as np
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Tuple, Set
import re
from collections import defaultdict
import json

class EnhancedGraphRAGQuery:
    def __init__(self):
        """Initialize enhanced query system."""
        self.model = SentenceTransformer('BAAI/bge-small-en-v1.5')
        
        # Query enhancement patterns
        self.query_patterns = {
            'definition': [
                'what is', 'what are', 'define', 'definition of', 'explain'
            ],
            'capability': [
                'can i', 'am i able', 'is it possible', 'allowed to', 'may i'
            ],
            'requirement': [
                'requirement', 'minimum', 'maximum', 'eligible', 'criteria',
                'need to', 'must', 'qualification'
            ],
            'process': [
                'how to', 'how do i', 'steps to', 'process for', 'procedure'
            ],
            'cost': [
                'cost', 'fee', 'charge', 'price', 'how much', 'expense'
            ]
        }
    
    def enhance_query(self, query: str) -> Dict:
        """Enhance query with type detection and term expansion."""
        query_lower = query.lower()
        
        # Detect query type
        query_type = 'other'
        for q_type, patterns in self.query_patterns.items():
            if any(pattern in query_lower for pattern in patterns):
                query_type = q_type
                break
        
        # Extract key entities
        entities = self._extract_query_entities(query)
        
        # Expand query terms
        expanded_terms = self._expand_terms(query, query_type)
        
        # Generate query embedding
        query_embedding = self.model.encode(query)
        
        return {
            'original': query,
            'type': query_type,
            'entities': entities,
            'expanded_terms': expanded_terms,
            'embedding': query_embedding
        }
    
    def _extract_query_entities(self, query: str) -> List[Dict]:
        """Extract entities from query."""
        entities = []
        query_lower = query.lower()
        
        # Product entities
        products = ['swap', 'option', 'forward', 'deposit', 'loan', 'swaption']
        for product in products:
            if product in query_lower:
                entities.append({'text': product, 'type': 'PRODUCT'})
        
        # Amount detection
        amount_pattern = r'\$[\d,]+(?:\.\d{2})?|\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:dollars?|AUD|USD)'
        amounts = re.findall(amount_pattern, query, re.IGNORECASE)
        for amount in amounts:
            entities.append({'text': amount, 'type': 'AMOUNT'})
        
        # Institution detection
        institutions = ['westpac', 'wbc', 'sgb', 'st.george', 'bom', 'bsa', 'wib']
        for inst in institutions:
            if inst in query_lower:
                entities.append({'text': inst.upper(), 'type': 'INSTITUTION'})
        
        return entities
    
    def _expand_terms(self, query: str, query_type: str) -> List[str]:
        """Expand query terms based on type."""
        expanded = []
        
        # Type-specific expansions
        if query_type == 'definition':
            expanded.extend(['means', 'refers to', 'defined as', 'description'])
        elif query_type == 'capability':
            expanded.extend(['permitted', 'authorize', 'eligible', 'qualify'])
        elif query_type == 'requirement':
            expanded.extend(['condition', 'prerequisite', 'necessary', 'mandatory'])
        elif query_type == 'process':
            expanded.extend(['procedure', 'method', 'instructions', 'guide'])
        elif query_type == 'cost':
            expanded.extend(['payment', 'amount', 'rate', 'pricing'])
        
        return expanded
    
    def vector_search(self, query_embedding: np.ndarray, chunk_embeddings: List[np.ndarray], 
                     top_k: int = 10) -> List[Tuple[int, float]]:
        """Perform vector similarity search."""
        # Calculate cosine similarities
        similarities = []
        
        query_norm = query_embedding / np.linalg.norm(query_embedding)
        
        for i, chunk_emb in enumerate(chunk_embeddings):
            chunk_norm = chunk_emb / np.linalg.norm(chunk_emb)
            similarity = np.dot(query_norm, chunk_norm)
            similarities.append((i, similarity))
        
        # Sort by similarity
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        return similarities[:top_k]
    
    def multi_path_retrieval(self, enhanced_query: Dict, graph_data: Dict) -> List[Dict]:
        """Perform multi-path retrieval combining multiple signals."""
        results = defaultdict(float)
        chunk_data = {}
        
        # Path 1: Vector similarity search
        if 'embeddings' in graph_data:
            vector_results = self.vector_search(
                enhanced_query['embedding'],
                graph_data['embeddings'],
                top_k=20
            )
            
            for chunk_idx, score in vector_results:
                chunk_id = graph_data['chunks'][chunk_idx]['id']
                results[chunk_id] += score * 0.4  # Weight for vector similarity
                chunk_data[chunk_id] = graph_data['chunks'][chunk_idx]
        
        # Path 2: Entity matching
        query_entities = set(e['text'].lower() for e in enhanced_query['entities'])
        
        for chunk in graph_data['chunks']:
            chunk_id = chunk['id']
            
            # Count entity matches
            entity_matches = 0
            if 'entities' in chunk:
                for entity in chunk['entities']:
                    if entity['text'].lower() in query_entities:
                        entity_matches += 1
            
            if entity_matches > 0:
                results[chunk_id] += (entity_matches / max(1, len(query_entities))) * 0.3
                chunk_data[chunk_id] = chunk
        
        # Path 3: Keyword matching with expanded terms
        all_terms = set(enhanced_query['original'].lower().split())
        all_terms.update(enhanced_query['expanded_terms'])
        
        for chunk in graph_data['chunks']:
            chunk_id = chunk['id']
            chunk_text_lower = chunk['text'].lower()
            
            # Count term matches
            term_matches = sum(1 for term in all_terms if term in chunk_text_lower)
            
            if term_matches > 0:
                results[chunk_id] += (term_matches / len(all_terms)) * 0.2
                chunk_data[chunk_id] = chunk
        
        # Path 4: Query type specific boosting
        if enhanced_query['type'] == 'requirement':
            # Boost chunks with requirement patterns
            for chunk in graph_data['chunks']:
                if chunk.get('has_requirements'):
                    results[chunk['id']] += 0.1
                    chunk_data[chunk['id']] = chunk
        
        elif enhanced_query['type'] == 'cost':
            # Boost chunks with amounts
            for chunk in graph_data['chunks']:
                if chunk.get('has_amounts'):
                    results[chunk['id']] += 0.1
                    chunk_data[chunk['id']] = chunk
        
        # Convert to sorted list
        final_results = []
        for chunk_id, score in sorted(results.items(), key=lambda x: x[1], reverse=True):
            if chunk_id in chunk_data:
                final_results.append({
                    'chunk': chunk_data[chunk_id],
                    'score': score,
                    'chunk_id': chunk_id
                })
        
        return final_results
    
    def aggregate_multi_chunk_answer(self, retrieved_chunks: List[Dict], 
                                   query: str, max_chunks: int = 3) -> Dict:
        """Aggregate answer from multiple chunks."""
        
        if not retrieved_chunks:
            return {
                'answer': 'No relevant information found.',
                'confidence': 0.0,
                'chunks_used': 0,
                'sources': []
            }
        
        # Select top chunks
        top_chunks = retrieved_chunks[:max_chunks]
        
        # Check if chunks are from same document
        doc_ids = set()
        for chunk_info in top_chunks:
            if 'document_id' in chunk_info['chunk']:
                doc_ids.add(chunk_info['chunk']['document_id'])
        
        same_document = len(doc_ids) == 1
        
        # Aggregate based on query type
        enhanced_query = self.enhance_query(query)
        
        if enhanced_query['type'] == 'definition':
            # For definitions, use the highest scoring chunk
            answer = top_chunks[0]['chunk']['text']
            confidence = top_chunks[0]['score']
            
        elif enhanced_query['type'] in ['requirement', 'cost']:
            # For requirements/costs, combine relevant information
            relevant_info = []
            for chunk_info in top_chunks:
                text = chunk_info['chunk']['text']
                # Extract sentences with key terms
                sentences = re.split(r'[.!?]+', text)
                for sent in sentences:
                    if any(term in sent.lower() for term in enhanced_query['entities']):
                        relevant_info.append(sent.strip())
            
            answer = ' '.join(relevant_info[:3])  # Limit to 3 most relevant sentences
            confidence = np.mean([c['score'] for c in top_chunks])
            
        else:
            # For other types, concatenate with context
            if same_document and len(top_chunks) > 1:
                # Chunks from same document - maintain order
                sorted_chunks = sorted(top_chunks, key=lambda x: x['chunk'].get('page_num', 0))
                answer = '\n\n'.join(c['chunk']['text'][:500] for c in sorted_chunks)
            else:
                # Different documents - use scoring order
                answer = '\n\n'.join(c['chunk']['text'][:500] for c in top_chunks)
            
            confidence = top_chunks[0]['score']
        
        # Compile sources
        sources = []
        for chunk_info in top_chunks:
            chunk = chunk_info['chunk']
            sources.append({
                'document': chunk.get('document_name', 'Unknown'),
                'page': chunk.get('page_num', 'N/A'),
                'score': chunk_info['score']
            })
        
        return {
            'answer': answer,
            'confidence': confidence,
            'chunks_used': len(top_chunks),
            'sources': sources,
            'same_document': same_document
        }
    
    def calculate_answer_confidence(self, result: Dict, expected_doc: str = None) -> float:
        """Calculate final confidence score for answer."""
        base_confidence = result['confidence']
        
        # Adjust based on number of supporting chunks
        if result['chunks_used'] >= 3:
            base_confidence *= 1.1
        elif result['chunks_used'] == 1:
            base_confidence *= 0.9
        
        # Adjust based on same document coherence
        if result['same_document'] and result['chunks_used'] > 1:
            base_confidence *= 1.05
        
        # Check document match if expected
        if expected_doc and result['sources']:
            doc_match = any(expected_doc.lower() in s['document'].lower() 
                          for s in result['sources'])
            if doc_match:
                base_confidence *= 1.2
        
        return min(1.0, base_confidence)

def create_enhanced_cypher_query(enhanced_query: Dict) -> str:
    """Create optimized Cypher query for Neo4j."""
    
    # Build entity conditions
    entity_conditions = []
    for entity in enhanced_query['entities']:
        if entity['type'] == 'PRODUCT':
            entity_conditions.append(f"(c)-[:MENTIONS]->(:Product {{name: '{entity['text']}'}})")
        elif entity['type'] == 'INSTITUTION':
            entity_conditions.append(f"(d)-[:ISSUED_BY]->(:Institution {{code: '{entity['text']}'}})")
    
    # Build text conditions
    term_conditions = []
    for term in enhanced_query['original'].lower().split():
        if len(term) > 2:  # Skip short words
            term_conditions.append(f"toLower(c.text) CONTAINS '{term}'")
    
    query = f"""
    MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk)
    WHERE {' OR '.join(term_conditions) if term_conditions else 'true'}
    
    // Entity matching
    {"WITH d, c WHERE " + ' OR '.join(entity_conditions) if entity_conditions else ''}
    
    // Get related information
    OPTIONAL MATCH (c)-[:MENTIONS]->(e:Entity)
    OPTIONAL MATCH (c)-[:NEXT_CHUNK]->(next:Chunk)
    OPTIONAL MATCH (c)<-[:NEXT_CHUNK]-(prev:Chunk)
    
    // Calculate relevance
    WITH d, c, 
         COLLECT(DISTINCT e) as entities,
         next, prev,
         {len([t for t in enhanced_query['original'].lower().split() if len(t) > 2])} as query_terms,
         SIZE([term IN {[t for t in enhanced_query['original'].lower().split() if len(t) > 2]} WHERE toLower(c.text) CONTAINS term]) as matching_terms
    
    WITH d, c, entities, next, prev,
         toFloat(matching_terms) / toFloat(query_terms) as term_coverage,
         CASE WHEN SIZE(entities) > 0 THEN 1.0 ELSE 0.0 END as has_entities
    
    RETURN d.filename as document,
           d.id as document_id,
           c.id as chunk_id,
           c.text as text,
           c.page_num as page_num,
           c.embedding as embedding,
           term_coverage + has_entities * 0.3 as score,
           entities,
           next.text as next_text,
           prev.text as prev_text
    ORDER BY score DESC
    LIMIT 10
    """
    
    return query

def main():
    """Test enhanced query system."""
    print("Enhanced GraphRAG Query System")
    print("="*60)
    
    # Initialize query system
    query_system = EnhancedGraphRAGQuery()
    
    # Test queries
    test_queries = [
        "Can I reduce my Option Premium?",
        "What is an interest rate swaption?",
        "What are the minimum transaction requirements for foreign currency term deposits?",
        "How do I cancel a participating forward contract before maturity?"
    ]
    
    for query in test_queries:
        print(f"\nQuery: {query}")
        print("-" * 40)
        
        # Enhance query
        enhanced = query_system.enhance_query(query)
        print(f"Type: {enhanced['type']}")
        print(f"Entities: {enhanced['entities']}")
        print(f"Expanded terms: {enhanced['expanded_terms'][:5]}")
        
        # Generate Cypher query
        cypher = create_enhanced_cypher_query(enhanced)
        print(f"\nCypher query generated (first 200 chars):")
        print(cypher[:200] + "...")
    
    print("\n✓ Enhanced query system ready!")

if __name__ == "__main__":
    main()