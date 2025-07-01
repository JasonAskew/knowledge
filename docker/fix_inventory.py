#!/usr/bin/env python3
"""
Fix inventory paths to work with docker mount
"""

import json
import os

# Read the inventory
with open('/data/inventories/mvp_inventory.json', 'r') as f:
    inventory = json.load(f)

# Fix paths - remove the prefix and just use the path after westpac_pdfs
fixed_files = []
for item in inventory['files']:
    # Extract the path after westpac_pdfs/
    parts = item['file_path'].split('westpac_pdfs/')
    if len(parts) > 1:
        new_path = '/data/pdfs/' + parts[1]
        item['file_path'] = new_path
        fixed_files.append(item)

# Save fixed inventory
fixed_inventory = {
    "title": inventory.get("title", "MVP PDF Inventory"),
    "description": inventory.get("description", "Fixed paths for docker"),
    "files": fixed_files
}

with open('/data/inventories/mvp_inventory_fixed.json', 'w') as f:
    json.dump(fixed_inventory, f, indent=2)

print(f"Fixed {len(fixed_files)} file paths")
print("Sample fixed path:", fixed_files[0]['file_path'] if fixed_files else "No files")