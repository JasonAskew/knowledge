# Knowledge Graph System with GraphRAG

A production-ready knowledge graph system with GraphRAG (Graph Retrieval Augmented Generation) capabilities, featuring multiple search methods, intelligent reranking, and MCP (Model Context Protocol) support for Claude Desktop integration.

## 🚀 Features

- **Multiple Search Methods**:
  - Vector search with semantic embeddings
  - Graph search with Neo4j
  - Hybrid search combining vector and graph
  - Text2Cypher for natural language to graph queries
  
- **Enhanced Chunking**:
  - Semantic density calculation
  - Definition and example detection
  - Chunk type classification
  - Optimized chunk sizes with overlap

- **Intelligent Reranking**:
  - Cross-encoder reranking with BERT
  - Keyword and metadata boosting
  - Configurable scoring weights
  - Citation support with page numbers

- **MCP Integration**:
  - Direct Neo4j access via Claude Desktop
  - Pure proxy to neo4j-cypher tools
  - Real-time database queries

- **Backup & Restore**:
  - Full database export to JSON format (66MB compressed)
  - Quick bootstrap from existing backups
  - Automated chunk relationship repair
  - Git LFS support for large backups

## 📊 Current Status

- **Database**: 75,773 nodes, 592,823 relationships
- **Documents**: 435 Westpac PDFs fully indexed
- **Performance**:
  - Vector Search + Reranking: 73.8% accuracy
  - Text2Cypher: 66.2% citation accuracy
  - Average query time: < 2 seconds
- **Storage**: 66MB compressed backup available

## 🏗️ Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Claude Desktop │────▶│  MCP Server     │────▶│   Neo4j DB      │
│                 │     │ (neo4j proxy)   │     │ (75,773 nodes)  │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                          │
                        ┌─────────────────────────────────┤
                        │                                 │
                ┌───────▼────────┐              ┌────────▼────────┐
                │  Knowledge API │              │  Vector Store   │
                │  (FastAPI)     │              │  (Embeddings)   │
                └────────────────┘              └─────────────────┘
                        │
                ┌───────▼────────┐
                │  435 PDFs      │
                │  (Indexed)     │
                └────────────────┘
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
cd docker
docker-compose up -d
```

This starts:
- Neo4j database
- Knowledge API
- Redis cache

### 3. Bootstrap from Backup (Recommended)

```bash
# Import existing database with 435 indexed PDFs
make bootstrap

# Or ingest documents manually
cd knowledge_ingestion_agent
python knowledge_ingestion_agent.py
```

### 4. Configure Claude Desktop

Edit Claude Desktop config at:
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "knowledge-graph": {
      "command": "/opt/anaconda3/bin/python3",
      "args": [
        "/path/to/knowledge/mcp_server/neo4j_exact_proxy.py"
      ],
      "cwd": "/path/to/knowledge",
      "env": {
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_USERNAME": "neo4j",
        "NEO4J_PASSWORD": "knowledge123",
        "NEO4J_DATABASE": "neo4j"
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
│   └── search_engine.py
├── knowledge_discovery_agent/ # Discovery tools
│   └── westpac_pdfs/         # 435 indexed PDFs
├── knowledge_test_agent/      # Testing framework
│   ├── enhanced_test_runner.py
│   └── test_cases.csv
├── mcp_server/               # MCP integration
│   └── neo4j_exact_proxy.py  # Clean Neo4j proxy
├── scripts/                  # Utility scripts
│   ├── bootstrap_neo4j.py    # Database import
│   └── fix_chunk_relationships.py
├── utils/                    # Shared utilities
│   ├── citation_formatter.py
│   └── citation_query_examples.py
├── backups/                  # Database backups
└── data/                     # Test results
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
RERANKER_MODEL=cross-encoder/ms-marco-MiniLM-L-12-v2
```

## 📈 Testing

### Run Accuracy Tests

```bash
cd knowledge_test_agent
python enhanced_test_runner.py --search-type hybrid --rerank
```

### Test Results

Test results are saved in:
- CSV format: `/data/test_results/test_report_*.csv`
- Markdown summary: `/data/test_results/test_report_*.md`

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

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch
3. Run tests to ensure accuracy
4. Submit a pull request

## 📄 License

[Your License Here]

## 🙏 Acknowledgments

- Built with Neo4j, FastAPI, and Sentence Transformers
- MCP integration for Claude Desktop
- GraphRAG architecture inspired by Microsoft Research
- 435 Westpac PDF documents indexed for knowledge base