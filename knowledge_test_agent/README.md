# Knowledge Test Agent

This folder contains the test suite for the Graph RAG knowledge system, filtered to only include test cases for publicly available documents.

## Contents

- `test.csv` - The filtered test set with 80 test questions (original had 90)
- `test_original.csv` - Backup of the original test set for reference
- `filter_summary.txt` - Summary of which test cases were removed and why

## Test Set Overview

The test set covers questions about financial products from publicly available PDFs, including:
- Foreign Exchange (FX) products
- Interest rate products
- Term deposits
- Various financial instruments

## Removed Test Cases

10 test cases were removed because they reference PDFs that could not be verified as publicly available:

1. **WBC Fixed Rate BBBL 0225.pdf** (6 questions removed)
   - What is a fixed rate bank bill business loan?
   - What is a FRR-BBBL?
   - What are the benefits of a FRR-BBBL to cover interest rate risk?
   - What are the break costs of a FRR-BBBL?
   - Customer onboarding question for FR BBBL
   - What is the minimum and maximum term for a FR-BBBL?

2. **WBC_Rebate_PIS_0225.pdf** (2 questions removed)
   - What are the risks of entering a RFR-BBBL?
   - What is a RFR-BBBL?

3. **WBC Forward Start Security Agreement 0824** (2 questions removed)
   - When is the customer required to enter into a Forward Start Security Agreement?
   - What is the purpose of a forward start security agreement?

## Using the Test Set

This filtered test set ensures all test questions reference only publicly available documents that have been verified and included in the `mvp_inventory.json`.

The test cases can be used to:
- Evaluate the accuracy of the Graph RAG system
- Benchmark different retrieval and answer generation approaches
- Validate that the system correctly retrieves information from the knowledge base

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