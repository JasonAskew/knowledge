# Document Ingestion Enhancement Recommendation

## Current State
- Documents in Neo4j are stored without file extensions (e.g., "WBC-ForeignExchangeOptionPDS")
- Test data includes file extensions (e.g., "WBC-ForeignExchangeOptionPDS.pdf")
- This mismatch causes validation issues

## Recommended Enhancement
Update the ingestion process to preserve full filenames including extensions:

1. **In knowledge_ingestion_agent.py**, modify document creation:
   ```python
   # Instead of stripping extensions:
   document_id = os.path.basename(pdf_path)  # Keep full filename
   
   # Store both full filename and base name
   doc_node = Node(
       "Document",
       id=document_id,  # Full filename with extension
       filename=document_id,
       base_name=os.path.splitext(document_id)[0],  # Name without extension
       ...
   )
   ```

2. **Benefits**:
   - Exact match between test data and stored documents
   - Ability to distinguish between different file types
   - Better traceability to source files
   - Support for documents with same base name but different extensions

3. **Migration Strategy**:
   - Add a migration script to update existing documents
   - Or re-ingest all documents with the new naming convention

This would eliminate the need for normalization during validation while maintaining data consistency.
