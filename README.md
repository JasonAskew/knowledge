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

- **MCP Integration**:
  - Direct integration with Claude Desktop
  - Natural language access to knowledge base
  - Real-time search and retrieval

- **Backup & Restore**:
  - Full database export to JSON format
  - Quick bootstrap from existing backups
  - Automated backup management
  - Optional bootstrap on startup

## 📊 Performance

Current accuracy metrics on MVP test set:
- Vector Search + Reranking: 73.8% accuracy
- Text2Cypher: 66.2% citation accuracy
- Average query time: < 2 seconds

## 🏗️ Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Claude Desktop │────▶│   MCP Server    │────▶│   Knowledge API │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                          │
                                ┌─────────────────────────┴─────────────────────────┐
                                │                                                   │
                        ┌───────▼────────┐              ┌──────────▼────────┐      │
                        │   Neo4j Graph  │              │  Vector Store     │      │
                        │    Database    │              │  (Embeddings)     │      │
                        └────────────────┘              └───────────────────┘      │
                                                                                   │
                        ┌─────────────────────────────────────────────────────────┘
                        │
                ┌───────▼────────┐
                │  Document Store │
                │   (PDF Files)   │
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
git clone <repository>
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

### 3. Ingest Documents

```bash
cd knowledge_ingestion_agent
python knowledge_ingestion_agent.py
```

### 4. Configure Claude Desktop

Add to your Claude Desktop config:

```json
{
  "mcpServers": {
    "knowledge-graph": {
      "command": "python",
      "args": ["-m", "mcp_server.standalone_server"],
      "cwd": "/path/to/knowledge/mcp_server",
      "env": {
        "API_BASE_URL": "http://localhost:8000"
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
│   └── enhanced_chunking.py
├── knowledge_test_agent/      # Testing framework
│   ├── enhanced_test_runner.py
│   └── test_cases.csv
├── mcp_server/               # MCP integration
│   ├── standalone_server.py
│   └── setup.sh
├── utils/                    # Shared utilities
└── data/                     # Documents and test results
```

## 🔧 Configuration

### Environment Variables

```bash
# Neo4j Configuration
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password

# API Configuration
API_BASE_URL=http://localhost:8000
API_KEY=your-api-key  # For production

# Model Configuration
EMBEDDING_MODEL=all-MiniLM-L6-v2
RERANKER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2
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

# Bootstrap (force import)
make bootstrap

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

See [docs/BACKUP_RESTORE_GUIDE.md](docs/BACKUP_RESTORE_GUIDE.md) for detailed documentation.

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