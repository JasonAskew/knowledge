#!/usr/bin/env python3
"""
Patch for knowledge_ingestion_agent.py to add hierarchical classification
This shows the changes needed to integrate hierarchy into ingestion
"""

# Add import at the top of the file
# from hierarchical_classifier import HierarchicalDocumentClassifier

# In the __init__ method of KnowledgeIngestionAgent class, add:
# self.hierarchical_classifier = HierarchicalDocumentClassifier()

# Replace the document creation section (around line 724) with:
"""
# Classify document into hierarchy
classification = self.hierarchical_classifier.classify_document(
    filename=document_metadata.get('filename', ''),
    content=document_text[:5000] if 'document_text' in locals() else '',  # First 5000 chars for classification
    metadata=document_metadata
)

# Now create the document node with hierarchy
session.run('''
    MERGE (d:Document {id: $doc_id})
    SET d.filename = $filename,
        d.path = $path,
        d.total_pages = $total_pages,
        d.processed_date = $processed_date,
        d.category = $category,
        d.institution = $institution,
        d.division = $division,
        d.division_code = $division_code,
        d.category_hierarchy = $category_hierarchy,
        d.product_scope = $product_scope,
        d.hierarchy_confidence = $hierarchy_confidence
    
    // Create relationships to hierarchy nodes
    WITH d
    MATCH (div:Division {code: $division_code})
    MERGE (d)-[:BELONGS_TO_DIVISION]->(div)
    
    WITH d
    MATCH (cat:Category {name: $category_hierarchy, division: $division_code})
    MERGE (d)-[:COVERS_CATEGORY]->(cat)
    
    // Link to relevant products
    WITH d
    UNWIND $product_scope as product_name
    MATCH (p:Product {name: product_name, category: $category_hierarchy})
    MERGE (d)-[:COVERS_PRODUCT]->(p)
''', 
doc_id=doc_id,
filename=document_metadata.get('filename'),
path=document_metadata.get('path'),
total_pages=document_metadata.get('total_pages'),
processed_date=datetime.now().isoformat(),
category=document_metadata.get('category', 'misc'),
institution=classification.institution,
division=classification.division,
division_code=classification.division_code,
category_hierarchy=classification.category,
product_scope=classification.products,
hierarchy_confidence=classification.confidence)
"""

# Also update chunks to inherit hierarchy from document (in chunk creation around line 744):
"""
session.run('''
    CREATE (c:Chunk {
        id: $chunk_id,
        text: $text,
        page_num: $page_num,
        chunk_index: $chunk_index,
        token_count: $token_count,
        embedding: $embedding,
        semantic_density: $semantic_density,
        has_definitions: $has_definitions,
        has_examples: $has_examples,
        chunk_type: $chunk_type,
        keywords: $keywords,
        division: $division,
        category_hierarchy: $category_hierarchy
    })
    WITH c
    MATCH (d:Document {id: $doc_id})
    CREATE (d)-[:HAS_CHUNK]->(c)
''',
chunk_id=chunk.metadata.chunk_id,
text=chunk.text,
page_num=chunk.metadata.page_num,
chunk_index=chunk.metadata.chunk_index,
token_count=chunk.metadata.token_count,
embedding=chunk.embedding.tolist() if chunk.embedding is not None else None,
semantic_density=chunk.semantic_density,
has_definitions=chunk.has_definitions,
has_examples=chunk.has_examples,
chunk_type=chunk.chunk_type,
keywords=chunk.keywords,
doc_id=doc_id,
division=classification.division,
category_hierarchy=classification.category)
"""