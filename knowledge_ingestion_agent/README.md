# Knowledge Ingestion Agent

Autonomous agent for ingesting, processing, and indexing PDF documents into a Neo4j knowledge graph with support for multiple search modalities.

## Features

### Document Processing
- **PyMuPDF Integration**: Full text extraction with page structure preservation
- **Smart Chunking**: Semantic boundary-aware text chunking (400 tokens with 100 overlap)
- **Table Detection**: Automatic detection and handling of tabular data
- **Batch Processing**: Parallel processing with configurable workers

### Entity Recognition
- **spaCy NER**: Standard named entity recognition
- **Domain-Specific Patterns**: 150+ financial product patterns
- **Financial Terms**: Strike rates, premiums, notional amounts, etc.
- **Requirements Extraction**: Minimum amounts, eligibility criteria
- **Confidence Scoring**: Entity confidence ratings

### Embeddings & Deduplication
- **BGE-Small Embeddings**: 384-dimensional vectors for semantic search
- **Content Deduplication**: Hash-based and semantic similarity deduplication
- **Entity Deduplication**: TF-IDF with cosine similarity (0.85 threshold)
- **Batch Generation**: Efficient batch embedding generation

### Knowledge Graph
- **Hierarchical Structure**: Document → Chunks → Entities
- **Rich Relationships**: HAS_CHUNK, CONTAINS_ENTITY, NEXT_CHUNK, RELATED_TO
- **Optimized Indexes**: Vector, full-text, and graph indexes
- **Graph Statistics**: Track occurrences and relationships

### Search Capabilities
1. **Vector Search**: Pure embedding-based similarity search
2. **Graph Search**: Entity-based graph traversal
3. **Full-Text Search**: Keyword matching with Neo4j indexes
4. **Hybrid Search**: Weighted combination of all methods
5. **GraphRAG Search**: Context-expanded retrieval

## Installation

```bash
# Install Python dependencies
pip install -r requirements.txt

# Download spaCy model
python -m spacy download en_core_web_sm

# Install Neo4j (if not already installed)
# See: https://neo4j.com/download/
```

## Usage

### Basic Ingestion

```bash
# Process MVP inventory
python knowledge_ingestion_agent.py \
  --inventory ../knowledge_discovery_agent/mvp_inventory.json \
  --neo4j-password your-password

# Process all verified PDFs
python knowledge_ingestion_agent.py \
  --inventory ../knowledge_discovery_agent/downloaded_pdfs_inventory_verified.json \
  --neo4j-password your-password \
  --workers 8

# With graph optimization
python knowledge_ingestion_agent.py \
  --inventory ../knowledge_discovery_agent/mvp_inventory.json \
  --neo4j-password your-password \
  --optimize
```

### Search Examples

```bash
# Hybrid search (recommended)
python search_engine.py --query "What is an FX Forward?" --type hybrid

# Vector similarity search
python search_engine.py --query "foreign exchange options" --type vector

# Graph-based search
python search_engine.py --query "Interest Rate Swap" --type graph

# Full-text search
python search_engine.py --query "minimum deposit requirement" --type full_text

# GraphRAG with context expansion
python search_engine.py --query "Can I reduce my option premium?" --type graphrag

# With explanation
python search_engine.py --query "What are the risks?" --type hybrid --explain
```

## Configuration

### Neo4j Connection
```python
# Default connection settings
neo4j_uri = "bolt://localhost:7687"
neo4j_user = "neo4j"
neo4j_password = "password"
```

### Processing Parameters
```python
# Chunking configuration
chunk_size = 400  # tokens
chunk_overlap = 100  # tokens

# Batch processing
batch_size = 32  # for embeddings
num_workers = 4  # parallel processes

# Deduplication
similarity_threshold = 0.85  # for semantic dedup
```

### Search Weights (Hybrid)
```python
weights = {
    'vector': 0.4,      # Semantic similarity
    'graph': 0.3,       # Entity relationships
    'full_text': 0.2,   # Keyword matching
    'query_boost': 0.1  # Query-type boosting
}
```

## Architecture

### Processing Pipeline
1. **PDF Extraction**: PyMuPDF extracts text with structure
2. **Chunking**: Smart chunking preserves semantic boundaries
3. **Entity Extraction**: spaCy + custom patterns extract entities
4. **Embedding Generation**: BGE-small creates vector representations
5. **Deduplication**: Remove duplicate content and entities
6. **Graph Construction**: Build Neo4j graph with relationships
7. **Index Creation**: Create vector and text indexes

### Graph Schema

```cypher
// Core nodes
(:Document {id, filename, path, total_pages, category})
(:Chunk {id, text, page_num, chunk_index, embedding})
(:Entity {text, type, first_seen, occurrences})

// Relationships
(:Document)-[:HAS_CHUNK]->(:Chunk)
(:Chunk)-[:CONTAINS_ENTITY {confidence}]->(:Entity)
(:Chunk)-[:NEXT_CHUNK]->(:Chunk)
(:Entity)-[:RELATED_TO {strength}]->(:Entity)
```

### Search Architecture

```
Query → Query Analysis → Multi-Path Retrieval → Result Fusion → Ranking
         ↓                ↓
         Entity          - Vector Search (embeddings)
         Extraction      - Graph Search (entities)
         ↓               - Full-Text Search (keywords)
         Query Type      - Context Expansion (GraphRAG)
         Detection
```

## Performance

### Ingestion Performance
- **Single PDF**: ~5-10 seconds
- **Batch (10 PDFs)**: ~1-2 minutes with 4 workers
- **Full Collection (430 PDFs)**: ~30-45 minutes with 8 workers

### Search Performance
- **Vector Search**: <100ms for top-10
- **Graph Search**: <200ms depending on complexity
- **Hybrid Search**: <500ms combining all methods
- **GraphRAG**: <1s with 2-hop expansion

### Resource Requirements
- **Memory**: 8GB minimum, 16GB recommended
- **Storage**: ~1GB per 100 PDFs (including embeddings)
- **GPU**: Optional but recommended for embedding generation

## Monitoring

### Ingestion Statistics
```json
{
  "documents_processed": 26,
  "chunks_created": 1250,
  "entities_extracted": 3500,
  "duplicates_removed": 125,
  "processing_time": 485.3
}
```

### Search Metrics
- Query latency
- Result relevance scores
- Cache hit rates
- Index performance

## Troubleshooting

### Common Issues

1. **Neo4j Connection Failed**
   ```
   Error: Unable to connect to Neo4j
   Solution: Ensure Neo4j is running and credentials are correct
   ```

2. **Out of Memory**
   ```
   Solution: Reduce batch_size or num_workers
   ```

3. **Slow Embedding Generation**
   ```
   Solution: Use GPU or reduce batch_size
   ```

### Performance Tuning

1. **Increase Workers**: For CPU-bound processing
2. **Increase Batch Size**: For GPU embedding generation
3. **Optimize Neo4j**: Increase heap memory, tune caches
4. **Use SSD**: For better I/O performance

## Future Enhancements

1. **Multi-language Support**: Beyond English
2. **Incremental Updates**: Process only new/changed documents
3. **Advanced Deduplication**: Cross-document entity resolution
4. **Query Expansion**: Automatic synonym expansion
5. **Learning to Rank**: ML-based result ranking
6. **Streaming Ingestion**: Real-time document processing