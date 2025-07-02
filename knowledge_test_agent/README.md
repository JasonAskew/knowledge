# Knowledge Test Agent

Automated testing framework for evaluating the accuracy and performance of the GraphRAG knowledge system with multiple search methods and reranking capabilities.

## Contents

- `enhanced_test_runner.py` - Main test runner with multiple search methods
- `test_cases.csv` - MVP test set with 26 questions
- `test.csv` - Full test set with 80 questions
- `mvp_test_cases.csv` - Subset for quick testing
- Test results saved to `/data/test_results/`

## Test Set Overview

The test framework evaluates different search methods:
- **Vector Search**: Semantic similarity using embeddings
- **Graph Search**: Entity-based graph traversal
- **Hybrid Search**: Weighted combination of methods
- **Text2Cypher**: Natural language to graph queries
- **Cross-encoder Reranking**: BERT-based result reranking

Current accuracy (MVP test set):
- Vector + Reranking: 73.8%
- Hybrid + Reranking: 69.2%
- Text2Cypher: 66.2%

## Running Tests

```bash
# Run with vector search and reranking
python enhanced_test_runner.py --search-type vector --rerank

# Run with hybrid search
python enhanced_test_runner.py --search-type hybrid --rerank

# Run text2cypher tests
python enhanced_test_runner.py --search-type text2cypher

# Test all search methods
python enhanced_test_runner.py --all

# Specify custom test file
python enhanced_test_runner.py --test-file mvp_test_cases.csv --search-type hybrid
```

## Test Features

### Document Name Normalization
- Automatically strips .pdf extensions for comparison
- Handles case-insensitive matching
- Resolves 86.2% validation issue from extension mismatches

### Evaluation Metrics
- **Valid Tests**: Document exists in knowledge base
- **Invalid Tests**: Referenced document not found
- **Accurate Results**: Correct document retrieved
- **Partial Match**: Some relevant content found
- **Query Time**: Average response time per query

### Result Output
- CSV report with detailed results
- Markdown summary with statistics
- Per-question accuracy tracking
- Failed test analysis

## Test Format

The CSV file contains the following columns:
- `#` - Test case number
- `FM Business` - Business category (BCG/ICG/Both)
- `Document Type` - Type of document (PDS, etc.)
- `Document Name` - PDF filename containing the answer
- `Brand` - Financial institution (Westpac/SGB/BOM/BSA)
- `Product Category` - Product category (FX, etc.)
- `Product` - Specific product name
- `Question` - The test question
- `Acceptable answer` - Expected answer or key points
- `Document Reference` - Additional reference information

## Configuration

```bash
# Environment variables
API_BASE_URL=http://localhost:8000
NEO4J_PASSWORD=knowledge123

# Test parameters
--top-k 5        # Number of results to retrieve
--workers 4      # Parallel test execution
--debug          # Enable debug logging
```