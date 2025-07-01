#!/usr/bin/env python3
"""
Simple S3 sync script for knowledge discovery agent
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from knowledge_discovery_agent_v2 import KnowledgeDiscoveryAgent, S3Config, DownloadLimits
import argparse

def main():
    parser = argparse.ArgumentParser(description='Sync PDFs to S3')
    parser.add_argument('--mvp', action='store_true', help='Sync only MVP inventory')
    parser.add_argument('--all', action='store_true', help='Sync all verified PDFs')
    parser.add_argument('--bucket', default='knowledge4westpac', help='S3 bucket name')
    parser.add_argument('--dry-run', action='store_true', help='Dry run mode')
    
    args = parser.parse_args()
    
    # Configure S3
    s3_config = S3Config(
        bucket_name=args.bucket,
        sync_enabled=True,
        dry_run=args.dry_run
    )
    
    # Create agent
    agent = KnowledgeDiscoveryAgent(
        base_path='./westpac_pdfs',
        s3_config=s3_config
    )
    
    if args.mvp:
        print("🚀 Syncing MVP inventory to S3...")
        results = agent.sync_inventory_to_s3('mvp_inventory.json')
    elif args.all:
        print("🚀 Syncing all verified PDFs to S3...")
        results = agent.sync_inventory_to_s3('downloaded_pdfs_inventory_verified.json')
    else:
        print("Please specify --mvp or --all")
        return
    
    # Print summary
    if results.get('status') == 'success':
        print(f"\n✅ S3 Sync Complete!")
        print(f"   Synced: {results.get('synced', 0)} files")
        print(f"   Failed: {results.get('failed', 0)} files")
        print(f"   Bucket: s3://{args.bucket}/verified-pdfs/")
    else:
        print(f"\n❌ S3 Sync Failed: {results.get('message', 'Unknown error')}")

if __name__ == "__main__":
    main()