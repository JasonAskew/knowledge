#!/usr/bin/env python3
"""
Patch for Docker-compatible ingestion
"""

import os

# Create a patch for the ingestion agent
patch_content = """
# Docker-compatible patch
import os
if os.environ.get('DOCKER_ENVIRONMENT'):
    print("Running in Docker - using ThreadPoolExecutor instead of ProcessPoolExecutor")
    from concurrent.futures import ThreadPoolExecutor as PoolExecutor
else:
    from concurrent.futures import ProcessPoolExecutor as PoolExecutor

# Replace line 697 in process_inventory method
"""

print(patch_content)

# The actual fix is to use ThreadPoolExecutor in Docker
# or process files sequentially