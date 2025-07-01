#!/usr/bin/env python3
"""
St.George PDS Directory Explorer
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
        logging.FileHandler('stgeorge_pds_explorer.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class StGeorgePDSExplorer:
    """Explorer for St.George PDS directories and similar document areas"""
    
    def __init__(self, base_path: str = "/Users/jaskew/workspace/Skynet/desktop/claude/westpac/agents/westpac_pdfs"):
        self.base_path = base_path
        self.base_url = "https://www.stgeorge.com.au"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        self.discovered_urls: Set[str] = set()
        
    def explore_potential_directories(self) -> List[str]:
        """Explore potential document directories"""
        logger.info("🔍 Exploring potential St.George document directories...")
        
        # Potential document directory paths
        directory_paths = [
            "/content/dam/stg/downloads/pds/",
            "/content/dam/stg/downloads/forms/",
            "/content/dam/stg/downloads/guides/", 
            "/content/dam/stg/downloads/brochures/",
            "/content/dam/stg/downloads/terms/",
            "/content/dam/stg/downloads/fees/",
            "/content/dam/stg/downloads/personal/",
            "/content/dam/stg/downloads/business/",
            "/content/dam/stg/downloads/corporate/",
            "/content/dam/stg/downloads/",
            "/content/dam/stg/documents/pds/",
            "/content/dam/stg/documents/forms/",
            "/content/dam/stg/documents/guides/",
            "/content/dam/stg/documents/",
            "/content/dam/public/stg/downloads/",
            "/content/dam/public/stg/documents/",
            "/docs/pdf/",
            "/documents/",
            "/downloads/",
        ]
        
        # Also try some specific document names in these directories
        common_documents = [
            "home-loan-pds.pdf",
            "personal-loan-pds.pdf", 
            "credit-card-pds.pdf",
            "deposit-products-pds.pdf",
            "investment-pds.pdf",
            "insurance-pds.pdf",
            "terms-and-conditions.pdf",
            "deposit-terms.pdf",
            "lending-terms.pdf",
            "fees-and-charges.pdf",
            "banking-code.pdf",
            "privacy-policy.pdf",
            "financial-services-guide.pdf",
            "target-market-determination.pdf",
        ]
        
        pdf_urls = []
        
        # Try each directory path
        for dir_path in directory_paths:
            try:
                logger.info(f"   Checking directory: {dir_path}")
                url = self.base_url + dir_path
                
                # Try to access the directory
                response = self.session.get(url, timeout=10)
                
                if response.status_code == 200:
                    logger.info(f"✅ Directory accessible: {dir_path}")
                    
                    # Try to parse as HTML to look for file listings
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # Look for PDF links in directory listing
                    pdf_links = soup.find_all('a', href=re.compile(r'\.pdf(?:\?|$)', re.I))
                    for link in pdf_links:
                        href = link.get('href')
                        if href:
                            if href.startswith('/'):
                                pdf_url = self.base_url + href
                            elif href.startswith('http'):
                                pdf_url = href
                            else:
                                pdf_url = urljoin(url, href)
                            
                            clean_url = pdf_url.split('?')[0]
                            if clean_url.lower().endswith('.pdf'):
                                pdf_urls.append(clean_url)
                                logger.info(f"   Found PDF: {os.path.basename(clean_url)}")
                
                # Also try common document names in this directory
                for doc in common_documents:
                    test_url = url.rstrip('/') + '/' + doc
                    pdf_urls.append(test_url)
                
                time.sleep(0.3)  # Rate limiting
                
            except Exception as e:
                logger.debug(f"Error checking {dir_path}: {e}")
                continue
        
        # Try some additional specific URLs based on patterns we've seen
        additional_urls = [
            "https://www.stgeorge.com.au/content/dam/stg/downloads/pds/home-loan-variable-rate-pds.pdf",
            "https://www.stgeorge.com.au/content/dam/stg/downloads/pds/home-loan-fixed-rate-pds.pdf",
            "https://www.stgeorge.com.au/content/dam/stg/downloads/pds/personal-loan-pds.pdf",
            "https://www.stgeorge.com.au/content/dam/stg/downloads/pds/credit-card-pds.pdf",
            "https://www.stgeorge.com.au/content/dam/stg/downloads/pds/transaction-account-pds.pdf",
            "https://www.stgeorge.com.au/content/dam/stg/downloads/pds/savings-account-pds.pdf",
            "https://www.stgeorge.com.au/content/dam/stg/downloads/pds/term-deposit-pds.pdf",
            "https://www.stgeorge.com.au/content/dam/stg/downloads/pds/investment-pds.pdf",
            "https://www.stgeorge.com.au/content/dam/stg/downloads/forms/home-loan-application.pdf",
            "https://www.stgeorge.com.au/content/dam/stg/downloads/forms/personal-loan-application.pdf",
            "https://www.stgeorge.com.au/content/dam/stg/downloads/forms/account-application.pdf",
            "https://www.stgeorge.com.au/content/dam/stg/downloads/terms/deposit-products-terms.pdf",
            "https://www.stgeorge.com.au/content/dam/stg/downloads/terms/lending-terms.pdf",
            "https://www.stgeorge.com.au/content/dam/stg/downloads/fees/personal-banking-fees.pdf",
            "https://www.stgeorge.com.au/content/dam/stg/downloads/fees/business-banking-fees.pdf",
            "https://www.stgeorge.com.au/content/dam/stg/downloads/guides/first-home-buyer-guide.pdf",
            "https://www.stgeorge.com.au/content/dam/stg/downloads/guides/investment-property-guide.pdf",
        ]
        
        pdf_urls.extend(additional_urls)
        
        # Remove duplicates
        unique_urls = list(set(pdf_urls))
        logger.info(f"📋 Found {len(unique_urls)} potential PDF URLs to test")
        
        return unique_urls
    
    def test_pdf_urls(self, urls: List[str]) -> List[str]:
        """Test which PDF URLs actually exist"""
        logger.info(f"🔗 Testing {len(urls)} PDF URLs for accessibility...")
        
        valid_urls = []
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_url = {executor.submit(self._test_url, url): url for url in urls}
            
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    is_valid = future.result()
                    if is_valid:
                        valid_urls.append(url)
                        filename = os.path.basename(urlparse(url).path)
                        logger.info(f"✅ Found: {filename}")
                except Exception as e:
                    logger.debug(f"Error testing {url}: {e}")
                
                time.sleep(0.1)  # Rate limiting
        
        logger.info(f"📊 Found {len(valid_urls)} accessible PDFs")
        return valid_urls
    
    def _test_url(self, url: str) -> bool:
        """Test if a URL returns a valid PDF"""
        try:
            response = self.session.head(url, timeout=10)
            if response.status_code == 200:
                # Check if it's actually a PDF
                content_type = response.headers.get('content-type', '').lower()
                if 'pdf' in content_type or url.lower().endswith('.pdf'):
                    return True
        except Exception:
            pass
        return False
    
    def download_pdfs(self, urls: List[str]) -> List[Dict[str, Any]]:
        """Download the discovered PDFs"""
        if not urls:
            return []
            
        logger.info(f"📥 Downloading {len(urls)} PDFs...")
        
        results = []
        
        for url in urls:
            filename = unquote(os.path.basename(urlparse(url).path))
            if not filename or not filename.endswith('.pdf'):
                filename = f"stgeorge_pds_{len(results)}.pdf"
            
            # Determine category
            category = self._categorize_pdf(filename)
            local_path = os.path.join(self.base_path, category, filename)
            
            # Skip if already exists
            if os.path.exists(local_path):
                logger.info(f"⏭️  Skipping {filename} (already exists)")
                continue
            
            # Download
            result = self._download_file(url, local_path)
            result["filename"] = filename
            result["category"] = category
            result["source"] = "stgeorge.com.au"
            results.append(result)
            
            if result["success"]:
                size_mb = result["size"] / (1024 * 1024)
                logger.info(f"✅ Downloaded: {filename} ({size_mb:.1f}MB)")
            else:
                logger.error(f"❌ Failed: {filename} - {result.get('error', 'Unknown error')}")
            
            time.sleep(0.2)  # Rate limiting
        
        return results
    
    def _download_file(self, url: str, local_path: str) -> Dict[str, Any]:
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
    
    def _categorize_pdf(self, filename: str) -> str:
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
        else:
            return 'misc'
    
    def run(self) -> Dict[str, Any]:
        """Run the PDS directory exploration"""
        start_time = datetime.now()
        logger.info("🚀 Starting St.George PDS Directory Explorer...")
        
        # Explore potential directories
        potential_urls = self.explore_potential_directories()
        
        # Test which URLs are valid
        valid_urls = self.test_pdf_urls(potential_urls)
        
        if not valid_urls:
            logger.info("❌ No accessible PDFs found in directories")
            return {"status": "complete", "new_downloads": 0}
        
        # Download the valid PDFs
        download_results = self.download_pdfs(valid_urls)
        
        # Count successes
        successful_downloads = sum(1 for r in download_results if r["success"])
        failed_downloads = len(download_results) - successful_downloads
        
        # Generate summary
        end_time = datetime.now()
        duration = end_time - start_time
        
        summary = {
            "status": "complete",
            "potential_urls_tested": len(potential_urls),
            "valid_urls_found": len(valid_urls),
            "download_attempts": len(download_results),
            "successful_downloads": successful_downloads,
            "failed_downloads": failed_downloads,
            "duration_seconds": duration.total_seconds(),
            "download_results": download_results
        }
        
        logger.info(f"✅ PDS Explorer completed!")
        logger.info(f"📊 Summary: {successful_downloads} successful downloads")
        logger.info(f"⏱️  Duration: {duration}")
        
        # Save results
        with open("stgeorge_pds_results.json", "w") as f:
            json.dump(summary, f, indent=2)
        
        return summary

def main():
    """Main entry point"""
    explorer = StGeorgePDSExplorer()
    results = explorer.run()
    print(f"\n✅ PDS Explorer completed! Downloaded {results['successful_downloads']} new PDFs")

if __name__ == "__main__":
    main()