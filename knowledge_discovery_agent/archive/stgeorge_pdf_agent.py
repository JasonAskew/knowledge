#!/usr/bin/env python3
"""
St.George Bank PDF Discovery and Download Agent
"""

import json
import os
import time
import requests
import hashlib
from datetime import datetime
from urllib.parse import urlparse, unquote, urljoin
from typing import List, Dict, Any, Optional
import logging
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('stgeorge_pdf_agent.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class PDFFile:
    """Represents a PDF file with metadata"""
    url: str
    filename: str
    category: str
    local_path: str
    file_size: Optional[int] = None
    download_time: Optional[str] = None
    checksum: Optional[str] = None
    source: str = "stgeorge.com.au"

class PDFCategorizer:
    """Handles PDF categorization logic"""
    
    CATEGORY_RULES = {
        'product-disclosure': [
            lambda f: 'pds' in f,
            lambda f: 'product' in f and 'disclosure' in f,
            lambda f: 'disclosure' in f and 'statement' in f,
            lambda f: 'fsg' in f,  # Financial Services Guide
        ],
        'legal-terms': [
            lambda f: 'terms' in f and 'conditions' in f,
            lambda f: 'tandc' in f,
            lambda f: 'agreement' in f,
            lambda f: 'tc_' in f or 'tcs' in f,
        ],
        'fees-charges': [
            lambda f: 'fee' in f or 'fees' in f,
            lambda f: 'charge' in f or 'charges' in f,
            lambda f: 'cost' in f or 'costs' in f,
            lambda f: 'pricing' in f,
        ],
        'forms': [
            lambda f: 'form' in f,
            lambda f: 'application' in f,
            lambda f: 'checklist' in f,
        ],
        'brochures': [
            lambda f: 'brochure' in f,
            lambda f: 'guide' in f,
            lambda f: 'fact' in f and 'sheet' in f,
        ],
        'annual-reports': [
            lambda f: 'annual' in f and 'report' in f,
        ],
        'sustainability': [
            lambda f: 'sustainability' in f,
            lambda f: 'climate' in f,
            lambda f: 'esg' in f,
        ],
        'policies': [
            lambda f: 'policy' in f or 'policies' in f,
            lambda f: 'code' in f,
            lambda f: 'governance' in f,
        ],
        'misc': []  # Default category
    }
    
    @classmethod
    def categorize(cls, filename: str) -> str:
        """Categorize PDF based on filename"""
        filename_lower = filename.lower()
        
        for category, rules in cls.CATEGORY_RULES.items():
            if any(rule(filename_lower) for rule in rules):
                return category
        
        return 'misc'

class StGeorgePDFAgent:
    """Agent to discover and download PDFs from St.George Bank website"""
    
    def __init__(self, base_path: str = "/Users/jaskew/workspace/Skynet/desktop/claude/westpac/agents/westpac_pdfs"):
        self.base_path = base_path
        self.base_url = "https://www.stgeorge.com.au"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        
        # Ensure base directory exists
        os.makedirs(base_path, exist_ok=True)
        
        # Create category directories
        categories = ['product-disclosure', 'legal-terms', 'fees-charges', 'forms', 'brochures', 
                     'annual-reports', 'sustainability', 'policies', 'misc']
        for category in categories:
            os.makedirs(os.path.join(base_path, category), exist_ok=True)
    
    def discover_pdf_urls(self) -> List[str]:
        """Discover PDF URLs on St.George website"""
        pdf_urls = set()
        
        # Define key pages to search for PDFs
        search_pages = [
            "/",
            "/personal",
            "/business", 
            "/corporate",
            "/about",
            "/about/corporate-information",
            "/about/corporate-information/annual-reports",
            "/about/corporate-information/sustainability",
            "/personal/bank-accounts",
            "/personal/home-loans", 
            "/personal/personal-loans",
            "/personal/credit-cards",
            "/personal/investment-services",
            "/business/bank-accounts",
            "/business/business-lending",
            "/business/business-credit-cards",
            "/business/merchant-services",
            "/business/international-services",
            "/corporate/transaction-banking",
            "/corporate/lending",
            "/corporate/treasury-markets",
            "/help-centre",
            "/help-centre/online-banking",
            "/help-centre/mobile-banking",
            "/help-centre/forms-documents"
        ]
        
        logger.info(f"🔍 Searching {len(search_pages)} pages for PDF links...")
        
        for page in search_pages:
            try:
                url = self.base_url + page
                logger.info(f"   Checking: {page}")
                
                response = self.session.get(url, timeout=10)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # Find all links to PDFs
                    pdf_links = soup.find_all('a', href=re.compile(r'\.pdf(?:\?|$)', re.I))
                    
                    for link in pdf_links:
                        href = link.get('href')
                        if href:
                            # Convert relative URLs to absolute
                            if href.startswith('/'):
                                pdf_url = self.base_url + href
                            elif href.startswith('http'):
                                pdf_url = href
                            else:
                                pdf_url = urljoin(url, href)
                            
                            # Clean URL (remove query parameters for deduplication)
                            clean_url = pdf_url.split('?')[0]
                            if clean_url.lower().endswith('.pdf'):
                                pdf_urls.add(clean_url)
                
                time.sleep(0.5)  # Rate limiting
                
            except Exception as e:
                logger.warning(f"Error checking {page}: {e}")
                continue
        
        # Additional pattern-based URL discovery
        pattern_urls = self._discover_pattern_urls()
        pdf_urls.update(pattern_urls)
        
        logger.info(f"📋 Discovered {len(pdf_urls)} unique PDF URLs")
        return sorted(list(pdf_urls))
    
    def _discover_pattern_urls(self) -> List[str]:
        """Discover PDFs using common URL patterns"""
        pattern_urls = []
        
        # Common St.George PDF URL patterns
        base_patterns = [
            "https://www.stgeorge.com.au/content/dam/stg/downloads/personal/",
            "https://www.stgeorge.com.au/content/dam/stg/downloads/business/",
            "https://www.stgeorge.com.au/content/dam/stg/downloads/corporate/",
            "https://www.stgeorge.com.au/content/dam/stg/documents/",
            "https://www.stgeorge.com.au/content/dam/public/stg/documents/",
        ]
        
        # Common document names
        common_docs = [
            "terms-and-conditions.pdf",
            "deposit-products-terms-conditions.pdf", 
            "lending-terms-conditions.pdf",
            "credit-card-terms-conditions.pdf",
            "fees-charges-guide.pdf",
            "deposit-rates.pdf",
            "lending-rates.pdf",
            "financial-services-guide.pdf",
            "product-disclosure-statement.pdf",
            "annual-report.pdf",
            "sustainability-report.pdf",
            "home-loan-application.pdf",
            "personal-loan-application.pdf",
            "business-loan-application.pdf",
            "account-application.pdf",
            "credit-card-application.pdf",
        ]
        
        # Try pattern combinations
        for base_pattern in base_patterns:
            for doc in common_docs:
                pattern_urls.append(base_pattern + doc)
        
        return pattern_urls
    
    def download_file(self, url: str, local_path: str) -> Dict[str, Any]:
        """Download a single PDF file"""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            with open(local_path, 'wb') as f:
                f.write(response.content)
            
            # Calculate checksum
            checksum = hashlib.md5(response.content).hexdigest()
            
            return {
                "success": True,
                "url": url,
                "local_path": local_path,
                "size": len(response.content),
                "checksum": checksum,
                "download_time": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "success": False,
                "url": url,
                "local_path": local_path,
                "error": str(e)
            }
    
    def create_pdf_files(self, urls: List[str]) -> List[PDFFile]:
        """Create PDFFile objects from URLs"""
        pdf_files = []
        
        for url in urls:
            filename = unquote(os.path.basename(urlparse(url).path))
            if not filename or not filename.endswith('.pdf'):
                filename = f"stgeorge_doc_{len(pdf_files)}.pdf"
            
            category = PDFCategorizer.categorize(filename)
            local_path = os.path.join(self.base_path, category, filename)
            
            pdf_files.append(PDFFile(
                url=url,
                filename=filename,
                category=category,
                local_path=local_path,
                source="stgeorge.com.au"
            ))
        
        return pdf_files
    
    def download_pdfs(self, pdf_files: List[PDFFile]) -> List[Dict[str, Any]]:
        """Download PDFs with concurrent processing"""
        results = []
        
        logger.info(f"📥 Starting download of {len(pdf_files)} PDFs...")
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_pdf = {
                executor.submit(self.download_file, pdf.url, pdf.local_path): pdf
                for pdf in pdf_files
            }
            
            for future in as_completed(future_to_pdf):
                pdf = future_to_pdf[future]
                try:
                    result = future.result()
                    result["filename"] = pdf.filename
                    result["category"] = pdf.category
                    result["source"] = pdf.source
                    results.append(result)
                    
                    if result["success"]:
                        size_mb = result["size"] / (1024 * 1024)
                        logger.info(f"✅ Downloaded: {pdf.filename} ({size_mb:.1f}MB)")
                    else:
                        logger.error(f"❌ Failed: {pdf.filename} - {result.get('error', 'Unknown error')}")
                
                except Exception as e:
                    logger.error(f"❌ Exception downloading {pdf.filename}: {e}")
                    results.append({
                        "success": False,
                        "url": pdf.url,
                        "filename": pdf.filename,
                        "error": str(e)
                    })
                
                # Rate limiting
                time.sleep(0.2)
        
        return results
    
    def run(self) -> Dict[str, Any]:
        """Run the St.George PDF discovery and download process"""
        start_time = datetime.now()
        logger.info("🚀 Starting St.George PDF Agent...")
        
        # Discover PDFs
        urls = self.discover_pdf_urls()
        
        if not urls:
            logger.warning("⚠️  No PDF URLs discovered")
            return {"status": "complete", "new_downloads": 0}
        
        # Create PDF objects
        pdf_files = self.create_pdf_files(urls)
        
        # Filter out already existing files
        new_pdf_files = []
        for pdf in pdf_files:
            if not os.path.exists(pdf.local_path):
                new_pdf_files.append(pdf)
            else:
                logger.info(f"⏭️  Skipping {pdf.filename} (already exists)")
        
        logger.info(f"📥 Will attempt to download {len(new_pdf_files)} new PDFs")
        
        if not new_pdf_files:
            logger.info("✅ All St.George PDFs already downloaded!")
            return {"status": "complete", "new_downloads": 0}
        
        # Download PDFs
        download_results = self.download_pdfs(new_pdf_files)
        
        # Count successes
        successful_downloads = sum(1 for r in download_results if r["success"])
        failed_downloads = len(download_results) - successful_downloads
        
        # Generate summary
        end_time = datetime.now()
        duration = end_time - start_time
        
        summary = {
            "status": "complete",
            "total_urls_discovered": len(urls),
            "new_downloads_attempted": len(new_pdf_files),
            "successful_downloads": successful_downloads,
            "failed_downloads": failed_downloads,
            "duration_seconds": duration.total_seconds(),
            "download_results": download_results
        }
        
        logger.info(f"✅ St.George PDF Agent completed!")
        logger.info(f"📊 Summary: {successful_downloads} successful, {failed_downloads} failed")
        logger.info(f"⏱️  Duration: {duration}")
        
        # Save results
        with open("stgeorge_pdfs_results.json", "w") as f:
            json.dump(summary, f, indent=2)
        
        return summary

def main():
    """Main entry point"""
    agent = StGeorgePDFAgent()
    results = agent.run()
    print(f"\n✅ Agent completed! Downloaded {results['successful_downloads']} new PDFs from St.George Bank")

if __name__ == "__main__":
    main()