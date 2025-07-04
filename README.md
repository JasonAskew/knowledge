# Knowledge Graph System with GraphRAG

[![Release](https://img.shields.io/github/v/release/JasonAskew/knowledge)](https://github.com/JasonAskew/knowledge/releases)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A production-ready knowledge graph system with GraphRAG (Graph Retrieval Augmented Generation) capabilities, featuring community detection, multiple search methods, intelligent reranking, and MCP (Model Context Protocol) support for Claude Desktop integration.

## 🚀 Features

- **Community Detection** (NEW in v0.0.1):
  - Louvain algorithm detecting 42 communities
  - Two-phase search: intra-community → bridge nodes
  - 147 bridge nodes connecting multiple communities
  - Community-aware ranking with configurable weights

- **Multiple Search Methods**:
  - **Optimized Keyword Search** (Default): 0.2s response, 80%+ accuracy
  - **Vector Search**: Semantic embeddings (384-dim), 4-5s response, 75-80% accuracy
  - **Hybrid + Reranking**: Best accuracy (88.8%), 5-6s response
  - **Graph Search**: Neo4j Cypher queries, 0.1s response, 86% accuracy (expert users)
  - **Text2Cypher**: Natural language to graph queries
  - **Community-aware Search**: Enhanced relevance with 42 communities
  
- **Enhanced Chunking**:
  - Semantic density calculation
  - Definition and example detection
  - Chunk type classification
  - Optimized 512 tokens with 128 overlap

- **Intelligent Reranking**:
  - Cross-encoder reranking with BERT
  - Multi-factor scoring (content, keywords, metadata)
  - Configurable scoring weights
  - Complete citation support with page numbers

- **MCP Integration**:
  - **Optimized Server**: Fast keyword search by default (<0.2s response)
  - **Flexible Options**: Enable vector search + reranking when accuracy is critical
  - **Lightweight Startup**: <1s startup with lazy model loading
  - **Real-time Access**: Direct Neo4j queries via Claude Desktop
  - **Multiple Tools**: Search, entity lookup, schema inspection

- **Backup & Restore**:
  - Full database export to JSON format (66MB compressed)
  - Quick bootstrap from existing backups
  - Automated relationship repair
  - Complete graph preservation

## 📊 Current Status (v0.0.1)

- **Database**: 75,773 nodes, 970,278 relationships
  - 435 documents (9,638 pages)
  - 12,709 chunks with embeddings
  - 10,150 entities in 42 communities
  - 376,227 entity co-occurrence relationships
- **Performance**:
  - **Optimized Keyword Search**: 80%+ accuracy, 0.2s response (default)
  - **Hybrid + Reranking**: 88.8% accuracy (71/80), 5-6s response
  - **Vector Search**: 75-80% accuracy, 4-5s response
  - **Expert Cypher**: 86% accuracy, 0.1-0.5s response
  - **Community Search**: 18.75% baseline (automated only)
- **Storage**: 66MB compressed backup available

## 📈 Search Method Performance Analysis

### Comprehensive Performance Comparison

Based on extensive testing with 80 test questions across various banking topics:

| Search Method | Query Time | Accuracy | Memory Usage | Best Use Case |
|---------------|------------|----------|--------------|---------------|
| **Keyword Search (Optimized)** | 0.1-0.3s | 80%+ | Low | Interactive queries, real-time responses |
| **Hybrid + Reranking** | 5-6s | 88.8% (71/80) | High | Batch processing, maximum accuracy |
| **Vector Search** | 4-5s | 75-80% | Medium | Semantic similarity, concept exploration |
| **Pattern Search (AND)** | 0.05-0.2s | ~70% | Minimal | Specific document lookup, compliance |
| **Expert Cypher** | 0.1-0.5s | 86% | Minimal | Power users, custom business logic |

### Search Method Trade-offs

**Speed vs Accuracy Spectrum:**
```
Fast & Interactive  ←────────────────────→  Slow & Accurate
     │                                              │
Keyword Search                            Hybrid + Reranking
   (0.2s, 80%+)                             (5-6s, 88.8%)
     │                                              │
 Real-time use                              Batch processing
```

### When to Use Each Method

**🚀 Keyword Search (Default)**
- ✅ Interactive queries in Claude Desktop
- ✅ Quick document lookups
- ✅ Banking terminology searches
- ✅ When speed > perfect accuracy
- ❌ Complex semantic queries

**🎯 Hybrid + Reranking**
- ✅ Research and analysis tasks
- ✅ When maximum accuracy is critical
- ✅ Complex semantic relationships
- ✅ Batch processing scenarios
- ❌ Real-time interactive use

**🔍 Vector Search**
- ✅ Semantic similarity matching
- ✅ Concept exploration
- ✅ Finding related content
- ❌ Exact keyword requirements

**⚡ Expert Cypher**
- ✅ Power users with graph knowledge
- ✅ Custom business logic
- ✅ Complex relationship queries
- ✅ Full control over search logic
- ❌ General users without Cypher knowledge

### Performance Insights

The **86% vs 18.75%** accuracy discrepancy between expert Cypher usage and automated testing reveals:

**Expert Approach (86% success):**
- Flexible OR keyword matching
- Domain expertise in banking terminology
- Iterative query refinement
- Multiple search strategies per query
- Understanding of synonyms (fee/charge/cost)

**Automated Approach (18.75% success):**
- Rigid query patterns
- No iteration or refinement
- Limited vocabulary matching
- Single query attempt per question
- No domain knowledge integration

This demonstrates that the MCP server's **optimized keyword search** bridges this gap by providing fast, intelligent keyword matching with domain-aware patterns.

## 🏗️ Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Claude Desktop │────▶│  MCP Server     │────▶│   Neo4j DB      │
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
                              │
                    ┌─────────▼──────────┐
                    │  Knowledge API     │
                    │  (FastAPI:8000)    │
                    └────────────────────┘
```

## 🚦 Quick Start

### Prerequisites

- Python 3.9+
- Docker and Docker Compose
- Neo4j 5.0+
- Claude Desktop (for MCP integration)

### 1. Clone and Setup

```bash
git clone https://github.com/JasonAskew/knowledge.git
cd knowledge
```

### 2. Start Services

```bash
# Quick start with existing database
make up-bootstrap

# Or start fresh
docker-compose up -d
```

This starts:
- Neo4j database with 970,278 relationships
- Knowledge API with search endpoints
- Community detection features

### 3. Community Detection Setup

```bash
# Build entity relationships (if not already done)
python build_entity_relationships.py

# Run community detection
cd knowledge_ingestion_agent
python community_detection.py --resolution 1.0
```

### 4. Configure Claude Desktop

Edit Claude Desktop config at:
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "knowledge-graph-search": {
      "command": "/opt/anaconda3/bin/python3",
      "args": [
        "/path/to/knowledge/mcp_server/neo4j_mcp_optimized.py"
      ],
      "cwd": "/path/to/knowledge",
      "env": {
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_USERNAME": "neo4j",
        "NEO4J_PASSWORD": "knowledge123",
        "NEO4J_DATABASE": "neo4j",
        "PYTHONPATH": "/path/to/knowledge"
      }
    }
  }
}
```

## 📁 Project Structure

```
knowledge/
├── docker/                    # Docker configurations
│   ├── api.py                # Main API server
│   ├── docker-compose.yml    # Service orchestration
│   └── Dockerfile.api        # API container
├── knowledge_ingestion_agent/ # Document ingestion
│   ├── knowledge_ingestion_agent.py
│   ├── enhanced_chunking.py
│   ├── search_engine.py
│   └── community_detection.py # NEW: Community detection
├── knowledge_discovery_agent/ # Discovery tools
│   └── westpac_pdfs/         # 435 indexed PDFs
├── knowledge_test_agent/      # Testing framework
│   ├── enhanced_test_runner.py
│   └── test.csv              # 80 test questions
├── mcp_server/               # MCP integration
│   ├── neo4j_mcp_optimized.py # CURRENT: Fast keyword + optional vector
│   ├── neo4j_mcp_lightweight.py # Previous: Always vector search
│   ├── neo4j_enhanced_search.py # Full ML features (non-MCP)
│   └── neo4j_exact_proxy.py  # Basic Neo4j proxy only
├── scripts/                  # Utility scripts
│   ├── bootstrap_neo4j.py    # Database import
│   ├── fix_chunk_relationships.py
│   └── export_neo4j.py       # Database export
├── utils/                    # Shared utilities
│   ├── citation_formatter.py
│   └── citation_query_examples.py
├── data/                     # Test results & backups
│   └── backups/             # Compressed exports
└── CLAUDE.md                # Development guide
```

## 🔧 Configuration

### Environment Variables

```bash
# Neo4j Configuration
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=knowledge123

# API Configuration  
API_PORT=8000
API_BASE_URL=http://localhost:8000

# Model Configuration
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
RERANKER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2
```

## 📈 Testing

### Run Accuracy Tests

```bash
cd knowledge_test_agent

# Test different search methods
python enhanced_test_runner.py --search-type vector --use-reranking
python enhanced_test_runner.py --search-type hybrid --use-reranking

# Test community search
python test_community_cypher_only.py
```

### Test Results Summary

| Search Method | Accuracy | Query Time | Test Status |
|---------------|----------|------------|-------------|
| **Hybrid + Reranking** | 88.8% (71/80) | 5-6s | ✅ Verified |
| **Optimized Keyword** | 80%+ | 0.2s | ✅ Production |
| **Vector Search** | 75-80% | 4-5s | ✅ Available |
| **Expert Cypher** | 86% | 0.1-0.5s | ✅ Manual testing |
| **Community Search** | 18.75% | 0.1s | ❌ Baseline only |

### Test Suite Details

- **Test Questions**: 80 questions across various banking topics
- **Results Location**: `data/test_results/`
- **Test Categories**: definitions, procedures, costs/fees, capabilities, general queries
- **Validation**: Automated document accuracy + semantic similarity scoring

## 🚀 Deployment

### Production Deployment

See [MCP_DEPLOYMENT.md](MCP_DEPLOYMENT.md) for detailed deployment instructions.

### Docker Deployment

```bash
# Build all images
docker-compose build

# Start services
docker-compose up -d

# Scale API servers
docker-compose up -d --scale knowledge-api=3
```

## 💾 Backup & Restore

### Quick Bootstrap (Recommended)

```bash
# Bootstrap from latest backup (66MB, includes 435 PDFs)
make bootstrap

# Fix any missing chunk relationships
make fix-relationships
```

### Export Database

```bash
# Export current database to JSON
make export

# List available backups
make list-backups
```

### Import Database

```bash
# Import from latest backup
make import

# Start with bootstrap from backup
make up-bootstrap
```

### Automated Backup

```bash
# Clean old backups (keep last 5)
make clean-backups

# Add to crontab for daily backups
0 2 * * * cd /path/to/project && make export && make clean-backups
```

## 🛠️ MCP Tools & API Endpoints

### MCP Tools (Claude Desktop)

- `search_documents` - Flexible search with speed/accuracy options
- `search_entities` - Find specific entities and documents
- `read_neo4j_cypher` - Execute Cypher read queries
- `write_neo4j_cypher` - Execute Cypher write queries
- `get_neo4j_schema` - Retrieve database schema

### Search Methods Comparison

| Method | Speed | Accuracy | Use Case | Example |
|--------|-------|----------|----------|----------|
| **Keyword (Default)** | ★★★★★ (0.2s) | ★★★★☆ (80%+) | Interactive queries | `search_documents` with default settings |
| **Vector Search** | ★★☆☆☆ (4-5s) | ★★★★☆ (75-80%) | Semantic similarity | `use_vector_search=true` |
| **Hybrid + Reranking** | ★★☆☆☆ (5-6s) | ★★★★★ (88.8%) | Maximum accuracy | `use_vector_search=true, use_reranking=true` |
| **Expert Cypher** | ★★★★★ (0.1s) | ★★★★★ (86%) | Power users | `read_neo4j_cypher` with custom queries |

### API Endpoints (Optional)

- `POST /search` - Main search endpoint
- `POST /text2cypher` - Natural language to Cypher
- `GET /stats` - System statistics
- `GET /text2cypher/examples` - Query examples

### Example Usage

```python
# MCP Tools in Claude Desktop
# Fast keyword search (default)
search_documents(query="minimum account balance requirements", top_k=5)

# Maximum accuracy (when needed)
search_documents(query="minimum account balance requirements", 
                use_vector_search=True, use_reranking=True, top_k=5)

# Expert Cypher query
read_neo4j_cypher(query="""
MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk)
WHERE toLower(c.text) CONTAINS 'minimum' 
  AND toLower(c.text) CONTAINS 'balance'
RETURN d.filename, c.text, c.page_num
ORDER BY c.page_num LIMIT 10
""")
```

## 🎯 What's New in v0.0.1

- **Optimized MCP Server**: Fast keyword search by default (0.2s response, 80%+ accuracy)
- **Speed vs Accuracy Options**: Choose between fast keyword search or best accuracy (88.8%)
- **Community Detection**: Louvain algorithm organizing 10,150 entities into 42 communities
- **Enhanced Search Tools**: New entity search and flexible search parameters
- **Improved User Experience**: <1s startup with lazy model loading
- **376,227 New Relationships**: Entity co-occurrence for better graph connectivity
- **Production Ready**: Optimized for real-time use in Claude Desktop

## 🎛️ Search Method Selection Guide

### When to Use Each Method

**Fast Keyword Search (Default)**
- ✅ Interactive queries in Claude Desktop
- ✅ Quick document lookups
- ✅ Banking terminology searches
- ✅ When speed is more important than perfect accuracy
- ❌ Complex semantic queries

**Vector Search + Reranking**
- ✅ Research and analysis tasks
- ✅ When maximum accuracy is critical
- ✅ Complex semantic relationships
- ✅ Batch processing scenarios
- ❌ Real-time interactive use

**Expert Cypher Queries**
- ✅ Power users with graph database knowledge
- ✅ Custom business logic
- ✅ Complex relationship queries
- ✅ When you need full control
- ❌ General users without Cypher knowledge

### Performance Trade-offs

```
Speed vs Accuracy Spectrum:

Keyword Search ────────────── Vector + Reranking
    ↑                              ↑
  0.2s, 80%+                   5-6s, 88.8%
  Interactive                  Batch Processing
```

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Run tests to ensure accuracy (`python enhanced_test_runner.py`)
4. Commit your changes (`git commit -m 'feat: Add amazing feature'`)
5. Push to the branch (`git push origin feature/amazing-feature`)
6. Open a Pull Request

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details

## 🙏 Acknowledgments

- Built with [Neo4j](https://neo4j.com/), [FastAPI](https://fastapi.tiangolo.com/), and [Sentence Transformers](https://www.sbert.net/)
- MCP integration for [Claude Desktop](https://claude.ai/download)
- GraphRAG architecture inspired by [Microsoft Research](https://github.com/microsoft/graphrag)
- Community detection using [python-louvain](https://github.com/taynaud/python-louvain)
- 435 Westpac PDF documents indexed for knowledge base

## 📚 Documentation

- [CLAUDE.md](CLAUDE.md) - Comprehensive development guide
- [MCP_SERVER_FIX.md](MCP_SERVER_FIX.md) - MCP server troubleshooting
- [COMMUNITY_DETECTION_SUMMARY.md](COMMUNITY_DETECTION_SUMMARY.md) - Community detection details

---

**Latest Release**: [v0.0.1](https://github.com/JasonAskew/knowledge/releases/tag/v0.0.1) | **Status**: Production Ready | **Default**: 0.2s, 80%+ accuracy | **Max**: 5-6s, 88.8% accuracy