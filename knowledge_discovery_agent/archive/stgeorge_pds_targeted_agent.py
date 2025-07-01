#!/usr/bin/env python3
"""
Targeted St.George PDS Agent using known patterns from domains_westpac_fm
"""

import json
import os
import time
import requests
import hashlib
from datetime import datetime
from urllib.parse import urlparse, unquote
from typing import List, Dict, Any, Optional
import logging
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('stgeorge_pds_targeted.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class StGeorgeTargetedPDSAgent:
    """Targeted agent to find St.George PDFs using known patterns"""
    
    def __init__(self, base_path: str = "/Users/jaskew/workspace/Skynet/desktop/claude/westpac/agents/westpac_pdfs"):
        self.base_path = base_path
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        
    def generate_potential_urls(self) -> List[str]:
        """Generate potential URLs based on known patterns"""
        logger.info("🎯 Generating targeted St.George PDF URLs...")
        
        base_url = "https://www.stgeorge.com.au/content/dam/stg/downloads/pds/"
        
        # We know SGB-FgnCurrencyAccountTC.pdf exists, so let's build patterns from domains_westpac_fm
        # that show St.George (SGB) document patterns
        
        potential_files = [
            # Known working file
            "SGB-FgnCurrencyAccountTC.pdf",
            
            # Foreign Exchange products (based on domains_westpac_fm patterns)
            "SGB-FXSwapPDS.pdf",
            "SGB-FXTransactionPDS.pdf", 
            "SGB-FlexiForwardPDS.pdf",
            "SGB-ForeignExchangeOptionPDS.pdf",
            "SGB-ParticipatingForwardPDS.pdf",
            "SGB-RangeForwardPDS.pdf",
            "SGB-BonusForwardContractPIS.pdf",
            "SGB-DualCurrencyInvestmentPIS.pdf",
            "SGB-EnhancedForwardContractPIS.pdf",
            "SGB-Knock-OutSmartForwardContractPIS.pdf",
            "SGB-ResetFowardContractPIS.pdf",
            "SGB-TargetForwardContractPIS.pdf",
            "SGB-WindowSmartForwardContractPIS.pdf",
            
            # Interest Rate products
            "SGB-InterestRateSwapPIS.pdf",
            "SGB_Range_PIS_0523.pdf",
            "SGB_Rebate_PIS_0523.pdf",
            "SGB-callable-swap.pdf",
            "SGB-interest-rate-swaption.pdf",
            "STG-interest-rate-cap-floors-collars_pis.pdf",
            
            # Term deposits and lending
            "SGB-TLDProductInformationStatement.pdf",
            "SGB-ForeignCurrencyTermDepositPDS_Mar_2020.pdf",
            "SGB Fixed Rate BBBL 0523.pdf",
            "SGB Fixed Rate Bill 0523.pdf",
            "STG Forward Start Security Agreement 1123.pdf",
            "USTLD_ProductInformationStatement_SGB.pdf",
            
            # Try variations without SGB prefix (might be stored differently)
            "FgnCurrencyAccountTC.pdf",
            "FXSwapPDS.pdf",
            "FXTransactionPDS.pdf",
            "FlexiForwardPDS.pdf",
            "ForeignExchangeOptionPDS.pdf",
            "ParticipatingForwardPDS.pdf",
            "RangeForwardPDS.pdf",
            "InterestRateSwapPIS.pdf",
            "TLDProductInformationStatement.pdf",
            
            # Standard banking product PDS files
            "home-loan-pds.pdf",
            "personal-loan-pds.pdf", 
            "credit-card-pds.pdf",
            "transaction-account-pds.pdf",
            "savings-account-pds.pdf",
            "term-deposit-pds.pdf",
            "business-loan-pds.pdf",
            "overdraft-pds.pdf",
            "line-of-credit-pds.pdf",
            "investment-loan-pds.pdf",
            
            # Try St.George specific naming
            "stg-home-loan-pds.pdf",
            "stg-personal-loan-pds.pdf",
            "stg-credit-card-pds.pdf",
            "stg-transaction-account-pds.pdf",
            "stg-savings-account-pds.pdf",
            "stg-term-deposit-pds.pdf",
            "stg-business-loan-pds.pdf",
            
            # Financial Services Guides
            "financial-services-guide.pdf",
            "fsg.pdf",
            "SGB-fsg.pdf",
            "stg-fsg.pdf",
            
            # Terms and conditions
            "terms-and-conditions.pdf",
            "deposit-terms-conditions.pdf",
            "lending-terms-conditions.pdf",
            "SGB-terms-conditions.pdf",
            
            # Target Market Determinations (newer regulatory requirement)
            "home-loan-tmd.pdf",
            "personal-loan-tmd.pdf",
            "credit-card-tmd.pdf",
            "SGB-home-loan-tmd.pdf",
            "SGB-personal-loan-tmd.pdf",
            "SGB-credit-card-tmd.pdf",
        ]
        
        # Also try different directory paths
        additional_paths = [
            "https://www.stgeorge.com.au/content/dam/stg/downloads/",
            "https://www.stgeorge.com.au/content/dam/stg/documents/pds/",
            "https://www.stgeorge.com.au/content/dam/stg/documents/",
            "https://www.stgeorge.com.au/content/dam/public/stg/downloads/pds/",
            "https://www.stgeorge.com.au/content/dam/public/stg/documents/pds/",
        ]
        
        urls = []
        
        # Add base PDS directory files
        for file in potential_files:
            urls.append(base_url + file)
        
        # Add files in other potential directories
        for path in additional_paths:
            for file in potential_files[:20]:  # Try key files in other dirs
                urls.append(path + file)
        
        logger.info(f"📋 Generated {len(urls)} potential URLs to test")
        return urls
    
    def test_and_download_pdfs(self, urls: List[str]) -> Dict[str, Any]:
        """Test URLs and download valid PDFs"""
        logger.info(f"🔗 Testing and downloading from {len(urls)} URLs...")
        
        results = []
        successful_downloads = 0
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_url = {executor.submit(self._test_and_download, url): url for url in urls}
            
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                        if result["success"]:
                            successful_downloads += 1
                            size_mb = result["size"] / (1024 * 1024)
                            logger.info(f"✅ Downloaded: {result['filename']} ({size_mb:.1f}MB)")
                        else:
                            logger.debug(f"❌ Failed: {result['filename']} - {result.get('error', 'Unknown error')}")
                except Exception as e:
                    logger.debug(f"Exception with {url}: {e}")
                
                time.sleep(0.1)  # Rate limiting
        
        summary = {
            "status": "complete",
            "urls_tested": len(urls),
            "successful_downloads": successful_downloads,
            "failed_downloads": len(results) - successful_downloads,
            "download_results": results
        }
        
        return summary
    
    def _test_and_download(self, url: str) -> Optional[Dict[str, Any]]:
        """Test if URL exists and download if it does"""
        try:
            # Test with HEAD request first
            response = self.session.head(url, timeout=10)
            
            if response.status_code == 200:
                # File exists, now download it
                filename = unquote(os.path.basename(urlparse(url).path))
                category = self._categorize_pdf(filename)
                local_path = os.path.join(self.base_path, category, filename)
                
                # Skip if already exists
                if os.path.exists(local_path):
                    return None
                
                # Download the file
                download_response = self.session.get(url, timeout=30)
                download_response.raise_for_status()
                
                # Ensure directory exists
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                
                with open(local_path, 'wb') as f:
                    f.write(download_response.content)
                
                # Calculate checksum
                checksum = hashlib.md5(download_response.content).hexdigest()
                
                return {
                    "success": True,
                    "url": url,
                    "filename": filename,
                    "local_path": local_path,
                    "category": category,
                    "size": len(download_response.content),
                    "checksum": checksum,
                    "download_time": datetime.now().isoformat(),
                    "source": "stgeorge.com.au"
                }
            
        except Exception as e:
            filename = unquote(os.path.basename(urlparse(url).path))
            return {
                "success": False,
                "url": url,
                "filename": filename,
                "error": str(e)
            }
        
        return None
    
    def _categorize_pdf(self, filename: str) -> str:
        """Categorize PDF based on filename"""
        filename_lower = filename.lower()
        
        if any(term in filename_lower for term in ['pds', 'pis', 'disclosure', 'fsg']):
            return 'product-disclosure'
        elif any(term in filename_lower for term in ['terms', 'conditions', 'tc']):
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
        """Run the targeted PDS discovery"""
        start_time = datetime.now()
        logger.info("🚀 Starting Targeted St.George PDS Agent...")
        
        # Generate potential URLs
        urls = self.generate_potential_urls()
        
        # Test and download
        results = self.test_and_download_pdfs(urls)
        
        # Add timing info
        end_time = datetime.now()
        duration = end_time - start_time
        results["duration_seconds"] = duration.total_seconds()
        
        logger.info(f"✅ Targeted PDS Agent completed!")
        logger.info(f"📊 Summary: {results['successful_downloads']} successful downloads")
        logger.info(f"⏱️  Duration: {duration}")
        
        # Save results
        with open("stgeorge_targeted_pds_results.json", "w") as f:
            json.dump(results, f, indent=2)
        
        return results

def main():
    """Main entry point"""
    agent = StGeorgeTargetedPDSAgent()
    results = agent.run()
    print(f"\n✅ Targeted agent completed! Downloaded {results['successful_downloads']} new PDFs")

if __name__ == "__main__":
    main()