"""
Processing Queue Service for handling entry processing requests
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Callable
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, asdict
from collections import deque

from app.schemas.entry import ProcessingMode
from app.services.entry_processing import get_entry_processing_service
from app.services.websocket import get_websocket_manager
from app.db.repositories.entry_repository import EntryRepository
from app.models.entry import Entry

logger = logging.getLogger(__name__)


class ProcessingStatus(str, Enum):
    """Processing job status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class ProcessingJob:
    """Represents a processing job in the queue"""
    id: str
    entry_id: int
    mode: ProcessingMode
    raw_text: str
    status: ProcessingStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    error_message: Optional[str] = None
    result: Optional[Dict] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        data['started_at'] = self.started_at.isoformat() if self.started_at else None
        data['completed_at'] = self.completed_at.isoformat() if self.completed_at else None
        data['mode'] = self.mode.value
        data['status'] = self.status.value
        return data


class ProcessingQueue:
    """Queue service for managing entry processing jobs"""
    
    def __init__(self):
        self._queue: deque = deque()
        self._jobs: Dict[str, ProcessingJob] = {}
        self._processing = False
        self._worker_task: Optional[asyncio.Task] = None
        self._status_callbacks: List[Callable] = []
        
    async def start(self):
        """Start the processing queue worker"""
        if self._worker_task is None or self._worker_task.done():
            self._processing = True
            self._worker_task = asyncio.create_task(self._worker())
            logger.info("Processing queue worker started")
    
    async def stop(self):
        """Stop the processing queue worker"""
        self._processing = False
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("Processing queue worker stopped")
    
    def add_status_callback(self, callback: Callable):
        """Add a status update callback"""
        self._status_callbacks.append(callback)
    
    async def add_job(
        self, 
        entry_id: int, 
        mode: ProcessingMode, 
        raw_text: str,
        max_retries: int = 3
    ) -> str:
        """Add a new processing job to the queue"""
        job_id = f"job_{entry_id}_{mode.value}_{datetime.now().timestamp()}"
        
        job = ProcessingJob(
            id=job_id,
            entry_id=entry_id,
            mode=mode,
            raw_text=raw_text,
            status=ProcessingStatus.PENDING,
            created_at=datetime.now(),
            max_retries=max_retries
        )
        
        self._jobs[job_id] = job
        self._queue.append(job_id)
        
        logger.info(f"Added processing job {job_id} for entry {entry_id} mode {mode.value}")
        
        # Notify status callbacks
        await self._notify_status_change(job)
        
        # Ensure worker is running
        await self.start()
        
        return job_id
    
    def get_job(self, job_id: str) -> Optional[ProcessingJob]:
        """Get job by ID"""
        return self._jobs.get(job_id)
    
    def get_job_status(self, job_id: str) -> Optional[ProcessingStatus]:
        """Get job status"""
        job = self._jobs.get(job_id)
        return job.status if job else None
    
    def get_queue_status(self) -> Dict:
        """Get overall queue status"""
        pending = sum(1 for job in self._jobs.values() if job.status == ProcessingStatus.PENDING)
        processing = sum(1 for job in self._jobs.values() if job.status == ProcessingStatus.PROCESSING)
        completed = sum(1 for job in self._jobs.values() if job.status == ProcessingStatus.COMPLETED)
        failed = sum(1 for job in self._jobs.values() if job.status == ProcessingStatus.FAILED)
        
        return {
            "queue_size": len(self._queue),
            "total_jobs": len(self._jobs),
            "pending": pending,
            "processing": processing,
            "completed": completed,
            "failed": failed,
            "worker_active": self._processing
        }
    
    async def _worker(self):
        """Background worker to process jobs"""
        logger.info("Processing queue worker loop started")
        
        while self._processing:
            try:
                if not self._queue:
                    # No jobs, wait a bit
                    await asyncio.sleep(0.5)
                    continue
                
                job_id = self._queue.popleft()
                job = self._jobs.get(job_id)
                
                if not job:
                    logger.warning(f"Job {job_id} not found, skipping")
                    continue
                
                if job.status != ProcessingStatus.PENDING:
                    logger.warning(f"Job {job_id} status is {job.status}, skipping")
                    continue
                
                await self._process_job(job)
                
            except asyncio.CancelledError:
                logger.info("Processing queue worker cancelled")
                break
            except Exception as e:
                logger.error(f"Error in processing queue worker: {str(e)}")
                await asyncio.sleep(1)  # Brief pause on error
    
    async def _process_job(self, job: ProcessingJob):
        """Process a single job"""
        logger.info(f"Processing job {job.id} for entry {job.entry_id} mode {job.mode.value}")
        
        # Update status to processing
        job.status = ProcessingStatus.PROCESSING
        job.started_at = datetime.now()
        await self._notify_status_change(job)
        
        try:
            # Get processing service
            processing_service = await get_entry_processing_service()
            
            # Get entry from database
            entry = await EntryRepository.get_by_id(job.entry_id)
            if not entry:
                raise Exception(f"Entry {job.entry_id} not found")
            
            # Process the entry
            result = await processing_service.process_entry(
                raw_text=job.raw_text,
                mode=job.mode,
                existing_entry=entry
            )
            
            # Update entry based on processing mode
            if job.mode == ProcessingMode.ENHANCED:
                entry.enhanced_text = result["processed_text"]
            elif job.mode == ProcessingMode.STRUCTURED:
                entry.structured_summary = result["processed_text"]
            
            # Update processing metadata and word count
            entry.processing_metadata = result["processing_metadata"]
            entry.word_count = result["word_count"]
            # Don't overwrite entry.mode - keep it as "raw" since this is the base entry
            
            # Save to database
            await EntryRepository.update(entry)
            
            # Extract memories if this is enhanced text processing
            if job.mode == ProcessingMode.ENHANCED and entry.enhanced_text:
                try:
                    from app.services.memory_service import MemoryService
                    memory_service = MemoryService()
                    memory_count = memory_service.process_entry_for_memories(entry.id, entry.enhanced_text)
                    logger.info(f"Extracted {memory_count} memories from entry {entry.id}")
                except Exception as e:
                    logger.error(f"Failed to extract memories from entry {entry.id}: {e}")
            
            # Mark job as completed
            job.status = ProcessingStatus.COMPLETED
            job.completed_at = datetime.now()
            job.result = result
            job.error_message = None
            
            logger.info(f"Job {job.id} completed successfully")
            
        except Exception as e:
            logger.error(f"Job {job.id} failed: {str(e)}")
            
            job.error_message = str(e)
            job.retry_count += 1
            
            if job.retry_count <= job.max_retries:
                # Retry the job
                job.status = ProcessingStatus.RETRYING
                logger.info(f"Retrying job {job.id} (attempt {job.retry_count}/{job.max_retries})")
                
                # Add back to queue after a delay
                await asyncio.sleep(2 ** job.retry_count)  # Exponential backoff
                job.status = ProcessingStatus.PENDING
                self._queue.append(job.id)
            else:
                # Max retries reached
                job.status = ProcessingStatus.FAILED
                logger.error(f"Job {job.id} failed permanently after {job.retry_count} retries")
        
        # Notify status change
        await self._notify_status_change(job)
    
    async def _notify_status_change(self, job: ProcessingJob):
        """Notify all callbacks about status change"""
        for callback in self._status_callbacks:
            try:
                await callback(job)
            except Exception as e:
                logger.error(f"Error in status callback: {str(e)}")
    
    async def cleanup_old_jobs(self, max_age_hours: int = 24):
        """Clean up old completed/failed jobs"""
        cutoff_time = datetime.now().timestamp() - (max_age_hours * 3600)
        
        jobs_to_remove = []
        for job_id, job in self._jobs.items():
            if job.status in [ProcessingStatus.COMPLETED, ProcessingStatus.FAILED]:
                if job.created_at.timestamp() < cutoff_time:
                    jobs_to_remove.append(job_id)
        
        for job_id in jobs_to_remove:
            del self._jobs[job_id]
        
        if jobs_to_remove:
            logger.info(f"Cleaned up {len(jobs_to_remove)} old jobs")


# Global processing queue instance
_processing_queue: Optional[ProcessingQueue] = None


async def get_processing_queue() -> ProcessingQueue:
    """Get the global processing queue instance"""
    global _processing_queue
    
    if _processing_queue is None:
        _processing_queue = ProcessingQueue()
        
        # Add WebSocket status callback
        websocket_manager = await get_websocket_manager()
        _processing_queue.add_status_callback(
            lambda job: websocket_manager.broadcast_processing_status(job.to_dict())
        )
        
        # Start the queue
        await _processing_queue.start()
    
    return _processing_queue


async def cleanup_processing_queue():
    """Cleanup the processing queue on shutdown"""
    global _processing_queue
    if _processing_queue:
        await _processing_queue.stop()
        _processing_queue = None