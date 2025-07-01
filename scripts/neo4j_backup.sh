#!/bin/bash
# Neo4j Backup Management Script

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKUP_DIR="/data/backups"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

function print_usage() {
    echo "Neo4j Knowledge Graph Backup Management"
    echo ""
    echo "Usage: $0 [command] [options]"
    echo ""
    echo "Commands:"
    echo "  export    - Export the Neo4j database to JSON"
    echo "  import    - Import from a JSON backup file"
    echo "  list      - List available backups"
    echo "  clean     - Remove old backups (keep last 5)"
    echo ""
    echo "Options:"
    echo "  --file <path>    - Specify backup file for import"
    echo "  --force          - Force import even if database has data"
    echo ""
}

function export_database() {
    echo -e "${GREEN}Starting Neo4j export...${NC}"
    
    # Change to project root for docker-compose
    cd "${SCRIPT_DIR}/.."
    
    # Check if Neo4j is running
    if ! docker-compose ps neo4j 2>/dev/null | grep -q "running"; then
        echo -e "${RED}Error: Neo4j is not running${NC}"
        exit 1
    fi
    
    # Run export inside container
    docker-compose exec -T neo4j python3 /scripts/export_neo4j.py
    
    # The backup is already in the mounted volume, just create symlink
    HOST_BACKUP_DIR="${SCRIPT_DIR}/../data/backups"
    mkdir -p "$HOST_BACKUP_DIR"
    
    # Find the latest backup
    cd "$HOST_BACKUP_DIR"
    LATEST_BACKUP=$(ls -t neo4j_export_*.json 2>/dev/null | head -1)
    
    if [ -n "$LATEST_BACKUP" ]; then
        ln -sf "$LATEST_BACKUP" latest_export.json
        echo -e "${GREEN}Export completed: $HOST_BACKUP_DIR/$LATEST_BACKUP${NC}"
        echo -e "${GREEN}Latest symlink updated${NC}"
    else
        echo -e "${RED}Error: No backup file found${NC}"
        exit 1
    fi
}

function import_database() {
    echo -e "${GREEN}Starting Neo4j import...${NC}"
    
    # Parse arguments
    IMPORT_FILE=""
    FORCE_FLAG=""
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --file)
                IMPORT_FILE="$2"
                shift 2
                ;;
            --force)
                FORCE_FLAG="--force"
                shift
                ;;
            *)
                shift
                ;;
        esac
    done
    
    # Change to project root for docker-compose
    cd "${SCRIPT_DIR}/.."
    
    # Check if Neo4j is running
    if ! docker-compose ps neo4j 2>/dev/null | grep -q "running"; then
        echo -e "${RED}Error: Neo4j is not running${NC}"
        exit 1
    fi
    
    HOST_BACKUP_DIR="${SCRIPT_DIR}/../data/backups"
    
    # Determine import file
    if [ -z "$IMPORT_FILE" ]; then
        # Use latest
        if [ -f "$HOST_BACKUP_DIR/latest_export.json" ]; then
            IMPORT_FILE="latest_export.json"
        else
            echo -e "${RED}Error: No backup file found. Please run export first or specify --file${NC}"
            exit 1
        fi
    else
        # Convert to relative path if absolute
        if [[ "$IMPORT_FILE" = /* ]]; then
            IMPORT_FILE=$(basename "$IMPORT_FILE")
        fi
    fi
    
    # Run import (file is already in mounted volume)
    docker-compose exec -T neo4j python3 /scripts/bootstrap_neo4j.py --file "/data/backups/$IMPORT_FILE" $FORCE_FLAG
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Import completed successfully!${NC}"
    else
        echo -e "${RED}Import failed${NC}"
        exit 1
    fi
}

function list_backups() {
    HOST_BACKUP_DIR="${SCRIPT_DIR}/../data/backups"
    
    echo -e "${GREEN}Available backups:${NC}"
    echo ""
    
    if [ -d "$HOST_BACKUP_DIR" ]; then
        ls -lah "$HOST_BACKUP_DIR"/*.json 2>/dev/null || echo "No backups found"
    else
        echo "No backup directory found"
    fi
}

function clean_backups() {
    HOST_BACKUP_DIR="${SCRIPT_DIR}/../data/backups"
    
    echo -e "${YELLOW}Cleaning old backups (keeping last 5)...${NC}"
    
    if [ -d "$HOST_BACKUP_DIR" ]; then
        # Keep only the 5 most recent backups
        cd "$HOST_BACKUP_DIR"
        ls -t neo4j_export_*.json 2>/dev/null | tail -n +6 | xargs rm -f
        echo -e "${GREEN}Cleanup completed${NC}"
    fi
}

# Main script logic
case "$1" in
    export)
        export_database
        ;;
    import)
        shift
        import_database "$@"
        ;;
    list)
        list_backups
        ;;
    clean)
        clean_backups
        ;;
    *)
        print_usage
        exit 1
        ;;
esac