"""
Robust PDF extractor for handling problematic PDFs like annual reports.
Includes timeout handling, chunked processing, and multiple fallback methods.
"""

import warnings
import time
import logging
import re
from typing import Dict, List, Optional, Any
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, TimeoutError
import multiprocessing
from dataclasses import dataclass

# Suppress PyMuPDF warnings
warnings.filterwarnings("ignore", message="Could get FontBBox")
warnings.filterwarnings("ignore", message="Cannot set stroke color")
warnings.filterwarnings("ignore", message="Cannot set gray")

import fitz  # PyMuPDF
import pdfplumber
from PyPDF2 import PdfReader

logger = logging.getLogger(__name__)


@dataclass
class PDFExtractionResult:
    """Result of PDF extraction"""
    text: str
    metadata: Dict[str, Any]
    errors: List[str]
    pages_processed: int
    sections: Dict[str, str]
    tables: List[Any]
    success: bool


class RobustPDFExtractor:
    """Robust PDF extraction with multiple fallback methods."""
    
    def __init__(self, timeout_per_page: int = 30, chunk_size: int = 10):
        self.timeout_per_page = timeout_per_page
        self.chunk_size = chunk_size
        
        # Suppress PyMuPDF display errors
        try:
            fitz.TOOLS.mupdf_display_errors(False)
        except:
            pass
    
    def extract_from_pdf(self, pdf_path: str, max_pages: Optional[int] = None) -> PDFExtractionResult:
        """
        Extract content from PDF with multiple fallback methods.
        Especially designed for problematic PDFs like annual reports.
        """
        result = PDFExtractionResult(
            text="",
            metadata={},
            errors=[],
            pages_processed=0,
            sections={},
            tables=[],
            success=False
        )
        
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            result.errors.append(f"File not found: {pdf_path}")
            return result
        
        # Try multiple extraction methods in order of preference
        methods = [
            ("PyMuPDF", self._extract_with_pymupdf),
            ("PDFPlumber", self._extract_with_pdfplumber),
            ("PyPDF2", self._extract_with_pypdf2),
            ("Chunked PyMuPDF", self._extract_with_pymupdf_chunks)
        ]
        
        for method_name, method in methods:
            try:
                logger.info(f"Attempting extraction with {method_name}")
                extracted = method(str(pdf_path), max_pages)
                
                if extracted and extracted.text.strip():
                    result = extracted
                    result.success = True
                    logger.info(f"Successfully extracted with {method_name}")
                    break
                    
            except Exception as e:
                error_msg = f"{method_name} failed: {str(e)}"
                result.errors.append(error_msg)
                logger.warning(error_msg)
                continue
        
        # Post-process text
        if result.text:
            result.text = self._clean_text(result.text)
            result.sections = self._extract_sections(result.text)
        
        return result
    
    def _extract_with_pymupdf(self, pdf_path: str, max_pages: Optional[int] = None) -> PDFExtractionResult:
        """Extract using PyMuPDF with timeout handling."""
        result = PDFExtractionResult(
            text="",
            metadata={},
            errors=[],
            pages_processed=0,
            sections={},
            tables=[],
            success=False
        )
        
        try:
            doc = fitz.open(pdf_path)
            result.metadata = doc.metadata or {}
            
            total_pages = min(len(doc), max_pages) if max_pages else len(doc)
            
            for page_num in range(total_pages):
                try:
                    # Use ThreadPoolExecutor for timeout per page
                    with ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(self._extract_page_pymupdf, doc, page_num)
                        page_text = future.result(timeout=self.timeout_per_page)
                        
                        if page_text:
                            result.text += page_text + "\n\n"
                            result.pages_processed += 1
                            
                except TimeoutError:
                    result.errors.append(f"Page {page_num} timed out")
                except Exception as e:
                    result.errors.append(f"Page {page_num}: {str(e)}")
            
            doc.close()
            
        except Exception as e:
            result.errors.append(f"Document error: {str(e)}")
        
        return result
    
    def _extract_page_pymupdf(self, doc, page_num: int) -> str:
        """Extract text from a single page using PyMuPDF."""
        page = doc[page_num]
        
        # Try different extraction methods
        try:
            # Method 1: Standard text extraction with flags
            text = page.get_text("text", flags=fitz.TEXT_PRESERVE_LIGATURES)
        except:
            try:
                # Method 2: Extract as dict and rebuild
                text_dict = page.get_text("dict")
                text = self._extract_text_from_dict(text_dict)
            except:
                # Method 3: Basic extraction
                text = page.get_text()
        
        return text
    
    def _extract_text_from_dict(self, text_dict: dict) -> str:
        """Extract text from PyMuPDF dict format."""
        text = ""
        for block in text_dict.get("blocks", []):
            if block.get("type") == 0:  # Text block
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text += span.get("text", "") + " "
                    text += "\n"
                text += "\n"
        return text
    
    def _extract_with_pymupdf_chunks(self, pdf_path: str, max_pages: Optional[int] = None) -> PDFExtractionResult:
        """Extract PDF in chunks to handle large files."""
        result = PDFExtractionResult(
            text="",
            metadata={},
            errors=[],
            pages_processed=0,
            sections={},
            tables=[],
            success=False
        )
        
        try:
            doc = fitz.open(pdf_path)
            result.metadata = doc.metadata or {}
            total_pages = min(len(doc), max_pages) if max_pages else len(doc)
            
            for start_page in range(0, total_pages, self.chunk_size):
                end_page = min(start_page + self.chunk_size, total_pages)
                
                try:
                    # Create a new document with subset of pages
                    chunk_doc = fitz.open()
                    chunk_doc.insert_pdf(doc, from_page=start_page, to_page=end_page-1)
                    
                    # Process chunk
                    chunk_text = ""
                    for page in chunk_doc:
                        try:
                            chunk_text += page.get_text() + "\n\n"
                            result.pages_processed += 1
                        except:
                            continue
                    
                    result.text += chunk_text
                    chunk_doc.close()
                    
                    # Small delay between chunks
                    time.sleep(0.1)
                    
                except Exception as e:
                    result.errors.append(f"Chunk {start_page}-{end_page}: {str(e)}")
            
            doc.close()
            
        except Exception as e:
            result.errors.append(f"Chunked extraction error: {str(e)}")
        
        return result
    
    def _extract_with_pdfplumber(self, pdf_path: str, max_pages: Optional[int] = None) -> PDFExtractionResult:
        """Extract using pdfplumber (good for tables)."""
        result = PDFExtractionResult(
            text="",
            metadata={},
            errors=[],
            pages_processed=0,
            sections={},
            tables=[],
            success=False
        )
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                result.metadata = pdf.metadata or {}
                total_pages = min(len(pdf.pages), max_pages) if max_pages else len(pdf.pages)
                
                for i in range(total_pages):
                    try:
                        page = pdf.pages[i]
                        
                        # Extract text
                        page_text = page.extract_text()
                        if page_text:
                            result.text += page_text + "\n\n"
                        
                        # Extract tables
                        tables = page.extract_tables()
                        if tables:
                            result.tables.extend(tables)
                        
                        result.pages_processed += 1
                        
                    except Exception as e:
                        result.errors.append(f"Page {i}: {str(e)}")
                        
        except Exception as e:
            result.errors.append(f"PDFPlumber error: {str(e)}")
        
        return result
    
    def _extract_with_pypdf2(self, pdf_path: str, max_pages: Optional[int] = None) -> PDFExtractionResult:
        """Extract using PyPDF2 as fallback."""
        result = PDFExtractionResult(
            text="",
            metadata={},
            errors=[],
            pages_processed=0,
            sections={},
            tables=[],
            success=False
        )
        
        try:
            reader = PdfReader(pdf_path)
            result.metadata = reader.metadata or {}
            
            total_pages = min(len(reader.pages), max_pages) if max_pages else len(reader.pages)
            
            for i in range(total_pages):
                try:
                    page = reader.pages[i]
                    page_text = page.extract_text()
                    
                    if page_text:
                        result.text += page_text + "\n\n"
                        result.pages_processed += 1
                        
                except Exception as e:
                    result.errors.append(f"Page {i}: {str(e)}")
                    
        except Exception as e:
            result.errors.append(f"PyPDF2 error: {str(e)}")
        
        return result
    
    def _clean_text(self, text: str) -> str:
        """Clean extracted text."""
        # Remove excessive whitespace
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            if line:
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
    def _extract_sections(self, text: str) -> Dict[str, str]:
        """Extract common sections from financial documents."""
        sections = {}
        
        # Common section patterns in annual reports
        section_patterns = {
            'executive_summary': r'(?i)(executive\s+summary|ceo\s+message|chairman.*message)',
            'financial_highlights': r'(?i)(financial\s+highlights|key\s+financials|performance\s+summary)',
            'risk_factors': r'(?i)(risk\s+factors|principal\s+risks|risk\s+management)',
            'financial_statements': r'(?i)(financial\s+statements|consolidated\s+statements)',
            'notes': r'(?i)(notes\s+to\s+.*financial\s+statements)',
        }
        
        lines = text.split('\n')
        current_section = None
        section_content = []
        
        for line in lines:
            # Check if this line starts a new section
            for section_name, pattern in section_patterns.items():
                if re.search(pattern, line):
                    # Save previous section
                    if current_section and section_content:
                        sections[current_section] = '\n'.join(section_content)
                    
                    # Start new section
                    current_section = section_name
                    section_content = [line]
                    break
            else:
                # Continue current section
                if current_section:
                    section_content.append(line)
        
        # Save last section
        if current_section and section_content:
            sections[current_section] = '\n'.join(section_content)
        
        return sections


# Parallel processing helper for extremely large documents
def process_pdf_parallel(pdf_path: str, max_workers: int = None) -> PDFExtractionResult:
    """Process PDF using parallel page extraction."""
    if max_workers is None:
        max_workers = multiprocessing.cpu_count()
    
    extractor = RobustPDFExtractor()
    
    # First, get page count
    try:
        doc = fitz.open(pdf_path)
        num_pages = len(doc)
        metadata = doc.metadata or {}
        doc.close()
    except:
        return extractor.extract_from_pdf(pdf_path)  # Fallback to sequential
    
    # Prepare page extraction tasks
    def extract_page(args):
        pdf_path, page_num = args
        try:
            doc = fitz.open(pdf_path)
            page = doc[page_num]
            text = page.get_text()
            doc.close()
            return page_num, text, None
        except Exception as e:
            return page_num, "", str(e)
    
    # Process pages in parallel
    texts = {}
    errors = []
    
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        args = [(pdf_path, i) for i in range(num_pages)]
        
        for page_num, text, error in executor.map(extract_page, args):
            if error:
                errors.append(f"Page {page_num}: {error}")
            else:
                texts[page_num] = text
    
    # Combine results
    combined_text = "\n\n".join([texts.get(i, "") for i in range(num_pages)])
    
    result = PDFExtractionResult(
        text=combined_text,
        metadata=metadata,
        errors=errors,
        pages_processed=len(texts),
        sections={},
        tables=[],
        success=bool(combined_text.strip())
    )
    
    return result