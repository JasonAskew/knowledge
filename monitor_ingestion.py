#!/usr/bin/env python3
"""Monitor ingestion progress"""
import subprocess
import time
import sys
from neo4j import GraphDatabase

def get_document_count():
    """Get current document count from Neo4j"""
    try:
        driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "knowledge123"))
        with driver.session() as session:
            result = session.run("MATCH (d:Document) RETURN count(d) as count")
            count = result.single()["count"]
        driver.close()
        return count
    except:
        return "N/A"

def check_container_status():
    """Check if ingestion container is running"""
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=knowledge-ingestion-full", "--format", "{{.Status}}"],
            capture_output=True, text=True
        )
        return result.stdout.strip() if result.stdout else "Not running"
    except:
        return "Error checking status"

def get_latest_logs():
    """Get latest log lines"""
    try:
        result = subprocess.run(
            ["docker", "logs", "--tail", "5", "knowledge-ingestion-full"],
            capture_output=True, text=True, stderr=subprocess.STDOUT
        )
        return result.stdout.strip() if result.stdout else "No logs"
    except:
        return "Error getting logs"

print("📊 Monitoring PDF Ingestion Progress")
print("Target: 435 PDFs")
print("-" * 60)

start_count = get_document_count()
print(f"Starting document count: {start_count}")
print("-" * 60)

while True:
    current_count = get_document_count()
    container_status = check_container_status()
    
    if container_status == "Not running":
        print("\n❌ Container stopped!")
        logs = get_latest_logs()
        print(f"Last logs:\n{logs}")
        break
    
    print(f"\r📄 Documents: {current_count}/435 | Status: {container_status}", end="", flush=True)
    
    if current_count == 435 + start_count:
        print("\n✅ Ingestion complete!")
        break
    
    time.sleep(10)