#!/bin/bash

# Knowledge Graph RAG System - Startup Script

set -e

echo "🚀 Knowledge Graph RAG System Startup"
echo "===================================="

# Check prerequisites
echo "Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

echo "✅ Prerequisites satisfied"

# Create necessary directories
echo ""
echo "Creating directories..."
mkdir -p data/processed
mkdir -p data/test_results
mkdir -p backups
echo "✅ Directories created"

# Check if .env file exists
if [ ! -f .env ]; then
    echo ""
    echo "📝 Creating default .env file..."
    cat > .env << EOF
# Neo4j Configuration
NEO4J_AUTH=neo4j/knowledge123
NEO4J_PLUGINS=["apoc", "graph-data-science"]

# API Configuration
API_PORT=8000

# S3 Configuration (optional)
# AWS_ACCESS_KEY_ID=your-key
# AWS_SECRET_ACCESS_KEY=your-secret
# S3_BUCKET_NAME=knowledge4westpac
EOF
    echo "✅ Default .env file created"
fi

# Build images
echo ""
echo "🔨 Building Docker images..."
docker-compose build

# Start Neo4j first
echo ""
echo "🗄️  Starting Neo4j database..."
docker-compose up -d neo4j

# Wait for Neo4j to be ready
echo "⏳ Waiting for Neo4j to be ready..."
max_attempts=30
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if docker-compose exec neo4j cypher-shell -u neo4j -p knowledge123 "RETURN 1" &> /dev/null; then
        echo "✅ Neo4j is ready!"
        break
    fi
    attempt=$((attempt + 1))
    echo "   Attempt $attempt/$max_attempts..."
    sleep 2
done

if [ $attempt -eq $max_attempts ]; then
    echo "❌ Neo4j failed to start. Check logs with: docker-compose logs neo4j"
    exit 1
fi

# Start other services
echo ""
echo "🚀 Starting remaining services..."
docker-compose up -d knowledge-discovery knowledge-ingestion knowledge-api

# Wait for API to be ready
echo ""
echo "⏳ Waiting for API to be ready..."
max_attempts=15
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if curl -s http://localhost:8000/health > /dev/null; then
        echo "✅ API is ready!"
        break
    fi
    attempt=$((attempt + 1))
    echo "   Attempt $attempt/$max_attempts..."
    sleep 2
done

# Show status
echo ""
echo "📊 System Status:"
echo "================"
docker-compose ps

# Show URLs
echo ""
echo "🌐 Service URLs:"
echo "================"
echo "  Neo4j Browser: http://localhost:7474"
echo "  API: http://localhost:8000"
echo "  API Docs: http://localhost:8000/docs"
echo "  API Health: http://localhost:8000/health"

# Show stats
echo ""
echo "📈 Initial Statistics:"
curl -s http://localhost:8000/stats | python -m json.tool 2>/dev/null || echo "  Waiting for data..."

# Show next steps
echo ""
echo "✅ System started successfully!"
echo ""
echo "Next steps:"
echo "  - View logs: make logs"
echo "  - Run tests: make test"
echo "  - Check health: make health"
echo "  - View stats: make stats"
echo ""
echo "To stop the system: make down"