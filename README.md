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
  - Vector search with semantic embeddings (384-dim)
  - Graph search with Neo4j Cypher queries
  - Hybrid search combining vector and keyword matching
  - Text2Cypher for natural language to graph queries
  - Community-aware search for enhanced relevance
  
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
  - Lightweight server with lazy loading (<1s startup)
  - Both Cypher queries and ML-powered search
  - Real-time database access via Claude Desktop
  - Fixed startup timeout issues

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
  - Vector Search + Reranking: 88.8% accuracy (71/80)
  - Community Search (Cypher-only): 18.75% baseline
  - Hybrid Search + Reranking: 85%+ accuracy
  - Average query time: < 2 seconds
- **Storage**: 66MB compressed backup available

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
        "/path/to/knowledge/mcp_server/neo4j_mcp_lightweight.py"
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
│   ├── neo4j_exact_proxy.py  # Basic Neo4j proxy
│   ├── neo4j_enhanced_search.py # Full ML features
│   └── neo4j_mcp_lightweight.py # NEW: Optimized MCP
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

### Test Results

- **Current Accuracy**: 88.8% (71/80 correct)
- Results saved in: `data/test_results/`
- Test suite: 80 questions across various banking topics

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

## 🛠️ API Endpoints

### Search Endpoints

- `POST /search` - Main search endpoint
- `POST /text2cypher` - Natural language to Cypher
- `GET /stats` - System statistics
- `GET /text2cypher/examples` - Query examples

### Example Usage

```python
import requests

# Hybrid search with reranking
response = requests.post("http://localhost:8000/search", json={
    "query": "minimum account balance requirements",
    "search_type": "hybrid",
    "limit": 5,
    "rerank": True
})

results = response.json()
```

## 🎯 What's New in v0.0.1

- **Community Detection**: Louvain algorithm organizing 10,150 entities into 42 communities
- **Enhanced MCP Server**: Lightweight design with lazy loading for <1s startup
- **Improved Accuracy**: 88.8% on test suite (up from 73.8%)
- **376,227 New Relationships**: Entity co-occurrence for better graph connectivity
- **Two-Phase Search**: Intra-community search with bridge node exploration

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

**Latest Release**: [v0.0.1](https://github.com/JasonAskew/knowledge/releases/tag/v0.0.1) | **Status**: Production Ready | **Accuracy**: 88.8%