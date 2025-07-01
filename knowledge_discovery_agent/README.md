# Knowledge Discovery Agent

## Overview
Autonomous agent for discovering and downloading publicly available PDF documents from various sources. This agent ensures all documents in the knowledge system are publicly accessible and properly categorized.

## Core Components

### Main Discovery Agent
- `knowledge_discovery_agent.py` - Original autonomous discovery agent
- `knowledge_discovery_agent_v2.py` - Enhanced agent with S3 sync capabilities
- Supports multiple sources and institutions
- Automatic categorization and priority-based downloading
- AWS S3 sync integration for cloud storage

### Utilities
- `audit_pdf_collection.py` - Audits collection and identifies missing files
- `limited_pdf_agent.py` - Limited scope agent for specific discovery tasks
- `sync_to_s3.py` - Simple script to sync PDFs to AWS S3

### Inventories (JSON files)
- `downloaded_pdfs_inventory_verified.json` - Master inventory of verified publicly available PDFs
- `orphaned_pdfs_inventory.json` - PDFs that need URL discovery/verification
- `inventory_status.json` - Current collection status

## Directory Structure
```
knowledge_discovery_agent/
├── westpac_pdfs/          # Verified publicly available PDFs (429 files)
│   ├── product-disclosure/
│   ├── annual-reports/
│   ├── sustainability/
│   ├── policies/
│   ├── legal-terms/
│   ├── banking-products/
│   ├── fees-charges/
│   ├── forms/
│   ├── brochures/
│   ├── investor-centre/
│   └── misc/
├── orphaned_pdfs/         # PDFs pending URL discovery
│   └── misc/
└── archive/               # Historical agent versions
```

## Categories

### High Priority
1. **product-disclosure** - Product Disclosure Statements (PDS), Product Information Statements (PIS)
2. **annual-reports** - Annual reports and financial statements
3. **sustainability** - ESG, climate, and sustainability reports
4. **policies** - Corporate policies and governance documents
5. **legal-terms** - Terms and conditions, agreements

### Medium Priority
6. **investor-centre** - Investor relations documents
7. **research** - Research papers and analysis
8. **banking-products** - Product guides and information (non-PDS)

### Low Priority
9. **fees-charges** - Fee schedules and pricing information
10. **forms** - Application forms and checklists
11. **brochures** - Marketing brochures and guides
12. **misc** - Uncategorized documents

## Running the Agent

### Basic Discovery
```bash
python knowledge_discovery_agent.py
```

### Enhanced Agent with S3 Sync
```bash
# Run discovery and sync to S3
python knowledge_discovery_agent_v2.py

# Sync MVP inventory to S3
python knowledge_discovery_agent_v2.py --sync-inventory mvp_inventory.json

# Sync all verified PDFs to S3
python knowledge_discovery_agent_v2.py --sync-inventory downloaded_pdfs_inventory_verified.json

# Dry run mode (no actual uploads)
python knowledge_discovery_agent_v2.py --dry-run --sync-inventory mvp_inventory.json
```

### Simple S3 Sync
```bash
# Sync MVP PDFs to S3
python sync_to_s3.py --mvp

# Sync all verified PDFs to S3
python sync_to_s3.py --all

# Dry run mode
python sync_to_s3.py --mvp --dry-run

# Use different bucket
python sync_to_s3.py --mvp --bucket my-other-bucket
```

### Audit Collection
```bash
python audit_pdf_collection.py
```

### Limited Discovery (with constraints)
```bash
python limited_pdf_agent.py
```

## Configuration

### Download Limits
```python
limits = DownloadLimits(
    max_files_per_sync=100,     # Maximum files per run
    max_file_size_mb=50,        # Skip large files
    priority_categories=[...]    # Categories to prioritize
)
```

### Adding New Sources

To add new document sources, update the discovery methods in `knowledge_discovery_agent.py`:

1. Add a new discovery method (e.g., `_discover_new_source_pdfs()`)
2. Implement URL patterns or web crawling logic
3. Call the method from `discover_all_pdfs()`

## Features

- **Autonomous Discovery**: Automatically finds publicly available PDFs
- **Smart Categorization**: Categorizes documents based on content patterns
- **Priority-Based Downloads**: Downloads high-priority documents first
- **Duplicate Detection**: Skips already downloaded files
- **Concurrent Downloads**: Efficient parallel downloading
- **Rate Limiting**: Respects server rate limits
- **Inventory Management**: Maintains JSON inventory of all documents
- **Checksum Verification**: MD5 checksums for integrity

## Public Availability Verification

All documents in this system are verified to be publicly available through:
1. Direct discovery from public websites
2. No authentication required for access
3. Standard web crawling and URL patterns
4. Public document repositories only

## Requirements

See `requirements.txt` for Python dependencies:
- requests
- beautifulsoup4
- python-dateutil
- urllib3

## AWS S3 Integration

The enhanced agent includes built-in S3 sync capabilities:

### Prerequisites
- AWS CLI installed and configured (`aws configure`)
- S3 bucket created and accessible
- Appropriate IAM permissions for S3 operations

### S3 Features
- **Automatic sync** after discovery and download
- **Inventory-based sync** for specific file sets (MVP, all verified)
- **Dry run mode** to preview operations
- **Organized structure** in S3 (preserves categories)
- **Error handling** and retry logic
- **Progress tracking** and detailed logging

### S3 Bucket Structure
```
s3://your-bucket-name/
└── verified-pdfs/
    ├── product-disclosure/
    ├── annual-reports/
    ├── legal-terms/
    └── misc/
```

## Notes

- The agent only downloads publicly available documents
- Respects robots.txt and rate limiting
- Maintains detailed logs of all discovery activities
- Supports resumable downloads and incremental updates
- S3 sync maintains the same category structure as local storage
- All S3 operations are logged for audit purposes