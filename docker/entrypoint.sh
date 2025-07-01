#!/bin/bash
# Entrypoint script for ingestion agent

echo "Starting ingestion service..."

# Wait for Neo4j to be ready
echo "Waiting for Neo4j to be ready..."
python /app/wait_for_neo4j.py

if [ $? -eq 0 ]; then
    echo "Neo4j is ready! Starting sequential ingestion for Docker..."
    # Use the Docker-safe wrapper that processes files sequentially
    python /app/docker_wrapper.py --inventory /data/inventories/mvp_inventory.json
    echo "Ingestion complete. Container will exit."
    exit 0
else
    echo "Failed to connect to Neo4j"
    exit 1
fi