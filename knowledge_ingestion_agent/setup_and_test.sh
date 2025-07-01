#!/bin/bash

echo "Knowledge Ingestion Agent - Setup and Test"
echo "=========================================="

# Check Python version
echo "Checking Python version..."
python3 --version

# Create virtual environment
echo ""
echo "Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Download spaCy model
echo ""
echo "Downloading spaCy model..."
python -m spacy download en_core_web_sm

# Check Neo4j connection
echo ""
echo "Checking Neo4j connection..."
python -c "
from neo4j import GraphDatabase
import sys

try:
    driver = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', 'password'))
    driver.verify_connectivity()
    print('✅ Neo4j connection successful')
    driver.close()
except Exception as e:
    print(f'❌ Neo4j connection failed: {e}')
    print('Please ensure Neo4j is running and update the password in the script')
    sys.exit(1)
"

# Run a test ingestion with a small inventory
echo ""
echo "Running test ingestion..."
cat > test_inventory.json << EOF
{
  "download_summary": {
    "total_files": 2,
    "description": "Test inventory for ingestion"
  },
  "files": [
    {
      "filename": "WBC-FXSwapPDS.pdf",
      "url": "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/WBC-FXSwapPDS.pdf",
      "local_path": "../knowledge_discovery_agent/westpac_pdfs/product-disclosure/WBC-FXSwapPDS.pdf",
      "category": "product-disclosure",
      "size": 87529
    },
    {
      "filename": "WBC-ForeignExchangeOptionPDS.pdf",
      "url": "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/WBC-ForeignExchangeOptionPDS.pdf",
      "local_path": "../knowledge_discovery_agent/westpac_pdfs/product-disclosure/WBC-ForeignExchangeOptionPDS.pdf",
      "category": "product-disclosure",
      "size": 204283
    }
  ]
}
EOF

echo ""
echo "Starting ingestion of test documents..."
python knowledge_ingestion_agent.py --inventory test_inventory.json --optimize

# Test search
echo ""
echo "Testing search capabilities..."
echo ""
echo "1. Testing vector search..."
python search_engine.py --query "What is an FX Swap?" --type vector --top-k 3

echo ""
echo "2. Testing graph search..."
python search_engine.py --query "Foreign Exchange" --type graph --top-k 3

echo ""
echo "3. Testing hybrid search..."
python search_engine.py --query "Can I reduce my option premium?" --type hybrid --top-k 3

echo ""
echo "=========================================="
echo "Setup and test complete!"
echo ""
echo "To process the full MVP inventory, run:"
echo "python knowledge_ingestion_agent.py --inventory ../knowledge_discovery_agent/mvp_inventory.json --optimize"
echo ""
echo "To search the knowledge graph:"
echo "python search_engine.py --query 'your question here' --type hybrid"