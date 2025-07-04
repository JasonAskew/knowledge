#!/usr/bin/env python3
"""
Hierarchical Document Classifier
Classifies documents into the banking hierarchy during ingestion
"""

import re
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class HierarchicalClassification:
    """Document classification result"""
    institution: str = "Westpac Banking Corporation"
    division: str = "Retail Banking"
    division_code: str = "RETAIL"
    category: str = "General"
    products: List[str] = None
    confidence: float = 0.5
    
    def __post_init__(self):
        if self.products is None:
            self.products = []

class HierarchicalDocumentClassifier:
    """Classify documents into banking hierarchy"""
    
    def __init__(self):
        # Define classification patterns
        self.division_patterns = {
            'RETAIL': {
                'patterns': ['personal', 'retail', 'consumer', 'individual'],
                'exclude': ['business', 'corporate', 'institutional'],
                'name': 'Retail Banking'
            },
            'BUSINESS': {
                'patterns': ['business', 'commercial', 'corporate', 'sme', 'enterprise'],
                'exclude': ['personal', 'individual'],
                'name': 'Business Banking'
            },
            'INST': {
                'patterns': ['institutional', 'wholesale', 'markets', 'fx', 'treasury', 'trading'],
                'exclude': ['retail', 'personal'],
                'name': 'Institutional Banking'
            }
        }
        
        self.category_patterns = {
            'RETAIL': {
                'Accounts': {
                    'patterns': ['account', 'deposit', 'savings', 'checking', 'transaction'],
                    'products': ['Savings Account', 'Checking Account', 'Term Deposit', 'Youth Account']
                },
                'Cards': {
                    'patterns': ['card', 'credit', 'debit', 'mastercard', 'visa', 'payment card'],
                    'products': ['Credit Card', 'Debit Card', 'Prepaid Card']
                },
                'Loans': {
                    'patterns': ['loan', 'mortgage', 'lending', 'home loan', 'personal loan'],
                    'products': ['Home Loan', 'Personal Loan', 'Car Loan', 'Overdraft']
                },
                'Investments': {
                    'patterns': ['investment', 'wealth', 'portfolio', 'managed fund'],
                    'products': ['Managed Fund', 'Investment Account', 'Portfolio Service']
                }
            },
            'BUSINESS': {
                'Business Accounts': {
                    'patterns': ['business account', 'merchant', 'commercial account'],
                    'products': ['Business Transaction Account', 'Business Savings', 'Merchant Account']
                },
                'Business Lending': {
                    'patterns': ['business loan', 'equipment finance', 'invoice', 'working capital'],
                    'products': ['Business Loan', 'Equipment Finance', 'Invoice Finance', 'Overdraft Facility']
                },
                'Trade Services': {
                    'patterns': ['trade', 'import', 'export', 'guarantee'],
                    'products': ['Trade Finance', 'Bank Guarantee', 'Documentary Collection']
                }
            },
            'INST': {
                'Markets': {
                    'patterns': ['fx', 'foreign exchange', 'derivative', 'swap', 'option', 'forward'],
                    'products': ['FX Spot', 'FX Forward', 'Interest Rate Swap', 'Options', 'Futures']
                },
                'Trade Finance': {
                    'patterns': ['letter of credit', 'lc', 'trade finance', 'supply chain'],
                    'products': ['Letter of Credit', 'Trade Finance', 'Supply Chain Finance']
                },
                'Treasury': {
                    'patterns': ['treasury', 'liquidity', 'cash management', 'investment'],
                    'products': ['Treasury Management', 'Liquidity Solutions', 'Investment Products']
                }
            }
        }
    
    def classify_document(self, filename: str, content: str = None, 
                         metadata: Dict = None) -> HierarchicalClassification:
        """
        Classify a document into the hierarchy
        
        Args:
            filename: Document filename
            content: Optional document content for better classification
            metadata: Optional metadata dictionary
            
        Returns:
            HierarchicalClassification object
        """
        classification = HierarchicalClassification()
        
        # Normalize inputs
        filename_lower = filename.lower()
        content_lower = content.lower() if content else ""
        combined_text = f"{filename_lower} {content_lower}"
        
        # Step 1: Determine division
        division_scores = self._score_divisions(combined_text)
        if division_scores:
            best_division = max(division_scores.items(), key=lambda x: x[1])
            classification.division_code = best_division[0]
            classification.division = self.division_patterns[best_division[0]]['name']
            classification.confidence = min(best_division[1], 0.95)
        
        # Step 2: Determine category and products
        category_result = self._classify_category(
            combined_text, 
            classification.division_code
        )
        
        if category_result:
            classification.category = category_result['category']
            classification.products = category_result['products']
            classification.confidence = max(
                classification.confidence, 
                category_result['confidence']
            )
        
        # Step 3: Apply metadata hints if available
        if metadata:
            classification = self._apply_metadata_hints(classification, metadata)
        
        logger.info(f"Classified '{filename}' as {classification.division}/{classification.category} "
                   f"with confidence {classification.confidence:.2f}")
        
        return classification
    
    def _score_divisions(self, text: str) -> Dict[str, float]:
        """Score text against each division"""
        scores = {}
        
        for division_code, config in self.division_patterns.items():
            score = 0.0
            
            # Check positive patterns
            for pattern in config['patterns']:
                if pattern in text:
                    score += 0.3
            
            # Check exclusion patterns (negative score)
            for pattern in config.get('exclude', []):
                if pattern in text:
                    score -= 0.2
            
            if score > 0:
                scores[division_code] = min(score, 1.0)
        
        # Default to RETAIL if no clear match
        if not scores:
            scores['RETAIL'] = 0.5
        
        return scores
    
    def _classify_category(self, text: str, division_code: str) -> Optional[Dict]:
        """Classify into category within a division"""
        
        categories = self.category_patterns.get(division_code, {})
        best_match = None
        best_score = 0
        
        for category_name, config in categories.items():
            score = 0
            
            # Score based on pattern matches
            for pattern in config['patterns']:
                if pattern in text:
                    score += 1
            
            if score > best_score:
                best_score = score
                best_match = {
                    'category': category_name,
                    'products': config['products'],
                    'confidence': min(score * 0.3, 0.9)
                }
        
        # Default category if no match
        if not best_match:
            best_match = {
                'category': 'General',
                'products': [],
                'confidence': 0.3
            }
        
        return best_match
    
    def _apply_metadata_hints(self, classification: HierarchicalClassification, 
                             metadata: Dict) -> HierarchicalClassification:
        """Apply metadata hints to improve classification"""
        
        # Check for explicit category in metadata
        if 'category' in metadata:
            meta_category = metadata['category'].lower()
            
            # Try to match with our categories
            for div_categories in self.category_patterns.values():
                for category_name in div_categories:
                    if meta_category in category_name.lower():
                        classification.category = category_name
                        classification.confidence = max(
                            classification.confidence, 0.8
                        )
                        break
        
        # Check for product hints
        if 'product_type' in metadata:
            product = metadata['product_type']
            if product and product not in classification.products:
                classification.products.append(product)
        
        return classification
    
    def classify_batch(self, documents: List[Dict]) -> List[HierarchicalClassification]:
        """Classify multiple documents"""
        results = []
        
        for doc in documents:
            classification = self.classify_document(
                filename=doc.get('filename', ''),
                content=doc.get('content', ''),
                metadata=doc.get('metadata', {})
            )
            results.append(classification)
        
        return results