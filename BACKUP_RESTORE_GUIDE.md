# Backup and Restore Guide

## Current Backup Status

A complete backup has been created on **2025-07-03 at 15:43** containing:
- **423 documents** (98.4% of expected 430)
- **12,808 chunks** 
- **74,766 total nodes**
- **172,499 relationships**
- **62.5 MB compressed** (75% compression ratio)

## Backup Location

```
data/backups/neo4j_export_20250703_154308.json.gz
data/backups/neo4j_export_latest.json.gz (symlink to latest)
```

## How to Create a New Backup

```bash
# Using the Makefile
make export

# Or directly with Python
python export_database_now.py
```

This will:
1. Export all nodes and relationships to JSON
2. Compress with gzip (~75% reduction)
3. Save with timestamp in `data/backups/`
4. Update the `neo4j_export_latest.json.gz` symlink

## How to Restore from Backup

### Option 1: Using the restore script (Recommended)
```bash
# Restore from latest backup
python restore_from_backup.py

# Or restore from a specific backup (will list options)
python restore_from_backup.py 2
```

### Option 2: Using Makefile
```bash
# This uses the latest backup
make import
make fix-relationships
```

### Option 3: Manual restore
```bash
# 1. Stop Neo4j if running
docker-compose down

# 2. Start fresh Neo4j
docker-compose up -d neo4j

# 3. Import the backup
python scripts/bootstrap_neo4j.py

# 4. Fix relationships
python scripts/fix_chunk_relationships.py
```

## Important Notes

1. **Restore is destructive** - it will DELETE all current data
2. Always run `fix_chunk_relationships.py` after restore
3. The backup includes vector embeddings (384-dim)
4. Compressed backups save ~75% space

## Backup Contents

The backup includes:
- All Document nodes with metadata
- All Chunk nodes with embeddings
- All Entity nodes and relationships
- CONTAINS_ENTITY relationships with confidence scores
- RELATED_TO relationships with strength values
- HAS_CHUNK relationships

## Verification After Restore

```bash
# Check document count
docker exec knowledge-neo4j cypher-shell -u neo4j -p knowledge123 \
  "MATCH (d:Document) RETURN count(d)"

# Should return: 423

# Check total nodes
docker exec knowledge-neo4j cypher-shell -u neo4j -p knowledge123 \
  "MATCH (n) RETURN count(n)"

# Should return: 74,766
```