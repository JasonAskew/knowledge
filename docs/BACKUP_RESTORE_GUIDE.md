# Neo4j Knowledge Graph Backup & Restore Guide

This guide explains how to use the export/import system for the Neo4j knowledge graph.

## Overview

The backup system provides:
- Full export of Neo4j database to JSON format
- Preservation of all nodes, relationships, and properties
- Support for vector embeddings and metadata
- Easy restore/bootstrap functionality
- Optional bootstrap on system startup

## Quick Start

### Export Current Database

```bash
# Export the current database
make export

# List available backups
make list-backups
```

### Import/Restore Database

```bash
# Import from latest backup (prompts if database has data)
make import

# Force import (overwrites existing data)
make bootstrap

# Start system with bootstrap enabled
make up-bootstrap
```

## Detailed Usage

### Export Commands

The export functionality creates a complete snapshot of your Neo4j database:

```bash
# Using Makefile
make export

# Using script directly
./scripts/neo4j_backup.sh export

# Inside Docker container
docker-compose exec neo4j python3 /scripts/export_neo4j.py
```

Export files are saved to `./data/backups/` with timestamp-based naming:
- `neo4j_export_20250701_123456.json` - Timestamped export
- `latest_export.json` - Symlink to most recent export

### Import Commands

Import/restore a previously exported database:

```bash
# Import from latest backup
make import

# Import from specific file
./scripts/neo4j_backup.sh import --file ./data/backups/neo4j_export_20250701_123456.json

# Force import (overwrites existing data)
./scripts/neo4j_backup.sh import --force
```

### Bootstrap on Startup

You can configure the system to automatically bootstrap from a backup on startup:

```bash
# Start with bootstrap from latest backup
make up-bootstrap

# Start with forced bootstrap (overwrites existing data)
make up-bootstrap-force

# Using environment variables
NEO4J_BOOTSTRAP=true docker-compose up
```

### Environment Variables

Configure bootstrap behavior using environment variables:

```bash
# Enable bootstrap on startup
NEO4J_BOOTSTRAP=true

# Specify bootstrap file (default: /data/backups/latest_export.json)
NEO4J_BOOTSTRAP_FILE=/data/backups/specific_export.json

# Force bootstrap even if database has data
NEO4J_BOOTSTRAP_FORCE=true
```

## Backup Management

### List Backups

```bash
make list-backups
```

### Clean Old Backups

Keep only the 5 most recent backups:

```bash
make clean-backups
```

## Export File Format

The export creates a JSON file with the following structure:

```json
{
  "metadata": {
    "export_timestamp": "2025-07-01T12:34:56",
    "version": "1.0",
    "neo4j_uri": "bolt://neo4j:7687"
  },
  "nodes": [
    {
      "id": 123,
      "labels": ["Document"],
      "properties": {
        "title": "Sample Document",
        "embedding": {
          "_type": "vector",
          "values": [...],
          "dimension": 1536
        }
      }
    }
  ],
  "relationships": [
    {
      "id": 456,
      "type": "CONTAINS",
      "start_node_id": 123,
      "end_node_id": 789,
      "properties": {}
    }
  ],
  "statistics": {
    "total_nodes": 1000,
    "total_relationships": 5000,
    "node_count_by_label": [...],
    "relationship_count_by_type": [...]
  }
}
```

## Best Practices

1. **Regular Backups**: Schedule regular exports to prevent data loss
   ```bash
   # Add to crontab
   0 2 * * * cd /path/to/project && make export
   ```

2. **Before Major Changes**: Always export before:
   - System upgrades
   - Large-scale ingestion
   - Schema changes

3. **Verify Imports**: After importing, verify the data:
   ```bash
   make stats
   make health
   ```

4. **Storage Management**: Regularly clean old backups:
   ```bash
   make clean-backups
   ```

## Troubleshooting

### Export Fails

If export fails:
1. Check Neo4j is running: `make health`
2. Check disk space: `df -h ./data/backups`
3. Check logs: `make neo4j-logs`

### Import Fails

If import fails:
1. Verify export file exists: `make list-backups`
2. Check if database has data: Use `--force` flag
3. Check Neo4j memory settings in docker-compose.yml

### Bootstrap on Startup Issues

If bootstrap fails on startup:
1. Check logs: `docker-compose logs neo4j | grep -i bootstrap`
2. Verify backup file exists: `ls -la ./data/backups/latest_export.json`
3. Try manual import: `make import`

## Integration with CI/CD

### Backup Before Deployment

```yaml
# Example GitHub Actions
- name: Backup Database
  run: |
    make export
    # Upload to S3 or artifact storage
```

### Restore in Test Environment

```yaml
# Example for test environment
- name: Bootstrap Test Database
  run: |
    # Download backup from S3
    NEO4J_BOOTSTRAP=true make up
```

## Security Considerations

1. **Sensitive Data**: Export files contain all database content
   - Store backups securely
   - Encrypt backups for long-term storage
   - Control access to backup directory

2. **Production Use**:
   - Change default Neo4j password
   - Use environment-specific credentials
   - Implement backup rotation policy

## Performance Notes

- Export time depends on database size
- Import is typically faster than full ingestion
- Large databases may require increased memory settings
- Vector embeddings significantly increase file size

## Monitoring

Monitor backup operations:

```bash
# Check backup size trends
du -sh ./data/backups/* | sort -h

# Monitor export duration
time make export

# Verify backup integrity
python3 -m json.tool ./data/backups/latest_export.json > /dev/null
```