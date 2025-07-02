#!/usr/bin/env python3
import time
import subprocess
import sys

def get_document_count():
    """Get current document count from Neo4j"""
    try:
        result = subprocess.run(
            ['docker', 'exec', 'knowledge-neo4j', 'cypher-shell', '-u', 'neo4j', '-p', 'knowledge123', 
             'MATCH (d:Document) RETURN count(d) as doc_count'],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            if len(lines) >= 2:
                return int(lines[1])
    except:
        pass
    return 0

def monitor_bootstrap():
    """Monitor bootstrap progress"""
    target_docs = 428
    print(f"Monitoring bootstrap progress (target: {target_docs} documents)...")
    
    while True:
        doc_count = get_document_count()
        progress = (doc_count / target_docs) * 100
        print(f"\rDocuments loaded: {doc_count}/{target_docs} ({progress:.1f}%)", end='', flush=True)
        
        if doc_count >= target_docs:
            print("\n✅ Bootstrap complete!")
            break
            
        time.sleep(5)

if __name__ == "__main__":
    monitor_bootstrap()