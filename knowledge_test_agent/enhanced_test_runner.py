#!/usr/bin/env python3
"""
Enhanced test runner with detailed CSV and Markdown reports
"""

import pandas as pd
import requests
import json
import time
import logging
from datetime import datetime
import os
import argparse
from typing import Dict, List, Any, Optional, Tuple
import re
from sentence_transformers import SentenceTransformer, util
import numpy as np
from difflib import SequenceMatcher
from collections import defaultdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EnhancedTestRunner:
    def __init__(self, api_url: str = "http://localhost:8000"):
        self.api_url = api_url
        self.results = []
        self.start_time = None
        self.end_time = None
        
        # Initialize sentence transformer for semantic similarity
        logger.info("Loading sentence transformer for semantic similarity...")
        self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
        
    def validate_test_data(self, test_file: str, search_type: str = "vector", 
                          use_reranking: bool = False) -> Dict[str, Any]:
        """Validate test data by checking if expected answers can be found in expected documents"""
        logger.info("="*60)
        logger.info("Starting test data validation...")
        logger.info(f"Checking if expected answers can be found in expected documents")
        logger.info("="*60)
        
        # Load test cases
        df = pd.read_csv(test_file)
        total_tests = len(df)
        
        validation_results = []
        validation_summary = {
            "total_tests": total_tests,
            "valid_tests": 0,
            "invalid_tests": 0,
            "warnings": 0,
            "errors": 0,
            "invalid_test_ids": [],
            "warning_test_ids": [],
            "error_test_ids": [],
            "document_issues": defaultdict(list),
            "validation_time": 0
        }
        
        start_time = time.time()
        
        for idx, row in df.iterrows():
            test_id = idx + 1
            question = row['Question']
            expected_answer = row['Acceptable answer\n(entered by business / humans)']
            expected_doc = row.get('Document Name', '')
            expected_page = row.get('Page Number', '')
            
            logger.info(f"\nValidating test {test_id}/{total_tests}...")
            logger.info(f"  Question: {question[:80]}...")
            logger.info(f"  Expected doc: {expected_doc}")
            logger.info(f"  Expected page: {expected_page}")
            
            # Validate this test case
            validation = self._validate_single_test(
                test_id, question, expected_answer, expected_doc, 
                expected_page, search_type, use_reranking
            )
            
            validation_results.append(validation)
            
            # Update summary
            if validation['status'] == 'VALID':
                validation_summary['valid_tests'] += 1
            elif validation['status'] == 'INVALID':
                validation_summary['invalid_tests'] += 1
                validation_summary['invalid_test_ids'].append(test_id)
                validation_summary['document_issues'][expected_doc].append(test_id)
            elif validation['status'] == 'WARNING':
                validation_summary['warnings'] += 1
                validation_summary['warning_test_ids'].append(test_id)
            else:  # ERROR
                validation_summary['errors'] += 1
                validation_summary['error_test_ids'].append(test_id)
            
            # Small delay to avoid overwhelming the API
            time.sleep(0.1)
        
        validation_summary['validation_time'] = time.time() - start_time
        validation_summary['validation_results'] = validation_results
        
        # Generate validation report (MANDATORY)
        report_path = self._generate_validation_report(validation_summary, validation_results)
        validation_summary['report_path'] = report_path
        
        logger.info("\n" + "="*60)
        logger.info("📊 VALIDATION REPORT GENERATION COMPLETE")
        logger.info(f"📄 Report location: {report_path}")
        logger.info("="*60)
        
        return validation_summary
    
    def _validate_single_test(self, test_id: int, question: str, expected_answer: str,
                             expected_doc: str, expected_page: str, 
                             search_type: str, use_reranking: bool) -> Dict[str, Any]:
        """Validate a single test case"""
        validation_result = {
            "test_id": test_id,
            "question": question[:100] + "..." if len(question) > 100 else question,
            "expected_answer": expected_answer[:200] + "..." if len(expected_answer) > 200 else expected_answer,
            "expected_doc": expected_doc,
            "expected_page": expected_page,
            "status": "UNKNOWN",
            "found_in_doc": False,
            "found_on_page": False,
            "answer_similarity": 0.0,
            "content_match": False,
            "issues": [],
            "suggestions": []
        }
        
        try:
            # Build search query to find the specific document
            # First try to find by document name if provided
            if expected_doc:
                doc_search = {
                    "query": f"{expected_doc} {question}",
                    "search_type": search_type,
                    "top_k": 10,
                    "use_reranking": use_reranking
                }
                
                response = requests.post(
                    f"{self.api_url}/search",
                    json=doc_search,
                    timeout=30
                )
                
                if response.status_code == 200:
                    results = response.json()["results"]
                    
                    # Check if we found content from the expected document
                    doc_found = False
                    page_found = False
                    best_match_score = 0.0
                    best_match_text = ""
                    
                    for result in results:
                        # Normalize document names for comparison
                        result_doc_id = result.get("document_id", "")
                        
                        # Strip common file extensions from both names
                        common_extensions = ['.pdf', '.PDF', '.docx', '.DOCX', '.doc', '.DOC', 
                                           '.txt', '.TXT', '.html', '.HTML', '.htm', '.HTM']
                        
                        # Normalize expected document name
                        normalized_expected = expected_doc
                        for ext in common_extensions:
                            if normalized_expected.endswith(ext):
                                normalized_expected = normalized_expected[:-len(ext)]
                                break
                        normalized_expected = normalized_expected.lower().strip()
                        
                        # Normalize result document ID
                        normalized_result = result_doc_id
                        for ext in common_extensions:
                            if normalized_result.endswith(ext):
                                normalized_result = normalized_result[:-len(ext)]
                                break
                        normalized_result = normalized_result.lower().strip()
                        
                        # Log the normalized names being compared
                        logger.info(f"    Comparing: '{normalized_expected}' vs '{normalized_result}'")
                        
                        # Check if this result is from the expected document
                        if normalized_expected in normalized_result or normalized_result in normalized_expected:
                            doc_found = True
                            logger.info(f"    ✓ Document match found: '{result_doc_id}'")
                            
                            # Check if it's from the expected page
                            if expected_page and str(expected_page) in str(result.get("page_number", "")):
                                page_found = True
                        else:
                            logger.info(f"    ✗ No match: '{result_doc_id}'")
                        
                        # Check if the content contains the expected answer (for all results)
                        result_text = result.get("text", "")
                        
                        # Use multiple methods to check answer presence
                        # 1. Semantic similarity
                        similarity = self.calculate_semantic_similarity(result_text, expected_answer)
                        
                        # 2. Keyword matching
                        keyword_match = self._check_keyword_match(result_text, expected_answer)
                        
                        # 3. Fuzzy string matching
                        fuzzy_match = self._check_fuzzy_match(result_text, expected_answer)
                        
                        # Track best match
                        match_score = max(similarity, keyword_match, fuzzy_match)
                        if match_score > best_match_score:
                            best_match_score = match_score
                            best_match_text = result_text
                    
                    validation_result["found_in_doc"] = doc_found
                    validation_result["found_on_page"] = page_found
                    validation_result["answer_similarity"] = best_match_score
                    validation_result["content_match"] = best_match_score > 0.6
                    
                    # Determine validation status
                    if not doc_found:
                        validation_result["status"] = "INVALID"
                        validation_result["issues"].append(f"Document '{expected_doc}' not found in search results")
                        validation_result["suggestions"].append("Check if document name is correct or document is properly indexed")
                    elif expected_page and not page_found:
                        validation_result["status"] = "WARNING"
                        validation_result["issues"].append(f"Document found but not on expected page {expected_page}")
                        validation_result["suggestions"].append("Verify page number or consider page extraction accuracy")
                    elif best_match_score < 0.3:
                        validation_result["status"] = "INVALID"
                        validation_result["issues"].append("Expected answer not found in document content")
                        validation_result["suggestions"].append("Review expected answer accuracy or document content extraction")
                    elif best_match_score < 0.6:
                        validation_result["status"] = "WARNING"
                        validation_result["issues"].append(f"Expected answer partially matches (score: {best_match_score:.2f})")
                        validation_result["suggestions"].append("Consider refining expected answer or improving content extraction")
                    else:
                        validation_result["status"] = "VALID"
                    
                    # Add debug info for invalid/warning cases
                    if validation_result["status"] in ["INVALID", "WARNING"] and best_match_text:
                        validation_result["best_match_excerpt"] = best_match_text[:200] + "..."
                        
                else:
                    validation_result["status"] = "ERROR"
                    validation_result["issues"].append(f"Search API error: {response.status_code}")
                    
            else:
                validation_result["status"] = "WARNING"
                validation_result["issues"].append("No expected document specified")
                validation_result["suggestions"].append("Add expected document name to test case")
                
        except Exception as e:
            validation_result["status"] = "ERROR"
            validation_result["issues"].append(f"Validation error: {str(e)}")
        
        return validation_result
    
    def _check_keyword_match(self, text: str, expected_answer: str) -> float:
        """Check keyword overlap between text and expected answer"""
        # Extract important keywords (numbers, specific terms)
        text_lower = text.lower()
        answer_lower = expected_answer.lower()
        
        # Extract numbers
        text_numbers = set(re.findall(r'\b\d+(?:,\d{3})*(?:\.\d+)?\b', text))
        answer_numbers = set(re.findall(r'\b\d+(?:,\d{3})*(?:\.\d+)?\b', expected_answer))
        
        # Extract important words (excluding common words)
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were'}
        
        text_words = set(word for word in re.findall(r'\b\w+\b', text_lower) if word not in stop_words and len(word) > 2)
        answer_words = set(word for word in re.findall(r'\b\w+\b', answer_lower) if word not in stop_words and len(word) > 2)
        
        # Calculate overlap scores
        number_overlap = len(text_numbers & answer_numbers) / len(answer_numbers) if answer_numbers else 0
        word_overlap = len(text_words & answer_words) / len(answer_words) if answer_words else 0
        
        # Weight numbers more heavily as they're often critical in answers
        return (number_overlap * 0.7 + word_overlap * 0.3)
    
    def _check_fuzzy_match(self, text: str, expected_answer: str, chunk_size: int = 100) -> float:
        """Check fuzzy string matching using sliding window"""
        text_lower = text.lower()
        answer_lower = expected_answer.lower()
        
        # For short answers, check direct substring match
        if len(answer_lower) < 50:
            if answer_lower in text_lower:
                return 1.0
        
        # For longer answers, use sliding window with fuzzy matching
        best_ratio = 0.0
        
        # Slide through text in chunks
        for i in range(0, len(text_lower), chunk_size // 2):
            chunk = text_lower[i:i + chunk_size * 2]
            ratio = SequenceMatcher(None, chunk, answer_lower).ratio()
            best_ratio = max(best_ratio, ratio)
        
        return best_ratio
    
    def _generate_invalid_tests_csv(self, results: List[Dict[str, Any]], timestamp: str) -> str:
        """Generate CSV report specifically for invalid tests"""
        # Filter for invalid tests
        invalid_results = [r for r in results if r['status'] in ['INVALID', 'ERROR']]
        
        if not invalid_results:
            logger.info("No invalid tests found - skipping CSV generation")
            return None
        
        # Create CSV data
        csv_data = []
        for result in invalid_results:
            csv_data.append({
                'Test ID': result['test_id'],
                'Question': result['question'],
                'Expected Document': result['expected_doc'] if result['expected_doc'] else 'Not Specified',
                'Expected Answer': result.get('expected_answer', ''),
                'Issue/Error': result['issues'][0] if result['issues'] else 'Unknown issue',
                'Recommendation': result['suggestions'][0] if result['suggestions'] else 'Review test case',
                'Document Found': 'Yes' if result['found_in_doc'] else 'No',
                'Similarity Score': f"{result['answer_similarity']:.3f}" if result['answer_similarity'] > 0 else 'N/A',
                'Expected Page': result.get('expected_page', ''),
                'Page Found': 'Yes' if result.get('found_on_page', False) else 'No',
                'Status': result['status']
            })
        
        # Create DataFrame and save to CSV
        df = pd.DataFrame(csv_data)
        csv_path = f"../data/test_results/validation_invalid_tests_{timestamp}.csv"
        
        try:
            df.to_csv(csv_path, index=False, encoding='utf-8')
            file_size = os.path.getsize(csv_path)
            
            logger.info(f"📊 Invalid tests CSV generated: {csv_path}")
            logger.info(f"   - Total invalid tests: {len(invalid_results)}")
            logger.info(f"   - File size: {file_size:,} bytes")
            logger.info(f"   - Ready for Excel/Google Sheets import")
            
            return csv_path
            
        except Exception as e:
            logger.error(f"Failed to save invalid tests CSV: {str(e)}")
            return None
    
    def _generate_validation_report(self, summary: Dict[str, Any], results: List[Dict[str, Any]], force_filename: Optional[str] = None):
        """Generate and save comprehensive validation report (ALWAYS generated)"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Use provided filename or generate timestamped one
        if force_filename:
            report_path = force_filename
        else:
            report_path = f"../data/test_results/validation_report_{timestamp}.md"
        
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        
        logger.info("="*60)
        logger.info("GENERATING COMPREHENSIVE VALIDATION REPORT")
        logger.info("="*60)
        
        # Generate CSV report for invalid tests
        invalid_csv_path = self._generate_invalid_tests_csv(results, timestamp)
        
        report = f"""# Test Data Validation Report

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Executive Summary

This report provides a comprehensive analysis of test data validation, identifying tests where expected answers cannot be found in the specified documents. This validation is **MANDATORY** before running accuracy tests to ensure reliable results.

## Summary Statistics

| Metric | Value | Percentage | Status |
|--------|-------|------------|--------|
| **Total Tests** | {summary['total_tests']} | 100.0% | - |
| **Valid Tests** | {summary['valid_tests']} | {summary['valid_tests']/summary['total_tests']*100:.1f}% | {'✅ Good' if summary['valid_tests']/summary['total_tests'] > 0.8 else '⚠️ Needs Attention'} |
| **Invalid Tests** | {summary['invalid_tests']} | {summary['invalid_tests']/summary['total_tests']*100:.1f}% | {'❌ Critical' if summary['invalid_tests'] > 0 else '✅ None'} |
| **Warnings** | {summary['warnings']} | {summary['warnings']/summary['total_tests']*100:.1f}% | {'⚠️ Review' if summary['warnings'] > 0 else '✅ None'} |
| **Errors** | {summary['errors']} | {summary['errors']/summary['total_tests']*100:.1f}% | {'❌ Fix Required' if summary['errors'] > 0 else '✅ None'} |
| **Validation Time** | {summary['validation_time']:.1f}s | - | - |

### Quick Status Assessment

"""
        
        # Add status assessment
        if summary['invalid_tests'] == 0 and summary['errors'] == 0:
            report += "✅ **EXCELLENT**: All test cases have valid data. Ready for accuracy testing.\n\n"
        elif summary['invalid_tests'] < summary['total_tests'] * 0.05:
            report += "✅ **GOOD**: Most test cases are valid. Minor fixes needed for optimal results.\n\n"
        elif summary['invalid_tests'] < summary['total_tests'] * 0.2:
            report += "⚠️ **FAIR**: Significant number of invalid tests. Fixing recommended before accuracy testing.\n\n"
        else:
            report += "❌ **POOR**: High invalid test rate. Critical fixes required for meaningful results.\n\n"
        
        report += """## Invalid Tests Requiring Immediate Attention

These tests have expected answers that **CANNOT** be found in the specified documents. They will likely fail during accuracy testing.

"""
        
        # List invalid tests with enhanced formatting
        invalid_results = [r for r in results if r['status'] == 'INVALID']
        if invalid_results:
            report += "### Top Invalid Tests (Showing up to 30)\n\n"
            report += "| Test ID | Question | Expected Doc | Primary Issue | Recommendation |\n"
            report += "|:-------:|----------|--------------|---------------|----------------|\n"
            
            for result in invalid_results[:30]:  # Show top 30
                question = result['question'][:50] + "..." if len(result['question']) > 50 else result['question']
                doc = result['expected_doc'][:40] if result['expected_doc'] else "❌ None"
                issues = result['issues'][0] if result['issues'] else "Unknown issue"
                suggestion = result['suggestions'][0] if result['suggestions'] else "Review test case"
                report += f"| **{result['test_id']}** | {question} | {doc} | {issues} | {suggestion} |\n"
            
            if len(invalid_results) > 30:
                report += f"\n📊 *... and {len(invalid_results) - 30} more invalid tests*\n"
            
            # Add invalid test IDs list for easy reference
            report += f"\n### Complete List of Invalid Test IDs\n\n"
            report += f"```\n{', '.join(map(str, summary['invalid_test_ids']))}\n```\n"
            
            if invalid_csv_path:
                report += f"\n💡 **Tip**: A CSV file with all invalid test details has been generated for bulk updates:\n"
                report += f"`{os.path.basename(invalid_csv_path)}`\n"
        else:
            report += "*No invalid tests found! ✅*\n"
        
        # Document issues analysis with visual breakdown
        report += "\n## Document-Level Analysis\n\n"
        if summary['document_issues']:
            report += "### Documents with Multiple Test Failures\n\n"
            report += "The following documents have multiple tests that cannot find expected answers:\n\n"
            report += "| Document Name | Failed Tests | Test IDs | Severity |\n"
            report += "|---------------|:------------:|----------|:--------:|\n"
            
            for doc, test_ids in sorted(summary['document_issues'].items(), 
                                       key=lambda x: len(x[1]), reverse=True)[:15]:
                severity = "🔴 Critical" if len(test_ids) > 10 else "🟡 High" if len(test_ids) > 5 else "🟢 Low"
                test_id_list = ', '.join(map(str, test_ids[:8]))
                if len(test_ids) > 8:
                    test_id_list += f" ... (+{len(test_ids) - 8} more)"
                report += f"| {doc[:50]}{'...' if len(doc) > 50 else ''} | **{len(test_ids)}** | {test_id_list} | {severity} |\n"
            
            # Add visual chart
            report += "\n### Document Failure Distribution\n\n"
            report += "```\n"
            max_failures = max(len(ids) for ids in summary['document_issues'].values())
            for doc, test_ids in sorted(summary['document_issues'].items(), 
                                       key=lambda x: len(x[1]), reverse=True)[:10]:
                bar_length = int((len(test_ids) / max_failures) * 40)
                report += f"{doc[:30]:30s} |{'█' * bar_length}{' ' * (40 - bar_length)}| {len(test_ids)} failures\n"
            report += "```\n"
        else:
            report += "*No document-level issues found! ✅*\n"
        
        # Enhanced warnings section
        report += "\n## Warnings and Minor Issues\n\n"
        warning_results = [r for r in results if r['status'] == 'WARNING']
        if warning_results:
            report += "These tests may work but have potential issues that could affect accuracy:\n\n"
            report += "| Test ID | Warning Type | Details | Action Required |\n"
            report += "|:-------:|--------------|---------|----------------|\n"
            
            for result in warning_results[:20]:
                issue = result['issues'][0] if result['issues'] else "Unknown"
                suggestion = result['suggestions'][0] if result['suggestions'] else "Review test case"
                warning_type = "📄 Page Mismatch" if "page" in issue.lower() else "📊 Partial Match" if "partial" in issue.lower() else "⚠️ Other"
                report += f"| **{result['test_id']}** | {warning_type} | {issue} | {suggestion} |\n"
            
            if len(warning_results) > 20:
                report += f"\n📊 *... and {len(warning_results) - 20} more warnings*\n"
        else:
            report += "*No warnings found! ✅*\n"
        
        # Error analysis
        error_results = [r for r in results if r['status'] == 'ERROR']
        if error_results:
            report += "\n## Errors During Validation\n\n"
            report += "⚠️ The following tests encountered errors during validation:\n\n"
            report += "| Test ID | Error Type | Details |\n"
            report += "|:-------:|------------|--------|\n"
            
            for result in error_results[:10]:
                error_msg = result['issues'][0] if result['issues'] else "Unknown error"
                error_type = "🔌 API Error" if "API" in error_msg else "🚫 System Error"
                report += f"| **{result['test_id']}** | {error_type} | {error_msg} |\n"
        
        # Enhanced recommendations with specific actions
        report += "\n## Detailed Recommendations\n\n"
        
        if summary['invalid_tests'] > summary['total_tests'] * 0.2:
            report += "### 🔴 Critical: High Invalid Test Rate (>20%)\n\n"
            report += "**Immediate Actions Required:**\n\n"
            report += "1. **Document Verification**\n"
            report += "   - Verify all referenced documents are properly ingested\n"
            report += "   - Check for document naming inconsistencies\n"
            report += "   - Run: `python audit_pdf_collection.py` to verify document inventory\n\n"
            report += "2. **Test Data Review**\n"
            report += "   - Export invalid tests: Filter test.csv by IDs listed above\n"
            report += "   - Verify expected answers actually exist in source documents\n"
            report += "   - Check for OCR/extraction issues in problematic documents\n\n"
            report += "3. **Re-ingestion**\n"
            report += "   - Consider re-ingesting documents with multiple failures\n"
            report += "   - Use enhanced extraction settings for problematic PDFs\n\n"
        elif summary['invalid_tests'] > 0:
            report += "### 🟡 Moderate: Some Invalid Tests Found\n\n"
            report += "**Recommended Actions:**\n\n"
            report += "1. Review and fix invalid test cases listed above\n"
            report += "2. Verify document names match exactly (case-sensitive)\n"
            report += "3. Check if expected pages are correctly extracted\n\n"
        
        if summary['warnings'] > summary['total_tests'] * 0.3:
            report += "### ⚠️ High Warning Rate (>30%)\n\n"
            report += "**Optimization Suggestions:**\n\n"
            report += "1. **Page Number Accuracy**\n"
            report += "   - Review page extraction logic\n"
            report += "   - Consider page boundary detection improvements\n\n"
            report += "2. **Answer Matching**\n"
            report += "   - Refine expected answer formats\n"
            report += "   - Consider semantic variations in answers\n\n"
        
        if summary['document_issues']:
            report += "### 📚 Document-Specific Recommendations\n\n"
            top_problem_docs = sorted(summary['document_issues'].items(), 
                                     key=lambda x: len(x[1]), reverse=True)[:5]
            report += "**Priority Documents for Review:**\n\n"
            for doc, test_ids in top_problem_docs:
                report += f"- **{doc}**: {len(test_ids)} failing tests\n"
                report += f"  - Action: Re-ingest with enhanced extraction\n"
                report += f"  - Command: `python enhanced_ingestion.py --document \"{doc}\"`\n\n"
        
        # Next steps with clear priority
        report += "\n## Next Steps (Priority Order)\n\n"
        report += "### 🚀 Immediate Actions\n\n"
        
        if summary['invalid_tests'] > 0:
            report += f"1. **Fix {summary['invalid_tests']} Invalid Tests**\n"
            report += "   - Export invalid test IDs from the list above\n"
            report += "   - Review each test's expected document and answer\n"
            report += "   - Update test.csv with corrections\n\n"
        
        if summary['document_issues']:
            report += f"2. **Address {len(summary['document_issues'])} Problematic Documents**\n"
            report += "   - Focus on documents with 5+ failures first\n"
            report += "   - Verify these documents are properly indexed\n"
            report += "   - Re-ingest if necessary\n\n"
        
        report += "### 📋 Before Running Accuracy Tests\n\n"
        report += "3. **Re-run Validation**\n"
        report += "   ```bash\n"
        report += "   python enhanced_test_runner.py --validation-only\n"
        report += "   ```\n\n"
        report += "4. **Proceed with Testing** (only after validation passes)\n"
        report += "   ```bash\n"
        report += "   python enhanced_test_runner.py --use-reranking\n"
        report += "   ```\n\n"
        
        # Add metadata
        report += "## Report Metadata\n\n"
        report += f"- **Generated at**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        report += f"- **Total validation time**: {summary['validation_time']:.1f} seconds\n"
        report += f"- **Average time per test**: {summary['validation_time']/summary['total_tests']:.2f} seconds\n"
        report += f"- **Report version**: 2.0 (Enhanced)\n"
        
        if invalid_csv_path:
            report += f"\n### 📊 Invalid Tests CSV Export\n\n"
            report += f"A CSV file has been generated for easy bulk updates of invalid tests:\n\n"
            report += f"- **File**: `{os.path.basename(invalid_csv_path)}`\n"
            report += f"- **Location**: `{invalid_csv_path}`\n"
            report += f"- **Contains**: All invalid and error test cases with detailed information\n"
            report += f"- **Use**: Import into Excel/Google Sheets for bulk test data corrections\n"
        
        # Save report with confirmation logging
        try:
            with open(report_path, 'w') as f:
                f.write(report)
            
            # Get file size for confirmation
            file_size = os.path.getsize(report_path)
            
            logger.info("="*60)
            logger.info("✅ VALIDATION REPORT SUCCESSFULLY GENERATED")
            logger.info(f"📄 Report path: {report_path}")
            logger.info(f"📊 Report size: {file_size:,} bytes")
            logger.info(f"📈 Total tests validated: {summary['total_tests']}")
            logger.info(f"⚠️  Invalid tests found: {summary['invalid_tests']}")
            if invalid_csv_path:
                logger.info(f"📊 Invalid tests CSV: {invalid_csv_path}")
            logger.info("="*60)
            
        except Exception as e:
            logger.error(f"❌ Failed to save validation report: {str(e)}")
            raise
        
        # Also save detailed results as JSON with logging
        json_path = report_path.replace('.md', '.json')
        try:
            with open(json_path, 'w') as f:
                json.dump({
                    "summary": summary,
                    "validation_results": results,
                    "metadata": {
                        "generated_at": datetime.now().isoformat(),
                        "report_version": "2.0",
                        "validation_time_seconds": summary['validation_time']
                    }
                }, f, indent=2)
            
            json_size = os.path.getsize(json_path)
            logger.info(f"📊 JSON details saved: {json_path} ({json_size:,} bytes)")
            
        except Exception as e:
            logger.error(f"❌ Failed to save JSON details: {str(e)}")
        
        # Store CSV path in validation summary
        if invalid_csv_path:
            summary['invalid_tests_csv_path'] = invalid_csv_path
        
        return report_path
    
    def wait_for_api(self, max_attempts: int = 30, delay: int = 2) -> bool:
        """Wait for API to be ready"""
        logger.info(f"Waiting for API at {self.api_url}...")
        
        for attempt in range(max_attempts):
            try:
                response = requests.get(f"{self.api_url}/stats")
                if response.status_code == 200:
                    stats = response.json()
                    if stats.get("documents", 0) > 0:
                        logger.info("✅ API is ready!")
                        self.api_stats = stats
                        return True
            except:
                pass
            
            if attempt < max_attempts - 1:
                logger.info(f"Attempt {attempt + 1}/{max_attempts}: API not ready yet. Waiting {delay}s...")
                time.sleep(delay)
        
        logger.error("❌ API failed to become ready")
        return False
    
    def calculate_semantic_similarity(self, text1: str, text2: str) -> float:
        """Calculate semantic similarity between two texts"""
        try:
            embeddings1 = self.embedder.encode(text1, convert_to_tensor=True)
            embeddings2 = self.embedder.encode(text2, convert_to_tensor=True)
            similarity = util.pytorch_cos_sim(embeddings1, embeddings2).item()
            return similarity
        except:
            return 0.0
    
    def extract_key_points(self, text: str) -> List[str]:
        """Extract key points from text"""
        # Simple extraction based on sentences containing key terms
        sentences = text.split('.')
        key_terms = ['minimum', 'maximum', 'require', 'must', 'need', 'cost', 'fee', 'rate', 'amount']
        
        key_points = []
        for sentence in sentences:
            if any(term in sentence.lower() for term in key_terms):
                key_points.append(sentence.strip())
        
        return key_points[:3]  # Return top 3 key points
    
    def evaluate_answer(self, actual_answer: str, expected_answer: str, 
                       actual_citations: List[str], expected_doc: str) -> Dict[str, Any]:
        """Evaluate answer quality and correctness"""
        
        # Calculate semantic similarity
        similarity = self.calculate_semantic_similarity(actual_answer, expected_answer)
        
        # Extract key points from both answers
        expected_key_points = self.extract_key_points(expected_answer)
        actual_key_points = self.extract_key_points(actual_answer)
        
        # Check citation accuracy
        citation_match = False
        if expected_doc:
            for citation in actual_citations:
                if expected_doc.lower() in citation.lower():
                    citation_match = True
                    break
        
        # Determine if answer is semantically correct
        # Consider correct if similarity > 0.7 or has matching key information
        semantically_correct = similarity > 0.7
        
        # Check for specific values/numbers match
        expected_numbers = re.findall(r'\b\d+(?:,\d{3})*(?:\.\d+)?\b', expected_answer)
        actual_numbers = re.findall(r'\b\d+(?:,\d{3})*(?:\.\d+)?\b', actual_answer)
        
        numbers_match = False
        if expected_numbers and actual_numbers:
            numbers_match = any(num in actual_numbers for num in expected_numbers)
            if numbers_match:
                semantically_correct = True
        
        # Overall pass/fail
        status = "PASS" if (semantically_correct and citation_match) else "FAIL"
        
        return {
            "status": status,
            "semantic_similarity": similarity,
            "semantically_correct": semantically_correct,
            "citation_match": citation_match,
            "numbers_match": numbers_match,
            "expected_key_points": expected_key_points,
            "actual_key_points": actual_key_points
        }
    
    def run_test_case(self, test_id: int, question: str, expected_answer: str, 
                     expected_doc: str, search_type: str = "vector", 
                     use_reranking: bool = False, timeout: int = 30) -> Dict[str, Any]:
        """Run a single test case"""
        
        # Build search request
        search_request = {
            "query": question,
            "search_type": search_type,
            "top_k": 5
        }
        
        if use_reranking:
            search_request["use_reranking"] = True
        
        start_time = time.time()
        
        try:
            response = requests.post(
                f"{self.api_url}/search",
                json=search_request,
                timeout=timeout
            )
            
            query_time = time.time() - start_time
            
            if response.status_code == 200:
                result = response.json()
                
                # Extract top result
                if result["results"]:
                    top_result = result["results"][0]
                    actual_answer = top_result["text"]
                    actual_citations = [r["document_id"] for r in result["results"][:3]]
                    
                    # Evaluate answer
                    evaluation = self.evaluate_answer(
                        actual_answer, 
                        expected_answer, 
                        actual_citations, 
                        expected_doc
                    )
                    
                    return {
                        "test_id": test_id,
                        "question": question,
                        "expected_answer": expected_answer[:200] + "..." if len(expected_answer) > 200 else expected_answer,
                        "actual_answer": actual_answer[:200] + "..." if len(actual_answer) > 200 else actual_answer,
                        "expected_citations": expected_doc,
                        "actual_citations": ", ".join(actual_citations[:3]),
                        "status": evaluation["status"],
                        "semantic_similarity": round(evaluation["semantic_similarity"], 3),
                        "citation_match": evaluation["citation_match"],
                        "numbers_match": evaluation["numbers_match"],
                        "query_time": round(query_time, 2),
                        "search_type": search_type,
                        "reranking_used": use_reranking,
                        "top_score": round(top_result.get("score", 0), 3),
                        "rerank_score": round(top_result.get("rerank_score", 0), 3) if use_reranking else None,
                        "error": None
                    }
                else:
                    return {
                        "test_id": test_id,
                        "question": question,
                        "expected_answer": expected_answer[:200] + "...",
                        "actual_answer": "No results found",
                        "expected_citations": expected_doc,
                        "actual_citations": "",
                        "status": "FAIL",
                        "semantic_similarity": 0,
                        "citation_match": False,
                        "numbers_match": False,
                        "query_time": round(query_time, 2),
                        "search_type": search_type,
                        "reranking_used": use_reranking,
                        "top_score": 0,
                        "rerank_score": None,
                        "error": "No results returned"
                    }
            else:
                return self._create_error_result(test_id, question, expected_answer, expected_doc,
                                               f"API error: {response.status_code}", query_time,
                                               search_type, use_reranking)
                
        except Exception as e:
            return self._create_error_result(test_id, question, expected_answer, expected_doc,
                                           str(e), time.time() - start_time,
                                           search_type, use_reranking)
    
    def _create_error_result(self, test_id, question, expected_answer, expected_doc,
                           error, query_time, search_type, use_reranking):
        """Create error result entry"""
        return {
            "test_id": test_id,
            "question": question,
            "expected_answer": expected_answer[:200] + "...",
            "actual_answer": "",
            "expected_citations": expected_doc,
            "actual_citations": "",
            "status": "ERROR",
            "semantic_similarity": 0,
            "citation_match": False,
            "numbers_match": False,
            "query_time": round(query_time, 2),
            "search_type": search_type,
            "reranking_used": use_reranking,
            "top_score": 0,
            "rerank_score": None,
            "error": error
        }
    
    def run_all_tests(self, test_file: str = None, search_type: str = "vector",
                     use_reranking: bool = False, timeout: int = 30, 
                     continue_on_invalid: bool = True):
        """Run all tests from CSV file with MANDATORY validation"""
        logger.info(f"Loading test cases from {test_file}")
        
        # ALWAYS run validation (mandatory for comprehensive reporting)
        logger.info("\n" + "="*60)
        logger.info("PHASE 1: Running MANDATORY test data validation...")
        logger.info("="*60)
        
        validation_summary = self.validate_test_data(
            test_file, search_type, use_reranking
        )
        
        logger.info("\n" + "="*60)
        logger.info("VALIDATION COMPLETE")
        logger.info(f"  Valid tests: {validation_summary['valid_tests']}/{validation_summary['total_tests']}")
        logger.info(f"  Invalid tests: {validation_summary['invalid_tests']}")
        logger.info(f"  Warnings: {validation_summary['warnings']}")
        logger.info("="*60)
        
        # Store validation report path for later reference
        self.validation_report_path = validation_summary.get('report_path', None)
        
        if validation_summary['invalid_tests'] > 0 and not continue_on_invalid:
            logger.error("\nStopping due to invalid test cases. Fix them before proceeding.")
            logger.error(f"Invalid test IDs: {validation_summary['invalid_test_ids']}")
            logger.error(f"\n📄 See detailed validation report: {self.validation_report_path}")
            return
        elif validation_summary['invalid_tests'] > 0:
            logger.warning(f"\n⚠️  Continuing with {validation_summary['invalid_tests']} invalid test cases...")
            logger.warning("These tests are likely to fail. Consider fixing them for accurate results.")
            logger.warning(f"\n📄 See validation report for details: {self.validation_report_path}")
        
        # Load test cases
        df = pd.read_csv(test_file)
        total_tests = len(df)
        
        logger.info(f"\n" + "="*60)
        logger.info("PHASE 2: Running accuracy tests...")
        logger.info("="*60)
        logger.info(f"Running {total_tests} test cases...")
        logger.info(f"  Search type: {search_type}")
        logger.info(f"  Reranking: {'Enabled' if use_reranking else 'Disabled'}")
        logger.info(f"  Timeout: {timeout}s")
        
        self.start_time = datetime.now()
        self.validation_summary = validation_summary
        
        # Run each test
        for idx, row in df.iterrows():
            test_id = idx + 1
            question = row['Question']
            expected_answer = row['Acceptable answer\n(entered by business / humans)']
            expected_doc = row.get('Document Name', '')
            
            logger.info(f"Test {test_id}/{total_tests}: {question[:50]}...")
            
            result = self.run_test_case(
                test_id, question, expected_answer, expected_doc,
                search_type, use_reranking, timeout
            )
            
            self.results.append(result)
            
            # Small delay between tests
            time.sleep(0.1)
        
        self.end_time = datetime.now()
        logger.info(f"\nAll tests completed in {(self.end_time - self.start_time).total_seconds():.1f}s")
    
    def generate_summary(self) -> Dict[str, Any]:
        """Generate test summary statistics"""
        df = pd.DataFrame(self.results)
        
        total_tests = len(self.results)
        passed_tests = len(df[df['status'] == 'PASS'])
        failed_tests = len(df[df['status'] == 'FAIL'])
        error_tests = len(df[df['status'] == 'ERROR'])
        
        # Calculate various metrics
        # PRIMARY METRIC: Citation/Document accuracy (what we measured before)
        citation_matches = len(df[df['citation_match'] == True])
        citation_accuracy = citation_matches / total_tests if total_tests > 0 else 0
        
        # SECONDARY METRIC: Answer semantic similarity (strict threshold)
        semantic_pass_rate = passed_tests / total_tests if total_tests > 0 else 0
        
        summary = {
            "total_tests": total_tests,
            "passed": passed_tests,
            "failed": failed_tests,
            "errors": error_tests,
            "pass_rate": semantic_pass_rate,
            "citation_matches": citation_matches,
            "citation_accuracy": citation_accuracy,  # This is our main accuracy metric
            "avg_query_time": df['query_time'].mean(),
            "avg_semantic_similarity": df[df['semantic_similarity'] > 0]['semantic_similarity'].mean(),
            "numbers_accuracy": len(df[df['numbers_match'] == True]) / len(df[df['numbers_match'].notna()]),
            "total_time": (self.end_time - self.start_time).total_seconds() if self.end_time else 0,
            "timestamp": datetime.now().isoformat(),
            "configuration": {
                "search_type": self.results[0]['search_type'] if self.results else '',
                "reranking_used": self.results[0]['reranking_used'] if self.results else False,
                "api_stats": getattr(self, 'api_stats', {})
            }
        }
        
        return summary
    
    def save_csv_report(self, filename: Optional[str] = None):
        """Save detailed CSV report"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"../data/test_results/test_report_{timestamp}.csv"
        
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        df = pd.DataFrame(self.results)
        df.to_csv(filename, index=False)
        logger.info(f"CSV report saved to {filename}")
        
        return filename
    
    def generate_markdown_report(self, summary: Dict[str, Any]) -> str:
        """Generate detailed Markdown report"""
        df = pd.DataFrame(self.results)
        
        # Analyze strong and weak areas
        failed_df = df[df['status'] == 'FAIL']
        
        # Group failures by patterns
        failure_patterns = {}
        for _, row in failed_df.iterrows():
            question_type = self._categorize_question(row['question'])
            if question_type not in failure_patterns:
                failure_patterns[question_type] = []
            failure_patterns[question_type].append({
                'question': row['question'],
                'similarity': row['semantic_similarity'],
                'citation_match': row['citation_match']
            })
        
        # Build markdown report
        report = f"""# Knowledge Graph Test Report

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Test Configuration

- **Search Type**: {summary['configuration']['search_type']}
- **Reranking**: {'Enabled' if summary['configuration']['reranking_used'] else 'Disabled'}
- **Total Documents**: {summary['configuration']['api_stats'].get('documents', 'N/A')}
- **Total Chunks**: {summary['configuration']['api_stats'].get('chunks', 'N/A')}
- **Total Entities**: {summary['configuration']['api_stats'].get('entities', 'N/A')}
"""

        # Add validation summary if available
        if hasattr(self, 'validation_summary') and self.validation_summary:
            val_sum = self.validation_summary
            report += f"""
## Test Data Validation Results

- **Valid Tests**: {val_sum['valid_tests']}/{val_sum['total_tests']} ({val_sum['valid_tests']/val_sum['total_tests']*100:.1f}%)
- **Invalid Tests**: {val_sum['invalid_tests']} (IDs: {', '.join(map(str, val_sum['invalid_test_ids'][:10]))}{' ...' if len(val_sum['invalid_test_ids']) > 10 else ''})
- **Warnings**: {val_sum['warnings']}
- **Validation Time**: {val_sum['validation_time']:.1f}s

⚠️ **Note**: Invalid tests are likely to fail as their expected answers cannot be found in the specified documents.

📄 **See the comprehensive validation report for detailed analysis of test data quality issues.**
"""

        report += """
## Overall Summary

| Metric | Value |
|--------|-------|
| Total Tests | {summary['total_tests']} |
| **DOCUMENT ACCURACY** | **{summary['citation_accuracy']*100:.1f}%** |
| Citation Matches | {summary['citation_matches']} |
| Answer Correctness (Semantic > 0.7) | {summary['pass_rate']*100:.1f}% |
| Passed | {summary['passed']} |
| Failed | {summary['failed']} |
| Errors | {summary['errors']} |
| Average Query Time | {summary['avg_query_time']:.2f}s |
| Average Semantic Similarity | {summary['avg_semantic_similarity']:.3f} |
| Numbers Match Rate | {summary['numbers_accuracy']*100:.1f}% |
| Total Test Time | {summary['total_time']:.1f}s |

## Performance Analysis

### Strong Areas

"""
        
        # Identify strong areas (high pass rate by category)
        question_categories = df.groupby(df['question'].apply(self._categorize_question))
        
        strong_areas = []
        weak_areas = []
        
        for category, group in question_categories:
            pass_rate = len(group[group['status'] == 'PASS']) / len(group)
            avg_similarity = group['semantic_similarity'].mean()
            
            if pass_rate >= 0.8:
                strong_areas.append({
                    'category': category,
                    'pass_rate': pass_rate,
                    'avg_similarity': avg_similarity,
                    'count': len(group)
                })
            elif pass_rate < 0.6:
                weak_areas.append({
                    'category': category,
                    'pass_rate': pass_rate,
                    'avg_similarity': avg_similarity,
                    'count': len(group),
                    'examples': group[group['status'] == 'FAIL']['question'].head(3).tolist()
                })
        
        for area in sorted(strong_areas, key=lambda x: x['pass_rate'], reverse=True)[:5]:
            report += f"- **{area['category']}**: {area['pass_rate']*100:.1f}% pass rate ({area['count']} tests), avg similarity {area['avg_similarity']:.3f}\n"
        
        report += "\n### Weak Areas\n\n"
        
        for area in sorted(weak_areas, key=lambda x: x['pass_rate'])[:5]:
            report += f"- **{area['category']}**: {area['pass_rate']*100:.1f}% pass rate ({area['count']} tests)\n"
            report += f"  - Average similarity: {area['avg_similarity']:.3f}\n"
            report += f"  - Example failures:\n"
            for example in area['examples']:
                report += f"    - \"{example[:60]}...\"\n"
        
        # Add improvement recommendations
        report += """
## Recommendations for Improvement

Based on the test results, here are specific recommendations:

"""
        
        # Analyze failure patterns
        if summary['citation_accuracy'] < 0.8:
            report += f"1. **Document Accuracy ({summary['citation_accuracy']*100:.1f}%)**: This is our PRIMARY metric - finding the correct source documents. Consider:\n"
            report += "   - Improving document metadata extraction\n"
            report += "   - Enhancing the relationship between chunks and their parent documents\n"
            report += "   - Adding document-level boosting in search queries\n"
            report += "   - Testing different chunk sizes (current enhanced chunking may be too large)\n\n"
        
        if summary['pass_rate'] < 0.5:
            report += f"2. **Answer Extraction ({summary['pass_rate']*100:.1f}% pass rate)**: Even when finding correct documents, answer extraction is poor. Consider:\n"
            report += "   - Implementing dedicated answer extraction pipeline\n"
            report += "   - Using LLM for answer synthesis from chunks\n"
            report += "   - Creating question-type specific extraction strategies\n"
            report += "   - Combining multiple chunks for comprehensive answers\n\n"
        
        if summary['avg_semantic_similarity'] < 0.7:
            report += f"3. **Semantic Similarity ({summary['avg_semantic_similarity']:.3f})**: Retrieved content has moderate semantic similarity to expected answers. Consider:\n"
            report += "   - Fine-tuning the embedding model on domain-specific data\n"
            report += "   - Implementing query expansion techniques\n"
            report += "   - Better chunk ranking and selection\n\n"
        
        # Specific pattern-based recommendations
        if 'minimum/maximum requirements' in [wa['category'] for wa in weak_areas]:
            report += "3. **Numerical Requirements**: The system has difficulty with minimum/maximum value questions. Consider:\n"
            report += "   - Implementing specialized extraction for numerical constraints\n"
            report += "   - Adding metadata fields for numerical values\n"
            report += "   - Creating dedicated indexes for requirement-based queries\n\n"
        
        # Add detailed failure analysis
        report += """
## Detailed Failure Analysis

### Top 10 Failed Questions by Semantic Similarity

| Question | Expected Doc | Actual Doc | Similarity | Issue |
|----------|--------------|------------|------------|-------|
"""
        
        failed_sorted = failed_df.sort_values('semantic_similarity', ascending=False).head(10)
        for _, row in failed_sorted.iterrows():
            question = row['question'][:50] + "..."
            expected = row['expected_citations'][:30] if row['expected_citations'] else "N/A"
            actual = row['actual_citations'].split(',')[0][:30] if row['actual_citations'] else "No results"
            similarity = row['semantic_similarity']
            issue = "Citation mismatch" if not row['citation_match'] else "Low similarity"
            
            report += f"| {question} | {expected} | {actual} | {similarity:.3f} | {issue} |\n"
        
        # Add configuration comparison if available
        report += """
## Configuration Impact Analysis

Based on the current configuration:
"""
        
        if summary['configuration']['reranking_used']:
            report += "- **Reranking Enabled**: Cross-encoder reranking is active, which should improve accuracy\n"
            rerank_impact = df[df['rerank_score'].notna()]['rerank_score'].mean()
            if rerank_impact > 0:
                report += f"  - Average reranking score: {rerank_impact:.3f}\n"
        else:
            report += "- **Reranking Disabled**: Consider enabling reranking for improved accuracy\n"
        
        report += f"- **Search Type**: {summary['configuration']['search_type']}\n"
        
        if summary['configuration']['search_type'] == 'vector':
            report += "  - Vector search provides good semantic matching\n"
            report += "  - Consider trying hybrid search for better keyword matching\n"
        
        return report
    
    def _categorize_question(self, question: str) -> str:
        """Categorize question type for analysis"""
        q_lower = question.lower()
        
        if any(term in q_lower for term in ['minimum', 'maximum', 'how much', 'how many']):
            return "minimum/maximum requirements"
        elif any(term in q_lower for term in ['what is', 'what are', 'define']):
            return "definitions"
        elif any(term in q_lower for term in ['can i', 'can you', 'is it possible']):
            return "capabilities/permissions"
        elif any(term in q_lower for term in ['how to', 'how do', 'process']):
            return "procedures"
        elif any(term in q_lower for term in ['example', 'show me', 'demonstrate']):
            return "examples"
        elif any(term in q_lower for term in ['risk', 'danger', 'warning']):
            return "risks/warnings"
        elif any(term in q_lower for term in ['cost', 'fee', 'charge', 'price']):
            return "costs/fees"
        else:
            return "general"
    
    def save_markdown_report(self, summary: Dict[str, Any], filename: Optional[str] = None):
        """Save comprehensive Markdown report including validation details"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"../data/test_results/test_report_{timestamp}.md"
        
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        report = self.generate_markdown_report(summary)
        
        # Save main test report
        with open(filename, 'w') as f:
            f.write(report)
        
        file_size = os.path.getsize(filename)
        
        logger.info("\n" + "="*60)
        logger.info("📊 TEST REPORT GENERATION COMPLETE")
        logger.info(f"📄 Main report: {filename} ({file_size:,} bytes)")
        
        # Reference validation report if available
        if hasattr(self, 'validation_report_path') and self.validation_report_path:
            logger.info(f"📄 Validation report: {self.validation_report_path}")
        
        logger.info("="*60)
        
        return filename

def main():
    """Main test execution"""
    parser = argparse.ArgumentParser(description="Enhanced test runner for Knowledge Graph API")
    parser.add_argument("--api-url", default="http://localhost:8000",
                        help="API URL (default: http://localhost:8000)")
    parser.add_argument("--test-file", default=None,
                        help="Test CSV file (default: finds test.csv in current or parent directory)")
    parser.add_argument("--search-type", default="vector",
                        choices=["vector", "graph", "full_text", "hybrid", "graphrag", "text2cypher"],
                        help="Search type to test (default: vector)")
    parser.add_argument("--use-reranking", action="store_true",
                        help="Enable reranking")
    parser.add_argument("--timeout", type=int, default=30,
                        help="Request timeout in seconds (default: 30)")
    parser.add_argument("--no-validation", action="store_true",
                        help="DEPRECATED: Validation is now mandatory for all test runs")
    parser.add_argument("--validation-only", action="store_true",
                        help="Only run validation, don't run tests")
    parser.add_argument("--stop-on-invalid", action="store_true",
                        help="Stop if invalid test cases are found during validation")
    
    args = parser.parse_args()
    
    # Find test file if not specified
    if args.test_file is None:
        # Look for test.csv in current directory
        if os.path.exists("test.csv"):
            args.test_file = "test.csv"
        # Look in parent directory
        elif os.path.exists("../test.csv"):
            args.test_file = "../test.csv"
        # Look in knowledge_test_agent directory
        elif os.path.exists("knowledge_test_agent/test.csv"):
            args.test_file = "knowledge_test_agent/test.csv"
        # Look if we're in knowledge_test_agent directory
        elif os.path.basename(os.getcwd()) == "knowledge_test_agent" and os.path.exists("test.csv"):
            args.test_file = "test.csv"
        else:
            logger.error("Could not find test.csv file. Please specify with --test-file")
            return
    
    logger.info(f"Using test file: {args.test_file}")
    
    # Warn if deprecated --no-validation flag is used
    if args.no_validation:
        logger.warning("\n" + "="*60)
        logger.warning("⚠️  WARNING: --no-validation flag is DEPRECATED")
        logger.warning("Validation is now MANDATORY for all test runs to ensure data quality")
        logger.warning("Proceeding with mandatory validation...")
        logger.warning("="*60 + "\n")
    
    # Create test runner
    runner = EnhancedTestRunner(args.api_url)
    
    # Wait for API
    if not runner.wait_for_api():
        logger.error("API not available, exiting")
        return
    
    # If validation only mode
    if args.validation_only:
        logger.info("\n" + "="*60)
        logger.info("VALIDATION ONLY MODE")
        logger.info("="*60)
        
        validation_summary = runner.validate_test_data(
            args.test_file, args.search_type, args.use_reranking
        )
        
        logger.info("\n" + "="*60)
        logger.info("VALIDATION COMPLETE")
        logger.info(f"  Valid tests: {validation_summary['valid_tests']}/{validation_summary['total_tests']}")
        logger.info(f"  Invalid tests: {validation_summary['invalid_tests']}")
        logger.info(f"  Warnings: {validation_summary['warnings']}")
        logger.info(f"  Errors: {validation_summary['errors']}")
        logger.info("="*60)
        
        if validation_summary['invalid_tests'] > 0:
            logger.warning(f"\nInvalid test IDs: {validation_summary['invalid_test_ids']}")
            logger.warning("Fix these test cases for accurate results.")
        
        return
    
    # Run tests with MANDATORY validation
    runner.run_all_tests(
        test_file=args.test_file,
        search_type=args.search_type,
        use_reranking=args.use_reranking,
        timeout=args.timeout,
        continue_on_invalid=not args.stop_on_invalid
    )
    
    # Check if tests were actually run (might have stopped due to validation)
    if not hasattr(runner, 'results') or not runner.results:
        logger.warning("No test results to report.")
        return
    
    # Generate summary
    summary = runner.generate_summary()
    
    # Save reports
    csv_file = runner.save_csv_report()
    md_file = runner.save_markdown_report(summary)
    
    # Print summary
    logger.info("\n" + "="*60)
    logger.info("Test Results Summary:")
    logger.info(f"  Total tests: {summary['total_tests']}")
    logger.info(f"  **DOCUMENT ACCURACY: {summary['citation_accuracy']*100:.1f}%** (Primary metric)")
    logger.info(f"  Citation matches: {summary['citation_matches']}")
    logger.info(f"  Answer correctness: {summary['pass_rate']*100:.1f}% (Semantic > 0.7)")
    logger.info(f"  Passed: {summary['passed']}")
    logger.info(f"  Failed: {summary['failed']}")
    logger.info(f"  Errors: {summary['errors']}")
    logger.info(f"  Average query time: {summary['avg_query_time']:.2f}s")
    logger.info(f"\n📊 Reports Generated:")
    logger.info(f"  📄 Test Results (CSV): {csv_file}")
    logger.info(f"  📄 Test Report (Markdown): {md_file}")
    if hasattr(runner, 'validation_report_path') and runner.validation_report_path:
        logger.info(f"  📄 Validation Report (Markdown): {runner.validation_report_path}")
    logger.info("="*60)

if __name__ == "__main__":
    main()