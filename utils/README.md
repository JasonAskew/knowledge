# Utilities Directory

This directory contains specialized components extracted from the prototype systems that may be useful for future enhancements.

## Files

### financial_table_extractor.py
- Extracts structured financial data from PDF tables
- Handles TCE (Thermal Coal Equivalent) data, emissions data, sector breakdowns
- Useful for processing annual reports and financial documents

### robust_pdf_extractor.py
- Advanced PDF extraction with multiple fallback methods
- Handles problematic PDFs with timeout protection
- Better error handling than basic extractors

### enhanced_graphrag_query.py
- Advanced query system from the WIB prototype
- Features vector similarity, multi-path retrieval, and confidence scoring
- More sophisticated than the basic search implementation

## Usage

These utilities are not currently integrated into the main system but are preserved here for potential future use. They represent specialized capabilities that were developed in the prototypes and may be valuable for:

1. Processing financial reports with complex tables
2. Handling problematic PDFs that fail with standard extraction
3. Implementing more advanced query capabilities with confidence scoring

To integrate any of these utilities, review their requirements and adapt them to work with the current architecture in the knowledge_ingestion_agent.