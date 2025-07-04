#!/usr/bin/env python3
"""
Test hierarchical classification integration
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from knowledge_ingestion_agent.hierarchical_classifier import HierarchicalDocumentClassifier
import json

def test_classifier():
    """Test the hierarchical classifier with sample documents"""
    
    classifier = HierarchicalDocumentClassifier()
    
    # Test cases
    test_documents = [
        {
            'filename': 'Personal_Savings_Account_Terms.pdf',
            'content': 'This document outlines the terms and conditions for personal savings accounts...',
            'metadata': {'category': 'accounts'}
        },
        {
            'filename': 'Business_Loan_Application_Guide.pdf',
            'content': 'Guide for applying for business loans and commercial finance...',
            'metadata': {'category': 'lending'}
        },
        {
            'filename': 'FX_Forward_Contract_PDS.pdf',
            'content': 'Foreign exchange forward contracts for institutional clients...',
            'metadata': {'category': 'markets'}
        },
        {
            'filename': 'Credit_Card_Rewards_Program.pdf',
            'content': 'Details about credit card rewards and benefits for retail customers...',
            'metadata': {}
        }
    ]
    
    print("Testing Hierarchical Document Classifier\n")
    print("=" * 80)
    
    for doc in test_documents:
        print(f"\nDocument: {doc['filename']}")
        print("-" * 40)
        
        classification = classifier.classify_document(
            filename=doc['filename'],
            content=doc['content'],
            metadata=doc['metadata']
        )
        
        print(f"Institution: {classification.institution}")
        print(f"Division: {classification.division} ({classification.division_code})")
        print(f"Category: {classification.category}")
        print(f"Products: {', '.join(classification.products) if classification.products else 'None'}")
        print(f"Confidence: {classification.confidence:.2f}")
    
    print("\n" + "=" * 80)
    print("Classification test completed!")

def test_ingestion_integration():
    """Test that ingestion properly uses hierarchical classification"""
    
    print("\n\nTesting Ingestion Integration")
    print("=" * 80)
    
    # Check if the ingestion agent has the classifier
    from knowledge_ingestion_agent.knowledge_ingestion_agent import KnowledgeIngestionAgent
    
    agent = KnowledgeIngestionAgent()
    
    if hasattr(agent, 'hierarchical_classifier'):
        print("✓ Hierarchical classifier is integrated into ingestion agent")
        print(f"  Classifier type: {type(agent.hierarchical_classifier).__name__}")
    else:
        print("✗ Hierarchical classifier not found in ingestion agent")
        return
    
    # Test classification on a sample
    test_classification = agent.hierarchical_classifier.classify_document(
        filename="test_document.pdf",
        content="Test content for retail banking savings account",
        metadata={}
    )
    
    print(f"\nTest classification result:")
    print(f"  Division: {test_classification.division}")
    print(f"  Category: {test_classification.category}")
    print(f"  Confidence: {test_classification.confidence}")
    
    print("\nIntegration test completed!")

if __name__ == "__main__":
    test_classifier()
    test_ingestion_integration()