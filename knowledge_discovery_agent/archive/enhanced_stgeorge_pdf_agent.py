#!/usr/bin/env python3
"""
Enhanced St.George Bank PDF Discovery Agent with deeper search capabilities
"""

import json
import os
import time
import requests
import hashlib
from datetime import datetime
from urllib.parse import urlparse, unquote, urljoin
from typing import List, Dict, Any, Optional, Set
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
        logging.FileHandler('enhanced_stgeorge_pdf_agent.log'),
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

class EnhancedStGeorgePDFAgent:
    """Enhanced agent to discover and download PDFs from St.George Bank website"""
    
    def __init__(self, base_path: str = "/Users/jaskew/workspace/Skynet/desktop/claude/westpac/agents/westpac_pdfs"):
        self.base_path = base_path
        self.base_url = "https://www.stgeorge.com.au"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        self.discovered_urls: Set[str] = set()
        
        # Load existing inventory to avoid re-downloading
        self.existing_files = self._load_existing_files()
        
    def _load_existing_files(self) -> Set[str]:
        """Load existing filenames to avoid duplicates"""
        existing = set()
        if os.path.exists(self.base_path):
            for root, dirs, files in os.walk(self.base_path):
                for file in files:
                    if file.endswith('.pdf'):
                        existing.add(file.lower())
        return existing
    
    def discover_pdfs_comprehensive(self) -> List[str]:
        """Comprehensive PDF discovery using multiple strategies"""
        logger.info("🔍 Starting comprehensive St.George PDF discovery...")
        
        # Strategy 1: Deep website crawling
        self._crawl_website_deeply()
        
        # Strategy 2: Search for known document types
        self._search_known_document_types()
        
        # Strategy 3: Explore help and support sections
        self._explore_help_sections()
        
        # Strategy 4: Look for regulatory and compliance documents
        self._search_regulatory_documents()
        
        # Strategy 5: Search investor relations
        self._search_investor_relations()
        
        logger.info(f"📋 Total unique PDFs discovered: {len(self.discovered_urls)}")
        return sorted(list(self.discovered_urls))
    
    def _crawl_website_deeply(self):
        """Deep crawl of St.George website sections"""
        deep_search_pages = [
            # Main sections
            "/",
            "/personal", "/personal/bank-accounts", "/personal/savings-accounts",
            "/personal/transaction-accounts", "/personal/term-deposits", 
            "/personal/home-loans", "/personal/investment-home-loans",
            "/personal/personal-loans", "/personal/car-loans",
            "/personal/credit-cards", "/personal/travel-money",
            "/personal/insurance", "/personal/investment-services",
            
            # Business sections
            "/business", "/business/bank-accounts", "/business/business-lending",
            "/business/equipment-finance", "/business/business-credit-cards",
            "/business/merchant-services", "/business/international-services",
            "/business/business-insurance", "/business/payroll-services",
            
            # Corporate sections  
            "/corporate", "/corporate/transaction-banking", "/corporate/lending",
            "/corporate/treasury-markets", "/corporate/trade-finance",
            "/corporate/cash-management", "/corporate/foreign-exchange",
            
            # About and corporate info
            "/about", "/about/corporate-information", 
            "/about/corporate-information/annual-reports",
            "/about/corporate-information/sustainability",
            "/about/corporate-information/investor-centre",
            "/about/corporate-information/media-centre",
            "/about/corporate-information/governance",
            "/about/careers", "/about/community",
            
            # Help and support
            "/help-centre", "/help-centre/online-banking", "/help-centre/mobile-banking",
            "/help-centre/security", "/help-centre/complaints", "/help-centre/accessibility",
            "/help-centre/forms-documents", "/help-centre/rates-fees",
            "/help-centre/contact-us", "/help-centre/branch-atm-locator",
            
            # Additional areas
            "/rates-fees", "/forms-documents", "/security", "/digital-banking",
            "/tools-calculators", "/financial-planning", "/retirement-planning"
        ]
        
        logger.info(f"🌐 Deep crawling {len(deep_search_pages)} St.George pages...")
        
        for page in deep_search_pages:
            self._extract_pdfs_from_page(page)
            time.sleep(0.3)  # Rate limiting
    
    def _extract_pdfs_from_page(self, page_path: str):
        """Extract PDF links from a specific page"""
        try:
            url = self.base_url + page_path
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Find all PDF links
                pdf_links = soup.find_all('a', href=re.compile(r'\.pdf(?:\?|$)', re.I))
                
                for link in pdf_links:
                    href = link.get('href')
                    if href:
                        pdf_url = self._normalize_url(href, url)
                        if pdf_url and pdf_url.lower().endswith('.pdf'):
                            self.discovered_urls.add(pdf_url.split('?')[0])
                
                # Also look for embedded documents and iframes
                iframes = soup.find_all('iframe', src=re.compile(r'\.pdf(?:\?|$)', re.I))
                for iframe in iframes:
                    src = iframe.get('src')
                    if src:
                        pdf_url = self._normalize_url(src, url)
                        if pdf_url:
                            self.discovered_urls.add(pdf_url.split('?')[0])
                            
        except Exception as e:
            logger.debug(f"Error extracting PDFs from {page_path}: {e}")
    
    def _normalize_url(self, href: str, base_url: str) -> Optional[str]:
        """Normalize and validate PDF URL"""
        if href.startswith('/'):
            return self.base_url + href
        elif href.startswith('http'):
            return href
        else:
            return urljoin(base_url, href)
    
    def _search_known_document_types(self):
        """Search for known St.George document types"""
        logger.info("📄 Searching for known document types...")
        
        # Known St.George document patterns based on their URL structure
        known_patterns = [
            # Terms and conditions
            "https://www.stgeorge.com.au/content/dam/stg/downloads/personal/deposit-products-terms-conditions.pdf",
            "https://www.stgeorge.com.au/content/dam/stg/downloads/personal/lending-terms-conditions.pdf",
            "https://www.stgeorge.com.au/content/dam/stg/downloads/business/business-banking-terms-conditions.pdf",
            
            # Product disclosure statements
            "https://www.stgeorge.com.au/content/dam/stg/downloads/personal/home-loan-pds.pdf",
            "https://www.stgeorge.com.au/content/dam/stg/downloads/personal/personal-loan-pds.pdf",
            "https://www.stgeorge.com.au/content/dam/stg/downloads/personal/credit-card-pds.pdf",
            "https://www.stgeorge.com.au/content/dam/stg/downloads/personal/insurance-pds.pdf",
            
            # Fees and charges
            "https://www.stgeorge.com.au/content/dam/stg/downloads/personal/personal-banking-fees.pdf",
            "https://www.stgeorge.com.au/content/dam/stg/downloads/business/business-banking-fees.pdf",
            "https://www.stgeorge.com.au/content/dam/stg/downloads/personal/lending-fees.pdf",
            "https://www.stgeorge.com.au/content/dam/stg/downloads/personal/home-loan-fees.pdf",
            
            # Application forms
            "https://www.stgeorge.com.au/content/dam/stg/downloads/personal/home-loan-application.pdf",
            "https://www.stgeorge.com.au/content/dam/stg/downloads/personal/personal-loan-application.pdf",
            "https://www.stgeorge.com.au/content/dam/stg/downloads/business/business-loan-application.pdf",
            "https://www.stgeorge.com.au/content/dam/stg/downloads/personal/account-opening-form.pdf",
            
            # Financial services guides
            "https://www.stgeorge.com.au/content/dam/stg/downloads/personal/financial-services-guide.pdf",
            "https://www.stgeorge.com.au/content/dam/stg/downloads/business/financial-services-guide.pdf",
            "https://www.stgeorge.com.au/content/dam/stg/downloads/personal/investment-fsg.pdf",
            
            # Brochures and guides
            "https://www.stgeorge.com.au/content/dam/stg/downloads/personal/first-home-buyer-guide.pdf",
            "https://www.stgeorge.com.au/content/dam/stg/downloads/personal/investment-property-guide.pdf",
            "https://www.stgeorge.com.au/content/dam/stg/downloads/business/business-banking-guide.pdf",
            "https://www.stgeorge.com.au/content/dam/stg/downloads/personal/retirement-planning-guide.pdf",
        ]
        
        for url in known_patterns:
            self.discovered_urls.add(url)
    
    def _explore_help_sections(self):
        """Explore help center and documentation sections"""
        logger.info("❓ Exploring help and documentation sections...")
        
        help_sections = [
            "/help-centre/forms-documents",
            "/help-centre/rates-fees", 
            "/help-centre/terms-conditions",
            "/help-centre/complaints-resolution",
            "/help-centre/privacy-policy",
            "/help-centre/accessibility",
            "/help-centre/banking-code-practice",
            "/help-centre/financial-difficulty",
            "/digital-banking/security",
            "/digital-banking/getting-started"
        ]
        
        for section in help_sections:
            self._extract_pdfs_from_page(section)
            time.sleep(0.2)
    
    def _search_regulatory_documents(self):
        """Search for regulatory and compliance documents"""
        logger.info("⚖️ Searching for regulatory documents...")
        
        regulatory_urls = [
            "https://www.stgeorge.com.au/content/dam/stg/downloads/corporate/annual-report-2023.pdf",
            "https://www.stgeorge.com.au/content/dam/stg/downloads/corporate/annual-report-2022.pdf",
            "https://www.stgeorge.com.au/content/dam/stg/downloads/corporate/annual-report-2021.pdf", 
            "https://www.stgeorge.com.au/content/dam/stg/downloads/corporate/sustainability-report.pdf",
            "https://www.stgeorge.com.au/content/dam/stg/downloads/corporate/corporate-governance.pdf",
            "https://www.stgeorge.com.au/content/dam/stg/downloads/corporate/code-of-conduct.pdf",
            "https://www.stgeorge.com.au/content/dam/stg/downloads/corporate/privacy-policy.pdf",
            "https://www.stgeorge.com.au/content/dam/stg/downloads/corporate/whistleblower-policy.pdf",
            "https://www.stgeorge.com.au/content/dam/stg/downloads/corporate/modern-slavery-statement.pdf",
        ]
        
        for url in regulatory_urls:
            self.discovered_urls.add(url)
    
    def _search_investor_relations(self):
        """Search investor relations documents"""
        logger.info("📈 Searching investor relations documents...")
        
        # Try to find investor documents
        investor_pages = [
            "/about/corporate-information/investor-centre",
            "/about/corporate-information/annual-reports", 
            "/about/corporate-information/financial-results",
            "/about/corporate-information/asx-announcements"
        ]
        
        for page in investor_pages:
            self._extract_pdfs_from_page(page)
    
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
    
    def categorize_pdf(self, filename: str) -> str:
        """Categorize PDF based on filename"""
        filename_lower = filename.lower()
        
        if any(term in filename_lower for term in ['pds', 'disclosure', 'fsg']):
            return 'product-disclosure'
        elif any(term in filename_lower for term in ['terms', 'conditions', 'tandc']):
            return 'legal-terms'
        elif any(term in filename_lower for term in ['fee', 'fees', 'charge', 'charges']):
            return 'fees-charges'
        elif any(term in filename_lower for term in ['application', 'form']):
            return 'forms'
        elif any(term in filename_lower for term in ['guide', 'brochure', 'fact']):
            return 'brochures'
        elif any(term in filename_lower for term in ['annual', 'report']):
            return 'annual-reports'
        elif any(term in filename_lower for term in ['sustainability', 'climate', 'esg']):
            return 'sustainability'
        elif any(term in filename_lower for term in ['policy', 'governance', 'code']):
            return 'policies'
        else:
            return 'misc'
    
    def create_pdf_files(self, urls: List[str]) -> List[PDFFile]:
        """Create PDFFile objects from URLs"""
        pdf_files = []
        
        for url in urls:
            filename = unquote(os.path.basename(urlparse(url).path))
            if not filename or not filename.endswith('.pdf'):
                filename = f"stgeorge_doc_{len(pdf_files)}.pdf"
            
            # Skip if we already have this file
            if filename.lower() in self.existing_files:
                continue
                
            category = self.categorize_pdf(filename)
            local_path = os.path.join(self.base_path, category, filename)
            
            # Skip if file already exists
            if os.path.exists(local_path):
                continue
            
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
        
        logger.info(f"📥 Starting download of {len(pdf_files)} new PDFs...")
        
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
        """Run the enhanced St.George PDF discovery and download process"""
        start_time = datetime.now()
        logger.info("🚀 Starting Enhanced St.George PDF Agent...")
        
        # Discover PDFs using comprehensive strategies
        urls = self.discover_pdfs_comprehensive()
        
        if not urls:
            logger.warning("⚠️  No new PDF URLs discovered")
            return {"status": "complete", "new_downloads": 0}
        
        # Create PDF objects (filtering out existing files)
        pdf_files = self.create_pdf_files(urls)
        
        logger.info(f"📥 Will attempt to download {len(pdf_files)} new PDFs")
        
        if not pdf_files:
            logger.info("✅ All discovered St.George PDFs already exist!")
            return {"status": "complete", "new_downloads": 0}
        
        # Download PDFs
        download_results = self.download_pdfs(pdf_files)
        
        # Count successes
        successful_downloads = sum(1 for r in download_results if r["success"])
        failed_downloads = len(download_results) - successful_downloads
        
        # Generate summary
        end_time = datetime.now()
        duration = end_time - start_time
        
        summary = {
            "status": "complete",
            "total_urls_discovered": len(urls),
            "new_downloads_attempted": len(pdf_files),
            "successful_downloads": successful_downloads,
            "failed_downloads": failed_downloads,
            "duration_seconds": duration.total_seconds(),
            "download_results": download_results
        }
        
        logger.info(f"✅ Enhanced St.George PDF Agent completed!")
        logger.info(f"📊 Summary: {successful_downloads} successful, {failed_downloads} failed")
        logger.info(f"⏱️  Duration: {duration}")
        
        # Save results
        with open("enhanced_stgeorge_pdfs_results.json", "w") as f:
            json.dump(summary, f, indent=2)
        
        return summary

def main():
    """Main entry point"""
    agent = EnhancedStGeorgePDFAgent()
    results = agent.run()
    print(f"\n✅ Enhanced agent completed! Downloaded {results['successful_downloads']} new PDFs from St.George Bank")

if __name__ == "__main__":
    main()