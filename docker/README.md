# Docker Configuration

This directory contains Docker configurations for the Knowledge Graph System with GraphRAG.

## Services

### docker-compose.yml

The main orchestration file that runs three core services:

1. **neo4j** - Graph database (port 7687, 7474)
   - 75,773 nodes, 592,823 relationships
   - Includes APOC and Graph Data Science plugins
   - Persistent volume for data storage
   - Bootstrap capability from backups

2. **knowledge-api** - FastAPI server (port 8000)
   - Multiple search methods (vector, graph, hybrid, text2cypher)
   - Cross-encoder reranking
   - Citation support with page numbers
   - Connection to Neo4j and Redis

3. **redis** - Cache layer (port 6379)
   - Query result caching
   - Performance optimization

## Quick Start

```bash
# Start all services
docker-compose up -d

# Start with database bootstrap
docker-compose up -d --env-file ../.env BOOTSTRAP_NEO4J=true

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Stop and remove volumes
docker-compose down -v
```

## Container Images

### API Container (Dockerfile.api)
- Base: python:3.9-slim
- Includes all Python dependencies
- FastAPI with uvicorn
- Search engine and reranking models

### Neo4j Container (Dockerfile.neo4j)
- Base: neo4j:5.13.0
- Custom entrypoint for bootstrap support
- Automated backup import on startup (optional)

## Environment Variables

Required in `.env` file:

```bash
# Neo4j
NEO4J_AUTH=neo4j/knowledge123
NEO4J_PLUGINS=["apoc", "graph-data-science"]

# API
API_PORT=8000

# Bootstrap (optional)
BOOTSTRAP_NEO4J=true  # Set to bootstrap on startup
```

## Key Files

- **api.py** - Main API server with search endpoints
- **neo4j_entrypoint.sh** - Custom Neo4j startup script with bootstrap
- **wait_for_neo4j.py** - Utility to wait for Neo4j readiness
- **docker-compose.yml** - Service orchestration

## Networking

All services communicate on the `knowledge-network` Docker network:
- Neo4j: `neo4j:7687` (bolt), `neo4j:7474` (http)
- API: `knowledge-api:8000`
- Redis: `redis:6379`

## Volumes

- `neo4j_data` - Neo4j database files
- `neo4j_logs` - Neo4j log files
- `redis_data` - Redis persistence

## Bootstrap Process

When `BOOTSTRAP_NEO4J=true`:

1. Neo4j starts and waits for readiness
2. Checks for existing data
3. If empty, imports latest backup from `/backups`
4. Fixes chunk relationships automatically
5. Continues normal operation

## Monitoring

```bash
# Check service health
docker-compose ps

# View Neo4j browser
open http://localhost:7474

# Test API
curl http://localhost:8000/stats

# Monitor logs
docker-compose logs -f knowledge-api
```