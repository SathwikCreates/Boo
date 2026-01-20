"""
Background task services for memory processing and cleanup
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict
from contextlib import asynccontextmanager

from app.services.memory_service import MemoryService
from app.db.database import get_db

logger = logging.getLogger(__name__)


class BackgroundTaskManager:
    """Manages background tasks for memory processing"""
    
    def __init__(self):
        self.memory_service = MemoryService()
        self.is_running = False
        self.tasks = {}
        
    async def start(self):
        """Start all background tasks"""
        if self.is_running:
            return
            
        self.is_running = True
        logger.info("Starting background task manager")
        
        # Connect to database
        db = get_db()
        await db.connect()
        
        # Start periodic tasks
        self.tasks['llm_processing'] = asyncio.create_task(self._llm_processing_loop())
        self.tasks['cleanup_scheduler'] = asyncio.create_task(self._cleanup_scheduler_loop())
        
        logger.info("Background tasks started successfully")
    
    async def stop(self):
        """Stop all background tasks"""
        if not self.is_running:
            return
            
        self.is_running = False
        logger.info("Stopping background task manager")
        
        # Cancel all tasks
        for task_name, task in self.tasks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                logger.info(f"Cancelled task: {task_name}")
        
        self.tasks.clear()
        logger.info("Background tasks stopped")
    
    async def _llm_processing_loop(self):
        """Background loop for LLM processing cleanup (fallback only)"""
        logger.info("Started LLM processing cleanup loop")
        
        while self.is_running:
            try:
                # Fallback processing for any missed memories (run much less frequently)
                # Main scoring now happens in real-time via store_memory()
                processed_count = await self.memory_service.process_memories_with_llm_batch(batch_size=10)
                
                if processed_count > 0:
                    logger.info(f"Fallback processed {processed_count} missed memories with LLM")
                
                # Wait 1 hour (much less frequent than before)
                await asyncio.sleep(3600)  # 1 hour
                
            except asyncio.CancelledError:
                logger.info("LLM processing cleanup loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in LLM processing cleanup loop: {e}")
                # Wait 10 minutes before retrying on error
                await asyncio.sleep(600)
    
    async def _cleanup_scheduler_loop(self):
        """Background loop for scheduling memory cleanup tasks"""
        logger.info("Started cleanup scheduler loop")
        last_cleanup_check = datetime.now()
        
        while self.is_running:
            try:
                now = datetime.now()
                
                # Check if it's time for monthly cleanup (1st of the month)
                if (now.day == 1 and 
                    now.hour >= 2 and  # Run at 2 AM to avoid peak usage
                    (now - last_cleanup_check).days >= 28):  # Don't run more than once per month
                    
                    await self._run_monthly_cleanup()
                    last_cleanup_check = now
                
                # Check every hour
                await asyncio.sleep(3600)  # 1 hour
                
            except asyncio.CancelledError:
                logger.info("Cleanup scheduler loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in cleanup scheduler loop: {e}")
                # Wait 10 minutes before retrying on error
                await asyncio.sleep(600)
    
    async def _run_monthly_cleanup(self):
        """Run the monthly cleanup process"""
        logger.info("Starting monthly memory cleanup")
        
        try:
            # Phase 1: Mark memories for deletion
            marked_ids = await self.memory_service.mark_memories_for_deletion()
            logger.info(f"Phase 1: Marked {len(marked_ids)} memories for deletion")
            
            # Phase 2: Archive memories marked 2+ weeks ago
            archived_count = await self.memory_service.archive_marked_memories()
            logger.info(f"Phase 2: Archived {archived_count} memories")
            
            # Phase 3: Permanently delete memories archived 30+ days ago
            deleted_count = await self.memory_service.permanently_delete_archived()
            logger.info(f"Phase 3: Permanently deleted {deleted_count} memories")
            
            logger.info(f"Monthly cleanup completed: {len(marked_ids)} marked, {archived_count} archived, {deleted_count} deleted")
            
        except Exception as e:
            logger.error(f"Failed to run monthly cleanup: {e}")
    
    async def trigger_llm_processing(self, batch_size: int = 10) -> int:
        """Manually trigger LLM processing"""
        try:
            processed_count = await self.memory_service.process_memories_with_llm_batch(batch_size)
            logger.info(f"Manual LLM processing: processed {processed_count} memories")
            return processed_count
        except Exception as e:
            logger.error(f"Failed to trigger LLM processing: {e}")
            return 0
    
    async def get_task_status(self) -> Dict[str, Any]:
        """Get status of background tasks"""
        status = {
            'is_running': self.is_running,
            'tasks': {}
        }
        
        for task_name, task in self.tasks.items():
            status['tasks'][task_name] = {
                'running': not task.done(),
                'cancelled': task.cancelled(),
                'done': task.done()
            }
            
            if task.done() and not task.cancelled():
                try:
                    task.result()
                    status['tasks'][task_name]['status'] = 'completed'
                except Exception as e:
                    status['tasks'][task_name]['status'] = f'error: {str(e)}'
        
        return status


# Global instance
background_manager = BackgroundTaskManager()


@asynccontextmanager
async def lifespan_manager():
    """Context manager for background task lifecycle"""
    try:
        await background_manager.start()
        yield background_manager
    finally:
        await background_manager.stop()


# Convenience functions for manual triggering
async def trigger_llm_processing(batch_size: int = 10) -> int:
    """Manually trigger LLM processing"""
    return await background_manager.trigger_llm_processing(batch_size)


async def get_background_task_status() -> Dict[str, Any]:
    """Get status of background tasks"""
    return await background_manager.get_task_status()