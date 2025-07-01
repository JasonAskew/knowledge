#!/bin/bash
# Start the knowledge graph system with optional bootstrap

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
BOOTSTRAP=false
FORCE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --bootstrap)
            BOOTSTRAP=true
            shift
            ;;
        --force)
            FORCE=true
            shift
            ;;
        --help)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --bootstrap    Enable bootstrap from latest backup"
            echo "  --force        Force bootstrap even if database has data"
            echo "  --help         Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}Knowledge Graph RAG System Startup${NC}"
echo ""

# Check if bootstrap is requested
if [ "$BOOTSTRAP" = true ]; then
    echo -e "${YELLOW}Bootstrap mode enabled${NC}"
    
    # Check if backup exists
    if [ -f "./data/backups/latest_export.json" ]; then
        echo -e "${GREEN}Found bootstrap file${NC}"
        export NEO4J_BOOTSTRAP=true
        
        if [ "$FORCE" = true ]; then
            export NEO4J_BOOTSTRAP_FORCE=true
            echo -e "${YELLOW}Force mode enabled - will overwrite existing data${NC}"
        fi
    else
        echo -e "${RED}No bootstrap file found at ./data/backups/latest_export.json${NC}"
        echo "Run 'make export' first to create a backup, or start without --bootstrap"
        exit 1
    fi
fi

# Start services
echo -e "${GREEN}Starting services...${NC}"
docker-compose up -d neo4j

echo -e "${YELLOW}Waiting for Neo4j to be ready...${NC}"
sleep 15

# Check Neo4j health
if curl -s http://localhost:7474 > /dev/null; then
    echo -e "${GREEN}Neo4j is ready!${NC}"
else
    echo -e "${RED}Neo4j failed to start${NC}"
    docker-compose logs neo4j
    exit 1
fi

# Start remaining services
echo -e "${GREEN}Starting remaining services...${NC}"
docker-compose up -d knowledge-discovery knowledge-ingestion knowledge-api

echo ""
echo -e "${GREEN}All services started successfully!${NC}"
echo ""
echo "Services available at:"
echo "  - Neo4j Browser: http://localhost:7474"
echo "  - API: http://localhost:8000"
echo "  - API Docs: http://localhost:8000/docs"
echo ""

# Show bootstrap status if enabled
if [ "$BOOTSTRAP" = true ]; then
    echo -e "${BLUE}Bootstrap Status:${NC}"
    docker-compose logs neo4j | grep -E "(Bootstrap|bootstrap)" | tail -10
fi