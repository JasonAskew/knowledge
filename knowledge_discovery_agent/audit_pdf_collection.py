#!/usr/bin/env python3
"""
Audit PDF Collection - Verify which files are accessible on the web
Separates web-accessible files from orphaned local files
"""

import json
import os
import requests
import time
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Tuple
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pdf_audit.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class PDFCollectionAuditor:
    """Audits PDF collection to separate web-accessible from orphaned files"""
    
    def __init__(self, base_path: str = "./westpac_pdfs", inventory_path: str = "../downloaded_pdfs_inventory.json"):
        self.base_path = Path(base_path)
        self.inventory_path = Path(inventory_path)
        self.orphaned_path = Path("./orphaned_pdfs")
        
        # Setup session for web requests
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        
        # Results tracking
        self.web_accessible = []
        self.orphaned_files = []
        self.url_mapping = {}
        
    def load_inventory(self) -> Dict[str, Any]:
        """Load existing inventory file"""
        if not self.inventory_path.exists():
            logger.error(f"Inventory file not found: {self.inventory_path}")
            return {"files": []}
        
        with open(self.inventory_path, 'r') as f:
            return json.load(f)
    
    def scan_local_files(self) -> List[Dict[str, str]]:
        """Scan all PDF files in the collection"""
        local_files = []
        
        logger.info(f"📁 Scanning {self.base_path} for PDF files...")
        
        for pdf_file in self.base_path.rglob("*.pdf"):
            relative_path = pdf_file.relative_to(self.base_path)
            category = relative_path.parent.name if relative_path.parent.name != "westpac_pdfs" else "misc"
            
            local_files.append({
                "filename": pdf_file.name,
                "local_path": str(pdf_file),
                "relative_path": str(relative_path),
                "category": category,
                "size": pdf_file.stat().st_size
            })
        
        logger.info(f"Found {len(local_files)} PDF files locally")
        return local_files
    
    def find_potential_urls(self, filename: str) -> List[str]:
        """Generate potential URLs for a filename based on known patterns"""
        potential_urls = []
        
        # Westpac patterns - comprehensive including Firecrawl-discovered directories
        westpac_patterns = [
            # Firecrawl-discovered media centre and communications
            f"https://www.westpac.com.au/content/dam/public/wbc/images/about/media-centre/Documents/{filename}",
            f"https://www.westpac.com.au/content/dam/public/wbc/documents/media/{filename}",
            f"https://www.westpac.com.au/content/dam/public/wbc/documents/about/{filename}",
            # Main directories
            f"https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/pb/{filename}",
            f"https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/bb/{filename}",
            f"https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/{filename}",
            f"https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/aw/ic/{filename}",  # investor centre
            f"https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/col/{filename}",
            f"https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/olb/{filename}",
            f"https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/cb/{filename}",
            # Additional subdirectories
            f"https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/access-and-inclusion/{filename}",
            f"https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/contact-us/{filename}",
            f"https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/help/{filename}",
            f"https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/margin-lending/{filename}",
            f"https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/mobile/{filename}",
            f"https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/new-customer-checklist/{filename}",
            f"https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/other/{filename}",
            f"https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/privacy/{filename}",
            f"https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/security/{filename}",
            f"https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/super/{filename}",
            f"https://www.westpac.com.au/content/dam/public/wbc/documents/pdf/uk-disclosure-statements/{filename}",
            # Legacy docs paths
            f"https://www.westpac.com.au/docs/pdf/pb/{filename}",
            f"https://www.westpac.com.au/docs/pdf/bb/{filename}",
            f"https://www.westpac.com.au/docs/pdf/aw/{filename}",
            # Sharetrading
            f"https://sharetrading.westpac.com.au/media/*//{filename}",
        ]
        
        # St.George patterns
        if filename.startswith('SGB-') or 'stg' in filename.lower():
            stgeorge_patterns = [
                f"https://www.stgeorge.com.au/content/dam/stg/downloads/pds/{filename}",
                f"https://www.stgeorge.com.au/content/dam/stg/documents/{filename}",
            ]
            potential_urls.extend(stgeorge_patterns)
        
        # Bank of Melbourne patterns
        if filename.startswith('BOM-') or 'bom' in filename.lower():
            bom_patterns = [
                f"https://www.bankofmelbourne.com.au/content/dam/bom/downloads/pds/{filename}",
                f"https://www.bankofmelbourne.com.au/content/dam/bom/documents/pds/{filename}",
            ]
            potential_urls.extend(bom_patterns)
        
        # BankSA patterns
        if filename.startswith('BSA-') or 'bsa' in filename.lower():
            bsa_patterns = [
                f"https://www.banksa.com.au/content/dam/bsa/downloads/pds/{filename}",
                f"https://www.banksa.com.au/content/dam/bsa/documents/pds/{filename}",
            ]
            potential_urls.extend(bsa_patterns)
        
        potential_urls.extend(westpac_patterns)
        return potential_urls
    
    def test_url_accessibility(self, url: str, max_retries: int = 2) -> Tuple[bool, int, str]:
        """Test if a URL is accessible"""
        for attempt in range(max_retries + 1):
            try:
                response = self.session.head(url, timeout=10, allow_redirects=True)
                return response.status_code == 200, response.status_code, ""
            except requests.exceptions.RequestException as e:
                if attempt == max_retries:
                    return False, 0, str(e)
                time.sleep(1)  # Brief retry delay
        return False, 0, "Max retries exceeded"
    
    def audit_file(self, file_info: Dict[str, str], inventory_files: List[Dict]) -> Dict[str, Any]:
        """Audit a single file to see if it's web-accessible"""
        filename = file_info["filename"]
        
        # First check if we have a known URL from inventory
        known_url = None
        for inv_file in inventory_files:
            if inv_file.get("filename") == filename:
                known_url = inv_file.get("url")
                break
        
        # Test known URL first
        if known_url:
            accessible, status_code, error = self.test_url_accessibility(known_url)
            if accessible:
                logger.info(f"✅ {filename} - accessible at known URL")
                return {
                    "status": "web_accessible",
                    "url": known_url,
                    "status_code": status_code,
                    "method": "known_url"
                }
            else:
                logger.debug(f"❌ Known URL failed for {filename}: HTTP {status_code}")
        
        # Try potential URLs
        potential_urls = self.find_potential_urls(filename)
        
        for url in potential_urls[:5]:  # Limit to first 5 attempts
            accessible, status_code, error = self.test_url_accessibility(url)
            if accessible:
                logger.info(f"✅ {filename} - found at {url}")
                return {
                    "status": "web_accessible", 
                    "url": url,
                    "status_code": status_code,
                    "method": "pattern_match"
                }
            time.sleep(0.2)  # Rate limiting
        
        logger.warning(f"🔍 {filename} - not found on web")
        return {
            "status": "orphaned",
            "url": known_url,
            "method": "not_found",
            "tested_urls": len(potential_urls)
        }
    
    def run_audit(self, max_files: int = None) -> Dict[str, Any]:
        """Run complete audit of PDF collection"""
        start_time = datetime.now()
        logger.info("🔍 Starting PDF collection audit...")
        
        # Load inventory and scan files
        inventory = self.load_inventory()
        inventory_files = inventory.get("files", [])
        local_files = self.scan_local_files()
        
        if max_files:
            local_files = local_files[:max_files]
            logger.info(f"Limiting audit to first {max_files} files for testing")
        
        # Audit each file
        results = {
            "audit_date": start_time.isoformat(),
            "total_files": len(local_files),
            "web_accessible": [],
            "orphaned": [],
            "summary": {}
        }
        
        for i, file_info in enumerate(local_files, 1):
            logger.info(f"Testing {i}/{len(local_files)}: {file_info['filename']}")
            
            audit_result = self.audit_file(file_info, inventory_files)
            
            # Combine file info with audit result
            complete_info = {**file_info, **audit_result}
            
            if audit_result["status"] == "web_accessible":
                results["web_accessible"].append(complete_info)
                self.web_accessible.append(complete_info)
                self.url_mapping[complete_info["filename"]] = complete_info["url"]
            else:
                results["orphaned"].append(complete_info)
                self.orphaned_files.append(complete_info)
            
            # Progress update every 25 files
            if i % 25 == 0:
                accessible_count = len(results["web_accessible"])
                orphaned_count = len(results["orphaned"])
                logger.info(f"Progress: {accessible_count} accessible, {orphaned_count} orphaned")
        
        # Generate summary
        duration = datetime.now() - start_time
        results["summary"] = {
            "total_files": len(local_files),
            "web_accessible_count": len(results["web_accessible"]),
            "orphaned_count": len(results["orphaned"]),
            "duration_seconds": duration.total_seconds(),
            "success_rate": len(results["web_accessible"]) / len(local_files) * 100 if local_files else 0
        }
        
        logger.info(f"🎯 Audit complete!")
        logger.info(f"📊 Results: {results['summary']['web_accessible_count']} accessible, {results['summary']['orphaned_count']} orphaned")
        logger.info(f"⏱️  Duration: {duration}")
        
        return results
    
    def create_orphaned_directory(self):
        """Create directory for orphaned files"""
        self.orphaned_path.mkdir(exist_ok=True)
        
        # Create category subdirectories
        categories = ['product-disclosure', 'annual-reports', 'sustainability', 'policies', 
                     'forms', 'fees-charges', 'legal-terms', 'research', 'banking-products', 
                     'brochures', 'investor-centre', 'misc']
        
        for category in categories:
            (self.orphaned_path / category).mkdir(exist_ok=True)
    
    def move_orphaned_files(self, audit_results: Dict[str, Any]):
        """Move orphaned files to separate directory"""
        logger.info("📦 Creating orphaned files directory...")
        self.create_orphaned_directory()
        
        moved_count = 0
        for file_info in audit_results["orphaned"]:
            source_path = Path(file_info["local_path"])
            target_path = self.orphaned_path / file_info["relative_path"]
            
            # Ensure target directory exists
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            try:
                shutil.move(str(source_path), str(target_path))
                logger.info(f"📦 Moved: {file_info['filename']} → orphaned_pdfs/{file_info['relative_path']}")
                moved_count += 1
            except Exception as e:
                logger.error(f"Failed to move {file_info['filename']}: {e}")
        
        logger.info(f"✅ Moved {moved_count} orphaned files to ./orphaned_pdfs/")
    
    def update_inventory_files(self, audit_results: Dict[str, Any]):
        """Update inventory files"""
        # Create new verified inventory (web-accessible only)
        verified_inventory = {
            "download_summary": {
                "total_files": len(audit_results["web_accessible"]),
                "audit_date": audit_results["audit_date"],
                "last_updated": datetime.now().isoformat(),
                "base_directory": str(self.base_path),
                "verification_status": "web_verified"
            },
            "files": []
        }
        
        # Create orphaned inventory  
        orphaned_inventory = {
            "orphaned_summary": {
                "total_files": len(audit_results["orphaned"]),
                "audit_date": audit_results["audit_date"],
                "last_updated": datetime.now().isoformat(),
                "base_directory": str(self.orphaned_path),
                "reason": "not_found_on_web"
            },
            "files": []
        }
        
        # Populate verified inventory
        for file_info in audit_results["web_accessible"]:
            verified_inventory["files"].append({
                "filename": file_info["filename"],
                "url": file_info["url"],
                "local_path": file_info["local_path"],
                "category": file_info["category"],
                "size": file_info["size"],
                "verification_method": file_info["method"],
                "verified_date": audit_results["audit_date"]
            })
        
        # Populate orphaned inventory
        for file_info in audit_results["orphaned"]:
            orphaned_path = str(self.orphaned_path / file_info["relative_path"])
            orphaned_inventory["files"].append({
                "filename": file_info["filename"],
                "original_url": file_info.get("url"),
                "local_path": orphaned_path,
                "original_path": file_info["local_path"],
                "category": file_info["category"],
                "size": file_info["size"],
                "tested_urls": file_info.get("tested_urls", 0),
                "orphaned_date": audit_results["audit_date"]
            })
        
        # Write verified inventory (replaces original)
        verified_path = "downloaded_pdfs_inventory_verified.json"
        with open(verified_path, 'w') as f:
            json.dump(verified_inventory, f, indent=2)
        logger.info(f"✅ Created verified inventory: {verified_path}")
        
        # Write orphaned inventory
        orphaned_inv_path = "orphaned_pdfs_inventory.json"
        with open(orphaned_inv_path, 'w') as f:
            json.dump(orphaned_inventory, f, indent=2)
        logger.info(f"✅ Created orphaned inventory: {orphaned_inv_path}")
        
        return verified_path, orphaned_inv_path
    
    def save_audit_results(self, results: Dict[str, Any]):
        """Save complete audit results"""
        audit_file = f"pdf_audit_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(audit_file, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"💾 Saved audit results: {audit_file}")

def main():
    """Main execution"""
    print("🔍 PDF Collection Audit Tool")
    print("This will verify which PDFs are accessible on the web vs orphaned locally\n")
    
    # Ask for confirmation
    response = input("Proceed with full audit? This may take some time. (y/N): ")
    if response.lower() != 'y':
        print("Audit cancelled.")
        return
    
    auditor = PDFCollectionAuditor()
    
    # Run audit (limit for testing)
    test_mode = input("Run in test mode (first 20 files only)? (y/N): ")
    max_files = 20 if test_mode.lower() == 'y' else None
    
    audit_results = auditor.run_audit(max_files=max_files)
    
    # Save results
    auditor.save_audit_results(audit_results)
    
    # Ask about moving files
    if audit_results["summary"]["orphaned_count"] > 0:
        move_response = input(f"\nFound {audit_results['summary']['orphaned_count']} orphaned files. Move them to ./orphaned_pdfs/? (y/N): ")
        if move_response.lower() == 'y':
            auditor.move_orphaned_files(audit_results)
            auditor.update_inventory_files(audit_results)
            print("\n✅ Audit complete! Files have been organized and inventories updated.")
        else:
            print("\n📋 Audit complete! Run again with 'y' to move files when ready.")
    else:
        print("\n🎉 All files are web-accessible! No orphaned files found.")

if __name__ == "__main__":
    main()