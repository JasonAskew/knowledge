"""
Financial Table Extractor for extracting structured financial data from PDFs.
Focuses on tables containing TCE, exposure data, emissions, and other financial metrics.
"""

import re
from typing import List, Dict, Any, Optional, Tuple
import structlog
from pathlib import Path

logger = structlog.get_logger()


class FinancialTableExtractor:
    """Extract financial metrics and exposure data from PDF tables."""
    
    def __init__(self):
        # Patterns for financial amounts
        self.amount_patterns = {
            'currency_amount': re.compile(r'\$\s*([\d,]+(?:\.\d+)?)\s*(?:million|billion|m|b)?', re.IGNORECASE),
            'numeric_amount': re.compile(r'([\d,]+(?:\.\d+)?)\s*(?:million|billion|m|b)', re.IGNORECASE),
            'percentage': re.compile(r'([\d,]+(?:\.\d+)?)\s*%'),
            'decimal': re.compile(r'([\d,]+(?:\.\d+)?)')
        }
        
        # Keywords indicating financial tables
        self.table_keywords = {
            'exposure': ['exposure', 'tce', 'committed', 'lending'],
            'emissions': ['emissions', 'mtco2', 'carbon', 'ghg'],
            'financial': ['revenue', 'income', 'assets', 'liabilities'],
            'sector': ['sector', 'industry', 'anzsic', 'construction', 'mining']
        }
        
        # Sector mappings
        self.sectors = {
            'construction': ['construction', 'building', 'infrastructure'],
            'mining': ['mining', 'coal', 'metals', 'resources'],
            'agriculture': ['agriculture', 'farming', 'agribusiness', 'dairy', 'beef'],
            'finance': ['finance', 'insurance', 'banking'],
            'property': ['property', 'real estate', 'commercial property'],
            'manufacturing': ['manufacturing', 'industrial'],
            'utilities': ['utilities', 'electricity', 'gas', 'water'],
            'transport': ['transport', 'aviation', 'shipping', 'logistics']
        }
    
    def extract_financial_tables(self, tables: List[Dict[str, Any]], 
                               source_file: str = None,
                               page_numbers: List[int] = None) -> List[Dict[str, Any]]:
        """Extract financial data from tables."""
        extracted_data = []
        
        for i, table in enumerate(tables):
            page_num = page_numbers[i] if page_numbers and i < len(page_numbers) else None
            
            # Check if this is a financial table
            if self._is_financial_table(table):
                # Extract data based on table type
                table_type = self._identify_table_type(table)
                
                if table_type == 'exposure':
                    data = self._extract_exposure_data(table, source_file, page_num)
                elif table_type == 'emissions':
                    data = self._extract_emissions_data(table, source_file, page_num)
                elif table_type == 'sector':
                    data = self._extract_sector_data(table, source_file, page_num)
                else:
                    data = self._extract_generic_financial_data(table, source_file, page_num)
                
                if data:
                    extracted_data.extend(data)
        
        return extracted_data
    
    def _is_financial_table(self, table: Dict[str, Any]) -> bool:
        """Determine if a table contains financial data."""
        # Get table data
        data = table.get('data', [])
        if not data or len(data) < 2:
            return False
        
        # Check headers and content for financial keywords
        headers = data[0] if data else []
        all_text = ' '.join([' '.join(str(cell) for cell in row) for row in data]).lower()
        
        # Check for financial keywords
        for category, keywords in self.table_keywords.items():
            if any(keyword in all_text for keyword in keywords):
                return True
        
        # Check for amount patterns
        for row in data[1:]:  # Skip header
            for cell in row:
                cell_str = str(cell)
                if any(pattern.search(cell_str) for pattern in self.amount_patterns.values()):
                    return True
        
        return False
    
    def _identify_table_type(self, table: Dict[str, Any]) -> str:
        """Identify the type of financial table."""
        data = table.get('data', [])
        all_text = ' '.join([' '.join(str(cell) for cell in row) for row in data]).lower()
        
        # Check each category
        scores = {}
        for category, keywords in self.table_keywords.items():
            score = sum(1 for keyword in keywords if keyword in all_text)
            scores[category] = score
        
        # Return category with highest score
        return max(scores, key=scores.get) if any(scores.values()) else 'generic'
    
    def _extract_exposure_data(self, table: Dict[str, Any], source_file: str, page_num: int) -> List[Dict[str, Any]]:
        """Extract exposure data from table."""
        extracted = []
        data = table.get('data', [])
        
        if len(data) < 2:
            return extracted
        
        headers = [str(h).strip() for h in data[0]]
        
        # Find relevant column indices
        sector_col = self._find_column(headers, ['sector', 'industry', 'name'])
        amount_cols = self._find_amount_columns(headers)
        
        if sector_col is None or not amount_cols:
            return extracted
        
        # Extract data from rows
        for row in data[1:]:
            if len(row) <= max(sector_col, *amount_cols.keys()):
                continue
            
            sector_name = str(row[sector_col]).strip()
            if not sector_name or sector_name.lower() in ['total', 'other']:
                continue
            
            # Extract amounts
            for col_idx, col_info in amount_cols.items():
                amount_str = str(row[col_idx]).strip()
                amount, unit, currency = self._parse_amount(amount_str)
                
                if amount is not None:
                    extracted.append({
                        'type': 'exposure',
                        'sector': sector_name,
                        'metric_type': col_info.get('type', 'TCE'),
                        'value': amount,
                        'unit': unit or 'million',  # Default to million
                        'currency': currency or 'AUD',  # Default to AUD
                        'period': col_info.get('period', '2023'),
                        'source_table': f"Page {page_num}" if page_num else None,
                        'source_file': source_file
                    })
        
        return extracted
    
    def _extract_emissions_data(self, table: Dict[str, Any], source_file: str, page_num: int) -> List[Dict[str, Any]]:
        """Extract emissions data from table."""
        extracted = []
        data = table.get('data', [])
        
        if len(data) < 2:
            return extracted
        
        headers = [str(h).strip() for h in data[0]]
        
        # Similar to exposure extraction but for emissions
        sector_col = self._find_column(headers, ['sector', 'industry', 'name'])
        emissions_cols = self._find_column(headers, ['emissions', 'mtco2', 'carbon', 'scope'])
        
        if sector_col is None:
            return extracted
        
        for row in data[1:]:
            if len(row) <= sector_col:
                continue
            
            sector_name = str(row[sector_col]).strip()
            if not sector_name:
                continue
            
            # Look for emissions values in the row
            for i, cell in enumerate(row):
                cell_str = str(cell).strip()
                if self._is_emissions_value(cell_str):
                    amount, unit = self._parse_emissions_amount(cell_str)
                    if amount is not None:
                        extracted.append({
                            'type': 'emissions',
                            'sector': sector_name,
                            'metric_type': 'Financed Emissions',
                            'value': amount,
                            'unit': unit or 'MtCO2-e',
                            'source_table': f"Page {page_num}" if page_num else None,
                            'source_file': source_file
                        })
        
        return extracted
    
    def _extract_sector_data(self, table: Dict[str, Any], source_file: str, page_num: int) -> List[Dict[str, Any]]:
        """Extract sector-specific data from table."""
        extracted = []
        data = table.get('data', [])
        
        # Look specifically for construction and other sector data
        for row_idx, row in enumerate(data):
            row_text = ' '.join(str(cell) for cell in row).lower()
            
            # Check if construction is mentioned
            if 'construction' in row_text:
                # Extract any amounts in this row
                for cell in row:
                    cell_str = str(cell)
                    amount, unit, currency = self._parse_amount(cell_str)
                    if amount is not None:
                        # Try to determine the metric type from headers
                        metric_type = self._determine_metric_type(data[0] if row_idx > 0 else [])
                        
                        extracted.append({
                            'type': 'sector_metric',
                            'sector': 'Construction',
                            'metric_type': metric_type,
                            'value': amount,
                            'unit': unit or 'million',
                            'currency': currency or 'AUD',
                            'source_table': f"Page {page_num}" if page_num else None,
                            'source_file': source_file,
                            'context': row_text[:200]  # Store context for verification
                        })
        
        return extracted
    
    def _extract_generic_financial_data(self, table: Dict[str, Any], source_file: str, page_num: int) -> List[Dict[str, Any]]:
        """Extract generic financial data when table type is unclear."""
        extracted = []
        data = table.get('data', [])
        
        # Extract any clear financial metrics
        for row_idx, row in enumerate(data[1:], 1):  # Skip header
            for col_idx, cell in enumerate(row):
                cell_str = str(cell)
                amount, unit, currency = self._parse_amount(cell_str)
                
                if amount is not None and amount > 0:
                    # Try to get context from neighboring cells
                    label = self._get_cell_label(data, row_idx, col_idx)
                    
                    if label:
                        extracted.append({
                            'type': 'financial_metric',
                            'label': label,
                            'value': amount,
                            'unit': unit or 'units',
                            'currency': currency,
                            'source_table': f"Page {page_num}" if page_num else None,
                            'source_file': source_file
                        })
        
        return extracted
    
    def _find_column(self, headers: List[str], keywords: List[str]) -> Optional[int]:
        """Find column index matching keywords."""
        for i, header in enumerate(headers):
            header_lower = header.lower()
            if any(keyword in header_lower for keyword in keywords):
                return i
        return None
    
    def _find_amount_columns(self, headers: List[str]) -> Dict[int, Dict[str, str]]:
        """Find columns containing amounts."""
        amount_cols = {}
        
        for i, header in enumerate(headers):
            header_lower = header.lower()
            
            # Check for year patterns (e.g., "2023", "Sep 23")
            year_match = re.search(r'20\d{2}|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s*\d{2}', header_lower)
            if year_match:
                period = year_match.group()
                # Convert "Sep 23" to "2023"
                if ' ' in period and len(period.split()[1]) == 2:
                    year_part = period.split()[1]
                    period = f"20{year_part}"
            else:
                period = None
            
            # Check for metric types
            if any(term in header_lower for term in ['tce', 'exposure', 'committed']):
                amount_cols[i] = {'type': 'TCE', 'period': period}
            elif any(term in header_lower for term in ['revenue', 'income']):
                amount_cols[i] = {'type': 'Revenue', 'period': period}
            elif year_match and i not in amount_cols:
                # Column with just a year likely contains amounts
                amount_cols[i] = {'type': 'Value', 'period': period}
        
        return amount_cols
    
    def _parse_amount(self, amount_str: str) -> Tuple[Optional[float], Optional[str], Optional[str]]:
        """Parse amount string to extract value, unit, and currency."""
        amount_str = amount_str.strip()
        
        if not amount_str or amount_str == '-':
            return None, None, None
        
        # Try currency amount first
        currency_match = self.amount_patterns['currency_amount'].search(amount_str)
        if currency_match:
            value_str = currency_match.group(1).replace(',', '')
            value = float(value_str)
            
            # Determine unit
            unit = None
            if 'billion' in amount_str.lower() or ' b' in amount_str.lower():
                unit = 'billion'
            elif 'million' in amount_str.lower() or ' m' in amount_str.lower():
                unit = 'million'
            
            return value, unit, 'AUD'  # Default to AUD for $ amounts
        
        # Try numeric amount
        numeric_match = self.amount_patterns['numeric_amount'].search(amount_str)
        if numeric_match:
            value_str = numeric_match.group(1).replace(',', '')
            value = float(value_str)
            
            # Extract unit
            unit_match = re.search(r'(million|billion|m|b)', amount_str, re.IGNORECASE)
            unit = unit_match.group(1).lower() if unit_match else None
            if unit in ['m']:
                unit = 'million'
            elif unit in ['b']:
                unit = 'billion'
            
            return value, unit, None
        
        # Try plain number
        try:
            # Remove commas and try to parse
            clean_str = amount_str.replace(',', '').replace('$', '').strip()
            if clean_str and clean_str[0].isdigit():
                value = float(clean_str)
                return value, None, None
        except ValueError:
            pass
        
        return None, None, None
    
    def _parse_emissions_amount(self, amount_str: str) -> Tuple[Optional[float], Optional[str]]:
        """Parse emissions amount string."""
        amount_str = amount_str.strip()
        
        # Look for patterns like "0.3" or "5.4 MtCO2-e"
        match = re.search(r'([\d,]+(?:\.\d+)?)\s*(?:MtCO2-e|MtCO2|Mt)?', amount_str)
        if match:
            value = float(match.group(1).replace(',', ''))
            unit = 'MtCO2-e'
            return value, unit
        
        return None, None
    
    def _is_emissions_value(self, cell_str: str) -> bool:
        """Check if a cell contains emissions value."""
        return bool(re.search(r'\d+\.?\d*\s*(?:MtCO2|Mt|emissions)', cell_str, re.IGNORECASE))
    
    def _determine_metric_type(self, headers: List[str]) -> str:
        """Determine metric type from headers."""
        headers_text = ' '.join(str(h).lower() for h in headers)
        
        if 'tce' in headers_text or 'committed' in headers_text:
            return 'Total Committed Exposure'
        elif 'revenue' in headers_text:
            return 'Revenue'
        elif 'emission' in headers_text:
            return 'Emissions'
        elif 'sep 23' in headers_text or 'sep 22' in headers_text:
            # This is likely TCE data with date columns
            return 'Total Committed Exposure'
        else:
            return 'Financial Metric'
    
    def _get_cell_label(self, data: List[List[Any]], row_idx: int, col_idx: int) -> Optional[str]:
        """Get label for a cell from row header or column header."""
        # Try to get label from first cell of the row
        if row_idx < len(data) and data[row_idx]:
            row_label = str(data[row_idx][0]).strip()
            if row_label and not any(pattern.search(row_label) for pattern in self.amount_patterns.values()):
                return row_label
        
        # Try to get label from column header
        if data and col_idx < len(data[0]):
            col_label = str(data[0][col_idx]).strip()
            if col_label:
                return col_label
        
        return None
    
    def extract_from_content(self, content: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract financial data from PDF extraction content."""
        tables = content.get('tables', [])
        source_file = content.get('file_path', 'Unknown')
        
        # Get page numbers if available
        page_numbers = [table.get('page') for table in tables]
        
        return self.extract_financial_tables(tables, source_file, page_numbers)