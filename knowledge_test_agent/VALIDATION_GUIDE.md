# Test Data Validation Guide

## Overview

The enhanced test runner now includes a comprehensive validation feature that verifies test data quality before running accuracy tests. This helps identify issues where expected answers cannot be found in the specified documents, preventing false failures and improving test reliability.

## Why Validation Matters

Test data validation helps catch:
- **Incorrect expected answers**: Answers that don't match actual document content
- **Wrong document references**: Documents that don't contain the expected information
- **Page number mismatches**: Content exists but on different pages
- **Missing documents**: Referenced documents that aren't in the system
- **Content extraction issues**: Problems with how documents were processed

## How Validation Works

The validation process:

1. **Loads test cases** from the CSV file
2. **For each test case**:
   - Searches for the expected document
   - Checks if the expected answer can be found
   - Uses multiple matching techniques:
     - Semantic similarity (using sentence transformers)
     - Keyword matching (especially for numbers and key terms)
     - Fuzzy string matching (for partial matches)
3. **Categorizes results**:
   - **VALID**: Answer found in expected document/page
   - **INVALID**: Answer not found or document missing
   - **WARNING**: Partial match or page mismatch
   - **ERROR**: Technical issues during validation
4. **Generates reports** with detailed findings and recommendations

## Usage Examples

### 1. Run Validation Only

To validate test data without running tests:

```bash
python enhanced_test_runner.py --validation-only
```

### 2. Run Tests with Validation (Default)

By default, validation runs before tests:

```bash
python enhanced_test_runner.py --search-type vector --use-reranking
```

### 3. Skip Validation

To run tests without validation:

```bash
python enhanced_test_runner.py --no-validation
```

### 4. Stop on Invalid Tests

To stop execution if invalid tests are found:

```bash
python enhanced_test_runner.py --stop-on-invalid
```

### 5. Validate with Different Search Types

```bash
# Validate using hybrid search
python enhanced_test_runner.py --validation-only --search-type hybrid

# Validate with reranking
python enhanced_test_runner.py --validation-only --use-reranking
```

## Understanding Validation Results

### Console Output

During validation, you'll see:

```
============================================================
PHASE 1: Validating test data before running tests...
============================================================

Validating test 1/100...
  Question: What is the minimum deposit for a savings account...
  Expected doc: savings-account-guide.pdf
  Expected page: 5

[... validation progress ...]

============================================================
VALIDATION COMPLETE
  Valid tests: 85/100
  Invalid tests: 10
  Warnings: 5
============================================================
```

### Validation Report

The validation report (`validation_report_YYYYMMDD_HHMMSS.md`) includes:

1. **Summary Statistics**
   - Total tests validated
   - Valid/Invalid/Warning counts
   - Validation time

2. **Invalid Tests Details**
   - Test ID and question
   - Expected document
   - Specific issues found
   - Suggested fixes

3. **Document Analysis**
   - Documents with multiple failures
   - Patterns in validation issues

4. **Recommendations**
   - Specific actions to improve test data
   - Document re-ingestion suggestions

### JSON Results

Detailed results are saved in JSON format for programmatic analysis:

```json
{
  "summary": {
    "total_tests": 100,
    "valid_tests": 85,
    "invalid_tests": 10,
    "warnings": 5,
    "invalid_test_ids": [12, 34, 56, ...],
    "document_issues": {
      "problematic-doc.pdf": [12, 34],
      ...
    }
  },
  "validation_results": [
    {
      "test_id": 1,
      "status": "VALID",
      "found_in_doc": true,
      "answer_similarity": 0.89,
      ...
    }
  ]
}
```

## Validation Matching Techniques

### 1. Semantic Similarity
- Uses sentence transformers to compare meaning
- Threshold: 0.6 for valid, 0.3-0.6 for warning
- Good for conceptual matches

### 2. Keyword Matching
- Extracts numbers and important terms
- Weights numbers heavily (70% of score)
- Filters out common stop words

### 3. Fuzzy String Matching
- Uses sliding window comparison
- Helps find partial matches in long texts
- Direct substring matching for short answers

## Best Practices

1. **Always validate before important test runs**
   - Ensures test data quality
   - Saves time by identifying issues early

2. **Fix invalid tests before proceeding**
   - Invalid tests will likely fail
   - May skew accuracy metrics

3. **Review warnings carefully**
   - May indicate minor issues
   - Could still pass but with lower confidence

4. **Use validation to improve data**
   - Update test cases based on findings
   - Re-ingest problematic documents
   - Refine expected answers

5. **Run validation after system changes**
   - After document re-ingestion
   - After search algorithm updates
   - After embedding model changes

## Troubleshooting

### High Invalid Test Rate
If >20% tests are invalid:
- Review test creation process
- Check document ingestion completeness
- Verify document naming consistency

### Many Warnings
If >30% tests have warnings:
- Check page extraction accuracy
- Review answer formatting
- Consider content extraction quality

### Specific Document Issues
If one document has many failures:
- Re-ingest the document
- Check PDF quality/formatting
- Verify extraction worked correctly

### Performance Issues
If validation is slow:
- Reduce search top_k parameter
- Skip reranking for validation
- Process in batches

## Command Reference

| Option | Description | Default |
|--------|-------------|---------|
| `--validation-only` | Only run validation | False |
| `--no-validation` | Skip validation | False |
| `--stop-on-invalid` | Stop if invalid tests found | False |
| `--search-type` | Search method for validation | vector |
| `--use-reranking` | Enable reranking | False |
| `--test-file` | CSV file with test cases | test.csv |
| `--api-url` | API endpoint | http://localhost:8000 |

## Example Workflow

1. **Initial validation**:
   ```bash
   python enhanced_test_runner.py --validation-only
   ```

2. **Review validation report**:
   ```bash
   cat ../data/test_results/validation_report_*.md
   ```

3. **Fix invalid test cases** in CSV file

4. **Re-validate** to confirm fixes:
   ```bash
   python enhanced_test_runner.py --validation-only
   ```

5. **Run full test suite**:
   ```bash
   python enhanced_test_runner.py --use-reranking
   ```

## Integration with CI/CD

For automated testing:

```bash
# Validate and stop on issues
python enhanced_test_runner.py --stop-on-invalid

# Check exit code
if [ $? -eq 0 ]; then
    echo "All tests valid, proceeding with accuracy testing"
else
    echo "Invalid tests found, failing build"
    exit 1
fi
```

This validation feature ensures high-quality test data and more reliable accuracy measurements for your knowledge graph system.