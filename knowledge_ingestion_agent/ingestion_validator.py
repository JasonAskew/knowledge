#!/usr/bin/env python3
"""
Ingestion Validator and Error Handler
Ensures documents are completely ingested or rolled back
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from neo4j import GraphDatabase

logger = logging.getLogger(__name__)

class IngestionValidator:
    """Validates document ingestion completeness and handles errors"""
    
    def __init__(self, neo4j_driver):
        self.driver = neo4j_driver
        self.error_log_path = "data/ingestion_errors.json"
        self.validation_log_path = "data/ingestion_validation.json"
        
    def validate_document_completeness(self, document_id: str, pages_content: List[Dict], 
                                     chunks_created: List[Any]) -> Dict[str, Any]:
        """
        Validate that a document was completely ingested
        Returns validation result with any issues found
        """
        validation_result = {
            'document_id': document_id,
            'timestamp': datetime.now().isoformat(),
            'status': 'valid',
            'issues': [],
            'metrics': {}
        }
        
        # Check 1: All pages have content
        pages_with_content = sum(1 for p in pages_content if p.get('text', '').strip())
        total_pages = len(pages_content)
        
        if pages_with_content < total_pages:
            validation_result['issues'].append({
                'type': 'missing_page_content',
                'severity': 'warning',
                'details': f"{total_pages - pages_with_content} pages have no text content"
            })
        
        # Check 2: Reasonable chunk-to-page ratio
        chunk_ratio = len(chunks_created) / total_pages if total_pages > 0 else 0
        validation_result['metrics']['chunk_ratio'] = chunk_ratio
        
        if chunk_ratio < 0.2 and total_pages > 3:
            validation_result['issues'].append({
                'type': 'low_chunk_ratio',
                'severity': 'critical',
                'details': f"Only {len(chunks_created)} chunks for {total_pages} pages (ratio: {chunk_ratio:.2f})"
            })
            validation_result['status'] = 'incomplete'
        
        # Check 3: Chunks cover all pages
        pages_with_chunks = set(chunk.metadata.page_num for chunk in chunks_created)
        missing_pages = set(range(1, total_pages + 1)) - pages_with_chunks
        
        if missing_pages and len(missing_pages) > total_pages * 0.2:
            validation_result['issues'].append({
                'type': 'missing_page_coverage',
                'severity': 'high',
                'details': f"Pages without chunks: {sorted(missing_pages)}"
            })
            validation_result['status'] = 'incomplete'
        
        # Check 4: Minimum content threshold
        total_text_length = sum(len(chunk.text) for chunk in chunks_created)
        avg_chars_per_page = total_text_length / total_pages if total_pages > 0 else 0
        
        if avg_chars_per_page < 100 and total_pages > 1:
            validation_result['issues'].append({
                'type': 'insufficient_content',
                'severity': 'high',
                'details': f"Average {avg_chars_per_page:.0f} chars per page is too low"
            })
            validation_result['status'] = 'suspicious'
        
        validation_result['metrics'].update({
            'total_pages': total_pages,
            'pages_with_content': pages_with_content,
            'total_chunks': len(chunks_created),
            'pages_covered': len(pages_with_chunks),
            'total_text_length': total_text_length,
            'avg_chars_per_page': avg_chars_per_page
        })
        
        return validation_result
    
    def log_validation_result(self, validation_result: Dict[str, Any]):
        """Log validation results for monitoring"""
        try:
            # Load existing validations
            try:
                with open(self.validation_log_path, 'r') as f:
                    validations = json.load(f)
            except FileNotFoundError:
                validations = []
            
            # Add new validation
            validations.append(validation_result)
            
            # Keep last 1000 validations
            if len(validations) > 1000:
                validations = validations[-1000:]
            
            # Save
            with open(self.validation_log_path, 'w') as f:
                json.dump(validations, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to log validation result: {e}")
    
    def log_ingestion_error(self, document_id: str, error: Exception, 
                           metadata: Dict[str, Any], recovery_action: str = None):
        """Log ingestion errors for recovery"""
        error_entry = {
            'document_id': document_id,
            'timestamp': datetime.now().isoformat(),
            'error_type': type(error).__name__,
            'error_message': str(error),
            'metadata': metadata,
            'recovery_action': recovery_action,
            'resolved': False
        }
        
        try:
            # Load existing errors
            try:
                with open(self.error_log_path, 'r') as f:
                    errors = json.load(f)
            except FileNotFoundError:
                errors = []
            
            # Add new error
            errors.append(error_entry)
            
            # Save
            with open(self.error_log_path, 'w') as f:
                json.dump(errors, f, indent=2)
                
            logger.error(f"Logged ingestion error for {document_id}: {error}")
            
        except Exception as e:
            logger.error(f"Failed to log error: {e}")
    
    def rollback_incomplete_document(self, document_id: str):
        """Remove an incompletely ingested document from the graph"""
        try:
            with self.driver.session() as session:
                # Delete the document and all its relationships
                result = session.run("""
                    MATCH (d:Document {id: $doc_id})
                    OPTIONAL MATCH (d)-[:HAS_CHUNK]->(c:Chunk)
                    OPTIONAL MATCH (c)-[:CONTAINS_ENTITY]->(e:Entity)
                    DETACH DELETE d, c
                    RETURN count(d) as docs_deleted, count(c) as chunks_deleted
                """, doc_id=document_id)
                
                record = result.single()
                logger.info(f"Rolled back {document_id}: {record['docs_deleted']} docs, {record['chunks_deleted']} chunks deleted")
                return True
                
        except Exception as e:
            logger.error(f"Failed to rollback {document_id}: {e}")
            return False
    
    def get_unresolved_errors(self) -> List[Dict[str, Any]]:
        """Get list of unresolved ingestion errors"""
        try:
            with open(self.error_log_path, 'r') as f:
                errors = json.load(f)
            return [e for e in errors if not e.get('resolved', False)]
        except FileNotFoundError:
            return []
    
    def mark_error_resolved(self, document_id: str, resolution: str):
        """Mark an error as resolved"""
        try:
            with open(self.error_log_path, 'r') as f:
                errors = json.load(f)
            
            for error in errors:
                if error['document_id'] == document_id and not error.get('resolved'):
                    error['resolved'] = True
                    error['resolution'] = resolution
                    error['resolved_timestamp'] = datetime.now().isoformat()
            
            with open(self.error_log_path, 'w') as f:
                json.dump(errors, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to mark error resolved: {e}")
    
    def generate_recovery_report(self) -> Dict[str, Any]:
        """Generate a report of documents needing recovery"""
        unresolved_errors = self.get_unresolved_errors()
        
        # Group by error type
        error_groups = {}
        for error in unresolved_errors:
            error_type = error['error_type']
            if error_type not in error_groups:
                error_groups[error_type] = []
            error_groups[error_type].append(error)
        
        # Create recovery inventory
        recovery_inventory = {
            'generated_date': datetime.now().isoformat(),
            'total_errors': len(unresolved_errors),
            'error_summary': {error_type: len(errors) for error_type, errors in error_groups.items()},
            'documents_to_recover': []
        }
        
        for error in unresolved_errors:
            recovery_inventory['documents_to_recover'].append({
                'document_id': error['document_id'],
                'filename': error['metadata'].get('filename'),
                'path': error['metadata'].get('path'),
                'error_type': error['error_type'],
                'error_date': error['timestamp'],
                'suggested_action': error.get('recovery_action', 'reingest')
            })
        
        # Save report
        with open('data/recovery_inventory.json', 'w') as f:
            json.dump(recovery_inventory, f, indent=2)
        
        return recovery_inventory