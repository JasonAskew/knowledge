# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a production-ready GraphRAG (Graph Retrieval Augmented Generation) system built on Neo4j. The system ingests PDF documents (currently 428 documents, 9,638 pages), creates a knowledge graph with entities and relationships, and provides search capabilities with citation support.

**Key Architecture Components**:
1. **Neo4j Graph Database**: Stores 75,773 nodes (428 documents, 12,709 chunks, 62,636 entities) with 592,823 relationships
2. **Docker-based Services**: Neo4j, Knowledge API, Ingestion, Discovery agents
3. **MCP Server**: Pure proxy to Neo4j exposing `read-neo4j-cypher`, `write-neo4j-cypher`, `get-neo4j-schema`
4. **Search & Reranking**: Vector embeddings (384-dim), cross-encoder reranking, configurable weights

**Current State**:
- 73.8% accuracy with vector search + reranking
- 355 documents successfully ingested (excludes 5 scanned PDFs without text)
- Complete citation support (document name, page number, chunk ID)
- Backup/restore functionality validated with 66MB compressed exports
- Exclusion system for problematic documents (see data/exclusion_config.json)

## Common Development Commands

### Building and Running
```bash
make build              # Build all Docker images
make up                 # Start all services
make down               # Stop all services
make up-bootstrap       # Start with database restore from backup
make rebuild            # Rebuild and restart all services
```

### Testing
```bash
# Run test suite with specific search type
cd knowledge_test_agent
python enhanced_test_runner.py --search-type vector --use-reranking
python enhanced_test_runner.py --search-type hybrid --use-reranking
python enhanced_test_runner.py --search-type text2cypher

# Validate test data integrity
python enhanced_test_runner.py --validation-only
```

### Database Operations
```bash
make export             # Export Neo4j to JSON (data/backups/)
make import             # Import from latest backup
make fix-relationships  # Fix orphaned chunk relationships after import
make stats              # Show graph statistics

# Direct Neo4j queries
docker exec knowledge-neo4j cypher-shell -u neo4j -p knowledge123 "MATCH (n) RETURN labels(n)[0] as label, count(n) as count"
```

### Monitoring and Debugging
```bash
make logs               # View all service logs
make neo4j-logs         # View Neo4j logs
make api-logs           # View API logs
docker logs knowledge-neo4j --tail 50 -f  # Follow Neo4j logs
```

### Ingestion
```bash
# Ingest all PDFs from westpac_pdfs folder
docker-compose run --rm knowledge-ingestion python knowledge_ingestion_agent_v2.py --folder /data/pdfs/westpac_pdfs

# Monitor ingestion progress
python monitor_ingestion.py
```

## High-Level Architecture

### Graph Schema
```cypher
// Core nodes (355 total documents, all with chunks)
(:Document {id, filename, path, total_pages, chunk_count, category})
(:Chunk {id, text, page_num, chunk_index, embedding[384], semantic_density, chunk_type})
(:Entity {text, type, first_seen, occurrences})

// Relationships with properties
(:Document)-[:HAS_CHUNK]->(:Chunk)
(:Chunk)-[:CONTAINS_ENTITY {confidence: 0.85-0.95}]->(:Entity)
(:Entity)-[:RELATED_TO {strength: cooccurrence_count}]->(:Entity)
```

### Service Architecture
```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ Claude Desktop  │────▶│  MCP Server     │────▶│   Neo4j DB      │
│                 │     │ (neo4j proxy)   │     │ (75,773 nodes)  │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                          │
                        ┌─────────────────────────────────┴─────────┐
                        │                                           │
                ┌───────▼────────┐              ┌──────────────────▼─┐
                │ Knowledge API  │              │ Ingestion Pipeline │
                │ (FastAPI:8000) │              │ (Enhanced Chunking)│
                └────────────────┘              └────────────────────┘
```

### Key Design Decisions

1. **Weights Applied in Two Places**:
   - **Graph Storage**: Relationship properties (confidence, strength)
   - **Query Time**: Reranking weights in production_config.json

2. **Chunking Strategy**:
   - 512 tokens with 128 overlap
   - Metadata: semantic_density, chunk_type, has_definitions/examples
   - No weights in chunking - fixed parameters only

3. **Search & Reranking Pipeline**:
   ```python
   # Initial retrieval (top_k * 2 candidates)
   # ↓
   # Cross-encoder scoring
   # ↓
   # Multi-factor reranking:
   final_score = (
       cross_encoder * 0.5 +
       original_score * 0.3 +
       keyword_match * 0.1 +
       query_type_match * 0.1
   )
   ```

4. **MCP Server Configuration**:
   - Location: `mcp_server/neo4j_exact_proxy.py`
   - Exposes only: `read-neo4j-cypher`, `write-neo4j-cypher`, `get-neo4j-schema`
   - Pure proxy to Neo4j, no custom search logic

5. **Citation Support**:
   - Every chunk has: document reference, page_num, chunk_id
   - Format: "DocumentName.pdf, p. 12"
   - Utilities in: `utils/citation_formatter.py`

## Key Patterns and Conventions

### Test Validation Pattern
The test runner normalizes document names by stripping `.pdf` extensions:
```python
def _normalize_document_name(self, doc_name: str) -> str:
    if '.' in doc_name:
        doc_name = doc_name.rsplit('.', 1)[0]
    return doc_name.lower().strip()
```

### Bootstrap Recovery Pattern
After importing from backup, relationships may be missing:
```bash
make import
make fix-relationships  # Critical step to restore HAS_CHUNK relationships
```

### Entity Confidence Levels
- SpaCy NER: 0.9
- Pattern matching: 0.85
- Amount/Percentage extraction: 0.95

### Critical Files for Multi-File Understanding

1. **Search Pipeline** (requires understanding multiple components):
   - `docker/enhanced_api_reranker.py` - API endpoint and reranking orchestration
   - `knowledge_ingestion_agent/search_engine.py` - Search strategy implementations
   - `data/production_config.json` - Reranking weights configuration

2. **Ingestion Pipeline**:
   - `knowledge_ingestion_agent/knowledge_ingestion_agent.py` - Main ingestion logic
   - `knowledge_ingestion_agent/enhanced_chunking.py` - Chunking with metadata
   - Graph optimization creates RELATED_TO relationships based on co-occurrence

3. **MCP Integration**:
   - `mcp_server/neo4j_exact_proxy.py` - Current active MCP server
   - `~/Library/Application Support/Claude/claude_desktop_config.json` - Client config
   - Exposes only Neo4j standard tools, no custom search methods

4. **Test Framework**:
   - `knowledge_test_agent/enhanced_test_runner.py` - Test orchestration
   - `knowledge_test_agent/test.csv` - Test cases with expected documents/pages
   - Validates both document accuracy and semantic similarity (threshold: 0.7)