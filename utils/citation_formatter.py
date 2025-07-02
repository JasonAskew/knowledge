#!/usr/bin/env python3
"""
Citation Formatter for Knowledge Graph Results

This utility demonstrates how to format citations from the knowledge graph
for proper attribution of sources.
"""

from typing import Dict, List, Any


def format_citation(result: Dict[str, Any]) -> str:
    """
    Format a search result into a proper citation.
    
    Args:
        result: Dictionary containing search result with keys:
            - source_document: filename of the source PDF
            - page_number: page number in the document
            - chunk_id: unique identifier for the chunk
            - excerpt: text excerpt from the chunk
    
    Returns:
        Formatted citation string
    """
    doc = result.get('source_document', 'Unknown Document')
    page = result.get('page_number', 'n/a')
    chunk_id = result.get('chunk_id', '')
    
    # Remove .pdf extension for cleaner citation
    doc_name = doc.replace('.pdf', '')
    
    return f"{doc_name}, p. {page}"


def format_detailed_citation(result: Dict[str, Any]) -> str:
    """
    Format a detailed citation with excerpt.
    
    Returns:
        Detailed citation with source text
    """
    basic_citation = format_citation(result)
    excerpt = result.get('excerpt', '')
    
    # Truncate excerpt if too long
    if len(excerpt) > 200:
        excerpt = excerpt[:197] + "..."
    
    return f'"{excerpt}" - {basic_citation}'


def format_apa_style_citation(result: Dict[str, Any]) -> str:
    """
    Format citation in APA-like style.
    
    Returns:
        APA-style citation
    """
    doc = result.get('source_document', 'Unknown Document')
    page = result.get('page_number', 'n/a')
    
    # Extract organization from filename (assumes pattern like "WBC-DocumentName.pdf")
    org = "Unknown Organization"
    if '-' in doc:
        org_code = doc.split('-')[0]
        org_map = {
            'WBC': 'Westpac Banking Corporation',
            'BSA': 'BankSA',
            'SGB': 'St.George Bank',
            'BOM': 'Bank of Melbourne',
            'FSR': 'Westpac Financial Services',
            'WNZL': 'Westpac New Zealand Limited'
        }
        org = org_map.get(org_code, org_code)
    
    # Remove .pdf and clean document name
    doc_name = doc.replace('.pdf', '').replace('_', ' ').replace('-', ' - ')
    
    return f"{org}. {doc_name}, p. {page}."


def create_citations_report(results: List[Dict[str, Any]], query: str) -> str:
    """
    Create a formatted report with all citations for a query.
    
    Args:
        results: List of search results
        query: The original search query
    
    Returns:
        Formatted citations report
    """
    report = []
    report.append(f"Citations for query: '{query}'")
    report.append("=" * 50)
    report.append("")
    
    for i, result in enumerate(results, 1):
        report.append(f"{i}. {format_detailed_citation(result)}")
        report.append(f"   Full citation: {format_apa_style_citation(result)}")
        report.append(f"   Chunk ID: {result.get('chunk_id', 'N/A')}")
        report.append("")
    
    return "\n".join(report)


def format_inline_citation(result: Dict[str, Any], number: int) -> Dict[str, str]:
    """
    Format for inline citation (e.g., for use in generated text).
    
    Args:
        result: Search result
        number: Citation number
    
    Returns:
        Dict with 'inline' marker and 'full' citation
    """
    return {
        'inline': f"[{number}]",
        'full': format_apa_style_citation(result),
        'short': format_citation(result),
        'chunk_id': result.get('chunk_id', '')
    }


# Example usage
if __name__ == "__main__":
    # Sample results from a Neo4j query
    sample_results = [
        {
            'source_document': 'WBC-ForeignCurrencyAccountPDS.pdf',
            'page_number': 12,
            'chunk_id': 'WBC-ForeignCurrencyAccountPDS_p12_c15',
            'excerpt': 'The minimum balance requirement for foreign currency accounts is USD 1,000 or equivalent in other supported currencies.'
        },
        {
            'source_document': 'BSA-AccountFeesCharges.pdf',
            'page_number': 5,
            'chunk_id': 'BSA-AccountFeesCharges_p5_c8',
            'excerpt': 'Monthly account keeping fees apply unless minimum balance requirements are met.'
        }
    ]
    
    # Generate citations report
    report = create_citations_report(sample_results, "minimum balance foreign currency")
    print(report)
    
    print("\n" + "=" * 50 + "\n")
    
    # Show different citation formats
    for result in sample_results:
        print(f"Basic: {format_citation(result)}")
        print(f"APA Style: {format_apa_style_citation(result)}")
        print(f"Detailed: {format_detailed_citation(result)}")
        print("")