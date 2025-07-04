#!/usr/bin/env python3
"""
Design for swarm ingestion architecture to parallelize document processing
"""

import asyncio
import concurrent.futures
import multiprocessing as mp
import logging
import time
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import json
from dataclasses import dataclass
from enum import Enum
import queue
import redis
from neo4j import GraphDatabase

logger = logging.getLogger(__name__)

class IngestionTaskType(Enum):
    PDF_EXTRACT = "pdf_extract"
    CHUNK_PROCESSING = "chunk_processing"  
    EMBEDDING_GENERATION = "embedding_generation"
    ENTITY_EXTRACTION = "entity_extraction"
    GRAPH_INSERTION = "graph_insertion"
    RELATIONSHIP_BUILDING = "relationship_building"

@dataclass
class IngestionTask:
    task_id: str
    task_type: IngestionTaskType
    document_path: str
    chunk_data: Optional[Dict] = None
    priority: int = 1
    retry_count: int = 0
    max_retries: int = 3

class SwarmIngestionOrchestrator:
    """
    Orchestrate parallel ingestion using worker swarm
    
    Architecture:
    - Task Queue (Redis/RabbitMQ)
    - Worker Pool (CPU-bound: PDF processing, I/O-bound: DB operations)
    - Result Aggregator
    - Progress Monitor
    - Error Handler with retry logic
    """
    
    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str,
                 redis_url: str = "redis://localhost:6379"):
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user  
        self.neo4j_password = neo4j_password
        self.redis_client = redis.from_url(redis_url)
        
        # Worker configuration
        self.cpu_workers = mp.cpu_count()  # For CPU-intensive tasks
        self.io_workers = min(10, mp.cpu_count() * 2)  # For I/O operations
        
        # Task queues
        self.pdf_queue = "pdf_processing_queue"
        self.embedding_queue = "embedding_queue"
        self.graph_queue = "graph_insertion_queue"
        
    async def ingest_documents_swarm(self, document_paths: List[str]) -> Dict:
        """Coordinate swarm ingestion of multiple documents"""
        start_time = time.time()
        
        # Step 1: Create task pipeline
        tasks = self._create_task_pipeline(document_paths)
        
        # Step 2: Start worker pools
        workers = await self._start_worker_pools()
        
        # Step 3: Submit tasks and monitor progress
        results = await self._execute_pipeline(tasks, workers)
        
        # Step 4: Post-processing (relationships, community detection)
        await self._post_process_results(results)
        
        total_time = time.time() - start_time
        
        return {
            "documents_processed": len(document_paths),
            "total_time": total_time,
            "throughput": len(document_paths) / total_time,
            "results": results
        }
    
    def _create_task_pipeline(self, document_paths: List[str]) -> List[IngestionTask]:
        """Create ordered pipeline of tasks for parallel execution"""
        tasks = []
        
        for doc_path in document_paths:
            doc_id = Path(doc_path).stem
            
            # Phase 1: PDF extraction (parallel per document)
            tasks.append(IngestionTask(
                task_id=f"{doc_id}_extract",
                task_type=IngestionTaskType.PDF_EXTRACT,
                document_path=doc_path,
                priority=1
            ))
            
            # Phase 2: Chunking (depends on extraction)
            tasks.append(IngestionTask(
                task_id=f"{doc_id}_chunk",
                task_type=IngestionTaskType.CHUNK_PROCESSING,
                document_path=doc_path,
                priority=2
            ))
            
            # Phase 3: Embedding generation (parallel per chunk)
            tasks.append(IngestionTask(
                task_id=f"{doc_id}_embed",
                task_type=IngestionTaskType.EMBEDDING_GENERATION,
                document_path=doc_path,
                priority=3
            ))
            
            # Phase 4: Entity extraction (parallel per chunk)
            tasks.append(IngestionTask(
                task_id=f"{doc_id}_entities",
                task_type=IngestionTaskType.ENTITY_EXTRACTION,
                document_path=doc_path,
                priority=3
            ))
            
            # Phase 5: Graph insertion (serialized per document)
            tasks.append(IngestionTask(
                task_id=f"{doc_id}_graph",
                task_type=IngestionTaskType.GRAPH_INSERTION,
                document_path=doc_path,
                priority=4
            ))
        
        # Phase 6: Cross-document relationship building (final phase)
        tasks.append(IngestionTask(
            task_id="relationships",
            task_type=IngestionTaskType.RELATIONSHIP_BUILDING,
            document_path="",
            priority=5
        ))
        
        return tasks
    
    async def _start_worker_pools(self) -> Dict:
        """Start specialized worker pools for different task types"""
        workers = {}
        
        # CPU-intensive workers (PDF processing, chunking)
        workers['cpu_pool'] = concurrent.futures.ProcessPoolExecutor(
            max_workers=self.cpu_workers
        )
        
        # I/O workers (database operations)
        workers['io_pool'] = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.io_workers
        )
        
        # GPU workers (if available for embeddings)
        try:
            import torch
            if torch.cuda.is_available():
                workers['gpu_pool'] = concurrent.futures.ThreadPoolExecutor(
                    max_workers=torch.cuda.device_count()
                )
            else:
                workers['gpu_pool'] = workers['cpu_pool']  # Fallback to CPU
        except ImportError:
            workers['gpu_pool'] = workers['cpu_pool']
            
        return workers
    
    async def _execute_pipeline(self, tasks: List[IngestionTask], 
                               workers: Dict) -> Dict:
        """Execute task pipeline with dependency management"""
        results = {}
        completed_tasks = set()
        
        # Group tasks by priority (phase)
        phases = {}
        for task in tasks:
            if task.priority not in phases:
                phases[task.priority] = []
            phases[task.priority].append(task)
        
        # Execute phases sequentially, tasks within phase in parallel
        for phase_num in sorted(phases.keys()):
            phase_tasks = phases[phase_num]
            logger.info(f"Executing phase {phase_num} with {len(phase_tasks)} tasks")
            
            # Submit all tasks in phase
            futures = []
            for task in phase_tasks:
                future = self._submit_task(task, workers)
                futures.append((task, future))
            
            # Wait for phase completion
            phase_results = {}
            for task, future in futures:
                try:
                    result = await asyncio.wrap_future(future)
                    phase_results[task.task_id] = result
                    completed_tasks.add(task.task_id)
                except Exception as e:
                    logger.error(f"Task {task.task_id} failed: {e}")
                    if task.retry_count < task.max_retries:
                        # Retry logic
                        task.retry_count += 1
                        retry_future = self._submit_task(task, workers)
                        result = await asyncio.wrap_future(retry_future)
                        phase_results[task.task_id] = result
                    else:
                        phase_results[task.task_id] = {"error": str(e)}
            
            results[f"phase_{phase_num}"] = phase_results
            logger.info(f"Phase {phase_num} completed: {len(phase_results)} tasks")
        
        return results
    
    def _submit_task(self, task: IngestionTask, workers: Dict) -> concurrent.futures.Future:
        """Submit task to appropriate worker pool"""
        if task.task_type in [IngestionTaskType.PDF_EXTRACT, IngestionTaskType.CHUNK_PROCESSING]:
            # CPU-intensive tasks
            return workers['cpu_pool'].submit(self._execute_cpu_task, task)
        elif task.task_type == IngestionTaskType.EMBEDDING_GENERATION:
            # GPU/CPU task
            return workers['gpu_pool'].submit(self._execute_embedding_task, task)
        else:
            # I/O tasks (database operations)
            return workers['io_pool'].submit(self._execute_io_task, task)
    
    def _execute_cpu_task(self, task: IngestionTask) -> Dict:
        """Execute CPU-intensive task"""
        if task.task_type == IngestionTaskType.PDF_EXTRACT:
            return self._extract_pdf(task.document_path)
        elif task.task_type == IngestionTaskType.CHUNK_PROCESSING:
            return self._process_chunks(task.document_path)
        
    def _execute_embedding_task(self, task: IngestionTask) -> Dict:
        """Execute embedding generation task"""
        return self._generate_embeddings(task.document_path)
    
    def _execute_io_task(self, task: IngestionTask) -> Dict:
        """Execute I/O task"""
        if task.task_type == IngestionTaskType.GRAPH_INSERTION:
            return self._insert_to_graph(task.document_path)
        elif task.task_type == IngestionTaskType.RELATIONSHIP_BUILDING:
            return self._build_relationships()
    
    def _extract_pdf(self, document_path: str) -> Dict:
        """Extract text from PDF (CPU-intensive)"""
        # Simulate PDF processing
        time.sleep(0.1)  # Simulated processing time
        return {
            "pages_extracted": 10,
            "text_length": 5000,
            "processing_time": 0.1
        }
    
    def _process_chunks(self, document_path: str) -> Dict:
        """Process document into chunks (CPU-intensive)"""
        time.sleep(0.05)
        return {
            "chunks_created": 25,
            "processing_time": 0.05
        }
    
    def _generate_embeddings(self, document_path: str) -> Dict:
        """Generate embeddings (GPU/CPU intensive)"""
        time.sleep(0.2)  # Simulated embedding generation
        return {
            "embeddings_generated": 25,
            "processing_time": 0.2
        }
    
    def _insert_to_graph(self, document_path: str) -> Dict:
        """Insert data to graph database (I/O intensive)"""
        time.sleep(0.1)  # Simulated database operations
        return {
            "nodes_created": 50,
            "relationships_created": 100,
            "processing_time": 0.1
        }
    
    def _build_relationships(self) -> Dict:
        """Build cross-document relationships"""
        time.sleep(1.0)  # Simulated relationship building
        return {
            "relationships_built": 500,
            "processing_time": 1.0
        }
    
    async def _post_process_results(self, results: Dict):
        """Post-processing: community detection, optimization"""
        logger.info("Running post-processing...")
        
        # Run community detection on new entities
        # Update search indexes
        # Optimize graph structure
        
        return {"post_processing": "completed"}


class IngestionPerformanceAnalyzer:
    """Analyze performance gains from swarm ingestion"""
    
    @staticmethod
    def calculate_theoretical_speedup(num_documents: int, cpu_cores: int) -> Dict:
        """Calculate theoretical speedup from parallelization"""
        
        # Current sequential processing (simplified model)
        sequential_time_per_doc = {
            "pdf_extraction": 2.0,      # 2 seconds per document
            "chunking": 1.0,            # 1 second per document  
            "embedding": 5.0,           # 5 seconds per document
            "entity_extraction": 3.0,   # 3 seconds per document
            "graph_insertion": 2.0,     # 2 seconds per document
            "relationship_building": 10.0  # 10 seconds total (not per doc)
        }
        
        sequential_total = (
            sum(sequential_time_per_doc.values()) - 
            sequential_time_per_doc["relationship_building"]
        ) * num_documents + sequential_time_per_doc["relationship_building"]
        
        # Parallel processing with optimal distribution
        parallel_phases = {
            "phase_1_extraction": max(1, num_documents / cpu_cores) * sequential_time_per_doc["pdf_extraction"],
            "phase_2_chunking": max(1, num_documents / cpu_cores) * sequential_time_per_doc["chunking"],
            "phase_3_embedding": max(1, num_documents / cpu_cores) * sequential_time_per_doc["embedding"],
            "phase_4_entities": max(1, num_documents / cpu_cores) * sequential_time_per_doc["entity_extraction"],
            "phase_5_graph": max(1, num_documents / min(10, cpu_cores)) * sequential_time_per_doc["graph_insertion"],
            "phase_6_relationships": sequential_time_per_doc["relationship_building"]
        }
        
        parallel_total = sum(parallel_phases.values())
        
        return {
            "sequential_time": sequential_total,
            "parallel_time": parallel_total,
            "speedup_factor": sequential_total / parallel_total,
            "time_saved": sequential_total - parallel_total,
            "efficiency": (sequential_total / parallel_total) / cpu_cores,
            "bottleneck_phase": max(parallel_phases.items(), key=lambda x: x[1])[0]
        }


# Example usage and performance analysis
if __name__ == "__main__":
    # Performance analysis for different document counts
    scenarios = [10, 50, 100, 500]
    cpu_cores = mp.cpu_count()
    
    print(f"Swarm Ingestion Performance Analysis (CPU cores: {cpu_cores})")
    print("=" * 70)
    
    for num_docs in scenarios:
        analysis = IngestionPerformanceAnalyzer.calculate_theoretical_speedup(
            num_docs, cpu_cores
        )
        
        print(f"\n{num_docs} documents:")
        print(f"  Sequential time: {analysis['sequential_time']:.1f}s ({analysis['sequential_time']/60:.1f}m)")
        print(f"  Parallel time:   {analysis['parallel_time']:.1f}s ({analysis['parallel_time']/60:.1f}m)")
        print(f"  Speedup factor:  {analysis['speedup_factor']:.1f}x")
        print(f"  Time saved:      {analysis['time_saved']:.1f}s ({analysis['time_saved']/60:.1f}m)")
        print(f"  Efficiency:      {analysis['efficiency']*100:.1f}%")
        print(f"  Bottleneck:      {analysis['bottleneck_phase']}")