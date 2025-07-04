#!/usr/bin/env python3
"""
Autonomous Knowledge Ingestion Agent
Responsible for parsing PDFs, extracting entities, generating embeddings,
and constructing an optimized knowledge graph
"""

import os
import json
import logging
import hashlib
import fitz  # PyMuPDF
import spacy
import numpy as np
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import re
from collections import defaultdict
import time
from .hierarchical_classifier import HierarchicalDocumentClassifier

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Financial entity patterns
FINANCIAL_PATTERNS = {
    'PRODUCT': {
        'patterns': [
            r'\b(?:FX |Foreign Exchange )?(?:Forward|Swap|Option|Future)s?\b',
            r'\b(?:Interest Rate |IR )?(?:Swap|Cap|Floor|Collar|Swaption)s?\b',
            r'\b(?:Term |Call |Notice )?Deposits?\b',
            r'\b(?:Cross Currency |Currency )?Swaps?\b',
            r'\bStructured (?:Product|Investment|Deposit)s?\b',
            r'\b(?:Range |Participating |Window )?Forward Contracts?\b',
            r'\b(?:Dual Currency |Green Tailored )?(?:Investment|Deposit)s?\b',
            r'\b(?:Fixed Rate |Floating Rate )?(?:Note|Bond|Bill)s?\b',
        ],
        'keywords': [
            'swap', 'option', 'forward', 'future', 'deposit', 'investment',
            'swaption', 'collar', 'structured product', 'derivative'
        ]
    },
    'FINANCIAL_TERM': {
        'patterns': [
            r'\b(?:strike |spot |forward )?(?:price|rate|premium)\b',
            r'\b(?:notional |principal )?amount\b',
            r'\b(?:maturity |settlement |trade |value )?date\b',
            r'\b(?:interest |coupon |discount )?rate\b',
            r'\bmargin (?:call|requirement)\b',
            r'\b(?:bid|ask|mid) (?:price|rate)\b',
        ],
        'keywords': [
            'premium', 'strike', 'notional', 'maturity', 'settlement',
            'margin', 'spread', 'basis points', 'coupon', 'yield'
        ]
    },
    'REQUIREMENT': {
        'patterns': [
            r'(?:minimum|maximum) (?:amount|deposit|investment|balance)',
            r'(?:requires?|must have|need to have)',
            r'eligibility (?:criteria|requirement)',
            r'(?:qualified|wholesale|retail) (?:investor|client)',
        ]
    },
    'ACTION': {
        'patterns': [
            r'\b(?:can|may|able to|allow(?:ed|s)?|permit(?:ted|s)?)\b',
            r'\b(?:cannot|may not|unable to|prohibit(?:ed|s)?)\b',
            r'\b(?:must|shall|required to|need to)\b',
        ]
    }
}

@dataclass
class ChunkMetadata:
    """Metadata for a text chunk"""
    chunk_id: str
    document_id: str
    page_num: int
    chunk_index: int
    char_start: int
    char_end: int
    token_count: int
    has_table: bool = False
    chunk_type: str = "text"  # text, table, list

@dataclass
class ExtractedEntity:
    """Represents an extracted entity"""
    text: str
    entity_type: str
    start_char: int
    end_char: int
    confidence: float
    normalized_form: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ProcessedChunk:
    """Processed chunk with text, metadata, entities, and embedding"""
    text: str
    metadata: ChunkMetadata
    entities: List[ExtractedEntity]
    embedding: Optional[np.ndarray] = None
    keywords: List[str] = field(default_factory=list)
    semantic_density: float = 0.0
    has_definitions: bool = False
    has_examples: bool = False
    chunk_type: str = "content"  # content, definition, example, list, table

class KnowledgeIngestionAgent:
    """Main ingestion agent class"""
    
    def __init__(self, 
                 neo4j_uri: str = "bolt://localhost:7687",
                 neo4j_user: str = "neo4j", 
                 neo4j_password: str = "password",
                 chunk_size: int = 512,
                 chunk_overlap: int = 100,
                 batch_size: int = 32,
                 num_workers: int = 4,
                 exclusion_config_path: str = None):
        """Initialize the ingestion agent"""
        
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.batch_size = batch_size
        self.num_workers = num_workers
        
        # Load exclusion configuration
        self.exclusions = self._load_exclusions(exclusion_config_path)
        
        # Initialize models
        logger.info("Loading models...")
        self.nlp = self._load_spacy_model()
        self.embedder = SentenceTransformer('BAAI/bge-small-en-v1.5')
        
        # Initialize hierarchical classifier
        self.hierarchical_classifier = HierarchicalDocumentClassifier()
        
        # Initialize deduplication components
        self.entity_cache = {}
        self.chunk_hashes = set()
        self.tfidf_vectorizer = TfidfVectorizer(max_features=1000)
        self.entity_vectors = None
        
        # Statistics
        self.stats = {
            'documents_processed': 0,
            'chunks_created': 0,
            'entities_extracted': 0,
            'duplicates_removed': 0,
            'processing_time': 0
        }
    
    def _load_spacy_model(self) -> spacy.Language:
        """Load and configure spaCy model"""
        try:
            nlp = spacy.load("en_core_web_sm")
        except:
            logger.warning("Downloading spaCy model...")
            os.system("python -m spacy download en_core_web_sm")
            nlp = spacy.load("en_core_web_sm")
        
        # Add custom patterns to entity ruler
        ruler = nlp.add_pipe("entity_ruler", before="ner")
        patterns = []
        
        for entity_type, config in FINANCIAL_PATTERNS.items():
            if 'keywords' in config:
                for keyword in config['keywords']:
                    patterns.append({
                        "label": entity_type,
                        "pattern": keyword.lower()
                    })
        
        ruler.add_patterns(patterns)
        return nlp
    
    def _load_exclusions(self, config_path: str = None) -> Dict[str, Any]:
        """Load exclusion configuration"""
        default_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'exclusion_config.json')
        config_path = config_path or default_path
        
        if os.path.exists(config_path):
            logger.info(f"Loading exclusion config from {config_path}")
            with open(config_path, 'r') as f:
                return json.load(f)
        else:
            logger.info("No exclusion config found, proceeding without exclusions")
            return {"exclusions": {"files": [], "patterns": []}}
    
    def _is_excluded(self, filename: str) -> Tuple[bool, str]:
        """Check if a file should be excluded from ingestion"""
        # Check exact filename matches
        for exclusion in self.exclusions.get('exclusions', {}).get('files', []):
            if exclusion['filename'] == filename:
                return True, exclusion.get('reason', 'Excluded by configuration')
        
        # Check pattern matches
        import re
        for pattern_config in self.exclusions.get('exclusions', {}).get('patterns', []):
            if pattern_config.get('regex', False):
                pattern = pattern_config['pattern']
                if re.match(pattern, filename):
                    return True, pattern_config.get('reason', 'Excluded by pattern match')
        
        return False, ""
    
    def extract_pdf_content(self, pdf_path: str) -> List[Dict[str, Any]]:
        """Extract content from PDF using PyMuPDF with OCR fallback"""
        logger.info(f"Extracting content from {pdf_path}")
        
        pages_content = []
        
        try:
            pdf_document = fitz.open(pdf_path)
            total_text_length = 0
            
            for page_num, page in enumerate(pdf_document):
                # Extract text blocks with position information
                blocks = page.get_text("blocks")
                
                # Detect tables based on block positions
                table_blocks = self._detect_tables(blocks)
                
                # Extract full page text
                page_text = page.get_text()
                
                pages_content.append({
                    'page_num': page_num + 1,
                    'text': page_text,
                    'blocks': blocks,
                    'has_table': len(table_blocks) > 0,
                    'table_blocks': table_blocks,
                    'char_count': len(page_text)
                })
                
                total_text_length += len(page_text.strip())
            
            pdf_document.close()
            
            # Check if PDF has no extractable text (likely scanned)
            if total_text_length < 100:  # Less than 100 chars total
                logger.info(f"PDF appears to be scanned or has minimal text. Attempting OCR...")
                ocr_content = self._extract_pdf_with_ocr(pdf_path)
                if ocr_content:
                    pages_content = ocr_content
            
        except Exception as e:
            logger.error(f"Error extracting PDF content: {e}")
            raise
        
        return pages_content
    
    def _extract_pdf_with_ocr(self, pdf_path: str) -> List[Dict[str, Any]]:
        """Extract text from PDF using OCR"""
        try:
            import pytesseract
            from pdf2image import convert_from_path
            from PIL import Image
            
            logger.info("Performing OCR on PDF pages...")
            pages_content = []
            
            # Convert PDF to images
            images = convert_from_path(pdf_path, dpi=300)
            
            for page_num, image in enumerate(images):
                # Perform OCR on the image
                ocr_text = pytesseract.image_to_string(image, lang='eng')
                
                # Clean up the text
                ocr_text = ocr_text.strip()
                
                if ocr_text:
                    logger.info(f"OCR extracted {len(ocr_text)} characters from page {page_num + 1}")
                    pages_content.append({
                        'page_num': page_num + 1,
                        'text': ocr_text,
                        'blocks': [],  # No block info from OCR
                        'has_table': False,
                        'table_blocks': [],
                        'char_count': len(ocr_text),
                        'ocr_extracted': True
                    })
                else:
                    logger.warning(f"No text extracted from page {page_num + 1}")
            
            return pages_content if pages_content else None
            
        except ImportError as e:
            logger.error(f"OCR dependencies not installed: {e}")
            logger.info("Install with: pip install pytesseract pdf2image")
            return None
        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")
            return None
    
    def _detect_tables(self, blocks: List) -> List[Dict]:
        """Simple table detection based on block positioning"""
        table_blocks = []
        
        # Group blocks by vertical position
        y_groups = defaultdict(list)
        for block in blocks:
            if len(block) >= 5:  # Ensure block has position data
                y_pos = int(block[1] / 10) * 10  # Round to nearest 10
                y_groups[y_pos].append(block)
        
        # Detect potential table rows (multiple blocks at same y position)
        for y_pos, row_blocks in y_groups.items():
            if len(row_blocks) >= 3:  # At least 3 columns
                table_blocks.extend(row_blocks)
        
        return table_blocks
    
    def create_chunks(self, pages_content: List[Dict], document_id: str) -> List[ProcessedChunk]:
        """Create smart chunks from page content"""
        logger.info(f"Creating chunks for document {document_id}")
        
        chunks = []
        current_chunk_index = 0
        
        for page_data in pages_content:
            page_num = page_data['page_num']
            text = page_data['text']
            
            # Split into sentences for smart chunking
            doc = self.nlp(text)
            sentences = [sent.text for sent in doc.sents]
            
            current_chunk = []
            current_tokens = 0
            chunk_start_char = 0
            
            for sent in sentences:
                sent_tokens = len(sent.split())
                
                if current_tokens + sent_tokens > self.chunk_size and current_chunk:
                    # Create chunk
                    chunk_text = ' '.join(current_chunk)
                    chunk_id = f"{document_id}_p{page_num}_c{current_chunk_index}"
                    
                    metadata = ChunkMetadata(
                        chunk_id=chunk_id,
                        document_id=document_id,
                        page_num=page_num,
                        chunk_index=current_chunk_index,
                        char_start=chunk_start_char,
                        char_end=chunk_start_char + len(chunk_text),
                        token_count=current_tokens,
                        has_table=page_data['has_table']
                    )
                    
                    # Extract entities
                    entities = self.extract_entities(chunk_text)
                    
                    # Extract keywords
                    keywords = self.extract_keywords(chunk_text)
                    
                    # Calculate enhanced fields
                    semantic_density = self.calculate_semantic_density(chunk_text)
                    has_definitions = self.detect_definitions(chunk_text)
                    has_examples = self.detect_examples(chunk_text)
                    
                    # Determine chunk type
                    chunk_type = "content"
                    if has_definitions:
                        chunk_type = "definition"
                    elif has_examples:
                        chunk_type = "example"
                    elif metadata.has_table:
                        chunk_type = "table"
                    
                    chunk = ProcessedChunk(
                        text=chunk_text,
                        metadata=metadata,
                        entities=entities,
                        keywords=keywords,
                        semantic_density=semantic_density,
                        has_definitions=has_definitions,
                        has_examples=has_examples,
                        chunk_type=chunk_type
                    )
                    
                    chunks.append(chunk)
                    
                    # Reset for next chunk with overlap
                    overlap_sents = current_chunk[-2:] if len(current_chunk) > 2 else current_chunk
                    current_chunk = overlap_sents + [sent]
                    current_tokens = sum(len(s.split()) for s in current_chunk)
                    chunk_start_char = chunk_start_char + len(chunk_text) - len(' '.join(overlap_sents))
                    current_chunk_index += 1
                else:
                    current_chunk.append(sent)
                    current_tokens += sent_tokens
            
            # Handle remaining content
            if current_chunk:
                chunk_text = ' '.join(current_chunk)
                chunk_id = f"{document_id}_p{page_num}_c{current_chunk_index}"
                
                metadata = ChunkMetadata(
                    chunk_id=chunk_id,
                    document_id=document_id,
                    page_num=page_num,
                    chunk_index=current_chunk_index,
                    char_start=chunk_start_char,
                    char_end=chunk_start_char + len(chunk_text),
                    token_count=current_tokens,
                    has_table=page_data['has_table']
                )
                
                entities = self.extract_entities(chunk_text)
                keywords = self.extract_keywords(chunk_text)
                
                # Calculate enhanced fields
                semantic_density = self.calculate_semantic_density(chunk_text)
                has_definitions = self.detect_definitions(chunk_text)
                has_examples = self.detect_examples(chunk_text)
                
                # Determine chunk type
                chunk_type = "content"
                if has_definitions:
                    chunk_type = "definition"
                elif has_examples:
                    chunk_type = "example"
                elif metadata.has_table:
                    chunk_type = "table"
                
                chunk = ProcessedChunk(
                    text=chunk_text,
                    metadata=metadata,
                    entities=entities,
                    keywords=keywords,
                    semantic_density=semantic_density,
                    has_definitions=has_definitions,
                    has_examples=has_examples,
                    chunk_type=chunk_type
                )
                
                chunks.append(chunk)
                current_chunk_index += 1
        
        self.stats['chunks_created'] += len(chunks)
        return chunks
    
    def extract_entities(self, text: str) -> List[ExtractedEntity]:
        """Extract entities using spaCy and custom patterns"""
        entities = []
        
        # SpaCy NER
        doc = self.nlp(text)
        for ent in doc.ents:
            if ent.label_ in ['ORG', 'MONEY', 'DATE', 'PERCENT', 'CARDINAL']:
                entity = ExtractedEntity(
                    text=ent.text,
                    entity_type=ent.label_,
                    start_char=ent.start_char,
                    end_char=ent.end_char,
                    confidence=0.9
                )
                entities.append(entity)
        
        # Custom pattern matching
        for entity_type, config in FINANCIAL_PATTERNS.items():
            if 'patterns' in config:
                for pattern in config['patterns']:
                    matches = re.finditer(pattern, text, re.IGNORECASE)
                    for match in matches:
                        entity = ExtractedEntity(
                            text=match.group(),
                            entity_type=entity_type,
                            start_char=match.start(),
                            end_char=match.end(),
                            confidence=0.85
                        )
                        entities.append(entity)
        
        # Extract amounts
        amount_pattern = r'\$[\d,]+(?:\.\d{2})?(?:\s*(?:million|billion|k|m|b))?'
        for match in re.finditer(amount_pattern, text, re.IGNORECASE):
            entity = ExtractedEntity(
                text=match.group(),
                entity_type='AMOUNT',
                start_char=match.start(),
                end_char=match.end(),
                confidence=0.95,
                attributes={'currency': 'USD'}
            )
            entities.append(entity)
        
        # Extract percentages
        percent_pattern = r'\d+(?:\.\d+)?%'
        for match in re.finditer(percent_pattern, text):
            entity = ExtractedEntity(
                text=match.group(),
                entity_type='PERCENTAGE',
                start_char=match.start(),
                end_char=match.end(),
                confidence=0.95
            )
            entities.append(entity)
        
        # Deduplicate entities
        unique_entities = self._deduplicate_entities(entities)
        
        self.stats['entities_extracted'] += len(unique_entities)
        return unique_entities
    
    def _deduplicate_entities(self, entities: List[ExtractedEntity]) -> List[ExtractedEntity]:
        """Remove duplicate entities based on text and position"""
        seen = set()
        unique_entities = []
        
        for entity in entities:
            # Create a unique key
            key = (entity.text.lower(), entity.entity_type, entity.start_char)
            
            if key not in seen:
                seen.add(key)
                unique_entities.append(entity)
            else:
                self.stats['duplicates_removed'] += 1
        
        return unique_entities
    
    def extract_keywords(self, text: str, top_n: int = 10) -> List[str]:
        """Extract keywords using TF-IDF"""
        # Simple keyword extraction using spaCy
        doc = self.nlp(text.lower())
        
        # Extract noun phrases and named entities
        keywords = []
        
        # Add noun phrases
        for chunk in doc.noun_chunks:
            if len(chunk.text.split()) <= 3:  # Limit to 3-word phrases
                keywords.append(chunk.text)
        
        # Add important single tokens
        for token in doc:
            if (token.pos_ in ['NOUN', 'PROPN'] and 
                not token.is_stop and 
                len(token.text) > 3):
                keywords.append(token.text)
        
        # Deduplicate and return top keywords
        unique_keywords = list(set(keywords))
        return unique_keywords[:top_n]
    
    def calculate_semantic_density(self, text: str) -> float:
        """Calculate semantic density based on entity and keyword density"""
        doc = self.nlp(text)
        total_tokens = len([t for t in doc if not t.is_punct])
        
        if total_tokens == 0:
            return 0.0
        
        # Count entities and important terms
        entity_count = len(doc.ents)
        keyword_count = len([t for t in doc if t.pos_ in ['NOUN', 'PROPN'] and not t.is_stop])
        
        # Calculate density (ratio of meaningful tokens)
        density = (entity_count + keyword_count) / total_tokens
        return min(density, 1.0)  # Cap at 1.0
    
    def detect_definitions(self, text: str) -> bool:
        """Detect if chunk contains definitions"""
        definition_patterns = [
            r'\bis\s+defined\s+as\b',
            r'\bmeans\b.*\b(?:the|a|an)\b',
            r'\brefers?\s+to\b',
            r'\b(?:called|known\s+as)\b',
            r':\s*[A-Z][^.]*\.',  # Colon followed by capitalized explanation
            r'"[^"]+"\s+(?:is|means|refers)',
        ]
        
        text_lower = text.lower()
        for pattern in definition_patterns:
            if re.search(pattern, text_lower):
                return True
        return False
    
    def detect_examples(self, text: str) -> bool:
        """Detect if chunk contains examples"""
        example_patterns = [
            r'\bfor\s+example\b',
            r'\be\.g\.\b',
            r'\bsuch\s+as\b',
            r'\bincluding\b',
            r'\bfor\s+instance\b',
            r'\bexample\s*:\s*',
        ]
        
        text_lower = text.lower()
        for pattern in example_patterns:
            if re.search(pattern, text_lower):
                return True
        return False
    
    def generate_embeddings(self, chunks: List[ProcessedChunk]) -> List[ProcessedChunk]:
        """Generate embeddings for chunks in batches"""
        logger.info(f"Generating embeddings for {len(chunks)} chunks")
        
        # Process in batches
        for i in range(0, len(chunks), self.batch_size):
            batch = chunks[i:i + self.batch_size]
            texts = [chunk.text for chunk in batch]
            
            # Generate embeddings
            embeddings = self.embedder.encode(texts, 
                                            convert_to_numpy=True,
                                            show_progress_bar=False)
            
            # Assign embeddings to chunks
            for j, chunk in enumerate(batch):
                chunk.embedding = embeddings[j]
        
        return chunks
    
    def deduplicate_content(self, chunks: List[ProcessedChunk]) -> List[ProcessedChunk]:
        """Remove duplicate chunks based on content similarity"""
        logger.info("Deduplicating chunks...")
        
        unique_chunks = []
        
        for chunk in chunks:
            # Create content hash
            content_hash = hashlib.md5(chunk.text.encode()).hexdigest()
            
            if content_hash not in self.chunk_hashes:
                self.chunk_hashes.add(content_hash)
                unique_chunks.append(chunk)
            else:
                self.stats['duplicates_removed'] += 1
        
        # Advanced deduplication using embeddings
        if len(unique_chunks) > 1:
            unique_chunks = self._semantic_deduplication(unique_chunks)
        
        return unique_chunks
    
    def _semantic_deduplication(self, chunks: List[ProcessedChunk], 
                               threshold: float = 0.95) -> List[ProcessedChunk]:
        """Remove semantically similar chunks"""
        if not chunks or chunks[0].embedding is None:
            return chunks
        
        embeddings = np.array([chunk.embedding for chunk in chunks])
        similarities = cosine_similarity(embeddings)
        
        # Mark chunks for removal
        to_remove = set()
        
        for i in range(len(chunks)):
            if i in to_remove:
                continue
                
            for j in range(i + 1, len(chunks)):
                if j in to_remove:
                    continue
                    
                if similarities[i, j] > threshold:
                    # Keep the chunk with more entities
                    if len(chunks[i].entities) >= len(chunks[j].entities):
                        to_remove.add(j)
                    else:
                        to_remove.add(i)
                        break
        
        # Return chunks not marked for removal
        unique_chunks = [chunk for i, chunk in enumerate(chunks) if i not in to_remove]
        self.stats['duplicates_removed'] += len(to_remove)
        
        return unique_chunks
    
    def build_graph(self, chunks: List[ProcessedChunk], document_metadata: Dict[str, Any]):
        """Build Neo4j graph from processed chunks with validation"""
        logger.info("Building knowledge graph...")
        
        from neo4j import GraphDatabase
        try:
            from .ingestion_validator import IngestionValidator
            use_validator = True
        except ImportError:
            # Fallback if running as script
            try:
                from ingestion_validator import IngestionValidator
                use_validator = True
            except ImportError:
                use_validator = False
                logger.warning("Ingestion validator not available, proceeding without validation")
        
        driver = GraphDatabase.driver(self.neo4j_uri, 
                                    auth=(self.neo4j_user, self.neo4j_password))
        
        validator = IngestionValidator(driver) if use_validator else None
        
        try:
            with driver.session() as session:
                # Create or update document node
                doc_id = document_metadata.get('document_id')
                
                # First, delete any existing document and its relationships
                session.run("""
                    MATCH (d:Document {id: $doc_id})
                    OPTIONAL MATCH (d)-[:HAS_CHUNK]->(c:Chunk)
                    OPTIONAL MATCH (c)-[:CONTAINS_ENTITY]->(e:Entity)
                    DETACH DELETE c
                """, doc_id=doc_id)
                
                # Classify document into hierarchy
                # Get document text from first few chunks for classification
                document_text = ' '.join([chunk.text for chunk in chunks[:10]])[:5000]  # First 5000 chars
                classification = self.hierarchical_classifier.classify_document(
                    filename=document_metadata.get('filename', ''),
                    content=document_text,
                    metadata=document_metadata
                )
                
                # Now create the document node with hierarchy
                session.run("""
                    MERGE (d:Document {id: $doc_id})
                    SET d.filename = $filename,
                        d.path = $path,
                        d.total_pages = $total_pages,
                        d.processed_date = $processed_date,
                        d.category = $category,
                        d.institution = $institution,
                        d.division = $division,
                        d.division_code = $division_code,
                        d.category_hierarchy = $category_hierarchy,
                        d.product_scope = $product_scope,
                        d.hierarchy_confidence = $hierarchy_confidence
                    
                    // Create relationships to hierarchy nodes
                    WITH d
                    MATCH (div:Division {code: $division_code})
                    MERGE (d)-[:BELONGS_TO_DIVISION]->(div)
                    
                    WITH d
                    MATCH (cat:Category {name: $category_hierarchy, division: $division_code})
                    MERGE (d)-[:COVERS_CATEGORY]->(cat)
                    
                    // Link to relevant products
                    WITH d
                    UNWIND $product_scope as product_name
                    MATCH (p:Product {name: product_name, category: $category_hierarchy})
                    MERGE (d)-[:COVERS_PRODUCT]->(p)
                """, 
                doc_id=doc_id,
                filename=document_metadata.get('filename'),
                path=document_metadata.get('path'),
                total_pages=document_metadata.get('total_pages'),
                processed_date=datetime.now().isoformat(),
                category=document_metadata.get('category', 'misc'),
                institution=classification.institution,
                division=classification.division,
                division_code=classification.division_code,
                category_hierarchy=classification.category,
                product_scope=classification.products,
                hierarchy_confidence=classification.confidence)
                
                # Process chunks in batches
                for i in range(0, len(chunks), 10):
                    batch = chunks[i:i + 10]
                    
                    # Create chunk nodes
                    for chunk in batch:
                        session.run("""
                            CREATE (c:Chunk {
                                id: $chunk_id,
                                text: $text,
                                page_num: $page_num,
                                chunk_index: $chunk_index,
                                token_count: $token_count,
                                embedding: $embedding,
                                semantic_density: $semantic_density,
                                has_definitions: $has_definitions,
                                has_examples: $has_examples,
                                chunk_type: $chunk_type,
                                keywords: $keywords,
                                division: $division,
                                category_hierarchy: $category_hierarchy
                            })
                        """,
                        chunk_id=chunk.metadata.chunk_id,
                        text=chunk.text,
                        page_num=chunk.metadata.page_num,
                        chunk_index=chunk.metadata.chunk_index,
                        token_count=chunk.metadata.token_count,
                        embedding=chunk.embedding.tolist() if chunk.embedding is not None else None,
                        semantic_density=chunk.semantic_density,
                        has_definitions=chunk.has_definitions,
                        has_examples=chunk.has_examples,
                        chunk_type=chunk.chunk_type,
                        keywords=chunk.keywords,
                        division=classification.division,
                        category_hierarchy=classification.category)
                        
                        # Create document-chunk relationship
                        session.run("""
                            MATCH (d:Document {id: $doc_id})
                            MATCH (c:Chunk {id: $chunk_id})
                            CREATE (d)-[:HAS_CHUNK]->(c)
                        """,
                        doc_id=doc_id,
                        chunk_id=chunk.metadata.chunk_id)
                        
                        # Create entity nodes and relationships
                        for entity in chunk.entities:
                            # Create or merge entity
                            session.run("""
                                MERGE (e:Entity {
                                    text: $text,
                                    type: $type
                                })
                                ON CREATE SET 
                                    e.first_seen = $date,
                                    e.occurrences = 1
                                ON MATCH SET
                                    e.occurrences = e.occurrences + 1
                            """,
                            text=entity.text,
                            type=entity.entity_type,
                            date=datetime.now().isoformat())
                            
                            # Create chunk-entity relationship
                            session.run("""
                                MATCH (c:Chunk {id: $chunk_id})
                                MATCH (e:Entity {text: $text, type: $type})
                                CREATE (c)-[:CONTAINS_ENTITY {
                                    confidence: $confidence,
                                    start_char: $start_char,
                                    end_char: $end_char
                                }]->(e)
                            """,
                            chunk_id=chunk.metadata.chunk_id,
                            text=entity.text,
                            type=entity.entity_type,
                            confidence=entity.confidence,
                            start_char=entity.start_char,
                            end_char=entity.end_char)
                
                # Create chunk sequence relationships
                for i in range(len(chunks) - 1):
                    if chunks[i].metadata.page_num == chunks[i + 1].metadata.page_num:
                        session.run("""
                            MATCH (c1:Chunk {id: $chunk1_id})
                            MATCH (c2:Chunk {id: $chunk2_id})
                            CREATE (c1)-[:NEXT_CHUNK]->(c2)
                        """,
                        chunk1_id=chunks[i].metadata.chunk_id,
                        chunk2_id=chunks[i + 1].metadata.chunk_id)
                
                # Create indexes for optimization
                session.run("CREATE INDEX IF NOT EXISTS FOR (c:Chunk) ON (c.id)")
                session.run("CREATE INDEX IF NOT EXISTS FOR (e:Entity) ON (e.text)")
                session.run("CREATE INDEX IF NOT EXISTS FOR (e:Entity) ON (e.type)")
                session.run("CREATE INDEX IF NOT EXISTS FOR (d:Document) ON (d.id)")
                
                # Update document chunk count
                session.run("""
                    MATCH (d:Document {id: $doc_id})
                    OPTIONAL MATCH (d)-[:HAS_CHUNK]->(c:Chunk)
                    WITH d, count(c) as chunk_count
                    SET d.chunk_count = chunk_count
                """, doc_id=doc_id)
                
                # Create vector index for similarity search
                session.run("""
                    CREATE VECTOR INDEX `chunk-embeddings` IF NOT EXISTS
                    FOR (c:Chunk) ON (c.embedding)
                    OPTIONS {indexConfig: {
                        `vector.dimensions`: 384,
                        `vector.similarity_function`: 'cosine'
                    }}
                """)
                
                logger.info("Graph construction completed")
                
                # Validate the ingestion completeness if validator available
                if validator:
                    validation_result = validator.validate_document_completeness(
                        doc_id, 
                        [], # We don't have pages_content here, but chunks have the info
                        chunks
                    )
                    
                    validator.log_validation_result(validation_result)
                    
                    # If validation fails, rollback
                    if validation_result['status'] in ['incomplete', 'critical']:
                        logger.error(f"Validation failed for {doc_id}: {validation_result['issues']}")
                        validator.rollback_incomplete_document(doc_id)
                        raise ValueError(f"Document {doc_id} failed validation and was rolled back")
                
        finally:
            driver.close()
    
    def optimize_graph(self):
        """Optimize graph for search performance"""
        logger.info("Optimizing graph...")
        
        from neo4j import GraphDatabase
        
        driver = GraphDatabase.driver(self.neo4j_uri, 
                                    auth=(self.neo4j_user, self.neo4j_password))
        
        try:
            with driver.session() as session:
                # Create vector index for embeddings
                session.run("""
                    CALL db.index.vector.createNodeIndex(
                        'chunk-embeddings',
                        'Chunk',
                        'embedding',
                        384,
                        'cosine'
                    )
                """)
                
                # Create full-text search indexes
                session.run("""
                    CALL db.index.fulltext.createNodeIndex(
                        'chunk-text',
                        ['Chunk'],
                        ['text']
                    )
                """)
                
                session.run("""
                    CALL db.index.fulltext.createNodeIndex(
                        'entity-text',
                        ['Entity'],
                        ['text']
                    )
                """)
                
                # Analyze and optimize entity relationships
                session.run("""
                    MATCH (e1:Entity)-[:APPEARS_WITH]->(e2:Entity)
                    WITH e1, e2, count(*) as cooccurrence
                    WHERE cooccurrence > 5
                    MERGE (e1)-[r:RELATED_TO]->(e2)
                    SET r.strength = cooccurrence
                """)
                
                logger.info("Graph optimization completed")
                
        except Exception as e:
            logger.warning(f"Some optimizations may have failed: {e}")
        finally:
            driver.close()
    
    def process_inventory(self, inventory_file: str, s3_bucket: Optional[str] = None):
        """Process all PDFs in an inventory file"""
        logger.info(f"Processing inventory: {inventory_file}")
        
        start_time = time.time()
        
        # Load inventory
        with open(inventory_file, 'r') as f:
            inventory = json.load(f)
        
        total_files = len(inventory['files'])
        logger.info(f"Found {total_files} files to process")
        
        # Process files with progress tracking
        with ProcessPoolExecutor(max_workers=self.num_workers) as executor:
            futures = []
            
            for file_info in inventory['files']:
                # Determine file path
                if s3_bucket:
                    # Download from S3 if needed
                    local_path = self._download_from_s3(file_info, s3_bucket)
                else:
                    local_path = file_info['local_path']
                    # Adjust path if needed
                    if not os.path.isabs(local_path):
                        local_path = os.path.join('knowledge_discovery_agent', local_path)
                
                if os.path.exists(local_path):
                    future = executor.submit(self.process_single_pdf, local_path, file_info)
                    futures.append(future)
                else:
                    logger.warning(f"File not found: {local_path}")
            
            # Process results
            completed = 0
            for future in as_completed(futures):
                try:
                    result = future.result()
                    completed += 1
                    logger.info(f"Progress: {completed}/{len(futures)} files processed")
                except Exception as e:
                    logger.error(f"Error processing file: {e}")
        
        # Final statistics
        self.stats['processing_time'] = time.time() - start_time
        logger.info(f"Processing completed in {self.stats['processing_time']:.2f} seconds")
        logger.info(f"Statistics: {json.dumps(self.stats, indent=2)}")
        
        # Save statistics
        with open('ingestion_stats.json', 'w') as f:
            json.dump(self.stats, f, indent=2)
    
    def process_single_pdf(self, pdf_path: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single PDF file"""
        try:
            filename = metadata.get('filename', '')
            document_id = filename.replace('.pdf', '')
            
            # Check if file is excluded
            is_excluded, reason = self._is_excluded(filename)
            if is_excluded:
                logger.info(f"Skipping excluded file: {filename} - {reason}")
                return {
                    'status': 'skipped',
                    'document_id': document_id,
                    'reason': reason
                }
            
            # Extract content
            pages_content = self.extract_pdf_content(pdf_path)
            
            # Create metadata
            document_metadata = {
                'document_id': document_id,
                'filename': metadata.get('filename'),
                'path': pdf_path,
                'total_pages': len(pages_content),
                'category': metadata.get('category', 'misc'),
                'source_url': metadata.get('url') or metadata.get('original_url', '')
            }
            
            # Create chunks
            chunks = self.create_chunks(pages_content, document_id)
            
            # Generate embeddings
            chunks = self.generate_embeddings(chunks)
            
            # Deduplicate
            chunks = self.deduplicate_content(chunks)
            
            # Build graph
            self.build_graph(chunks, document_metadata)
            
            self.stats['documents_processed'] += 1
            
            return {
                'status': 'success',
                'document_id': document_id,
                'chunks_created': len(chunks),
                'entities_extracted': sum(len(c.entities) for c in chunks)
            }
            
        except Exception as e:
            logger.error(f"Error processing {pdf_path}: {e}")
            
            # Log error for recovery
            from neo4j import GraphDatabase
            from .ingestion_validator import IngestionValidator
            
            driver = GraphDatabase.driver(self.neo4j_uri, 
                                        auth=(self.neo4j_user, self.neo4j_password))
            validator = IngestionValidator(driver) if use_validator else None
            
            validator.log_ingestion_error(
                document_id=metadata.get('filename', ''),
                error=e,
                metadata=metadata,
                recovery_action='reingest'
            )
            
            driver.close()
            
            return {
                'status': 'error',
                'document_id': metadata.get('filename'),
                'error': str(e)
            }
    
    def _download_from_s3(self, file_info: Dict[str, Any], bucket: str) -> str:
        """Download file from S3 if needed"""
        # Implementation would download from S3
        # For now, return local path
        return file_info['local_path']

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Knowledge Ingestion Agent')
    parser.add_argument('--inventory', required=True, help='Inventory JSON file')
    parser.add_argument('--neo4j-uri', default='bolt://localhost:7687', help='Neo4j URI')
    parser.add_argument('--neo4j-user', default='neo4j', help='Neo4j username')
    parser.add_argument('--neo4j-password', default='password', help='Neo4j password')
    parser.add_argument('--workers', type=int, default=4, help='Number of parallel workers')
    parser.add_argument('--s3-bucket', help='S3 bucket for PDF retrieval')
    parser.add_argument('--optimize', action='store_true', help='Optimize graph after ingestion')
    
    args = parser.parse_args()
    
    # Create agent
    agent = KnowledgeIngestionAgent(
        neo4j_uri=args.neo4j_uri,
        neo4j_user=args.neo4j_user,
        neo4j_password=args.neo4j_password,
        num_workers=args.workers
    )
    
    # Process inventory
    agent.process_inventory(args.inventory, args.s3_bucket)
    
    # Optimize if requested
    if args.optimize:
        agent.optimize_graph()

if __name__ == "__main__":
    main()