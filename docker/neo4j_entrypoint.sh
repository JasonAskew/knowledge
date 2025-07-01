#!/bin/bash
# Custom entrypoint for Neo4j with optional bootstrap support

set -e

# Function to wait for Neo4j to be ready
wait_for_neo4j() {
    echo "Waiting for Neo4j to be ready..."
    until neo4j status | grep -q "Neo4j is running"; do
        sleep 2
    done
    echo "Neo4j is ready!"
}

# Start Neo4j in the background
/startup/docker-entrypoint.sh neo4j &
NEO4J_PID=$!

# Wait for Neo4j to be ready
wait_for_neo4j

# Check if bootstrap is requested
if [ "${NEO4J_BOOTSTRAP}" = "true" ]; then
    echo "Bootstrap mode enabled"
    
    # Check if bootstrap file exists
    BOOTSTRAP_FILE="${NEO4J_BOOTSTRAP_FILE:-/data/backups/latest_export.json}"
    
    if [ -f "$BOOTSTRAP_FILE" ]; then
        echo "Found bootstrap file: $BOOTSTRAP_FILE"
        
        # Check if database is empty
        NODE_COUNT=$(cypher-shell -u neo4j -p "${NEO4J_PASSWORD:-knowledge123}" \
            "MATCH (n) RETURN count(n) as count" --format plain | tail -1)
        
        if [ "$NODE_COUNT" = "0" ] || [ "${NEO4J_BOOTSTRAP_FORCE}" = "true" ]; then
            echo "Starting bootstrap process..."
            python3 /scripts/bootstrap_neo4j.py --file "$BOOTSTRAP_FILE" ${NEO4J_BOOTSTRAP_FORCE:+--force}
            
            if [ $? -eq 0 ]; then
                echo "Bootstrap completed successfully!"
            else
                echo "Bootstrap failed, but continuing with empty database"
            fi
        else
            echo "Database already contains data. Skipping bootstrap."
            echo "Set NEO4J_BOOTSTRAP_FORCE=true to force bootstrap."
        fi
    else
        echo "Bootstrap file not found: $BOOTSTRAP_FILE"
        echo "Starting with empty database."
    fi
fi

# Keep Neo4j running in the foreground
wait $NEO4J_PID