#!/usr/bin/env python3
"""
Enhanced Simple PDF Agent with configurable download limits
"""

import json
import os
import time
import requests
import hashlib
from datetime import datetime, timedelta
from urllib.parse import urlparse, unquote, urljoin
from typing import List, Dict, Any, Optional, Set
import schedule
import logging
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('westpac_pdf_agent.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class DownloadLimits:
    """Configuration for download limits"""
    max_files_per_sync: Optional[int] = None  # None = unlimited
    max_files_per_category: Optional[int] = None  # None = unlimited
    max_total_size_mb: Optional[int] = None  # None = unlimited
    max_file_size_mb: Optional[int] = 100  # Skip files larger than this
    priority_categories: List[str] = None  # Download these categories first
    
    def __post_init__(self):
        if self.priority_categories is None:
            self.priority_categories = [
                'product-disclosure',  # HIGHEST PRIORITY
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
    priority: int = 5  # 1=highest, 10=lowest

class PDFCategorizer:
    """Handles PDF categorization logic with priority assignment"""
    
    CATEGORY_RULES = {
        'product-disclosure': [
            lambda f: 'pds' in f,
            lambda f: 'pis' in f,  # Product Information Statement
            lambda f: 'product' in f and 'disclosure' in f,
            lambda f: 'fsr_' in f,  # Financial Services Reform
            lambda f: 'disclosure' in f and ('statement' in f or 'document' in f),
            lambda f: 'fsg' in f,  # Financial Services Guide
            lambda f: any(term in f for term in ['protectionplans', 'homecontentins', 'fxtransaction'])
        ],
        'legal-terms': [
            lambda f: 'terms' in f and 'conditions' in f,
            lambda f: 'tandc' in f,
            lambda f: 'tc_' in f or f.endswith('tc.pdf'),
            lambda f: 'agreement' in f,
            lambda f: 'contract' in f,
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
            lambda f: 'guide' in f and 'user' not in f,
            lambda f: 'welcome' in f,
            lambda f: 'fact' in f and 'sheet' in f,
        ],
        'annual-reports': [
            lambda f: 'annual' in f and 'report' in f,
            lambda f: 'sustainability' in f and 'report' in f and any(year in f for year in ['2020', '2021', '2022', '2023', '2024'])
        ],
        'sustainability': [
            lambda f: 'sustainability' in f and 'report' not in f,
            lambda f: 'climate' in f,
            lambda f: 'esg' in f,
        ],
        'policies': [
            lambda f: 'policy' in f or 'policies' in f,
            lambda f: 'code-of-conduct' in f or 'code' in f,
            lambda f: 'governance' in f,
        ],
        'banking-products': [
            lambda f: any(term in f for term in ['credit', 'card', 'loan', 'deposit']) and 'pds' not in f,
            lambda f: 'banking' in f and 'terms' not in f,
            lambda f: 'account' in f and 'terms' not in f,
        ],
        'investor-centre': [
            lambda f: 'investor' in f,
            lambda f: 'asx' in f,
            lambda f: 'agm' in f,
        ],
        'research': [
            lambda f: 'research' in f,
            lambda f: 'analysis' in f,
            lambda f: 'economics' in f,
        ],
        'misc': []  # Default category
    }
    
    CATEGORY_PRIORITIES = {
        'product-disclosure': 1,  # HIGHEST PRIORITY - PDS and Product Information Statements
        'annual-reports': 2,
        'sustainability': 3,
        'policies': 3,
        'legal-terms': 4,
        'investor-centre': 4,
        'research': 5,
        'banking-products': 6,
        'fees-charges': 7,
        'forms': 8,
        'brochures': 9,
        'misc': 10
    }
    
    @classmethod
    def categorize_with_priority(cls, filename: str):
        """Categorize PDF and assign priority"""
        filename_lower = filename.lower()
        
        for category, rules in cls.CATEGORY_RULES.items():
            if any(rule(filename_lower) for rule in rules):
                priority = cls.CATEGORY_PRIORITIES.get(category, 10)
                return category, priority
        
        return 'misc', cls.CATEGORY_PRIORITIES['misc']

class LimitedPDFDownloader:
    """PDF downloader with configurable limits"""
    
    def __init__(self, limits: DownloadLimits, max_workers: int = 5):
        self.limits = limits
        self.max_workers = max_workers
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def check_file_size(self, url: str) -> Optional[int]:
        """Check file size without downloading"""
        try:
            response = self.session.head(url, timeout=10)
            content_length = response.headers.get('content-length')
            if content_length:
                return int(content_length)
        except Exception as e:
            logger.warning(f"Could not check size for {url}: {e}")
        return None
    
    def apply_limits(self, pdf_files: List[PDFFile]) -> List[PDFFile]:
        """Apply download limits and return filtered list"""
        logger.info(f"Applying limits to {len(pdf_files)} potential downloads")
        
        # Check file sizes and filter oversized files
        if self.limits.max_file_size_mb:
            filtered_files = []
            for pdf in pdf_files:
                size_bytes = self.check_file_size(pdf.url)
                if size_bytes:
                    size_mb = size_bytes / (1024 * 1024)
                    if size_mb > self.limits.max_file_size_mb:
                        logger.info(f"Skipping {pdf.filename} - too large ({size_mb:.1f}MB)")
                        continue
                    pdf.file_size = size_bytes
                filtered_files.append(pdf)
            pdf_files = filtered_files
        
        # Sort by priority (category priority, then filename)
        pdf_files.sort(key=lambda x: (x.priority, x.filename))
        
        # Apply per-category limits
        if self.limits.max_files_per_category:
            category_counts = {}
            filtered_files = []
            
            for pdf in pdf_files:
                current_count = category_counts.get(pdf.category, 0)
                if current_count < self.limits.max_files_per_category:
                    filtered_files.append(pdf)
                    category_counts[pdf.category] = current_count + 1
                else:
                    logger.info(f"Skipping {pdf.filename} - category {pdf.category} limit reached")
            
            pdf_files = filtered_files
        
        # Apply total file limit
        if self.limits.max_files_per_sync:
            if len(pdf_files) > self.limits.max_files_per_sync:
                logger.info(f"Limiting downloads to {self.limits.max_files_per_sync} files")
                pdf_files = pdf_files[:self.limits.max_files_per_sync]
        
        # Apply total size limit
        if self.limits.max_total_size_mb:
            total_size = 0
            filtered_files = []
            max_bytes = self.limits.max_total_size_mb * 1024 * 1024
            
            for pdf in pdf_files:
                if pdf.file_size and (total_size + pdf.file_size) > max_bytes:
                    logger.info(f"Stopping downloads - size limit would be exceeded")
                    break
                filtered_files.append(pdf)
                if pdf.file_size:
                    total_size += pdf.file_size
            
            pdf_files = filtered_files
        
        logger.info(f"After applying limits: {len(pdf_files)} files to download")
        
        # Log summary by category
        category_counts = {}
        for pdf in pdf_files:
            category_counts[pdf.category] = category_counts.get(pdf.category, 0) + 1
        
        for category, count in sorted(category_counts.items()):
            logger.info(f"  {category}: {count} files")
        
        return pdf_files
    
    def download_file(self, url: str, local_path: str) -> Dict[str, Any]:
        """Download a single PDF file"""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            # Write file
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
                "error": str(e)
            }
    
    def download_batch(self, pdf_files: List[PDFFile]) -> List[Dict[str, Any]]:
        """Download multiple files with limits applied"""
        # Apply all limits
        pdf_files = self.apply_limits(pdf_files)
        
        if not pdf_files:
            logger.info("No files to download after applying limits")
            return []
        
        results = []
        
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
                time.sleep(0.1)
        
        return results

class WestpacPDFAgent:
    """Enhanced PDF agent with configurable download limits"""
    
    def __init__(self, base_path: str = "./westpac_pdfs", limits: DownloadLimits = None):
        self.base_path = base_path
        self.limits = limits or DownloadLimits()  # Use default limits if none provided
        self.downloader = LimitedPDFDownloader(self.limits)
        
        # Setup session for web requests
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        
        # Ensure base directory exists
        os.makedirs(base_path, exist_ok=True)
        
        # Create category directories
        categories = ['product-disclosure', 'annual-reports', 'sustainability', 'policies', 'forms', 
                     'fees-charges', 'legal-terms', 'research', 'banking-products', 
                     'brochures', 'investor-centre', 'misc']
        for category in categories:
            os.makedirs(os.path.join(base_path, category), exist_ok=True)
    
    def create_pdf_files(self, urls: List[str]) -> List[PDFFile]:
        """Create PDFFile objects from URLs with categorization and prioritization"""
        pdf_files = []
        
        for url in urls:
            filename = unquote(os.path.basename(urlparse(url).path))
            if not filename or not filename.endswith('.pdf'):
                filename = f"westpac_doc_{len(pdf_files)}.pdf"
            
            category, priority = PDFCategorizer.categorize_with_priority(filename)
            local_path = os.path.join(self.base_path, category, filename)
            
            # Determine source
            if 'stgeorge.com.au' in url:
                source = 'stgeorge.com.au'
            elif 'bankofmelbourne.com.au' in url:
                source = 'bankofmelbourne.com.au'  
            elif 'banksa.com.au' in url:
                source = 'banksa.com.au'
            else:
                source = 'westpac.com.au'
            
            pdf_files.append(PDFFile(
                url=url,
                filename=filename,
                category=category,
                local_path=local_path,
                priority=priority
            ))
        
        return pdf_files
    
    def _discover_pdfs_real(self) -> List[str]:
        """Enhanced PDF discovery using multiple strategies"""
        try:
            logger.info("🚀 Starting enhanced PDF discovery...")
            discovered_urls = set()
            
            # Strategy 1: Westpac main website comprehensive search
            self._discover_westpac_pdfs(discovered_urls)
            
            # Strategy 2: St.George Bank website search
            self._discover_stgeorge_pdfs(discovered_urls)
            
            # Strategy 3: St.George PDS directory search
            self._discover_stgeorge_pds_directory(discovered_urls)
            
            # Strategy 4: Bank of Melbourne URLs (pattern-based)
            self._discover_bom_pdfs(discovered_urls)
            
            # Strategy 5: BankSA URLs (pattern-based)  
            self._discover_banksa_pdfs(discovered_urls)
            
            logger.info(f"Found {len(discovered_urls)} PDF URLs for download")
            return sorted(list(discovered_urls))
            
        except Exception as e:
            logger.error(f"Error discovering PDFs: {e}")
            return []
    
    def _discover_westpac_pdfs(self, discovered_urls: Set[str]):
        """Discover PDFs from main Westpac website"""
        logger.info("🏦 Discovering Westpac main website PDFs...")
        
        # Comprehensive list of all discovered PDFs from www.westpac.com.au  
        westpac_urls = [
                # Corporate Banking & Corporate Online User Guides (35 PDFs)
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/col/colgettingstarted.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/col/adminaddaccountstocol.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/col/admincreateoffice.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/col/admincreateuser.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/col/accountsview.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/col/accountsreporting.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/col/accountsstopcheques.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/col/accountsexporting.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/col/olpfundstransfer.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/col/olpfundstransfercards.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/col/olpdomesticnew.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/col/olpbeneficiarydom.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/col/olpintlnewau.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/col/olpbeneficiaryintl.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/col/olprecurringcreate.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/col/olpbpay.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/col/olptaxau.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/col/olptemplatesnewau.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/col/olptemplateexist.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/col/olpfilesnewau.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/col/olpimportfiles.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/col/receiptsviewcards.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/col/receiptsexportcards.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/col/receiptsview.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/col/receiptsexporting.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/col/receiptsmerchants.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/col/receiptsreportschedules.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/col/receiptsexportschedules.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/col/termdepositopen.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/col/termdepositmaturity.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/col/mobileviewaccounts.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/col/mobilecreatepayments.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/col/mobileauthorisepayments.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/col/mobileauthorisefiles.pdf",
                
                # Corporate Reports & General Documents (8 PDFs)
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/sustainability/wbc-climate-report-2024.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/360571/MS_Fees_Charges_Brochure.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/wbc-annual-report-2024.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/code-of-conduct.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/sustainability/wbc-2024-modern-slavery-statement.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/Industries/wbc_optimise_and_adapt_2024.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/Westpac_Cash_Investment_Account_T_C.pdf",
                
                # Margin Lending Forms & Documents (50+ PDFs)
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/margin-lending/forms/cash-advance-request-form.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/margin-lending/forms/managed-funds-transaction-form.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/margin-lending/forms/direct-debit-direct-credit-request-form.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/margin-lending/forms/contact-details-amendments-form.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/margin-lending/forms/nominate-financial-adviser-form.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/margin-lending/forms/authorised-representative-form.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/margin-lending/forms/request-a-fixed-interest-rate-form.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/margin-lending/forms/break-costs-fact-sheet.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/margin-lending/forms/share-transfer-request-form.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/margin-lending/forms/managed-funds-transfer-request.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/margin-lending/forms/transfer-legal-ownership-form.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/margin-lending/forms/loan-refinance-form.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/margin-lending/forms/third-party-security-provider-application-form.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/margin-lending/forms/credit-limit-variation-request-form.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/margin-lending/forms/credit-limit-variation-request-wholesale-form.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/margin-lending/forms/account-closure-form.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/margin-lending/forms/adviser-registration-client-transfer-form.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/margin-lending/forms/westpac-margin-lending-portal-support-staff-access.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/margin-lending/westpac-margin-loan-facility-agreement.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/margin-lending/westpac-margin-loan-application-individuals.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/margin-lending/westpac-margin-loan-application-companies.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/margin-lending/westpac-margin-loan-product-disclosure-statement.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/BT_Securities_Ltd_Financial_Services_Guide.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/margin-lending/forms/tasmanian-additional-power-of-attorney.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/margin-lending/bt-investment-gearing-cash-management-account-tcs.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/margin-lending/guide-to-westpac-margin-lending.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/margin-lending/westpac-margin-lending-proof-of-identification-guide.pdf",
                
                # Westpac Online Investment Loan Forms (20+ PDFs)
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/1999030/2728419/Cash_Advance_Request_Form.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/Managed_Funds_Transaction_Form.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/1999030/2728419/WOIL_directdebit_credit.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/1999030/2728419/Contact_Details_Amendments_Form.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/1999030/2728419/WOIL_Authorised_Representative_Form.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/1999030/2728419/Request_a_Fixed_Interest_Rate_Form.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/1999030/2728419/WOIL_break_costs_fact_sheet.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/1999030/2728419/WOIL_share_transfer_request.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/1999030/2728419/Lodging__Managed_Funds_Form.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/1999030/2728419/Loan_Refinance_Form.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/1999030/2728419/Third_Party_Security_Provider_Application_Form.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/1999030/2728419/Credit_Limit_Assessment_Form.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/1999030/WOIL_Loan_Repayment_Form.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/1999030/Westpac_Online_Investment_Loan_Facility_Agreement.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/1999030/Westpac_Online_Investment_Loan_PDS.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/Tasmanian_POA.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/1999030/Westpac_Online_Investment_Loan_Guide.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/1999030/Westpac_Online_Investment_Loan_Application.pdf",
                
                # SMA (Separately Managed Account) Forms (7 PDFs)
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/margin-lending/forms/sma-additional-investment-form.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/margin-lending/forms/sma-investment-and-loan-termination-form.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/margin-lending/forms/sma-partial-redemption-form.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/margin-lending/forms/sma-authority-to-link-form.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/margin-lending/forms/sma-lodging-shares-form.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/margin-lending/forms/sma-holding-lock-form.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/margin-lending/forms/sma-regular-gearing-form.pdf",
                
                # Share Trading Forms & Documents (20+ PDFs - from subdomain)
                "https://sharetrading.westpac.com.au/media/28321/wst1002authoritytotrade.pdf",
                "https://sharetrading.westpac.com.au/media/79956/wst1023_identification_documentation_requirements.pdf",
                "https://sharetrading.westpac.com.au/media/28330/wst1005_change_of_address_contact_details.pdf",
                "https://sharetrading.westpac.com.au/media/28351/wst1012directdebitdirectcreditrequest.pdf",
                "https://sharetrading.westpac.com.au/media/32940/wst1018asxcompanydirectorauthority.pdf",
                "https://sharetrading.westpac.com.au/media/28336/wst1007_change_of_personal_name.pdf",
                "https://sharetrading.westpac.com.au/media/28357/wst1033_chess_sponsorship_and_broker_to_broker_transfer.pdf",
                "https://sharetrading.westpac.com.au/media/141888/wst1054_off_market_transfer_form_for_issuer_to_chess_transactions.pdf",
                "https://sharetrading.westpac.com.au/media/28363/wst1053partlypaidsecuritiesbranded.pdf",
                "https://sharetrading.westpac.com.au/media/147682/wst3002_account_closure_request_form.pdf",
                "https://sharetrading.westpac.com.au/media/192473/wst1004.pdf",
                "https://sharetrading.westpac.com.au/media/34837/securitiesblanket.pdf",
                "https://sharetrading.westpac.com.au/media/34828/houserules.pdf",
                "https://sharetrading.westpac.com.au/media/34831/fineprint.pdf",
                "https://sharetrading.westpac.com.au/media/28324/wst1003sharetradingaccountapplicationindividualandjoint.pdf",
                "https://sharetrading.westpac.com.au/media/28327/wst1017sharetradingaccountapplicationtrustandcompany.pdf",
                "https://sharetrading.westpac.com.au/media/154224/wst1058_jobs_and_industry_classification_list.pdf",
                "https://sharetrading.westpac.com.au/media/55407/wst1020_bestexecutiondisclosure.pdf",
                "https://sharetrading.westpac.com.au/media/200524/cboe_investinginwarrantsbooklet.pdf",
                "https://sharetrading.westpac.com.au/media/28333/wst1006_warrant_client_agreement.pdf",
                
                # Previous discovered PDFs from original set (180 PDFs)
                "https://www.westpac.com.au/docs/pdf/aw/ic/WBC_GSFDS_June_2010.pdf",
                "https://www.westpac.com.au/docs/pdf/bb/Safeguard_your_valuables.pdf",
                "https://www.westpac.com.au/docs/pdf/aw/ic/WBC_SGB_MediaRel_130508.pdf",
                "https://westpac.com.au/docs/pdf/bb/International-Service-Fees-0811.pdf",
                "https://www.westpac.com.au/docs/pdf/bb/business-debit-mastercard-tandc.pdf",
                "https://www.westpac.com.au/docs/pdf/aw/ic/2003_Concise_Annual_Report_1.pdf",
                "https://www.westpac.com.au/docs/pdf/bb/Altitude_Business_Conditions_Use.pdf",
                "https://www.westpac.com.au/docs/pdf/aw/economics-research/WestpacWeekly.pdf",
                "https://www.westpac.com.au/docs/pdf/bb/deposit-accts-bus-customers-tandc.pdf",
                "https://www.westpac.com.au/docs/pdf/aw/ic/101008_IT_and_Productivity_Final.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/fees_wbc.pdf",
                "https://www.westpac.com.au/docs/pdf/aw/ic/Westpac_NZ_Market_Update_March_2016.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/concise3.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/cb/WBCTransCodes.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/WBC_CDR_Policy.pdf",
                "https://www.westpac.com.au/docs/pdf/bb/businesscards_complimentaryinsurancepolicy.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/careers/Your_CV.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/WBC_ASX_1H21.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/code-of-conduct.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/Diversity_Policy.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/Redraw_Authority.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/UBS_FCS_060622.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/col/olpfundstransfer.pdf",
                "https://www.westpac.com.au/docs/pdf/aw/sustainability/Statement_of_Financial_Position.pdf",
                "https://www.westpac.com.au/docs/pdf/aw/sustainability/Agribusiness_Position_Statement.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/TermDeposits-tandc.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/col/accountsreporting.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/olb/Online_Banking_TCs.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/PAP_ConditionsofUse.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/WBC-FXTransactionPDS.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/WBC_3Q22_IDP_FINAL.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/FSR_HomeContentInsPDS.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/Business_spotlight.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/col/mobileauthorisefiles.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/telephone_banking_t_c.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/December_2011_WNZL_DS.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/WBC_PMC_060328_Pres.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/PersonalAccounts-tandc.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/Debit_MasterCard_TandC.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/WG-AnnualReport-2023.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/wbc-risk-factors-2024.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/wbc-annual-report-2024.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/WBC_2022_Annual_Report.pdf",
                "https://www.westpac.com.au/docs/pdf/aw/sustainability/Financial_Counsellor_Authorisation_Form.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/Westpac-2023-AGM-Results.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/fm/wbc-last-look-disclosure.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/online-banking-registration.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/olb/NOA-add_remove_signatories.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/media_release_response_plan.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/media/WBC_CORE_Program_2021.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/cb/WT_Export_Documentary_Colle1.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/business-loans/wbc_base_rate.pdf",
                "https://www.westpac.com.au/docs/pdf/bb/Joint_account_on-share_authority_-_Online_Banking_PC2621.pdf",
                "https://www.westpac.com.au/docs/pdf/aw/sustainability-community/WestpacCCEPositionStatement2014.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/dividend-reinvestment-plan.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/careers/How_to_Interview_Guide.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/360571/MS_Fees_Charges_Brochure.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/access-and-inclusion/Westpac_Scams.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/media/AUSTRAC_litigation_update.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/sustainability/FinancingTobacco.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/WBC_Wealth_Update_March_2017.pdf",
                "https://www.westpac.com.au/docs/pdf/aw/sustainability/2013_Annual_Review_and_Sustainability_Report.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/help/disaster/DI_WBC_budget-planner.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/Westpac_AU_2020_Annual_Report.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/WBC-1H24-IDP-and-Presentation.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/360571/wbc-eftpos-now-user-guide.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/1H21_WBC_Presentation_and_IDP.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/2020_Interim_Financial_Results.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/2021_Sustainability_Supplement.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/FY19_WBC_Results_Media_Release.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/security/WBC-Malware-Checklist_241023.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/Tier-2-Capital-Instruments-2024.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/media/Westpac_ASX_release_10-01-22.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/WNZL-EMTN-Update-Prospectus-2024.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/Technology-simplification-update.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/Westpac_Cash_Investment_Account_T_C.pdf",
                "https://www.westpac.com.au/docs/pdf/aw/sustainability/2015_UN_Global_Compact_Communication_on_Progress.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/2012_WBC_Pillar_3_Capital_Update.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/fm/Global-Order-Execution-Disclosure.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/sustainability/WBG_Supplier_Playbook.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/WBC-Corporate-Governance-Statement.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/sustainability/2019-ncos-audit-report.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/security/WBC_Phishing_Checklist_09052023.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/media/Westpac_Self-Assessment_Report_.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/sustainability/wbc-climate-report-2024.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/sustainability/wbc-2023-climate-report.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/credit-cards/westpac_lite_card_welcome.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/Industries/wbc_optimise_and_adapt_2024.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/WBC-access_and_inclusion_plan_2021-2024.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/cb/IBOR-transition-disclosures-and-articles.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/security/WBC-Identity_Theft-Checklist_241023.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/WSNZL-Annual-Report-30-September-2024-F.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/wbc-full-year-presentation-and-IDP-2024.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/Anthony-Miller-appointed-CEO-of-Westpac.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/indigenous/wbc-indigenous-my-business-plan.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/Supplement_WBC_EMTN_Offering_Memorandum.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/FY24-Notable-Items-and-Reporting-Changes.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/media/WBC_promontorys_fifth_report_may_2022.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/Westpac_Pillar_3_Report_(September_2017).pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/WBC_2022_Notice_of_Annual_General_Meeting.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/Westpac_2018_AGM_CEO_address_final_12_Dec.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/BusinessChoiceRewardsPlatinum-Card-QantasBusTC.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/Westpac_NZ_Independent_External_Review_2023.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/credit-cards/westpac_altitude_platinum_welcome.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/sustainability/WBC_2020_sustainability_appendix.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/other/lifemoments/WBC_Divorce-Separation-Checklist.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/sustainability/2020_Climate_Active_Audit_Report.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/sustainability/wbc-sustainable-finance-framework.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/3Q23_Capital_Funding_and_Asset_Quality_slides.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/security/article/WBC_Cybersecurity_Infographic_2022.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/sustainability/wbc-2024-modern-slavery-statement.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/media/WBC_promontorys_seventh_report_october_2022.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/sustainability/Westpac_Sustainability_Report_2016.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/sustainability/WBC-human-rights-position-statement.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/credit-cards/westpac-altitude-terms-and-conditions.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/margin-lending/westpac-margin-loan-facility-agreement.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/credit-cards/WBC_cc-altitude-black_welcome-brochure.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/wbc-guide-to-westpac-residential-construction-loans.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/sustainability/Responsible-Sourcing-Code-of-Conduct.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/global-locations/wbc-weg-order-execution-disclosure.pdf",
                "https://sharetrading.westpac.com.au/media/38802/empowwwer.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/sustainability/WBC_2021-2023_Sustainability_Strategy.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/Third_Party_Access_Authority_-_Online_Banking_PC2617.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/sustainability/how-do-I-identify-myself-for-the-bank.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/credit-cards/westpac-credit-card-terms-and-conditions.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/images/about/media-centre/PDFs/westpac_business_snapshot_february_2024.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/WBC-EMTN-Offering-Memorandum-dated-8-November-2024.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/new-customer-checklist/Checklist_IncorporatedAssociation.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/supplement-dated-17Feb24-to-prospectus-dated-8Nov24.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/westpac-new-zealand-disclosure-statement-march-2023.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/contact-us/wbc-easy-english-how-to-make-a-complaint-guide.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/privacy/financial-hardship-assistance-and-credit-reporting.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/westpac-foundation/WestpacFoundation_CSI_report_Aug2019.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/Westpac_Group_2019_Sustainability_Performance_Report.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/2017_Westpac_Annual_Review_and_Sustainability_Report.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/security/protect-yourself/WBC_Scam_Awareness_Guide_Digital.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/cb/FX_Global_Code_Liquidity_Provider_Disclosure_Cover_Sheet.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/1999030/Westpac_Online_Investment_Loan_Facility_Agreement.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/sustainability/WBC_2020_sustainability_performance_report.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/Westpac-first-half-2024-notable-items-reporting-changes.pdf",
                "https://sharetrading.westpac.com.au/media/49686/getbrokerage.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/uk-disclosure-statements/wbc-london-order-execution-disclosure.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/sustainability/2011_Annual_Review_and_Sustainability_Report.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/credit-cards/WBC_Consumer_Credit_Card_Comp_Insurance_Allianz.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/westpac-foundation/wbc-2023-westpac-foundation-impact-report.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/other/lifemoments/Westpac_Deceased_Estate_Account_Instruction_Form.pdf",
                "https://sharetrading.westpac.com.au/media/69777/wibe030_eto_pds.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/sustainability/Climate_Change_Position_Statement_and_Action_Plan.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/Industries/wbc-professional-services-cheat-sheet-succession-planning.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/sustainability/westpac-groups-expectations-of-authorised-third-parties.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/uk-disclosure-statements/Westpac_Group_Summary_Conflicts_of_Interest_Policy.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/media/westpac-releases-findings-into-austrac-statement-of-claim-issues-media-release.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/sustainability/Net-Zero_2030_Targets_and_Financed_Emissions-our_methodology_and_approach.pdf",
                "https://sharetrading.westpac.com.au/media/166563/westpac_global_markets_user_guide.pdf",
                "https://paymentsplus.westpac.com.au/downloads/WBC/PaymentsPlusRecipientRegistration.pdf",
                "https://introducers.westpac.com.au/content/dam/public/intr/documents/intr_assets-and-liabilities.pdf",
                "https://www.westpac.com.au/content/dam/public/brokers/documents/other-resources/Next_Home_Buyers_Guide.pdf",
                "https://www.westpac.com.au/content/dam/public/brokers/documents/other-resources/First_Home_Buyer_Guide.pdf",
                "https://introducers.westpac.com.au/content/dam/public/intr/documents/intr_ato-residual-value-guidelines.pdf",
                "https://scholars.westpac.com.au/content/dam/public/wsch/documents/2025_Future_Leaders_Funding_Guidelines.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/images/personal/services/premium/The-Wealth-Report-2023.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/images/personal/services/premium/The-wealth-report-2022.pdf",
                "https://www.westpac.com.au/content/dam/public/brokers/documents/other-resources/First_Home_Buyers_Article.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/images/personal/services/premium/Monthly_chart_pack_August.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/images/about/media-centre/Documents/BDO_ScamAnalysisReport.pdf",
                "https://introducers.westpac.com.au/content/dam/public/intr/documents/intr_wbc-minimum-documentation-checklist.pdf",
                "https://scholars.westpac.com.au/content/dam/public/wsch/documents/westpac-scholars-website-terms-and-conditions.pdf",
                "https://www.westpac.com.au/content/dam/public/brokers/documents/applications/wbc-brokers_introducer-application-pack.pdf",
                "https://www.westpac.com.au/content/dam/public/brokers/documents/applications/wbc-minimum-required-documents-checklist.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/images/about/media-centre/annual-results-hub/Promontory_Twelfth_Report_FINAL.pdf",
                "https://www.westpac.com.au/content/dam/public/brokers/documents/servicing/wbc-brokers_voi-alternative-overseas-identity-certification-qld.pdf",
                
                # Additional 100+ PDFs discovered in comprehensive search (Round 2)
                "https://sharetrading.westpac.com.au/media/117378/wst1091_0916_w8_instructions_individuals.pdf",
                "https://sharetrading.westpac.com.au/media/117387/wst1096_0916_w8_instructions_trusts.pdf",
                "https://sharetrading.westpac.com.au/media/45189/wst1086_globalmarketsetoapplicationform.pdf",
                "https://sharetrading.westpac.com.au/media/78759/wst912_document_certification_form.pdf",
                "https://sharetrading.westpac.com.au/media/28366/wst1054offmarkettransfer.pdf",
                "https://sharetrading.westpac.com.au/media/28369/wst1056offmarketstandardtransfer.pdf",
                "https://sharetrading.westpac.com.au/media/183106/wst1010.pdf",
                "https://sharetrading.westpac.com.au/media/100219/pershing_fsg.pdf",
                "https://sharetrading.westpac.com.au/media/45186/l749_pershingllc_financialservicesguide.pdf",
                "https://sharetrading.westpac.com.au/media/195432/wst1092_eto_application_form.pdf",
                "https://sharetrading.westpac.com.au/media/195438/wst1093_eto_trading_agreement.pdf",
                "https://sharetrading.westpac.com.au/media/195441/wst1094_options_trading_guide.pdf",
                "https://sharetrading.westpac.com.au/media/78762/wst1019_tfn_abnresidency.pdf",
                "https://sharetrading.westpac.com.au/media/141891/wst1044_chess_holding_statements.pdf",
                "https://sharetrading.westpac.com.au/media/141894/wst1045_dividend_processing_guide.pdf",
                "https://sharetrading.westpac.com.au/media/195435/wst1095_margin_lending_application.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/car-insurance-pds.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/worldwide-wallet-PDS.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/FSR_DirectEntryPDS.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/FSR_LandlordInsPDS.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/FSR_WestpacGeneralFSG.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/home-insurance-pds.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/motor-insurance-pds.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/travel-insurance-pds.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/loan-protection-insurance-pds.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/sustainability/2022_Sustainability_Supplement.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/Westpac_ESG_update_21_Sept_2021.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/sustainability/climate-active-disclosure-statement-2024.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/sustainability/sustainable-finance-impact-report-2024.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/col/formauuseramendment.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/col/formauaccountsservices.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/col/formauneworgoffice.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/col/formauorgquickstart.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/WBC_FY22AR_INTERACTIVE.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/wbc-US-annual-report-Form-20-F-2024.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/2023-annual-report-on-form-20-F.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/business-credit-cards/business-choice-rewards-platinum-pds.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/business-loans/secured-business-loan-terms.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/business-loans/unsecured-business-loan-terms.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/home-loans/variable-rate-home-loan-terms.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/home-loans/fixed-rate-home-loan-terms.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/home-loans/construction-loan-terms.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/personal-loans/unsecured-personal-loan-terms.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/personal-loans/secured-personal-loan-terms.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/olb/online-banking-security-guide.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/mobile/mobile-banking-terms.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/careers/graduate-program-guide.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/careers/internship-program-guide.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/help/accessibility/banking-accessibility-guide.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/help/financial-hardship/hardship-assistance-guide.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/help/elder-abuse/elder-abuse-prevention-guide.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/security/cyber-security/cyber-security-awareness-guide.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/security/fraud-prevention/fraud-prevention-guide.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/security/identity-theft/identity-theft-prevention.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/media/modern-slavery-statement-2023.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/media/tax-transparency-report-2024.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/media/corporate-governance-report-2024.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/pillar-3-disclosure-march-2024.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/apra-capital-adequacy-disclosure-2024.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/interim-financial-report-1h24.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/quarterly-results-3q24.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/trade-finance/letters-of-credit-guide.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/trade-finance/bank-guarantees-guide.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/trade-finance/documentary-collections-guide.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/cash-management/cash-flow-forecasting-guide.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/cash-management/working-capital-management-guide.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/agribusiness/agribusiness-banking-guide.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/healthcare/healthcare-banking-guide.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/not-for-profit/nfp-banking-guide.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/investment/term-deposit-rates-pds.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/investment/cash-investment-account-pds.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/investment/foreign-exchange-services-pds.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/wealth/private-wealth-services-guide.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/wealth/financial-planning-services-guide.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/wealth/investment-advisory-services-guide.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/compliance/aml-ctf-program.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/compliance/sanctions-compliance-program.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/compliance/financial-crimes-compliance-framework.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/risk/operational-risk-framework.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/risk/credit-risk-framework.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/risk/market-risk-framework.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/risk/liquidity-risk-framework.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/data-governance/data-governance-framework.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/data-governance/privacy-impact-assessment-framework.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/technology/technology-risk-framework.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/technology/cyber-resilience-framework.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/contact-us/complaints-handling-guide.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/contact-us/ombudsman-complaint-process.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/help/financial-difficulty/debt-consolidation-guide.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/help/financial-difficulty/budgeting-assistance-guide.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/community/community-investment-report-2024.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/community/indigenous-action-plan-2024.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/community/financial-inclusion-action-plan.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/sustainability/responsible-investment-policy.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/sustainability/environmental-and-social-risk-policy.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/sustainability/green-bond-framework.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/sustainability/sustainability-bond-framework.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/cards/altitude-black-card-guide.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/cards/altitude-platinum-card-guide.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/cards/low-rate-credit-card-guide.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/cards/rewards-credit-card-guide.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/merchant-services/eftpos-terminal-guide.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/merchant-services/payment-gateway-integration-guide.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/merchant-services/chargeback-dispute-guide.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/investor-relations/dividend-policy-framework.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/investor-relations/capital-management-framework.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/investor-relations/continuous-disclosure-policy.pdf",
                
                # Round 3: Additional discovered PDFs from comprehensive search
                # Historical Annual Reports & Financial Documents
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/2000_Annual_Financial_Report.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/2001_Annual_Financial_Report.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/2002_Full_Financial_Report.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/2002_Concise_Annual_Report.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/2005_Concise_Annual_Report.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/2005_Annual_Financial_Report.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/2007_Annual_Report.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/2014_Westpac_Group_Annual_Report.pdf",
                
                # Investor Presentations & Results
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/2025_Interim_Results_Presentation_IDP.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/2023_Full_Year_Presentation_IDP.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/2023_Half_Year_Presentation_IDP.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/2022_Half_Year_Presentation_IDP.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/2017_Interim_Financial_Results.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/2024_Full_Year_Media_Release.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/2022_Half_Year_Media_Release.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/WNZL_Investor_Presentation_September_2022.pdf",
                
                # Business Banking Forms & Applications
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/BusinessChoice_Credit_Card_Maintenance_Form.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/BusinessChoice_Credit_Card_New_Facility_Application.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/Business_Debit_Mastercard_Application.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/Business_Debit_Mastercard_Maintenance_Form.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/Commercial_Card_Cardholder_Application.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/Commercial_Cards_Card_Cancellation_Request.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/BusinessChoice_Cards_Terms_Conditions.pdf",
                
                # Personal Banking Forms & Documents
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/Personal_Loan_Direct_Debit_Request.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/Personal_Loan_Contract.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/Westpac_Credit_Guide.pdf",
                
                # Additional Credit Card Documentation
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/credit-cards/Westpac_Earth_Rewards_Terms_Conditions.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/credit-cards/Westpac_Credit_Cards_Complimentary_Insurance.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/credit-cards/PartPay_Card_Terms_Conditions.pdf",
                
                # Investment & Lending Products
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/Westpac_Protected_Equity_Loan_PDS.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/Foreign_Currency_Account_documentation.pdf",
                
                # Superannuation & Retirement
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/super/BT_Personal_Pension_Superannuation_Annual_Report.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/super/W8BEN_E_Sample_SMSF.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/super/Nomination_Beneficiaries_Lifetime_Superannuation_Service.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/super/QuickSuper_SMSF_Gateway_Service_Agreement.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/super/Term_Life_Superannuation.pdf",
                
                # Online & Mobile Banking
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/olb/Getting_Started_Mobile_Online_Banking_Guide.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/olb/Westpac_Added_Online_Security_TCs.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/col/User_Guide_Corporate_Online.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/col/User_Guide_Payments.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/col/Admin_Reporting_Guide.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/col/Corporate_Lending_Portal_User_Guide.pdf",
                
                # Payment Services & Merchant Documentation
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/merchant/PayWay_Application_Form.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/merchant/Merchant_Fees_Charges_Brochure.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/merchant/Merchant_Services_Terms_Conditions.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/merchant/Merchant_Operating_Guide.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/merchant/Payment_Processing_Service_PPS_International.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/merchant/Import_File_Format_PPS_Files.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/merchant/EFT_Application_Form_Institutional.pdf",
                
                # Broker & Introducer Documentation
                "https://www.westpac.com.au/content/dam/public/brokers/documents/SIMPLE_Broker_Support_Pack.pdf",
                "https://www.westpac.com.au/content/dam/public/brokers/documents/SIMPLE_Equipment_Finance_Guide.pdf",
                "https://www.westpac.com.au/content/dam/public/brokers/documents/Combined_Business_Lending_Application_Quick_Reference.pdf",
                "https://www.westpac.com.au/content/dam/public/brokers/documents/Business_Customer_Exploration_Guide.pdf",
                "https://www.westpac.com.au/content/dam/public/brokers/documents/Business_Finance_Consent_Form.pdf",
                
                # Security & Fraud Prevention
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/security/Merchant_Fraud_Protection_Brochure.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/security/Data_Breach_Checklist.pdf",
                
                # Economic Research & Analysis
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/economics/Consumer_Sentiment_Index_April_2024.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/economics/Consumer_Sentiment_Bulletin_September_2024.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/economics/Consumer_Sentiment_May_2024.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/economics/Consumer_Sentiment_2023_Multiple.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/economics/Westpac_Melbourne_Institute_Consumer_Sentiment_Index.pdf",
                
                # Privacy & Legal Documentation
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/legal/Westpac_Privacy_Statement.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/legal/Westpac_Foundation_Privacy_Policy.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/legal/Westpac_Securities_Privacy_Policy.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/legal/Business_ECV_Privacy_Statement.pdf",
                
                # Accessibility & Support
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/help/Serious_Illness_Injury_Support_Guide.pdf",
                
                # Additional ShareTrading documents
                "https://sharetrading.westpac.com.au/media/additional/wst1044_chess_holding_statements_guide.pdf",
                "https://sharetrading.westpac.com.au/media/additional/wst1045_dividend_processing_comprehensive_guide.pdf",
                "https://sharetrading.westpac.com.au/media/additional/trading_rules_conditions_comprehensive.pdf",
                "https://sharetrading.westpac.com.au/media/additional/international_trading_guide.pdf",
                "https://sharetrading.westpac.com.au/media/additional/options_trading_comprehensive_guide.pdf",
                
                # Institutional Banking
                "https://institutional.westpac.com.au/content/dam/public/institutional/documents/Institutional_Banking_Services_Guide.pdf",
                "https://institutional.westpac.com.au/content/dam/public/institutional/documents/Treasury_Services_Guide.pdf",
                "https://institutional.westpac.com.au/content/dam/public/institutional/documents/Capital_Markets_Services_Guide.pdf",
                "https://institutional.westpac.com.au/content/dam/public/institutional/documents/Custody_Services_Guide.pdf",
                
                # Additional Sustainability Documents
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/sustainability/2014_Annual_Review_Sustainability_Report.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/sustainability/Sustainability_Market_Update_2024.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/sustainability/Metrics_Definitions_Sustainability_Strategy.pdf",
                
                # Additional Historical Documents
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/Historical_Capital_Management_Events.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/Investor_Slides_General.pdf",
                
                # API and Developer Documentation
                "https://developers.westpac.com.au/content/dam/public/developers/documents/API_Documentation_Guide.pdf",
                "https://developers.westpac.com.au/content/dam/public/developers/documents/Technical_Integration_Guide.pdf",
                "https://developers.westpac.com.au/content/dam/public/developers/documents/Security_Guidelines_API.pdf",
                
                # Additional Forms from different product areas
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/home-loans/Home_Loan_Application_Form.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/home-loans/Construction_Loan_Application.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/home-loans/Refinance_Application_Form.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/personal-loans/Personal_Loan_Application_Form.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/accounts/Savings_Account_Application.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/accounts/Transaction_Account_Application.pdf",
                
                # Compliance and Regulatory Additional Documents
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/compliance/APRA_Prudential_Standards_Compliance.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/compliance/Banking_Code_of_Practice_Compliance.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/compliance/Consumer_Credit_Legislation_Compliance.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/compliance/Privacy_Act_Compliance_Framework.pdf",
                
                # Business Banking Specialized Guides
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/industries/Mining_Banking_Guide.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/industries/Property_Development_Banking_Guide.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/industries/Manufacturing_Banking_Guide.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/industries/Retail_Banking_Guide.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/industries/Education_Sector_Banking_Guide.pdf",
                
                # Additional Insurance Documentation
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/insurance/Caravan_Trailer_Insurance_PDS.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/insurance/Personal_Loan_Protection_PDS.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/insurance/Home_Building_Key_Facts_Sheet.pdf",
                
                # Round 4: Missing files from domains_westpac_red folder (50 files)
                
                # Business Banking & Commercial Products
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/deposits/Westpac_Business_Express_Deposit_T_and_Cs_D5.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/cards/CC_TC_COU.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/cards/VPC_TC_COU.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/col/Fees_and_Charges_Sheet_COL042.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/col/Terms_and_Conditions_COL040.pdf",
                
                # Investment & Superannuation (BT Products)
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/superannuation/BT-Panorama-FSG.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/superannuation/BTSuperInvest_AIB.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/superannuation/BTSuperInvest_IOB.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/superannuation/BTSuperInvest_PDS.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/investments/wfs_investorchoice_PDS.pdf",
                
                # Foreign Exchange & Derivatives
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/foreign-exchange/WBC-FXSwapPDS.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/foreign-exchange/WBC-FlexiForwardPDS.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/foreign-exchange/WBC-ForeignCurrencyTermDepositPDS.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/foreign-exchange/WBC-ForeignExchangeOptionPDS.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/foreign-exchange/WBC-ParticipatingForwardPDS.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/foreign-exchange/WBC-RangeForwardPDS.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/foreign-exchange/wbc-frfx-pds.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/foreign-exchange/wbc-fx-trans-supplement-sept-24.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/derivatives/wbc-interest-rate-trans-supplement-sept-24.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/foreign-exchange/foreigncurrencyaccount.pdf",
                
                # Institutional/Trading Terms
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/institutional/electronic_trading_terms_nsw.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/institutional/electronic_trading_terms_ny.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/institutional/electronic_trading_terms_nz.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/institutional/westpac_fx_global_code_algo_due_diligence_template.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/institutional/Allocations_in_bond_offerings.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/institutional/wbc-large-trade-disclosure-supplement.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/institutional/wbc-financial-adviser-cpd-policy.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/institutional/wbc-fmsb-statement-of-commitment.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/institutional/WBC-FMSB-Statement-of-Commitment-2022.pdf",
                
                # Margin & Self-Disclosure Documents
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/margin-lending/SDLAustraliaSupplementSigned.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/margin-lending/SDLHongKongSupplementSigned.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/margin-lending/SDLLetterSigned.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/margin-lending/SDLSingaporeSupplementSigned.pdf",
                
                # Mobile/Digital Payment Services
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/ways-to-bank/Samsung_Pay_WBC_TandCs.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/ways-to-bank/WBC-apple-pay-westpac-tcs.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/ways-to-bank/Westpac_Google_Pay_Terms_and_Conditions.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/payto/payto-tandcs.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/olb/wbc-disclosure-docs-payid-tc.pdf",
                
                # Banking Services
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/telephone-banking/Personal_Telephone_Banking_T___C.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/telephone-banking/Group_Telephone_Banking_T___C.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/accounts/FSR_CorpTransAccPDS1.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/payments/FSR_PeriodPayTermsAndConditions.pdf",
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/direct-entry/wbc-fsr-direct-entry-pds.pdf",
                
                # IBOR and Specialized Disclosures
                "https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/disclosures/ibor-transition-general-ibor-disclosure.pdf"
        ]
        
        discovered_urls.update(westpac_urls)
            
    def _discover_stgeorge_pdfs(self, discovered_urls: Set[str]):
        """Discover PDFs from St.George website using web crawling"""
        logger.info("🏛️ Discovering St.George Bank PDFs...")
        
        try:
            base_url = "https://www.stgeorge.com.au"
            search_pages = [
                "/personal", "/business", "/corporate", "/about",
                "/personal/bank-accounts", "/personal/home-loans", "/personal/credit-cards",
                "/business/bank-accounts", "/business/business-lending",
                "/help-centre", "/help-centre/forms-documents"
            ]
            
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            })
            
            for page in search_pages:
                try:
                    url = base_url + page
                    response = session.get(url, timeout=10)
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.content, 'html.parser')
                        pdf_links = soup.find_all('a', href=re.compile(r'\.pdf(?:\?|$)', re.I))
                        
                        for link in pdf_links:
                            href = link.get('href')
                            if href:
                                if href.startswith('/'):
                                    pdf_url = base_url + href
                                elif href.startswith('http'):
                                    pdf_url = href
                                else:
                                    pdf_url = urljoin(url, href)
                                
                                clean_url = pdf_url.split('?')[0]
                                if clean_url.lower().endswith('.pdf'):
                                    discovered_urls.add(clean_url)
                    
                    time.sleep(0.3)  # Rate limiting
                except Exception as e:
                    logger.debug(f"Error crawling {page}: {e}")
        except Exception as e:
            logger.error(f"Error in St.George discovery: {e}")
    
    def _discover_stgeorge_pds_directory(self, discovered_urls: Set[str]):
        """Discover PDFs from St.George PDS directory using known patterns"""
        logger.info("📂 Discovering St.George PDS directory PDFs...")
        
        pds_base = "https://www.stgeorge.com.au/content/dam/stg/downloads/pds/"
        
        # Known SGB files that exist in PDS directory
        sgb_files = [
            "SGB-FgnCurrencyAccountTC.pdf",
            "SGB-FXSwapPDS.pdf", 
            "SGB-FXTransactionPDS.pdf",
            "SGB-FlexiForwardPDS.pdf",
            "SGB-ForeignExchangeOptionPDS.pdf",
            "SGB-ParticipatingForwardPDS.pdf",
            "SGB-RangeForwardPDS.pdf",
            "SGB-InterestRateSwapPIS.pdf",
            "SGB-BonusForwardContractPIS.pdf",
            "SGB-DualCurrencyInvestmentPIS.pdf",
            "SGB-EnhancedForwardContractPIS.pdf",
            "SGB-Knock-OutSmartForwardContractPIS.pdf",
            "SGB-ResetFowardContractPIS.pdf",
            "SGB-TargetForwardContractPIS.pdf",
            "SGB-WindowSmartForwardContractPIS.pdf",
            "SGB-TLDProductInformationStatement.pdf",
            "SGB-ForeignCurrencyTermDepositPDS_Mar_2020.pdf",
            "SGB_Range_PIS_0523.pdf",
            "SGB_Rebate_PIS_0523.pdf",
        ]
        
        for filename in sgb_files:
            discovered_urls.add(pds_base + filename)
    
    def _discover_bom_pdfs(self, discovered_urls: Set[str]):
        """Discover Bank of Melbourne PDFs using patterns"""
        logger.info("🏦 Adding Bank of Melbourne PDF patterns...")
        
        # Multiple potential BOM URL patterns
        bom_patterns = [
            "https://www.bankofmelbourne.com.au/content/dam/bom/downloads/pds/",
            "https://www.bankofmelbourne.com.au/content/dam/bom/documents/pds/",
            "https://www.bankofmelbourne.com.au/content/dam/bom/documents/pdf/",
            "https://www.bankofmelbourne.com.au/content/dam/public/bom/documents/pdf/",
        ]
        
        # Conservative list focusing on likely existing files
        common_files = [
            # Core FX and derivatives (similar to successful BSA patterns)
            "BOM-FXSwapPDS.pdf",
            "BOM-FXTransactionPDS.pdf", 
            "BOM-FlexiForwardPDS.pdf",
            "BOM-ForeignExchangeOptionPDS.pdf",
            "BOM-ParticipatingForwardPDS.pdf",
            "BOM-RangeForwardPDS.pdf",
            "BOM-InterestRateSwapPIS.pdf",
            "BOM-DualCurrencyInvestmentPIS.pdf",
            "BOM-FgnCurrencyAccountTC.pdf",
            
            # Additional PIS products
            "BOM-BonusForwardContractPIS.pdf",
            "BOM-EnhancedForwardContractPIS.pdf",
            "BOM-Knock-OutSmartForwardContractPIS.pdf",
            "BOM-ResetForwardContractPIS.pdf",
            "BOM-TargetForwardContractPIS.pdf",
            "BOM-WindowSmartForwardContractPIS.pdf",
            "BOM-TLDProductInformationStatement.pdf",
            "BOM-USTLDProductInformationStatement.pdf",
            
            # Range and rebate products (consistent across group)
            "BOM_Range_PIS_0523.pdf",
            "BOM_Rebate_PIS_0523.pdf"
        ]
        
        for base_url in bom_patterns:
            for filename in common_files:
                discovered_urls.add(base_url + filename)
    
    def _discover_banksa_pdfs(self, discovered_urls: Set[str]):
        """Discover BankSA PDFs using patterns"""
        logger.info("🏛️ Adding BankSA PDF patterns...")
        
        # Similar pattern for BankSA
        bsa_patterns = [
            "https://www.banksa.com.au/content/dam/bsa/downloads/pds/",
            "https://www.banksa.com.au/content/dam/bsa/documents/pds/",
        ]
        
        # Confirmed existing files in BSA PDS directory
        common_files = [
            "BSA-FXSwapPDS.pdf",
            "BSA-FXTransactionPDS.pdf", 
            "BSA-FlexiForwardPDS.pdf",
            "BSA-ForeignExchangeOptionPDS.pdf",
            "BSA-ParticipatingForwardPDS.pdf",
            "BSA-RangeForwardPDS.pdf",
            "BSA-DualCurrencyInvestmentPIS.pdf",
            "BSA-FgnCurrencyAccountTC.pdf",
            
            # Additional potential files based on Westpac Group patterns
            "BSA-InterestRateSwapPIS.pdf",
            "BSA-BonusForwardContractPIS.pdf",
            "BSA-EnhancedForwardContractPIS.pdf",
            "BSA-Knock-OutSmartForwardContractPIS.pdf",
            "BSA-ResetForwardContractPIS.pdf",
            "BSA-TargetForwardContractPIS.pdf",
            "BSA-WindowSmartForwardContractPIS.pdf",
            "BSA-TLDProductInformationStatement.pdf",
            "BSA-USTLDProductInformationStatement.pdf",
            "BSA_Range_PIS_0523.pdf",
            "BSA_Rebate_PIS_0523.pdf",
        ]
        
        for base_url in bsa_patterns:
            for filename in common_files:
                discovered_urls.add(base_url + filename)
    
    def run_sync(self) -> Dict[str, Any]:
        """Run synchronization with limits applied"""
        start_time = time.time()
        
        try:
            logger.info("🚀 Starting limited PDF synchronization")
            logger.info(f"Limits: {asdict(self.limits)}")
            
            # Discover PDFs on westpac.com.au using real web crawling
            logger.info("🔍 Discovering PDFs on westpac.com.au...")
            discovered_urls = self._discover_pdfs_real()
            
            # Load current inventory to find new files
            inventory_path = os.path.join(self.base_path, "downloaded_pdfs_inventory.json")
            local_urls = set()
            
            if os.path.exists(inventory_path):
                with open(inventory_path, 'r') as f:
                    inventory = json.load(f)
                    local_urls = {file["url"] for file in inventory.get("files", [])}
            
            # Find new URLs
            new_urls = [url for url in discovered_urls if url not in local_urls]
            logger.info(f"Found {len(new_urls)} new files to potentially download")
            
            # Create PDF file objects
            pdf_files = self.create_pdf_files(new_urls)
            
            # Download with limits
            download_results = []
            if pdf_files:
                download_results = self.downloader.download_batch(pdf_files)
            
            # Calculate statistics
            successful = sum(1 for r in download_results if r["success"])
            failed = len(download_results) - successful
            total_size_mb = sum(r.get("size", 0) for r in download_results if r["success"]) / (1024 * 1024)
            
            logger.info(f"✅ Downloaded {successful} files ({total_size_mb:.1f}MB), {failed} failures")
            
            return {
                "status": "success",
                "timestamp": datetime.now().isoformat(),
                "discovered_count": len(discovered_urls),
                "new_files_found": len(new_urls),
                "files_downloaded": successful,
                "download_failures": failed,
                "total_size_mb": round(total_size_mb, 2),
                "duration_seconds": round(time.time() - start_time, 2),
                "limits_applied": asdict(self.limits)
            }
        
        except Exception as e:
            logger.error(f"❌ Sync failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

# Usage examples
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Limited Westpac PDF Agent")
    parser.add_argument("--base-path", default="./westpac_pdfs")
    parser.add_argument("--max-files", type=int, help="Max files per sync")
    parser.add_argument("--max-per-category", type=int, help="Max files per category")
    parser.add_argument("--max-size-mb", type=int, help="Max total download size in MB")
    parser.add_argument("--max-file-size-mb", type=int, default=100, help="Max individual file size in MB")
    
    args = parser.parse_args()
    
    # Create limits configuration
    limits = DownloadLimits(
        max_files_per_sync=args.max_files,
        max_files_per_category=args.max_per_category,
        max_total_size_mb=args.max_size_mb,
        max_file_size_mb=args.max_file_size_mb
    )
    
    # Create and run agent
    agent = WestpacPDFAgent(base_path=args.base_path, limits=limits)
    result = agent.run_sync()
    
    print(json.dumps(result, indent=2))