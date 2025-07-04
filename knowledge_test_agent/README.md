# Knowledge Test Agent

Comprehensive testing framework for evaluating the accuracy and performance of the optimized GraphRAG knowledge system with multiple search methods, performance benchmarking, and speed vs accuracy analysis.

## Contents

### Core Testing Tools
- `enhanced_test_runner.py` - Main test runner with performance grading and target validation
- `optimized_search_tester.py` - Specialized tester for current optimized search methods
- `performance_benchmarker.py` - Speed vs accuracy analysis and optimization recommendations

### Test Data
- `test.csv` - Full test set with 80+ comprehensive questions
- `test_small.csv` - Quick validation subset
- Test results automatically saved to `/data/test_results/`

## Current System Performance (2024)

The testing framework now validates against measured system performance benchmarks:

### 🎯 Performance Targets by Search Method

| Search Method | Accuracy Target | Speed Target | Use Case |
|---------------|----------------|--------------|----------|
| **Optimized Keyword** | 90% | 200ms | Real-time queries, fast response |
| **Vector Search** | 78% | 500ms | Semantic similarity, balanced |
| **Hybrid Search** | 73% | 1000ms | Comprehensive search, best coverage |
| **Graph Search** | 82% | 800ms | Entity-based, domain-specific |
| **GraphRAG** | 80% | 1500ms | Complex reasoning, highest accuracy |
| **Full Text** | 75% | 300ms | Traditional keyword matching |

### 🏆 Performance Grading System

- **A+**: Exceeds targets (>target accuracy, <80% target time)
- **A**: Meets targets (≥target accuracy, ≤target time)  
- **B**: Partial targets (meets accuracy OR speed)
- **C**: Below targets but functional
- **F**: Failing performance

## Running Tests

### 🚀 Quick Performance Testing

```bash
# Enhanced test runner with performance grading (RECOMMENDED)
python enhanced_test_runner.py --search-type hybrid --use-reranking

# Test optimized search methods with benchmarks
python optimized_search_tester.py --methods hybrid vector optimized_keyword

# Full performance analysis (speed vs accuracy)
python performance_benchmarker.py --methods hybrid vector graph
```

### 📊 Comprehensive Testing Options

```bash
# Test specific search method with performance validation
python enhanced_test_runner.py --search-type vector --use-reranking

# Optimized keyword search (fastest)
python enhanced_test_runner.py --search-type optimized_keyword

# Graph-based search (high accuracy)
python enhanced_test_runner.py --search-type graph --use-reranking

# Validation only (check test data quality)
python enhanced_test_runner.py --validation-only

# Custom test file with performance grading
python enhanced_test_runner.py --test-file test_small.csv --search-type hybrid
```

### ⚡ Performance Benchmarking

```bash
# Speed vs accuracy analysis
python performance_benchmarker.py

# Test specific methods with detailed profiling
python optimized_search_tester.py --methods hybrid vector --iterations 5

# Generate performance report
python performance_benchmarker.py --report performance_report.md
```

## Test Features

### 🎯 Performance Validation
- **Performance Grading**: A+ to F grades based on accuracy and speed targets
- **Target Validation**: Automatic comparison against expected performance benchmarks
- **Speed Analysis**: Fast queries (<500ms), slow queries (>2s) tracking
- **Optimization Recommendations**: Actionable insights for performance improvement

### 📊 Enhanced Metrics
- **Primary Metric**: Document/Citation accuracy (finding correct sources)
- **Secondary Metrics**: Semantic similarity, response time, query complexity
- **Performance Tracking**: P50, P95, P99 response times
- **Efficiency Scoring**: Accuracy per second calculations

### 🔍 Search Method Analysis
- **Current Methods**: Optimized keyword, vector, hybrid, graph, graphrag, full text
- **Reranking Impact**: Cross-encoder performance analysis
- **Query Complexity**: Simple, moderate, complex query categorization
- **Use Case Optimization**: Real-time, balanced, high-accuracy scenarios

### 📈 Advanced Reporting
- **Performance Reports**: Detailed markdown reports with optimization recommendations
- **Trend Analysis**: Performance tracking over time
- **Comparative Analysis**: Side-by-side method comparison
- **Speed vs Accuracy Trade-offs**: Data-driven optimization insights

### 🛠️ Test Data Quality
- **Mandatory Validation**: All test runs include data quality validation
- **Document Normalization**: Smart PDF extension handling and case-insensitive matching
- **Citation Verification**: Ensures expected answers exist in specified documents
- **Test Case Health**: Identifies invalid tests that need correction

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

### 🔧 System Configuration

```bash
# Environment variables
API_BASE_URL=http://localhost:8000          # Knowledge API endpoint
NEO4J_PASSWORD=knowledge123                 # Neo4j database password
MCP_SERVER_PORT=8001                        # MCP server port (if used)

# Performance testing parameters
--search-type hybrid                        # Default: hybrid (recommended)
--use-reranking                            # Default: enabled
--timeout 30                               # Request timeout (seconds)
--iterations 3                            # Benchmark iterations
```

### ⚙️ Performance Targets Configuration

Current targets are based on measured system performance:

```python
PERFORMANCE_BENCHMARKS = {
    "optimized_keyword": {"accuracy": 0.90, "speed_ms": 200},
    "vector": {"accuracy": 0.78, "speed_ms": 500},
    "hybrid": {"accuracy": 0.73, "speed_ms": 1000},
    "graph": {"accuracy": 0.82, "speed_ms": 800},
    "graphrag": {"accuracy": 0.80, "speed_ms": 1500},
    "full_text": {"accuracy": 0.75, "speed_ms": 300}
}
```

### 📁 Output Configuration

```bash
# Results saved to organized directories
data/test_results/
├── test_report_YYYYMMDD_HHMMSS.md          # Main test report
├── test_report_YYYYMMDD_HHMMSS.csv         # Detailed results
├── validation_report_YYYYMMDD_HHMMSS.md    # Data quality report
├── performance_analysis_YYYYMMDD_HHMMSS.json # Benchmark data
└── optimized_search_test_YYYYMMDD_HHMMSS.json # Search method tests
```