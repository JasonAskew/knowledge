#!/bin/bash
# Test script for backup/restore functionality

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "Testing Neo4j Backup/Restore Functionality"
echo "=========================================="

# 1. Check if Neo4j is running
echo -e "\n${YELLOW}1. Checking Neo4j status...${NC}"
cd "${SCRIPT_DIR}/.."
if docker-compose ps neo4j 2>/dev/null | grep -q "running"; then
    echo -e "${GREEN}✓ Neo4j is running${NC}"
else
    echo -e "${RED}✗ Neo4j is not running. Please start it first: make up${NC}"
    exit 1
fi

# 2. Get initial node count
echo -e "\n${YELLOW}2. Getting initial database statistics...${NC}"
INITIAL_COUNT=$(docker-compose exec -T neo4j cypher-shell -u neo4j -p knowledge123 \
    "MATCH (n) RETURN count(n) as count" --format plain 2>/dev/null | tail -1 || echo "0")
echo -e "Initial node count: ${INITIAL_COUNT}"

# 3. Run export
echo -e "\n${YELLOW}3. Testing export functionality...${NC}"
"${SCRIPT_DIR}/neo4j_backup.sh" export

# 4. Verify export file exists
echo -e "\n${YELLOW}4. Verifying export file...${NC}"
if [ -f "${SCRIPT_DIR}/../data/backups/latest_export.json" ]; then
    echo -e "${GREEN}✓ Export file created successfully${NC}"
    EXPORT_SIZE=$(ls -lh "${SCRIPT_DIR}/../data/backups/latest_export.json" | awk '{print $5}')
    echo -e "Export file size: ${EXPORT_SIZE}"
else
    echo -e "${RED}✗ Export file not found${NC}"
    exit 1
fi

# 5. Test import (non-destructive - should fail if data exists)
echo -e "\n${YELLOW}5. Testing import (should skip if data exists)...${NC}"
"${SCRIPT_DIR}/neo4j_backup.sh" import || true

# 6. List backups
echo -e "\n${YELLOW}6. Listing available backups...${NC}"
"${SCRIPT_DIR}/neo4j_backup.sh" list

echo -e "\n${GREEN}✓ All tests completed successfully!${NC}"
echo ""
echo "To test full restore functionality:"
echo "  1. Stop services: make down"
echo "  2. Clean data: make clean"
echo "  3. Start with bootstrap: make up-bootstrap"