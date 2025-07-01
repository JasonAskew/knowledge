# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a production-ready GraphRAG (Graph Retrieval Augmented Generation) system built on Neo4j with multiple search strategies. The system ingests PDF documents, creates a knowledge graph with entities and relationships, and provides various search capabilities including vector search, graph traversal, and natural language to Cypher query conversion.

**Current Performance**: 73.8% accuracy with vector search + reranking (target: 90%)
**Test Data Issue**: 86.2% of test cases were invalid due to document name mismatches (.pdf extensions) - now fixed with normalization

**Key Components**:
1. **Knowledge Discovery Agent** (`/knowledge_discovery_agent/`) - Discovers and downloads publicly available PDFs from financial institutions
2. **Knowledge Ingestion Agent** (`/knowledge_ingestion_agent/`) - Processes PDFs with enhanced chunking and builds a searchable knowledge graph
3. **Knowledge Test Agent** (`/knowledge_test_agent/`) - Validates system accuracy with comprehensive reporting
4. **API Layer** (`/docker/`) - FastAPI server with multiple search strategies and reranking
5. **MCP Server** (`/mcp_server/`) - Claude Desktop integration with streaming support and Neo4j proxy

## Common Development Commands

### Service Management (via Makefile)
```bash
make build      # Build all Docker images
make up         # Start all services (Neo4j, API, ingestion, etc.)
make down       # Stop all services
make logs       # View logs from all services
make health     # Check system health
make reset      # Complete system reset (WARNING: deletes all data)
```

### Development Workflow
```bash
make dev        # Start in development mode with hot reload
make rebuild    # Rebuild images and restart services
make shell      # Access service shells (e.g., make shell service=api)
```

### Data Ingestion & Backup
```bash
make ingest         # Run document ingestion (processes PDFs in data/mvp_documents/)
make discover       # Run discovery agent to find and download new PDFs
make stats          # Show graph statistics (documents, chunks, entities)
make export         # Export Neo4j database to JSON
make import         # Import Neo4j database from latest backup
make bootstrap      # Bootstrap database from backup (force mode)
make up-bootstrap   # Start system and bootstrap from backup
make list-backups   # List available database backups
```

### Testing
```bash
make test                              # Run full test suite with default strategy
python enhanced_test_runner.py --search-type vector --use-reranking  # Run specific test
python enhanced_test_runner.py --validation-only  # Validate test data only
python enhanced_test_runner.py --no-validation   # Skip validation
make test-results                      # View latest test results

# Test all strategies
for strategy in vector graph hybrid text2cypher; do
  python enhanced_test_runner.py --search-type $strategy
done
```

**Note**: Test validation now normalizes document names by stripping file extensions to handle mismatches between test data and ingested documents.

### Linting and Type Checking
```bash
# Python linting (run after finding correct command)
cd docker && python -m pylint *.py
cd knowledge_ingestion_agent && python -m pylint *.py

# Type checking
cd docker && python -m mypy *.py --ignore-missing-imports
```

### API Testing
```bash
# Quick search test
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "minimum balance foreign currency", "search_type": "vector", "limit": 5}'

# Text2Cypher test
curl -X POST http://localhost:8000/text2cypher \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the minimum balance for opening an account?", "limit": 5}'

# Get statistics
curl http://localhost:8000/stats
```

### Neo4j Database
```bash
# Default connection
bolt://localhost:7687
username: neo4j
password: knowledge123  # Default password (update in production)

# Check connection
python -c "from neo4j import GraphDatabase; driver = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', 'knowledge123')); driver.verify_connectivity()"
```

## Architecture Overview

### Core Components

1. **Neo4j Graph Database** (ports 7474, 7687)
   - Stores documents, chunks, entities, and relationships
   - Enhanced chunk metadata: semantic_density, chunk_type, has_definitions, has_examples

2. **Search Strategies** (in `knowledge_ingestion_agent/search_engine.py`)
   - `vector`: Semantic similarity using embeddings (BAAI/bge-small-en-v1.5, 384 dims)
   - `graph`: Entity-based graph traversal
   - `hybrid`: Weighted combination (50% vector, 30% graph, 20% full-text)
   - `text2cypher`: Natural language to Cypher conversion (pattern-based)
   - `graphrag`: Advanced graph-based retrieval with community detection
   - `neo4j_cypher`: Direct Neo4j queries with natural language support (MCP default)

3. **API Layer** (`docker/enhanced_api_reranker.py`)
   - FastAPI server on port 8000
   - Cross-encoder reranking with ms-marco-MiniLM-L-6-v2
   - Enhanced scoring formula:
     ```python
     final_score = (
         rerank_score * 0.4 +      # Cross-encoder weight
         original_score * 0.25 +   # Original score weight  
         keyword_boost * 0.15 +    # Keyword weight
         metadata_boost * 0.2      # Enhanced metadata weight
     )
     ```

4. **Enhanced Chunking** (`knowledge_ingestion_agent/knowledge_ingestion_agent.py`)
   - Chunk size: 512 tokens with 100 token overlap (increased from 400)
   - Semantic density calculation for information richness
   - Chunk type classification: content, definition, example, table
   - Definition and example detection using patterns

5. **Testing Framework** (`knowledge_test_agent/enhanced_test_runner.py`)
   - Dual metrics: Document/citation accuracy (primary) and semantic similarity
   - Test data validation before execution with document name normalization
   - Comprehensive CSV and Markdown reporting
   - Semantic similarity threshold: 0.7
   - Handles document name mismatches by stripping file extensions

### API Endpoints

```
POST /search
  - query: string
  - search_type: "vector" | "graph" | "hybrid" | "text2cypher" | "graphrag"
  - limit: int (default: 5)
  - rerank: bool (default: true, except for text2cypher)

POST /text2cypher
  - query: string
  - limit: int (default: 5)

GET /stats
  Returns: documents, chunks, entities, relationships counts

GET /health
  Health check endpoint
```

### MCP Server for Claude Desktop

Configuration in `~/Library/Application Support/Claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "enhanced-knowledge-graph": {
      "command": "/opt/anaconda3/bin/python3",
      "args": ["/path/to/knowledge/mcp_server/enhanced_server_final.py"],
      "cwd": "/path/to/knowledge",
      "env": {
        "API_BASE_URL": "http://localhost:8000",
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_USERNAME": "neo4j",
        "NEO4J_PASSWORD": "knowledge123",
        "NEO4J_DATABASE": "neo4j"
      },
      "features": {
        "streaming": true
      }
    }
  }
}
```

Available MCP tools:
- `search_knowledge`: Search with neo4j_cypher (default and only enabled type)
- `execute_cypher`: Direct Cypher query execution
- `get_knowledge_stats`: Knowledge base statistics

**Note**: The MCP server defaults to `neo4j_cypher` search type and currently restricts other search types for optimal performance. It includes direct Neo4j connection with fallback to text2cypher API.

### Neo4j Graph Schema

```cypher
// Enhanced nodes
(:Document {id, filename, path, total_pages, category})
(:Chunk {
  id, text, page_num, chunk_index, embedding,
  semantic_density, chunk_type, has_definitions, has_examples
})
(:Entity {text, type, first_seen, occurrences})

// Relationships
(:Document)-[:HAS_CHUNK]->(:Chunk)
(:Chunk)-[:CONTAINS_ENTITY {confidence}]->(:Entity)
(:Chunk)-[:NEXT_CHUNK]->(:Chunk)
(:Entity)-[:RELATED_TO {strength}]->(:Entity)
```

### Performance Metrics

- **Current Accuracy**: 73.8% (vector + reranking), 66.2% (text2cypher)
- **Query Response Time**: < 2 seconds average
- **Ingestion Speed**: ~5-10 seconds per PDF
- **Supported Documents**: 26 MVP PDFs currently ingested
- **Test Validation**: Document name normalization fixed 86.2% invalid test cases

## Key Design Patterns

### Enhanced Chunking Strategy
Each chunk stores metadata for improved relevance:
- `semantic_density`: Information richness score (0-1)
- `chunk_type`: Classification (content, definition, example, table)
- `has_definitions`: Boolean flag for presence of definitions
- `has_examples`: Boolean flag for presence of examples

### Reranking Algorithm
Multi-factor scoring with:
- Cross-encoder semantic relevance (40%)
- Original search score (25%)
- Keyword overlap boost (15%)
- Metadata quality boost (20%)

### Text2Cypher Patterns
Pattern-based query understanding for:
- Minimum/maximum values
- Product features and eligibility
- Interest rates and fees
- Process and requirements

## Common Tasks

### Adding a New Search Strategy
1. Implement strategy in `knowledge_ingestion_agent/search_engine.py`
2. Add to SEARCH_STRATEGIES in `docker/enhanced_api_reranker.py`
3. Update test cases if needed
4. Run validation: `python enhanced_test_runner.py --validation-only`

### Debugging Search Results
```bash
# Check graph contents
make stats

# Test specific query
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "your query", "search_type": "vector", "limit": 5}'

# View detailed logs
make logs service=api
```

### Improving Accuracy
1. Review failed test cases in test reports
2. Analyze chunk quality in Neo4j browser
3. Adjust reranking weights in API
4. Consider adding more pattern rules for text2cypher
5. Fine-tune chunk size and overlap parameters

## Troubleshooting

### Services Won't Start
```bash
make down
docker system prune -a  # WARNING: removes all Docker data
make build
make up
```

### Low Accuracy
1. Verify documents ingested: `make stats`
2. Validate test data: `python enhanced_test_runner.py --validation-only`
3. Check chunk quality: http://localhost:7474
4. Review reranking scores in API logs

### MCP Server Issues
1. Check Python path is correct: `/opt/anaconda3/bin/python3`
2. Ensure API is running: `curl http://localhost:8000/health`
3. View MCP logs in Claude Desktop developer console
4. Test Neo4j connection: `python mcp_server/test_neo4j_mcp_direct.py`
5. Check Neo4j credentials match configuration
6. Verify streaming is enabled in claude_desktop_config.json

## Important Constraints

1. **Public Documents Only**: System only processes publicly available PDFs
2. **Defensive Security**: Code is for defensive security analysis only
3. **Neo4j Required**: Ensure Neo4j is running before ingestion
4. **Docker Required**: All services run in containers
5. **Memory Requirements**: 8GB minimum, 16GB recommended

## Recent Updates

1. **Test Validation Fix** (2025-07-01)
   - Fixed document name validation to handle .pdf extension mismatches
   - Enhanced test runner now normalizes document names by stripping extensions
   - Test accuracy improved from 13.8% failed validations to near 0%

2. **MCP Server Enhancement** (2025-07-01)
   - Added neo4j_cypher search type that uses natural language to Cypher conversion
   - Restricted MCP server to only allow neo4j_cypher search type
   - Provides better retrieval accuracy than custom search methods

3. **Database Backup/Restore** (2025-07-01)
   - Added export/import functionality for Neo4j database
   - Supports JSON serialization of entire graph including vector embeddings
   - Enables quick bootstrapping of new instances from backups
   - Added Makefile commands: `make export`, `make import`, `make bootstrap`, `make up-bootstrap`
   - Successfully validated full system rebuild from backup (2,199 nodes, 21,479 relationships)

## Future Improvements

1. **Option 3 Implementation**: Preserve file extensions during document ingestion (currently using normalization workaround)
2. **True MCP Proxying**: Implement proper MCP-to-MCP communication for neo4j-cypher tool
3. **Query Caching**: Add caching layer for frequently asked questions
4. **Enhanced Entity Linking**: Improve entity disambiguation and relationship discovery
5. **Multi-language Support**: Extend system to handle documents in multiple languages