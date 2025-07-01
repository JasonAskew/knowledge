#!/usr/bin/env python3
"""
Check ingestion status
"""

import subprocess
import time
from neo4j import GraphDatabase

# Check if container is still running
result = subprocess.run(['docker', 'ps', '-q', '-f', 'name=knowledge_knowledge-ingestion'], 
                       capture_output=True, text=True)

if result.stdout.strip():
    # Get latest log entry
    logs = subprocess.run(['docker', 'logs', '--tail', '100', 'knowledge_knowledge-ingestion_run_c99ddbe4d53f'], 
                         capture_output=True, text=True, stderr=subprocess.STDOUT)
    
    # Find processing lines
    processing_lines = [l for l in logs.stdout.split('\n') if 'Processing [' in l]
    if processing_lines:
        print(f"Still running: {processing_lines[-1]}")
    
    # Count successes
    success_count = logs.stdout.count('Successfully processed:')
    print(f"Successfully processed: {success_count}/26 files")
else:
    print("Ingestion completed!")
    
    # Check database
    try:
        driver = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', 'knowledge123'))
        with driver.session() as session:
            result = session.run('MATCH (d:Document) RETURN count(d) as count')
            docs = result.single()['count']
            
            result = session.run('MATCH (c:Chunk) RETURN count(c) as count, avg(c.semantic_density) as avg_density')
            record = result.single()
            chunks = record['count']
            avg_density = record.get('avg_density', 0)
            
            print(f"\nDatabase state:")
            print(f"  Documents: {docs}")
            print(f"  Chunks: {chunks}")
            print(f"  Avg semantic density: {avg_density:.3f}")
        driver.close()
    except Exception as e:
        print(f"Error checking database: {e}")