# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a production-ready GraphRAG (Graph Retrieval Augmented Generation) system built on Neo4j. The system ingests PDF documents (currently 435 documents, 9,638 pages), creates a knowledge graph with entities and relationships, provides advanced search capabilities with citation support, and features community detection for enhanced graph understanding.

**Key Architecture Components**:
1. **Neo4j Graph Database**: Stores 75,773 nodes (435 documents, 12,709 chunks, 10,150 entities) with 970,278 relationships
2. **Docker-based Services**: Neo4j, Knowledge API, Ingestion, Discovery agents
3. **MCP Server**: Lightweight server with lazy loading, exposes both Cypher tools and high-accuracy search
4. **Search & Reranking**: Vector embeddings (384-dim), cross-encoder reranking, configurable weights
5. **Community Detection**: Louvain algorithm organizing entities into 42 communities with bridge node identification

**Current State**:
- 88.8% accuracy with vector search + reranking (71/80 test questions)
- 435 documents successfully ingested (all Westpac PDFs)
- Complete citation support (document name, page number, chunk ID)
- Backup/restore functionality validated with 66MB compressed exports
- Community detection implemented with two-phase search capability
- MCP server fixed with lazy loading pattern for Claude Desktop integration

## Common Development Commands

### Building and Running
```bash
make build              # Build all Docker images
make up                 # Start all services
make down               # Stop all services
make up-bootstrap       # Start with database restore from backup
make rebuild            # Rebuild and restart all services
make dev                # Start in development mode with live reload
```

### Testing
```bash
# Run test suite with specific search type
cd knowledge_test_agent
python enhanced_test_runner.py --search-type vector --use-reranking
python enhanced_test_runner.py --search-type hybrid --use-reranking
python enhanced_test_runner.py --search-type text2cypher

# Test community search (Cypher-only achieved 18.75% accuracy)
python test_community_cypher_only.py

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

### Community Detection
```bash
# Build entity relationships (prerequisite)
python build_entity_relationships.py

# Run community detection
cd knowledge_ingestion_agent
python community_detection.py --resolution 1.0

# Analyze communities
python analyze_communities.py

# Test community-aware search
python demo_community_search.py
```

### Monitoring and Debugging
```bash
make logs               # View all service logs
make neo4j-logs         # View Neo4j logs
make api-logs           # View API logs
make monitor            # View resource usage
docker logs knowledge-neo4j --tail 50 -f  # Follow Neo4j logs
```

### Ingestion
```bash
# Ingest all PDFs from westpac_pdfs folder
docker-compose run --rm knowledge-ingestion python knowledge_ingestion_agent.py --folder /data/pdfs/westpac_pdfs

# Monitor ingestion progress
python monitor_ingestion.py

# Validate ingestion completeness
python knowledge_ingestion_agent/ingestion_validator.py
```

## High-Level Architecture

### Graph Schema
```cypher
// Core nodes (435 documents with chunks, 10,150 entities in 42 communities)
(:Document {id, filename, path, total_pages, chunk_count, category})
(:Chunk {id, text, page_num, chunk_index, embedding[384], semantic_density, chunk_type})
(:Entity {text, type, first_seen, occurrences, community_id, community_degree_centrality, community_betweenness_centrality})

// Relationships with properties (970,278 total)
(:Document)-[:HAS_CHUNK]->(:Chunk)
(:Chunk)-[:CONTAINS_ENTITY {confidence: 0.85-0.95}]->(:Entity)
(:Entity)-[:RELATED_TO {strength: cooccurrence_count}]->(:Entity) // 376,227 relationships
```

### Service Architecture
```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ Claude Desktop  │────▶│  MCP Server     │────▶│   Neo4j DB      │
│                 │     │ (lightweight)   │     │ (75,773 nodes)  │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                              │                           │
                              │                           │
                    ┌─────────▼──────────┐    ┌─────────▼─────────┐
                    │ ML Models          │    │ Community Graph   │
                    │ (Lazy Loaded)      │    │ (42 communities)  │
                    │ - Embeddings       │    │ - Bridge nodes    │
                    │ - Reranker         │    │ - Centrality      │
                    └────────────────────┘    └───────────────────┘
```

### Key Design Decisions

1. **Community Detection Architecture**:
   - **Louvain Algorithm**: Resolution 1.0, detected 42 communities
   - **Two-Phase Search**: Phase 1 (intra-community), Phase 2 (bridge nodes)
   - **Bridge Nodes**: 147 entities connecting 2-5 communities
   - **Metrics**: Degree centrality, betweenness centrality per community

2. **Weights Applied in Two Places**:
   - **Graph Storage**: Relationship properties (confidence, strength, community metrics)
   - **Query Time**: Reranking weights in production_config.json

3. **Chunking Strategy**:
   - 512 tokens with 128 overlap
   - Metadata: semantic_density, chunk_type, has_definitions/examples
   - No weights in chunking - fixed parameters only

4. **Search & Reranking Pipeline**:
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

5. **MCP Server Evolution**:
   - **Original**: `neo4j_exact_proxy.py` - Pure Cypher proxy (18.75% accuracy)
   - **Enhanced**: `neo4j_enhanced_search.py` - Heavy ML models (startup failure)
   - **Current**: `neo4j_mcp_lightweight.py` - Lazy loading (85%+ accuracy)
   - Exposes: `read-neo4j-cypher`, `write-neo4j-cypher`, `get-neo4j-schema`, `search_documents`

6. **Citation Support**:
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

### Community Detection Pattern
```python
# Build entity relationships first
MATCH (c:Chunk)-[:CONTAINS_ENTITY]->(e1:Entity)
MATCH (c)-[:CONTAINS_ENTITY]->(e2:Entity)
WHERE id(e1) < id(e2)
WITH e1, e2, COUNT(DISTINCT c) as cooccurrence_count
WHERE cooccurrence_count > 1
MERGE (e1)-[r:RELATED_TO]-(e2)
SET r.strength = cooccurrence_count

# Then run Louvain algorithm
community_detector = CommunityDetector(driver)
communities = community_detector.run_louvain_detection(resolution=1.0)
community_detector.enrich_graph_with_communities(communities)
```

### MCP Server Configuration
```json
{
  "mcpServers": {
    "knowledge-graph-search": {
      "command": "/opt/anaconda3/bin/python3",
      "args": [
        "/Users/jaskew/workspace/Skynet/claude/knowledge/mcp_server/neo4j_mcp_lightweight.py"
      ],
      "cwd": "/Users/jaskew/workspace/Skynet/claude/knowledge",
      "env": {
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_USERNAME": "neo4j",
        "NEO4J_PASSWORD": "knowledge123",
        "NEO4J_DATABASE": "neo4j",
        "PYTHONPATH": "/Users/jaskew/workspace/Skynet/claude/knowledge"
      }
    }
  }
}
```

### Critical Files for Multi-File Understanding

1. **Search Pipeline** (requires understanding multiple components):
   - `docker/enhanced_api_reranker.py` - API endpoint and reranking orchestration
   - `knowledge_ingestion_agent/search_engine.py` - Search strategy implementations
   - `data/production_config.json` - Reranking weights configuration

2. **Community Detection**:
   - `knowledge_ingestion_agent/community_detection.py` - Louvain implementation
   - `build_entity_relationships.py` - Creates RELATED_TO relationships
   - `test_community_cypher_only.py` - Tests Cypher-only approach (18.75% accuracy)

3. **MCP Integration**:
   - `mcp_server/neo4j_mcp_lightweight.py` - Current active MCP server with lazy loading
   - `mcp_server/neo4j_enhanced_search.py` - Full-featured but heavy version
   - `~/Library/Application Support/Claude/claude_desktop_config.json` - Client config

4. **Test Framework**:
   - `knowledge_test_agent/enhanced_test_runner.py` - Test orchestration
   - `knowledge_test_agent/test.csv` - Test cases with expected documents/pages
   - Validates both document accuracy and semantic similarity (threshold: 0.7)

## Recent Improvements

### Community Detection Implementation
- Added Louvain algorithm detecting 42 communities among 10,150 entities
- Created 376,227 RELATED_TO relationships based on entity co-occurrence
- Identified 147 bridge nodes connecting multiple communities
- Implemented two-phase search: intra-community → bridge nodes
- Community metrics stored: degree centrality, betweenness centrality

### MCP Server Enhancement
- Fixed startup issues with lazy loading pattern
- Models load on-demand (first search ~5s, subsequent <2s)
- Maintains 85%+ accuracy while being responsive
- Combines Cypher access with ML-powered search in one interface

### Test Results
- Vector search + reranking: 88.8% (71/80 correct)
- Cypher-only community search: 18.75% (15/80 correct)
- Hybrid search + reranking: 85%+ accuracy
- Average query time: <2 seconds

## Performance Metrics

- **Startup time**: <1 second (MCP server)
- **First search**: ~5 seconds (loading models)
- **Subsequent searches**: <2 seconds
- **Graph size**: 75,773 nodes, 970,278 relationships
- **Communities**: 42 detected, 147 bridge nodes
- **Backup size**: 66MB compressed

## Troubleshooting

### MCP Server Issues
If the MCP server fails to start:
1. Check Claude Desktop logs: `~/Library/Logs/Claude/mcp*.log`
2. Ensure Neo4j is running: `docker ps | grep neo4j`
3. Verify Python path in config matches your system
4. Use lightweight version (`neo4j_mcp_lightweight.py`) not enhanced

### Missing Relationships After Import
Always run after database import:
```bash
make fix-relationships
```

### Community Detection Prerequisites
Before running community detection:
1. Ensure all documents are ingested
2. Run `build_entity_relationships.py` first
3. Check entity count: should be >10,000 for meaningful communities

# important-instruction-reminders
Do what has been asked; nothing more, nothing less.
NEVER create files unless they're absolutely necessary for achieving your goal.
ALWAYS prefer editing an existing file to creating a new one.
NEVER proactively create documentation files (*.md) or README files. Only create documentation files if explicitly requested by the User.