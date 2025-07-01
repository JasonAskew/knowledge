#!/bin/bash
# Startup script for ingestion agent

echo "Waiting for Neo4j to be ready..."

# Wait for Neo4j
max_attempts=30
attempt=0

while [ $attempt -lt $max_attempts ]; do
    if python -c "
from neo4j import GraphDatabase
try:
    driver = GraphDatabase.driver('bolt://neo4j:7687', auth=('neo4j', 'knowledge123'))
    driver.verify_connectivity()
    driver.close()
    exit(0)
except:
    exit(1)
    " 2>/dev/null; then
        echo "Neo4j is ready!"
        break
    fi
    
    attempt=$((attempt + 1))
    echo "Attempt $attempt/$max_attempts: Neo4j not ready yet. Waiting..."
    sleep 2
done

if [ $attempt -eq $max_attempts ]; then
    echo "Neo4j failed to become ready"
    exit 1
fi

# Start ingestion
echo "Starting knowledge ingestion agent..."
exec python knowledge_ingestion_agent.py --inventory /data/inventories/mvp_inventory.json