# Makefile for Knowledge Graph RAG System

.PHONY: help build up down logs test clean shell stats health

# Default target
help:
	@echo "Knowledge Graph RAG System - Available Commands:"
	@echo ""
	@echo "  make build    - Build all Docker images"
	@echo "  make up       - Start all services"
	@echo "  make down     - Stop all services"
	@echo "  make logs     - View logs from all services"
	@echo "  make test     - Run test suite"
	@echo "  make clean    - Remove all data and volumes"
	@echo "  make shell    - Open shell in a service"
	@echo "  make stats    - Show graph statistics"
	@echo "  make health   - Check system health"
	@echo ""
	@echo "Backup/Restore commands:"
	@echo "  make export           - Export Neo4j database to JSON"
	@echo "  make import           - Import Neo4j database from JSON"
	@echo "  make bootstrap        - Bootstrap database from latest export (force)"
	@echo "  make list-backups     - List available backups"
	@echo "  make clean-backups    - Clean old backups (keep last 5)"
	@echo ""
	@echo "Service-specific commands:"
	@echo "  make neo4j-logs       - View Neo4j logs"
	@echo "  make ingestion-logs   - View ingestion logs"
	@echo "  make api-logs         - View API logs"
	@echo "  make discovery-logs   - View discovery logs"
	@echo ""
	@echo "Development commands:"
	@echo "  make dev              - Start in development mode"
	@echo "  make rebuild          - Rebuild and restart all services"
	@echo "  make reset            - Reset entire system (WARNING: deletes data)"

# Build all images
build:
	@echo "🔨 Building all Docker images..."
	docker-compose build

# Start all services
up:
	@echo "🚀 Starting all services..."
	docker-compose up -d neo4j
	@echo "⏳ Waiting for Neo4j to be ready..."
	@sleep 10
	docker-compose up -d knowledge-discovery knowledge-ingestion knowledge-api
	@echo "✅ All services started!"
	@echo ""
	@echo "Services available at:"
	@echo "  - Neo4j Browser: http://localhost:7474"
	@echo "  - API: http://localhost:8000"
	@echo "  - API Docs: http://localhost:8000/docs"


# Stop all services
down:
	@echo "🛑 Stopping all services..."
	docker-compose down

# View logs from all services
logs:
	docker-compose logs -f

# Service-specific logs
neo4j-logs:
	docker-compose logs -f neo4j

ingestion-logs:
	docker-compose logs -f knowledge-ingestion

api-logs:
	docker-compose logs -f knowledge-api

discovery-logs:
	docker-compose logs -f knowledge-discovery

# Run test suite
test:
	@echo "🧪 Running test suite..."
	docker-compose run --rm test-runner
	@echo ""
	@echo "📊 Test results saved to ./data/test_results/"
	@ls -la ./data/test_results/ 2>/dev/null | tail -n 5 || echo "No test results found"

# Run enhanced test runner locally
test-local:
	@echo "🧪 Running enhanced test suite locally..."
	python knowledge_test_agent/enhanced_test_runner.py --search-type hybrid --use-reranking
	@echo ""
	@echo "📊 Test results saved to ./data/test_results/"
	@ls -la ./data/test_results/ 2>/dev/null | tail -n 5 || echo "No test results found"

# Clean all data and volumes
clean:
	@echo "🧹 Cleaning all data and volumes..."
	@echo "⚠️  WARNING: This will delete all data! Press Ctrl+C to cancel, or wait 5 seconds..."
	@sleep 5
	docker-compose down -v
	rm -rf ./data/processed/*
	rm -rf ./data/test_results/*
	@echo "✅ Cleanup complete!"

# Open shell in a service
shell:
	@echo "Select a service:"
	@echo "1) neo4j"
	@echo "2) knowledge-discovery"
	@echo "3) knowledge-ingestion"
	@echo "4) knowledge-api"
	@read -p "Enter number: " service; \
	case $$service in \
		1) docker-compose exec neo4j bash ;; \
		2) docker-compose exec knowledge-discovery bash ;; \
		3) docker-compose exec knowledge-ingestion bash ;; \
		4) docker-compose exec knowledge-api bash ;; \
		*) echo "Invalid selection" ;; \
	esac

# Show graph statistics
stats:
	@echo "📊 Knowledge Graph Statistics:"
	@curl -s http://localhost:8000/stats | python -m json.tool || echo "API not available"

# Check system health
health:
	@echo "🏥 System Health Check:"
	@echo ""
	@echo "Neo4j:"
	@curl -s http://localhost:7474 > /dev/null && echo "  ✅ Web interface available" || echo "  ❌ Web interface not available"
	@echo ""
	@echo "API:"
	@curl -s http://localhost:8000/health | python -m json.tool || echo "  ❌ API not available"
	@echo ""
	@echo "Containers:"
	@docker-compose ps

# Development mode - with live reload
dev:
	@echo "🔧 Starting in development mode..."
	docker-compose up neo4j knowledge-api

# Rebuild and restart
rebuild:
	@echo "🔄 Rebuilding and restarting services..."
	make down
	make build
	make up

# Reset entire system
reset:
	@echo "⚠️  WARNING: This will delete all data and rebuild from scratch!"
	@echo "Press Ctrl+C to cancel, or wait 10 seconds..."
	@sleep 10
	make clean
	make build
	make up

# Quick search test
search-test:
	@echo "🔍 Testing search functionality..."
	@curl -s -X POST http://localhost:8000/search \
		-H "Content-Type: application/json" \
		-d '{"query": "home loan interest rate", "search_type": "hybrid", "top_k": 3}' \
		| python -m json.tool


# List available backups
list-backups:
	@./scripts/neo4j_backup.sh list

# Clean old backups
clean-backups:
	@./scripts/neo4j_backup.sh clean

# Legacy backup using neo4j-admin (kept for compatibility)
backup-legacy:
	@echo "💾 Creating Neo4j backup (legacy method)..."
	@mkdir -p ./backups
	@docker-compose exec neo4j neo4j-admin dump \
		--database=neo4j \
		--to=/backup/knowledge-graph-$$(date +%Y%m%d-%H%M%S).dump
	@docker cp $$(docker-compose ps -q neo4j):/backup/. ./backups/
	@echo "✅ Backup saved to ./backups/"
	@ls -la ./backups/

# Monitor resource usage
monitor:
	@echo "📈 Resource Usage:"
	@docker stats --no-stream

# Export Neo4j to JSON
export:
	@echo "💾 Exporting Neo4j database to JSON..."
	@python scripts/export_neo4j.py
	@echo "✅ Export saved to ./data/backups/"
	@ls -la ./data/backups/ | tail -5

# Import from backup
import:
	@echo "📥 Importing from latest backup..."
	@python scripts/bootstrap_neo4j.py
	@echo "✅ Import completed!"

# Bootstrap from backup (force)
bootstrap:
	@echo "🔄 Bootstrapping from backup (will clear existing data)..."
	@echo "yes" | NEO4J_PASSWORD=knowledge123 python scripts/bootstrap_neo4j.py --force
	@echo "✅ Bootstrap completed!"

# Start fresh with bootstrap
up-bootstrap:
	@echo "🚀 Starting Neo4j..."
	@docker-compose up -d neo4j
	@echo "⏳ Waiting for Neo4j to be fully ready..."
	@sleep 30
	@echo "🔄 Bootstrapping database from backup..."
	@docker-compose run --rm -e BOOTSTRAP_FORCE=yes bootstrap
	@echo "🚀 Starting remaining services..."
	@docker-compose up -d knowledge-discovery knowledge-ingestion knowledge-api
	@echo "✅ System ready with bootstrapped data!"
	@echo ""
	@echo "Services available at:"
	@echo "  - Neo4j Browser: http://localhost:7474"
	@echo "  - API: http://localhost:8000"
	@echo "  - API Docs: http://localhost:8000/docs"

# Run specific ingestion
ingest:
	@echo "📥 Running ingestion..."
	docker-compose run --rm knowledge-ingestion

# Run discovery agent
discover:
	@echo "🔍 Running discovery agent..."
	docker-compose run --rm knowledge-discovery

# Tail latest test results
test-results:
	@echo "📋 Latest test results:"
	@if [ -d "./data/test_results" ] && [ "$$(ls -A ./data/test_results 2>/dev/null)" ]; then \
		latest=$$(ls -t ./data/test_results/*.json 2>/dev/null | head -1); \
		if [ -n "$$latest" ]; then \
			cat "$$latest" | python -m json.tool | head -30; \
		else \
			echo "No test results found"; \
		fi \
	else \
		echo "No test results directory found"; \
	fi