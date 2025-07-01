# Neo4j Database Backups

This directory contains database exports for the Knowledge Graph system.

## Latest Backup (2025-07-01)

**Full Export Statistics:**
- Documents: 428
- Chunks: 12,709
- Entities: 62,636
- Relationships: 592,823
- Total Nodes: 75,773

**Available Files:**
- `neo4j_export_20250701_210856.json.gz` (66MB) - Compressed backup
- `neo4j_export_20250701_210856.json` (326MB) - Full uncompressed backup (Git LFS)

## Usage

### Using Compressed Backup
```bash
# Decompress the backup
gunzip -k neo4j_export_20250701_210856.json.gz

# Bootstrap from backup
python scripts/bootstrap_neo4j.py --force --file data/backups/neo4j_export_20250701_210856.json
```

### Using Make Commands
```bash
# Start system with bootstrap from latest backup
make up-bootstrap

# Or just import into existing system
make import
```

## Backup Contents

The backup includes:
- All document content and metadata
- Vector embeddings (384-dimensional from BAAI/bge-small-en-v1.5)
- Entity relationships and graph structure
- Enhanced chunk metadata (semantic density, chunk types, etc.)

## Creating New Backups

```bash
# Export current database
make export

# Or run directly
NEO4J_PASSWORD=knowledge123 python scripts/export_neo4j.py
```

## Notes

- Backups are in JSON format for portability
- Large backups are tracked with Git LFS
- Compressed versions (.gz) are provided for faster downloads
- The backup preserves all vector embeddings and relationships