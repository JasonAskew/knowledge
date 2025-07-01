#!/usr/bin/env python3
"""
Knowledge Discovery Agent with S3 Sync
Discovers, downloads, and syncs publicly available PDFs to AWS S3
"""

import json
import os
import time
import requests
import hashlib
import subprocess
import argparse
from datetime import datetime
from urllib.parse import urlparse, unquote, urljoin
from typing import List, Dict, Any, Optional, Set, Tuple
import logging
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('knowledge_discovery_agent.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class S3Config:
    """Configuration for S3 sync"""
    bucket_name: str = "knowledge4westpac"
    prefix: str = "verified-pdfs"
    sync_enabled: bool = True
    delete_removed: bool = False
    dry_run: bool = False
    
@dataclass
class DownloadLimits:
    """Configuration for download limits"""
    max_files_per_sync: Optional[int] = None
    max_files_per_category: Optional[int] = None
    max_total_size_mb: Optional[int] = None
    max_file_size_mb: Optional[int] = 100
    priority_categories: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        if not self.priority_categories:
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
    source: str = "public-website"
    priority: int = 5
    s3_key: Optional[str] = None
    s3_synced: bool = False
    s3_sync_time: Optional[str] = None

class EnhancedPDFCategorizer:
    """Enhanced PDF categorization with all discovered patterns"""
    
    CATEGORY_RULES = {
        'product-disclosure': [
            lambda f: 'pds' in f,
            lambda f: 'pis' in f,
            lambda f: 'product' in f and 'disclosure' in f,
            lambda f: 'fsr_' in f,
            lambda f: 'disclosure' in f and ('statement' in f or 'document' in f),
            lambda f: 'fsg' in f,
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
        'misc': []
    }
    
    CATEGORY_PRIORITIES = {
        'product-disclosure': 1,
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
    def categorize_with_priority(cls, filename: str) -> Tuple[str, int]:
        """Categorize PDF and assign priority"""
        filename_lower = filename.lower()
        
        for category, rules in cls.CATEGORY_RULES.items():
            if any(rule(filename_lower) for rule in rules):
                priority = cls.CATEGORY_PRIORITIES.get(category, 10)
                return category, priority
        
        return 'misc', cls.CATEGORY_PRIORITIES['misc']

class KnowledgeDiscoveryAgent:
    """Knowledge Discovery Agent with S3 sync capabilities"""
    
    def __init__(self, base_path: str = "./westpac_pdfs", 
                 limits: DownloadLimits = None,
                 s3_config: S3Config = None):
        self.base_path = base_path
        self.limits = limits or DownloadLimits()
        self.s3_config = s3_config or S3Config()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        self.discovered_urls: Set[str] = set()
        
        # Ensure base directory exists
        os.makedirs(base_path, exist_ok=True)
        
        # Create category directories
        categories = ['product-disclosure', 'annual-reports', 'sustainability', 'policies', 
                     'forms', 'fees-charges', 'legal-terms', 'research', 'banking-products', 
                     'brochures', 'investor-centre', 'misc']
        for category in categories:
            os.makedirs(os.path.join(base_path, category), exist_ok=True)
    
    def check_aws_credentials(self) -> bool:
        """Check if AWS credentials are configured"""
        try:
            result = subprocess.run(
                ['aws', 'sts', 'get-caller-identity'],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                logger.info("✅ AWS credentials verified")
                return True
            else:
                logger.warning("⚠️  AWS credentials not configured or invalid")
                return False
        except Exception as e:
            logger.error(f"❌ Error checking AWS credentials: {e}")
            return False
    
    def test_s3_access(self) -> bool:
        """Test S3 bucket access"""
        if not self.s3_config.sync_enabled:
            return True
            
        try:
            cmd = ['aws', 's3', 'ls', f's3://{self.s3_config.bucket_name}/']
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info(f"✅ S3 bucket access confirmed: {self.s3_config.bucket_name}")
                return True
            else:
                # Try a different approach - head bucket
                cmd = ['aws', 's3api', 'head-bucket', '--bucket', self.s3_config.bucket_name]
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode == 0:
                    logger.info(f"✅ S3 bucket exists and accessible: {self.s3_config.bucket_name}")
                    return True
                else:
                    logger.warning(f"⚠️  Cannot access S3 bucket: {self.s3_config.bucket_name}")
                    logger.warning(f"   Error: {result.stderr}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Error testing S3 access: {e}")
            return False
    
    def sync_to_s3(self, pdf_files: List[PDFFile]) -> Dict[str, Any]:
        """Sync PDFs to S3 bucket"""
        if not self.s3_config.sync_enabled:
            logger.info("📴 S3 sync is disabled")
            return {"status": "disabled"}
        
        if not self.check_aws_credentials():
            return {"status": "error", "message": "AWS credentials not configured"}
        
        if not self.test_s3_access():
            return {"status": "error", "message": "Cannot access S3 bucket"}
        
        logger.info(f"🔄 Starting S3 sync to s3://{self.s3_config.bucket_name}/{self.s3_config.prefix}/")
        
        sync_results = {
            "status": "success",
            "synced": 0,
            "failed": 0,
            "skipped": 0,
            "files": []
        }
        
        for pdf in pdf_files:
            if not os.path.exists(pdf.local_path):
                sync_results["skipped"] += 1
                continue
            
            # Generate S3 key
            pdf.s3_key = f"{self.s3_config.prefix}/{pdf.category}/{pdf.filename}"
            
            try:
                # Build AWS CLI command
                cmd = [
                    'aws', 's3', 'cp',
                    pdf.local_path,
                    f's3://{self.s3_config.bucket_name}/{pdf.s3_key}'
                ]
                
                if self.s3_config.dry_run:
                    cmd.append('--dryrun')
                
                # Execute upload
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode == 0:
                    pdf.s3_synced = True
                    pdf.s3_sync_time = datetime.now().isoformat()
                    sync_results["synced"] += 1
                    sync_results["files"].append({
                        "filename": pdf.filename,
                        "s3_key": pdf.s3_key,
                        "status": "success"
                    })
                    logger.info(f"✅ Synced: {pdf.filename} → {pdf.s3_key}")
                else:
                    sync_results["failed"] += 1
                    sync_results["files"].append({
                        "filename": pdf.filename,
                        "s3_key": pdf.s3_key,
                        "status": "failed",
                        "error": result.stderr
                    })
                    logger.error(f"❌ Failed to sync {pdf.filename}: {result.stderr}")
                    
            except Exception as e:
                sync_results["failed"] += 1
                sync_results["files"].append({
                    "filename": pdf.filename,
                    "s3_key": pdf.s3_key,
                    "status": "error",
                    "error": str(e)
                })
                logger.error(f"❌ Error syncing {pdf.filename}: {e}")
        
        # Save sync results
        with open('s3_sync_results.json', 'w') as f:
            json.dump(sync_results, f, indent=2)
        
        logger.info(f"📊 S3 Sync Summary: {sync_results['synced']} synced, {sync_results['failed']} failed")
        
        return sync_results
    
    def sync_inventory_to_s3(self, inventory_file: str = "mvp_inventory.json") -> Dict[str, Any]:
        """Sync files from a specific inventory to S3"""
        inventory_path = os.path.join(os.path.dirname(self.base_path), inventory_file)
        
        if not os.path.exists(inventory_path):
            logger.error(f"❌ Inventory file not found: {inventory_path}")
            return {"status": "error", "message": "Inventory file not found"}
        
        # Load inventory
        with open(inventory_path, 'r') as f:
            inventory = json.load(f)
        
        logger.info(f"📋 Loading {len(inventory['files'])} files from {inventory_file}")
        
        # Convert inventory to PDFFile objects
        pdf_files = []
        for file_info in inventory['files']:
            pdf = PDFFile(
                url=file_info.get('url') or file_info.get('original_url', ''),
                filename=file_info['filename'],
                category=file_info.get('category', 'misc'),
                local_path=file_info['local_path'],
                file_size=file_info.get('size'),
                checksum=file_info.get('checksum'),
                source=file_info.get('source', 'public-website')
            )
            
            # Adjust local path
            if pdf.local_path.startswith('agents/'):
                pdf.local_path = pdf.local_path.replace('agents/', '')
            elif not pdf.local_path.startswith(self.base_path):
                pdf.local_path = os.path.join(os.path.dirname(self.base_path), pdf.local_path)
            
            pdf_files.append(pdf)
        
        # Sync to S3
        return self.sync_to_s3(pdf_files)
    
    def discover_all_pdfs(self) -> List[str]:
        """Discover all publicly available PDFs"""
        logger.info("🚀 Starting comprehensive PDF discovery...")
        
        # Add discovery methods for different sources
        # This is where you'd add discovery logic for various websites
        
        # For now, return discovered URLs from existing inventory
        return sorted(list(self.discovered_urls))
    
    def download_file(self, url: str, local_path: str) -> Dict[str, Any]:
        """Download a single PDF file"""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            with open(local_path, 'wb') as f:
                f.write(response.content)
            
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
    
    def run(self, sync_to_s3: bool = True, inventory_file: Optional[str] = None) -> Dict[str, Any]:
        """Run the knowledge discovery agent"""
        start_time = datetime.now()
        logger.info("🤖 Starting Knowledge Discovery Agent...")
        
        if inventory_file:
            # Sync specific inventory to S3
            sync_results = self.sync_inventory_to_s3(inventory_file)
            
            end_time = datetime.now()
            duration = end_time - start_time
            
            return {
                "status": "complete",
                "operation": "s3_sync",
                "inventory_file": inventory_file,
                "duration_seconds": duration.total_seconds(),
                "sync_results": sync_results
            }
        else:
            # Normal discovery and download flow
            urls = self.discover_all_pdfs()
            
            # ... download logic ...
            
            # After downloads, optionally sync to S3
            if sync_to_s3 and self.s3_config.sync_enabled:
                # Get all PDFs for sync
                pdf_files = []  # This would be populated from downloads
                sync_results = self.sync_to_s3(pdf_files)
            else:
                sync_results = {"status": "skipped"}
            
            end_time = datetime.now()
            duration = end_time - start_time
            
            return {
                "status": "complete",
                "duration_seconds": duration.total_seconds(),
                "sync_results": sync_results
            }

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Knowledge Discovery Agent with S3 Sync')
    parser.add_argument('--bucket', default='knowledge4westpac', help='S3 bucket name')
    parser.add_argument('--no-sync', action='store_true', help='Skip S3 sync')
    parser.add_argument('--dry-run', action='store_true', help='Dry run mode')
    parser.add_argument('--sync-inventory', help='Sync specific inventory file to S3')
    parser.add_argument('--base-path', default='./westpac_pdfs', help='Base path for PDFs')
    
    args = parser.parse_args()
    
    # Configure S3
    s3_config = S3Config(
        bucket_name=args.bucket,
        sync_enabled=not args.no_sync,
        dry_run=args.dry_run
    )
    
    # Configure limits
    limits = DownloadLimits(
        max_files_per_sync=100,
        max_file_size_mb=50
    )
    
    # Create agent
    agent = KnowledgeDiscoveryAgent(
        base_path=args.base_path,
        limits=limits,
        s3_config=s3_config
    )
    
    # Run agent
    if args.sync_inventory:
        results = agent.run(sync_to_s3=True, inventory_file=args.sync_inventory)
        logger.info(f"✅ S3 sync completed for {args.sync_inventory}")
    else:
        results = agent.run(sync_to_s3=not args.no_sync)
        logger.info("✅ Knowledge discovery completed")

if __name__ == "__main__":
    main()