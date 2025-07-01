"""
Enhanced document ingestion with optimized chunking and metadata
"""

import hashlib
import json
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import re
from pathlib import Path

import fitz  # PyMuPDF
import numpy as np
from sentence_transformers import SentenceTransformer
from neo4j import GraphDatabase
import spacy
from langchain.text_splitter import RecursiveCharacterTextSplitter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class EnhancedChunk:
    """Enhanced chunk with additional metadata"""
    id: str
    text: str
    page_num: int
    chunk_index: int
    document_id: str
    embedding: List[float]
    entities: List[Dict[str, str]]
    metadata: Dict[str, Any]
    
    # New fields for enhanced search
    title: Optional[str] = None
    section: Optional[str] = None
    keywords: List[str] = None
    chunk_type: str = "content"  # content, title, list, table
    semantic_density: float = 0.0
    has_definitions: bool = False
    has_examples: bool = False

class EnhancedKnowledgeIngestion:
    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str):
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        
        # Initialize models
        logger.info("Loading enhanced models...")
        self.embedder = SentenceTransformer('BAAI/bge-small-en-v1.5')
        self.nlp = spacy.load('en_core_web_sm')
        
        # Optimized chunking parameters
        self.chunk_size = 512  # tokens
        self.chunk_overlap = 128  # 25% overlap
        
        # Initialize text splitter with better parameters
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size * 4,  # Approximate chars
            chunk_overlap=self.chunk_overlap * 4,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""],
            keep_separator=True
        )
        
        # Financial term patterns
        self.financial_patterns = {
            'product': re.compile(r'\b(deposit|account|option|forward|swap|swaption|collar|cap|floor|FX|FXO|BCF|PFC|RFC|TFC|DCI|WIBTD|TLD|IRS)\b', re.I),
            'amount': re.compile(r'\$[\d,]+(?:\.\d{2})?|\b\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:AUD|USD|EUR|GBP)'),
            'rate': re.compile(r'\d+(?:\.\d+)?%|\b\d+(?:\.\d+)?\s*(?:bp|basis points|percent)'),
            'date': re.compile(r'\b(?:maturity|settlement|expiry|commencement)\s*date\b', re.I),
            'definition': re.compile(r'(?:means|refers to|is defined as|is a|is an)\b', re.I),
            'example': re.compile(r'(?:for example|e\.g\.|example:|such as)\b', re.I)
        }
    
    def extract_document_structure(self, pdf_path: str) -> Dict[str, Any]:
        """Extract document structure including titles, sections, and lists"""
        doc = fitz.open(pdf_path)
        structure = {
            'title': None,
            'sections': [],
            'total_pages': len(doc)
        }
        
        # Extract title from first page
        if len(doc) > 0:
            first_page = doc[0]
            text = first_page.get_text()
            lines = text.strip().split('\n')
            if lines:
                # Assume first non-empty line is title
                for line in lines[:5]:  # Check first 5 lines
                    if line.strip() and len(line.strip()) > 10:
                        structure['title'] = line.strip()
                        break
        
        # Extract section headers (simplified)
        for page_num, page in enumerate(doc):
            text = page.get_text()
            # Look for section headers (lines that are short and possibly in caps)
            lines = text.split('\n')
            for line in lines:
                line = line.strip()
                if line and len(line) < 100 and (line.isupper() or line.endswith(':')):
                    structure['sections'].append({
                        'title': line,
                        'page': page_num + 1
                    })
        
        doc.close()
        return structure
    
    def classify_chunk_type(self, text: str) -> str:
        """Classify chunk type based on content"""
        lines = text.strip().split('\n')
        
        # Check if it's a title/header
        if len(lines) <= 2 and all(len(line) < 100 for line in lines):
            return "title"
        
        # Check if it's a list
        list_markers = sum(1 for line in lines if line.strip().startswith(('•', '-', '*', '1.', '2.', '3.')))
        if list_markers >= 3:
            return "list"
        
        # Check if it's a table-like structure
        if '|' in text or '\t' in text:
            return "table"
        
        return "content"
    
    def extract_keywords(self, text: str) -> List[str]:
        """Extract important keywords from text"""
        keywords = set()
        
        # Extract financial terms
        for pattern_type, pattern in self.financial_patterns.items():
            if pattern_type == 'product':
                matches = pattern.findall(text)
                keywords.update(m.lower() for m in matches)
        
        # Extract noun phrases using spaCy
        doc = self.nlp(text)
        for chunk in doc.noun_chunks:
            if 2 <= len(chunk.text.split()) <= 4:  # 2-4 word phrases
                keywords.add(chunk.text.lower())
        
        return list(keywords)[:10]  # Limit to top 10
    
    def calculate_semantic_density(self, text: str) -> float:
        """Calculate semantic density of chunk"""
        # Simple heuristic: ratio of named entities and financial terms to total words
        doc = self.nlp(text)
        
        entity_count = len(doc.ents)
        financial_terms = sum(len(pattern.findall(text)) for pattern in self.financial_patterns.values())
        total_words = len([token for token in doc if not token.is_stop and not token.is_punct])
        
        if total_words == 0:
            return 0.0
        
        return min(1.0, (entity_count + financial_terms) / total_words * 10)
    
    def create_enhanced_chunks(self, text: str, document_id: str, document_title: str, 
                             page_num: int = 1) -> List[EnhancedChunk]:
        """Create enhanced chunks with additional metadata"""
        chunks = []
        
        # Split text into chunks
        chunk_texts = self.text_splitter.split_text(text)
        
        for chunk_index, chunk_text in enumerate(chunk_texts):
            if not chunk_text.strip():
                continue
            
            # Generate chunk ID
            chunk_id = f"{document_id}_p{page_num}_c{chunk_index}"
            
            # Extract entities
            doc = self.nlp(chunk_text)
            entities = []
            for ent in doc.ents:
                entities.append({
                    'text': ent.text,
                    'type': ent.label_,
                    'start': ent.start_char,
                    'end': ent.end_char
                })
            
            # Extract financial entities
            for match in self.financial_patterns['product'].finditer(chunk_text):
                entities.append({
                    'text': match.group(),
                    'type': 'FINANCIAL_PRODUCT',
                    'start': match.start(),
                    'end': match.end()
                })
            
            # Generate embedding
            embedding = self.embedder.encode(chunk_text, normalize_embeddings=True)
            
            # Detect features
            has_definitions = bool(self.financial_patterns['definition'].search(chunk_text))
            has_examples = bool(self.financial_patterns['example'].search(chunk_text))
            
            # Create enhanced chunk
            chunk = EnhancedChunk(
                id=chunk_id,
                text=chunk_text,
                page_num=page_num,
                chunk_index=chunk_index,
                document_id=document_id,
                embedding=embedding.tolist(),
                entities=entities,
                metadata={
                    'char_count': len(chunk_text),
                    'word_count': len(chunk_text.split()),
                    'sentence_count': len(list(doc.sents))
                },
                title=document_title,
                keywords=self.extract_keywords(chunk_text),
                chunk_type=self.classify_chunk_type(chunk_text),
                semantic_density=self.calculate_semantic_density(chunk_text),
                has_definitions=has_definitions,
                has_examples=has_examples
            )
            
            chunks.append(chunk)
        
        return chunks
    
    def process_document_enhanced(self, pdf_path: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Process document with enhanced extraction"""
        logger.info(f"Processing document with enhanced extraction: {pdf_path}")
        
        # Extract document structure
        structure = self.extract_document_structure(pdf_path)
        
        # Extract text and create chunks
        doc = fitz.open(pdf_path)
        all_chunks = []
        
        document_id = metadata.get('id', Path(pdf_path).stem)
        document_title = structure.get('title', metadata.get('filename', 'Unknown'))
        
        for page_num, page in enumerate(doc):
            text = page.get_text()
            if text.strip():
                chunks = self.create_enhanced_chunks(
                    text, 
                    document_id,
                    document_title,
                    page_num + 1
                )
                all_chunks.extend(chunks)
        
        doc.close()
        
        # Create relationships between chunks
        chunk_relationships = []
        for i in range(len(all_chunks) - 1):
            chunk_relationships.append({
                'from': all_chunks[i].id,
                'to': all_chunks[i + 1].id,
                'type': 'NEXT_CHUNK'
            })
        
        # Extract document-level metadata
        all_keywords = set()
        for chunk in all_chunks:
            all_keywords.update(chunk.keywords or [])
        
        result = {
            'document': {
                'id': document_id,
                'title': document_title,
                'filename': metadata.get('filename'),
                'structure': structure,
                'keywords': list(all_keywords)[:20],
                'chunk_count': len(all_chunks),
                'metadata': metadata
            },
            'chunks': all_chunks,
            'relationships': chunk_relationships,
            'stats': {
                'total_chunks': len(all_chunks),
                'avg_chunk_size': np.mean([c.metadata['word_count'] for c in all_chunks]),
                'chunks_with_definitions': sum(1 for c in all_chunks if c.has_definitions),
                'chunks_with_examples': sum(1 for c in all_chunks if c.has_examples),
                'unique_entities': len(set(e['text'] for c in all_chunks for e in c.entities))
            }
        }
        
        return result
    
    def store_enhanced_knowledge(self, knowledge_data: Dict[str, Any]):
        """Store enhanced knowledge in Neo4j"""
        driver = GraphDatabase.driver(self.neo4j_uri,
                                     auth=(self.neo4j_user, self.neo4j_password))
        
        try:
            with driver.session() as session:
                # Store document
                session.run("""
                    MERGE (d:Document {id: $id})
                    SET d.title = $title,
                        d.filename = $filename,
                        d.keywords = $keywords,
                        d.chunk_count = $chunk_count,
                        d.has_definitions = $has_definitions,
                        d.has_examples = $has_examples
                """, 
                    id=knowledge_data['document']['id'],
                    title=knowledge_data['document']['title'],
                    filename=knowledge_data['document']['filename'],
                    keywords=knowledge_data['document']['keywords'],
                    chunk_count=knowledge_data['document']['chunk_count'],
                    has_definitions=knowledge_data['stats']['chunks_with_definitions'] > 0,
                    has_examples=knowledge_data['stats']['chunks_with_examples'] > 0
                )
                
                # Store chunks with enhanced metadata
                for chunk in knowledge_data['chunks']:
                    session.run("""
                        MERGE (c:Chunk {id: $id})
                        SET c.text = $text,
                            c.page_num = $page_num,
                            c.chunk_index = $chunk_index,
                            c.embedding = $embedding,
                            c.keywords = $keywords,
                            c.chunk_type = $chunk_type,
                            c.semantic_density = $semantic_density,
                            c.has_definitions = $has_definitions,
                            c.has_examples = $has_examples,
                            c.word_count = $word_count
                    """,
                        id=chunk.id,
                        text=chunk.text,
                        page_num=chunk.page_num,
                        chunk_index=chunk.chunk_index,
                        embedding=chunk.embedding,
                        keywords=chunk.keywords,
                        chunk_type=chunk.chunk_type,
                        semantic_density=chunk.semantic_density,
                        has_definitions=chunk.has_definitions,
                        has_examples=chunk.has_examples,
                        word_count=chunk.metadata['word_count']
                    )
                    
                    # Create document relationship
                    session.run("""
                        MATCH (d:Document {id: $doc_id})
                        MATCH (c:Chunk {id: $chunk_id})
                        MERGE (d)-[:HAS_CHUNK]->(c)
                    """, doc_id=knowledge_data['document']['id'], chunk_id=chunk.id)
                    
                    # Store entities
                    for entity in chunk.entities:
                        session.run("""
                            MERGE (e:Entity {text: $text, type: $type})
                            WITH e
                            MATCH (c:Chunk {id: $chunk_id})
                            MERGE (c)-[:CONTAINS_ENTITY]->(e)
                        """, text=entity['text'].lower(), type=entity['type'], chunk_id=chunk.id)
                
                # Create chunk relationships
                for rel in knowledge_data['relationships']:
                    session.run("""
                        MATCH (c1:Chunk {id: $from})
                        MATCH (c2:Chunk {id: $to})
                        MERGE (c1)-[:NEXT_CHUNK]->(c2)
                    """, **rel)
                
                # Create similarity relationships for chunks with high keyword overlap
                session.run("""
                    MATCH (c1:Chunk), (c2:Chunk)
                    WHERE c1.id < c2.id
                    AND size([k IN c1.keywords WHERE k IN c2.keywords]) >= 3
                    MERGE (c1)-[:SIMILAR_TO]->(c2)
                """)
                
                logger.info(f"Stored enhanced document with {len(knowledge_data['chunks'])} chunks")
                
        finally:
            driver.close()