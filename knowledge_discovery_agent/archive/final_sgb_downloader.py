#!/usr/bin/env python3
"""
Final SGB downloader to get remaining St.George PDFs from PDS directory
"""

import os
import requests
import hashlib
from datetime import datetime
from typing import List, Dict, Any

def download_remaining_sgb_pdfs():
    """Download any remaining SGB PDFs from St.George PDS directory"""
    
    base_path = "/Users/jaskew/workspace/Skynet/desktop/claude/westpac/agents/westpac_pdfs"
    pds_url = "https://www.stgeorge.com.au/content/dam/stg/downloads/pds/"
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    })
    
    # List of SGB files that might be in the PDS directory
    sgb_files = [
        "SGB-FgnCurrencyAccountTC.pdf",  # We know this one exists
        "SGB-FXSwapPDS.pdf",            # We know this one exists
        "SGB-FXTransactionPDS.pdf",     # We know this one exists  
        "SGB-FlexiForwardPDS.pdf",
        "SGB-ForeignExchangeOptionPDS.pdf",
        "SGB-ParticipatingForwardPDS.pdf",
        "SGB-RangeForwardPDS.pdf",
        "SGB-BonusForwardContractPIS.pdf",
        "SGB-DualCurrencyInvestmentPIS.pdf",
        "SGB-EnhancedForwardContractPIS.pdf",
        "SGB-InterestRateSwapPIS.pdf",
        "SGB-Knock-OutSmartForwardContractPIS.pdf",
        "SGB-ResetFowardContractPIS.pdf",
        "SGB-TargetForwardContractPIS.pdf",
        "SGB-WindowSmartForwardContractPIS.pdf",
        "SGB-TLDProductInformationStatement.pdf",
        "SGB-ForeignCurrencyTermDepositPDS_Mar_2020.pdf",
        "SGB_Range_PIS_0523.pdf",
        "SGB_Rebate_PIS_0523.pdf",
    ]
    
    results = []
    new_downloads = 0
    
    print("🎯 Testing specific SGB files in St.George PDS directory...")
    
    for filename in sgb_files:
        url = pds_url + filename
        
        # Check if file already exists locally
        local_path = os.path.join(base_path, "product-disclosure", filename)
        if os.path.exists(local_path):
            print(f"⏭️  Skipping {filename} (already exists)")
            continue
        
        try:
            # Test if URL exists
            response = session.head(url, timeout=10)
            
            if response.status_code == 200:
                print(f"✅ Found: {filename}")
                
                # Download the file
                download_response = session.get(url, timeout=30)
                download_response.raise_for_status()
                
                # Ensure directory exists
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                
                with open(local_path, 'wb') as f:
                    f.write(download_response.content)
                
                size_mb = len(download_response.content) / (1024 * 1024)
                checksum = hashlib.md5(download_response.content).hexdigest()
                
                result = {
                    "success": True,
                    "url": url,
                    "filename": filename,
                    "local_path": local_path,
                    "category": "product-disclosure",
                    "size": len(download_response.content),
                    "checksum": checksum,
                    "download_time": datetime.now().isoformat(),
                    "source": "stgeorge.com.au/pds"
                }
                
                results.append(result)
                new_downloads += 1
                print(f"📥 Downloaded: {filename} ({size_mb:.1f}MB)")
                
            else:
                print(f"❌ Not found: {filename} (HTTP {response.status_code})")
                
        except Exception as e:
            print(f"❌ Error with {filename}: {e}")
            
    print(f"\n✅ Completed! Downloaded {new_downloads} new SGB PDFs")
    return results, new_downloads

if __name__ == "__main__":
    results, count = download_remaining_sgb_pdfs()
    print(f"Final result: {count} new PDFs downloaded")