#!/usr/bin/env python3
"""
Focused PDF Agent to download the 50 missing files from domains_westpac_red
"""

import json
import os
import time
import requests
import hashlib
from datetime import datetime, timedelta
from urllib.parse import urlparse, unquote
from typing import List, Dict, Any, Optional
import logging
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('missing_pdfs_agent.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class DownloadLimits:
    """Configuration for download limits"""
    max_files_per_sync: Optional[int] = None
    max_files_per_category: Optional[int] = None
    max_total_size_mb: Optional[int] = None
    max_file_size_mb: Optional[int] = 100
    priority_categories: List[str] = None
    
    def __post_init__(self):
        if self.priority_categories is None:
            self.priority_categories = [
                'product-disclosure',
                'annual-reports', 
                'sustainability', 
                'policies',
                'legal-terms'
            ]

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
    last_modified: Optional[str] = None
    priority: int = 5

class PDFCategorizer:
    """Handles PDF categorization logic with priority assignment"""
    
    CATEGORY_RULES = {
        'product-disclosure': [
            lambda f: 'pds' in f,
            lambda f: 'product' in f and 'disclosure' in f,
            lambda f: 'fsr_' in f,
            lambda f: 'disclosure' in f and ('statement' in f or 'document' in f),
        ],
        'legal-terms': [
            lambda f: 'terms' in f and 'conditions' in f,
            lambda f: 'tandc' in f,
            lambda f: 'agreement' in f,
            lambda f: 'tc_' in f or 'tcs' in f,
        ],
        'policies': [
            lambda f: 'policy' in f or 'policies' in f,
            lambda f: 'code-of-conduct' in f,
            lambda f: 'governance' in f,
        ],
        'forms': [
            lambda f: 'form' in f,
            lambda f: 'application' in f,
            lambda f: 'checklist' in f,
        ],
        'fees-charges': [
            lambda f: 'fee' in f or 'fees' in f,
            lambda f: 'charge' in f or 'charges' in f,
            lambda f: 'cost' in f or 'costs' in f,
        ],
        'misc': []  # Default category
    }
    
    PRIORITY_MAP = {
        'product-disclosure': 1,
        'legal-terms': 2,
        'policies': 3,
        'forms': 4,
        'fees-charges': 5,
        'misc': 10
    }
    
    @classmethod
    def categorize_with_priority(cls, filename: str) -> tuple[str, int]:
        """Categorize PDF and assign priority based on filename"""
        filename_lower = filename.lower()
        
        for category, rules in cls.CATEGORY_RULES.items():
            if any(rule(filename_lower) for rule in rules):
                return category, cls.PRIORITY_MAP.get(category, 10)
        
        return 'misc', cls.PRIORITY_MAP['misc']

class LimitedPDFDownloader:
    """PDF downloader with configurable limits"""
    
    def __init__(self, limits: DownloadLimits):
        self.limits = limits
        self.max_workers = 3  # Conservative for rate limiting
        
    def get_file_size(self, url: str) -> Optional[int]:
        """Get file size without downloading"""
        try:
            response = requests.head(url, timeout=10, allow_redirects=True)
            if response.status_code == 200:
                return int(response.headers.get('content-length', 0))
        except Exception as e:
            logger.warning(f"Could not get size for {url}: {e}")
        return None
    
    def download_file(self, url: str, local_path: str) -> Dict[str, Any]:
        """Download a single PDF file"""
        try:
            response = requests.get(url, timeout=30)
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
    
    def download_pdfs(self, pdf_files: List[PDFFile]) -> List[Dict[str, Any]]:
        """Download PDFs with limits and priority"""
        results = []
        
        # Sort by priority (lower number = higher priority)
        pdf_files.sort(key=lambda x: (x.priority, x.filename))
        
        logger.info(f"Starting download of {len(pdf_files)} PDFs...")
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
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
                    result["priority"] = pdf.priority
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

class MissingPDFsAgent:
    """Agent focused on downloading the 50 missing PDFs"""
    
    def __init__(self, base_path: str = "./westpac_pdfs"):
        self.base_path = base_path
        self.limits = DownloadLimits()
        self.downloader = LimitedPDFDownloader(self.limits)
        
        # Ensure base directory exists
        os.makedirs(base_path, exist_ok=True)
        
        # Create category directories
        categories = ['product-disclosure', 'legal-terms', 'policies', 'forms', 'fees-charges', 'misc']
        for category in categories:
            os.makedirs(os.path.join(base_path, category), exist_ok=True)
    
    def get_missing_pdf_urls(self) -> List[str]:
        """Get URLs for the 50 missing PDFs mapped to likely Westpac URLs"""
        # These are the 50 missing files mapped to likely URLs based on filename patterns
        missing_urls = [
            # PDS and Disclosure Documents (Highest Priority)
            "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/FSR_CorpTransAccPDS1.pdf",
            "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/BTSuperInvest_PDS.pdf",
            "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/WBC-FXSwapPDS.pdf",
            "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/WBC-FXTransactionPDS.pdf",
            "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/WBC-FlexiForwardPDS.pdf",
            "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/WBC-ForeignCurrencyTermDepositPDS.pdf",
            "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/WBC-ForeignExchangeOptionPDS.pdf",
            "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/WBC-ParticipatingForwardPDS.pdf",
            "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/WBC-RangeForwardPDS.pdf",
            "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/wbc-frfx-pds.pdf",
            "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/wbc-fsr-direct-entry-pds.pdf",
            "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/worldwide-wallet-PDS.pdf",
            "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/wfs_investorchoice_PDS.pdf",
            
            # Terms and Conditions
            "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/Online_Banking_TCs.pdf",
            "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/Terms_and_Conditions_COL040.pdf",
            "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/CC_TC_COU.pdf",
            "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/VPC_TC_COU.pdf",
            "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/Group_Telephone_Banking_T___C.pdf",
            "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/Personal_Telephone_Banking_T___C.pdf",
            "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/FSR_PeriodPayTermsAndConditions.pdf",
            "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/Samsung_Pay_WBC_TandCs.pdf",
            "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/WBC-apple-pay-westpac-tcs.pdf",
            "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/Westpac_Google_Pay_Terms_and_Conditions.pdf",
            "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/Westpac_Business_Express_Deposit_T_and_Cs_D5.pdf",
            "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/payto-tandcs.pdf",
            "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/wbc-disclosure-docs-payid-tc.pdf.pdf",
            "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/electronic_trading_terms_nsw.pdf",
            "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/electronic_trading_terms_ny.pdf",
            "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/electronic_trading_terms_nz.pdf",
            
            # Financial Services Guides and Information
            "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/BT-Panorama-FSG.pdf",
            "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/BTSuperInvest_AIB.pdf",
            "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/BTSuperInvest_IOB.pdf",
            
            # Fees and Charges
            "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/Fees_and_Charges_Sheet_COL042.pdf",
            
            # Trading and Investment Documents
            "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/Global-Order-Execution-Disclosure.pdf",
            "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/securitiesblanket.pdf",
            "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/houserules.pdf",
            "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/Allocations_in_bond_offerings.pdf",
            
            # Foreign Exchange and International
            "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/FX_Global_Code_Liquidity_Provider_Disclosure_Cover_Sheet.pdf",
            "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/foreigncurrencyaccount.pdf",
            "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/wbc-fx-trans-supplement-sept-24.pdf",
            "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/wbc-interest-rate-trans-supplement-sept-24.pdf",
            "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/wbc-large-trade-disclosure-supplement.pdf",
            "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/westpac_fx_global_code_algo_due_diligence_template.pdf",
            
            # SDL Documents
            "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/SDLAustraliaSupplementSigned.pdf",
            "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/SDLHongKongSupplementSigned.pdf",
            "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/SDLLetterSigned.pdf",
            "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/SDLSingaporeSupplementSigned.pdf",
            
            # Policy and Governance Documents
            "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/WBC-FMSB-Statement-of-Commitment-2022.pdf",
            "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/wbc-financial-adviser-cpd-policy.pdf",
            "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/wbc-fmsb-statement-of-commitment.pdf",
            
            # IBOR Transition
            "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/ibor-transition-general-ibor-disclosure.pdf"
        ]
        
        return missing_urls
    
    def create_pdf_files(self, urls: List[str]) -> List[PDFFile]:
        """Create PDFFile objects from URLs with categorization and prioritization"""
        pdf_files = []
        
        for url in urls:
            filename = unquote(os.path.basename(urlparse(url).path))
            category, priority = PDFCategorizer.categorize_with_priority(filename)
            local_path = os.path.join(self.base_path, category, filename)
            
            pdf_files.append(PDFFile(
                url=url,
                filename=filename,
                category=category,
                local_path=local_path,
                priority=priority
            ))
        
        return pdf_files
    
    def run(self) -> Dict[str, Any]:
        """Run the missing PDFs download process"""
        start_time = datetime.now()
        logger.info("🚀 Starting Missing PDFs Agent...")
        
        # Get URLs for missing PDFs
        urls = self.get_missing_pdf_urls()
        logger.info(f"📋 Found {len(urls)} missing PDF URLs to check")
        
        # Create PDF objects
        pdf_files = self.create_pdf_files(urls)
        
        # Filter out already downloaded files
        new_pdf_files = []
        for pdf in pdf_files:
            if not os.path.exists(pdf.local_path):
                new_pdf_files.append(pdf)
            else:
                logger.info(f"⏭️  Skipping {pdf.filename} (already exists)")
        
        logger.info(f"📥 Will attempt to download {len(new_pdf_files)} new PDFs")
        
        if not new_pdf_files:
            logger.info("✅ All missing PDFs already downloaded!")
            return {"status": "complete", "new_downloads": 0}
        
        # Download PDFs
        download_results = self.downloader.download_pdfs(new_pdf_files)
        
        # Count successes
        successful_downloads = sum(1 for r in download_results if r["success"])
        failed_downloads = len(download_results) - successful_downloads
        
        # Generate summary
        end_time = datetime.now()
        duration = end_time - start_time
        
        summary = {
            "status": "complete",
            "total_urls_checked": len(urls),
            "new_downloads_attempted": len(new_pdf_files),
            "successful_downloads": successful_downloads,
            "failed_downloads": failed_downloads,
            "duration_seconds": duration.total_seconds(),
            "download_results": download_results
        }
        
        logger.info(f"✅ Missing PDFs Agent completed!")
        logger.info(f"📊 Summary: {successful_downloads} successful, {failed_downloads} failed")
        logger.info(f"⏱️  Duration: {duration}")
        
        # Save results
        with open("missing_pdfs_results.json", "w") as f:
            json.dump(summary, f, indent=2)
        
        return summary

def main():
    """Main entry point"""
    agent = MissingPDFsAgent()
    results = agent.run()
    print(f"\n✅ Agent completed! Downloaded {results['successful_downloads']} new PDFs")

if __name__ == "__main__":
    main()