# Docker Deployment Guide

This guide explains how to deploy and test the Knowledge Graph RAG system using Docker.

## Prerequisites

- Docker and Docker Compose installed
- AWS CLI configured (for S3 sync functionality)
- At least 4GB of available RAM
- 10GB of free disk space

## Quick Start

```bash
# Build and start all services
make up

# View logs
make logs

# Run tests
make test

# Stop all services
make down
```

## Services Overview

The docker-compose.yml defines the following services:

### 1. Neo4j Database
- **Image**: neo4j:5-community
- **Ports**: 7474 (HTTP), 7687 (Bolt)
- **Credentials**: neo4j/knowledge123
- **Plugins**: APOC, Graph Data Science
- **Health Check**: Monitors database availability

### 2. Knowledge Discovery Agent
- **Purpose**: Discovers and downloads public PDFs
- **Schedule**: Runs daily at 2 AM
- **Features**: 
  - S3 sync capability
  - Inventory management
  - Public availability verification

### 3. Knowledge Ingestion Agent
- **Purpose**: Processes PDFs and populates the knowledge graph
- **Dependencies**: Neo4j must be ready
- **Features**:
  - PyMuPDF for PDF parsing
  - spaCy for NER
  - BAAI/bge-small-en-v1.5 for embeddings
  - Smart chunking and deduplication

### 4. Knowledge API
- **Purpose**: REST API for searching the knowledge graph
- **Port**: 8000
- **Endpoints**:
  - `/health` - Health check
  - `/search` - Multi-modal search
  - `/stats` - Graph statistics
  - `/docs` - API documentation

### 5. Test Runner
- **Purpose**: Automated testing against the API
- **Output**: Test results saved to `/data/test_results`

## Step-by-Step Deployment

### 1. Build Images

```bash
# Build all images
docker-compose build

# Or build specific service
docker-compose build knowledge-ingestion
```

### 2. Start Core Services

```bash
# Start Neo4j first
docker-compose up -d neo4j

# Wait for Neo4j to be ready (check logs)
docker-compose logs -f neo4j

# Start ingestion agent
docker-compose up -d knowledge-ingestion

# Start API
docker-compose up -d knowledge-api
```

### 3. Monitor Progress

```bash
# View ingestion progress
docker-compose logs -f knowledge-ingestion

# Check API health
curl http://localhost:8000/health

# View graph statistics
curl http://localhost:8000/stats
```

### 4. Run Tests

```bash
# Run test suite
docker-compose run test-runner

# View test results
ls -la data/test_results/
```

## Configuration

### Environment Variables

Create a `.env` file for custom configuration:

```env
# Neo4j
NEO4J_AUTH=neo4j/your-password
NEO4J_PLUGINS=["apoc", "graph-data-science"]

# S3 Configuration
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
S3_BUCKET_NAME=knowledge4westpac

# API Configuration
API_PORT=8000
```

### Volumes

The system uses several Docker volumes for persistence:

- `neo4j_data`: Neo4j database files
- `neo4j_logs`: Neo4j logs
- `processed_data`: Processed chunks and embeddings
- `test_results`: Test execution results

### AWS S3 Configuration

To enable S3 sync in the discovery agent:

1. Ensure AWS credentials are available:
   ```bash
   # Option 1: Mount AWS credentials
   volumes:
     - ~/.aws:/root/.aws:ro
   
   # Option 2: Use environment variables
   environment:
     - AWS_ACCESS_KEY_ID
     - AWS_SECRET_ACCESS_KEY
   ```

2. Set S3 configuration in discovery agent:
   ```python
   s3_config = S3Config(
       bucket_name="knowledge4westpac",
       sync_enabled=True
   )
   ```

## Testing the System

### 1. Manual Search Test

```bash
# Vector search
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How do I reduce my home loan interest rate?",
    "search_type": "vector",
    "top_k": 5
  }'

# Hybrid search
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Option Premium calculation",
    "search_type": "hybrid",
    "top_k": 10
  }'
```

### 2. Automated Test Suite

The test runner uses the `test.csv` file to run comprehensive tests:

```bash
# Run full test suite
docker-compose run test-runner

# Check results
cat data/test_results/test_results_*.json | jq '.summary'
```

### 3. Performance Testing

```bash
# Run performance benchmark
docker-compose exec knowledge-api python -m pytest tests/performance_test.py
```

## Troubleshooting

### Neo4j Won't Start

```bash
# Check logs
docker-compose logs neo4j

# Verify memory settings
docker stats

# Reset data (WARNING: deletes all data)
docker-compose down -v
docker-compose up -d neo4j
```

### Ingestion Errors

```bash
# Check agent logs
docker-compose logs knowledge-ingestion

# Verify PDF inventory
docker-compose exec knowledge-ingestion ls -la /data/pdfs/

# Re-run ingestion
docker-compose restart knowledge-ingestion
```

### API Connection Issues

```bash
# Check API health
curl http://localhost:8000/health

# Verify Neo4j connection
docker-compose exec knowledge-api python -c "
from neo4j import GraphDatabase
driver = GraphDatabase.driver('bolt://neo4j:7687', auth=('neo4j', 'knowledge123'))
driver.verify_connectivity()
print('Connected!')
"
```

### S3 Sync Issues

```bash
# Test AWS credentials
docker-compose exec knowledge-discovery aws s3 ls s3://knowledge4westpac/

# Check sync logs
docker-compose logs knowledge-discovery | grep S3
```

## Maintenance

### Backup Neo4j

```bash
# Create backup
docker-compose exec neo4j neo4j-admin dump --database=neo4j --to=/backup/knowledge-graph.dump

# Copy backup to host
docker cp $(docker-compose ps -q neo4j):/backup/knowledge-graph.dump ./backups/
```

### Update Embeddings Model

```bash
# Pull latest model
docker-compose exec knowledge-ingestion python -c "
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('BAAI/bge-small-en-v1.5')
model.save('/models/bge-small-en-v1.5')
"
```

### Clear and Rebuild

```bash
# Stop all services
make down

# Remove all data
make clean

# Rebuild from scratch
make build
make up
```

## Production Considerations

1. **Security**:
   - Change default Neo4j password
   - Use environment-specific .env files
   - Enable SSL/TLS for API
   - Restrict network access

2. **Scaling**:
   - Use Neo4j Enterprise for clustering
   - Deploy multiple API instances behind load balancer
   - Use Redis for caching
   - Implement rate limiting

3. **Monitoring**:
   - Enable Prometheus metrics
   - Set up Grafana dashboards
   - Configure alerts for failures
   - Monitor disk usage

4. **Backup Strategy**:
   - Daily Neo4j backups
   - S3 versioning for PDFs
   - Test restore procedures
   - Document recovery process

## Next Steps

1. Review test results in `/data/test_results`
2. Fine-tune search weights based on performance
3. Add more PDFs to the inventory
4. Implement additional search strategies
5. Set up monitoring and alerts