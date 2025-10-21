"""
Task scheduler and rate limiting system
"""

import asyncio
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum
from worker_manager import WorkerManager
from database import Database
from logger import bot_logger
from config import Config


class TaskType(Enum):
    """Task types"""

    LIKE = "like"
    COMMENT = "comment"
    RETWEET = "retweet"
    QUOTE = "quote"
    FOLLOW = "follow"
    UNFOLLOW = "unfollow"
    SYNC_FOLLOWS = "sync_follows"


class TaskStatus(Enum):
    """Task status"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """Task data structure"""

    id: str
    task_type: TaskType
    payload: Dict[str, Any]
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = None
    scheduled_for: datetime = None
    completed_at: datetime = None
    retry_count: int = 0
    max_retries: int = 3
    priority: int = 1  # Higher number = higher priority

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.scheduled_for is None:
            self.scheduled_for = datetime.now()


class RateLimiter:
    """Global rate limiter for all bots"""

    def __init__(self):
        self.like_last_action = None
        self.comment_last_action = None
        self.retweet_last_action = None
        self.quote_last_action = None
        self.like_cycle_start = None
        self.retweet_cycle_start = None
        self.quote_cycle_start = None

        self.rate_limits = Config.get_rate_limits()

    def can_perform_like(self) -> bool:
        """Check if like action can be performed"""
        now = datetime.now()

        # Check if we're in a break period
        if self.like_cycle_start:
            time_since_cycle = (now - self.like_cycle_start).total_seconds() / 60

            # If we've been active for too long, start break
            if time_since_cycle > self.rate_limits["like_break"]:
                if self.like_last_action:
                    time_since_last = (now - self.like_last_action).total_seconds() / 60
                    if time_since_last < self.rate_limits["like_break"]:
                        return False
                    else:
                        # Reset cycle
                        self.like_cycle_start = None

        # Check minimum interval
        if self.like_last_action:
            time_since_last = (now - self.like_last_action).total_seconds() / 60
            if time_since_last < self.rate_limits["like_interval"]:
                return False

        return True

    def can_perform_comment(self) -> bool:
        """Check if comment action can be performed"""
        now = datetime.now()

        if self.comment_last_action:
            time_since_last = (now - self.comment_last_action).total_seconds() / 60
            min_interval = self.rate_limits["comment_min"]

            if time_since_last < min_interval:
                return False

        return True

    def can_perform_retweet(self) -> bool:
        """Check if retweet action can be performed (same as like)"""
        return self.can_perform_like()

    def can_perform_quote(self) -> bool:
        """Check if quote action can be performed"""
        now = datetime.now()

        # Check cycle timing
        if self.quote_cycle_start:
            time_since_cycle = (now - self.quote_cycle_start).total_seconds() / 60

            # If we've been in quote cycle too long, wait for break
            if time_since_cycle > self.rate_limits["quote_max"]:
                if self.quote_last_action:
                    time_since_last = (
                        now - self.quote_last_action
                    ).total_seconds() / 60
                    if time_since_last < self.rate_limits["quote_min"]:
                        return False
                    else:
                        # Reset cycle
                        self.quote_cycle_start = None

        # Check minimum interval
        if self.quote_last_action:
            time_since_last = (now - self.quote_last_action).total_seconds() / 60
            if time_since_last < self.rate_limits["quote_min"]:
                return False

        return True

    def record_like_action(self):
        """Record that a like action was performed"""
        now = datetime.now()
        self.like_last_action = now

        # Start cycle if not started
        if not self.like_cycle_start:
            self.like_cycle_start = now

    def record_comment_action(self):
        """Record that a comment action was performed"""
        self.comment_last_action = datetime.now()

    def record_retweet_action(self):
        """Record that a retweet action was performed"""
        now = datetime.now()
        self.retweet_last_action = now

        # Start cycle if not started
        if not self.retweet_cycle_start:
            self.retweet_cycle_start = now

    def record_quote_action(self):
        """Record that a quote action was performed"""
        now = datetime.now()
        self.quote_last_action = now

        # Start cycle if not started
        if not self.quote_cycle_start:
            self.quote_cycle_start = now


class TaskScheduler:
    """Main task scheduler"""

    def __init__(self, worker_manager: WorkerManager, db: Database):
        self.worker_manager = worker_manager
        self.db = db
        self.logger = bot_logger
        self.rate_limiter = RateLimiter()

        self.task_queue: asyncio.Queue = asyncio.Queue(maxsize=Config.TASK_QUEUE_SIZE)
        self.active_tasks: Dict[str, Task] = {}
        self.is_running = False

        # Task handlers
        self.task_handlers: Dict[TaskType, Callable] = {
            TaskType.LIKE: self._handle_like_task,
            TaskType.COMMENT: self._handle_comment_task,
            TaskType.RETWEET: self._handle_retweet_task,
            TaskType.QUOTE: self._handle_quote_task,
            TaskType.FOLLOW: self._handle_follow_task,
            TaskType.SYNC_FOLLOWS: self._handle_sync_follows_task,
        }

    async def start(self):
        """Start the scheduler"""
        self.is_running = True
        self.logger.info("Task scheduler started")

        # Start background tasks
        asyncio.create_task(self._process_tasks())
        asyncio.create_task(self._cleanup_completed_tasks())
        asyncio.create_task(self._resume_rate_limited_workers())

    async def stop(self):
        """Stop the scheduler"""
        self.is_running = False
        self.logger.info("Task scheduler stopped")

    async def add_task(
        self,
        task_type: TaskType,
        payload: Dict[str, Any],
        priority: int = 1,
        delay_minutes: int = 0,
    ) -> str:
        """Add a new task to the queue"""
        try:
            task_id = f"{task_type.value}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{random.randint(1000, 9999)}"

            scheduled_for = datetime.now() + timedelta(minutes=delay_minutes)

            task = Task(
                id=task_id,
                task_type=task_type,
                payload=payload,
                priority=priority,
                scheduled_for=scheduled_for,
            )

            await self.task_queue.put(task)
            self.active_tasks[task_id] = task

            # Add to database
            self.db.add_task(
                {
                    "id": task_id,
                    "task_type": task_type.value,
                    "payload": payload,
                    "status": TaskStatus.PENDING.value,
                    "priority": priority,
                    "created_at": task.created_at.isoformat(),
                    "scheduled_for": scheduled_for.isoformat(),
                }
            )

            self.logger.info(
                f"Task {task_id} added to queue (scheduled for {scheduled_for})"
            )
            return task_id

        except Exception as e:
            self.logger.error(f"Failed to add task: {e}")
            return None

    async def _process_tasks(self):
        """Process tasks from the queue"""
        while self.is_running:
            try:
                # Get task from queue with timeout
                task = await asyncio.wait_for(self.task_queue.get(), timeout=1.0)

                # Check if task is ready to be executed
                if datetime.now() < task.scheduled_for:
                    # Put task back and wait
                    await self.task_queue.put(task)
                    await asyncio.sleep(1)
                    continue

                # Check if we have active workers
                active_workers = self.worker_manager.get_active_workers()
                if not active_workers:
                    self.logger.warning("No active workers available, skipping task")
                    await asyncio.sleep(5)
                    continue

                # Execute task
                await self._execute_task(task)

            except asyncio.TimeoutError:
                # No tasks in queue, continue
                continue
            except Exception as e:
                self.logger.error(f"Error processing tasks: {e}")
                await asyncio.sleep(1)

    async def _execute_task(self, task: Task):
        """Execute a specific task"""
        try:
            task.status = TaskStatus.IN_PROGRESS
            self.db.update_task_status(
                int(task.id.split("_")[-1]), TaskStatus.IN_PROGRESS.value
            )

            self.logger.info(f"Executing task {task.id}: {task.task_type.value}")

            # Get appropriate handler
            handler = self.task_handlers.get(task.task_type)
            if handler:
                success = await handler(task)

                if success:
                    task.status = TaskStatus.COMPLETED
                    task.completed_at = datetime.now()
                    self.logger.info(f"Task {task.id} completed successfully")
                else:
                    task.status = TaskStatus.FAILED
                    task.retry_count += 1

                    # Retry if under max retries
                    if task.retry_count < task.max_retries:
                        task.status = TaskStatus.PENDING
                        task.scheduled_for = datetime.now() + timedelta(
                            minutes=5
                        )  # Retry in 5 minutes
                        await self.task_queue.put(task)
                        self.logger.info(
                            f"Task {task.id} failed, retrying ({task.retry_count}/{task.max_retries})"
                        )
                    else:
                        self.logger.error(
                            f"Task {task.id} failed after {task.max_retries} retries"
                        )

                self.db.update_task_status(
                    int(task.id.split("_")[-1]), task.status.value
                )

            else:
                self.logger.error(f"No handler for task type: {task.task_type}")
                task.status = TaskStatus.FAILED

        except Exception as e:
            self.logger.error(f"Error executing task {task.id}: {e}")
            task.status = TaskStatus.FAILED

    async def _handle_like_task(self, task: Task) -> bool:
        """Handle like task"""
        if not self.rate_limiter.can_perform_like():
            return False

        tweet_url = task.payload.get("tweet_url")
        if not tweet_url:
            return False

        results = await self.worker_manager.like_tweet_all(tweet_url)
        self.rate_limiter.record_like_action()

        success_count = sum(1 for success in results.values() if success)
        self.logger.info(
            f"Like task completed: {success_count}/{len(results)} bots successful"
        )

        return success_count > 0

    async def _handle_comment_task(self, task: Task) -> bool:
        """Handle comment task"""
        if not self.rate_limiter.can_perform_comment():
            return False

        tweet_url = task.payload.get("tweet_url")
        comments = task.payload.get("comments", ["Nice post! 👍"])

        if not tweet_url:
            return False

        results = await self.worker_manager.comment_all(tweet_url, comments)
        self.rate_limiter.record_comment_action()

        success_count = sum(1 for success in results.values() if success)
        self.logger.info(
            f"Comment task completed: {success_count}/{len(results)} bots successful"
        )

        return success_count > 0

    async def _handle_retweet_task(self, task: Task) -> bool:
        """Handle retweet task"""
        if not self.rate_limiter.can_perform_retweet():
            return False

        tweet_url = task.payload.get("tweet_url")
        if not tweet_url:
            return False

        results = await self.worker_manager.retweet_all(tweet_url)
        self.rate_limiter.record_retweet_action()

        success_count = sum(1 for success in results.values() if success)
        self.logger.info(
            f"Retweet task completed: {success_count}/{len(results)} bots successful"
        )

        return success_count > 0

    async def _handle_quote_task(self, task: Task) -> bool:
        """Handle quote task"""
        if not self.rate_limiter.can_perform_quote():
            return False

        tweet_url = task.payload.get("tweet_url")
        quote_text = task.payload.get("quote_text")
        keyword = task.payload.get("keyword")

        if not all([tweet_url, quote_text, keyword]):
            return False

        results = await self.worker_manager.quote_tweet_all(
            tweet_url, quote_text, keyword
        )
        self.rate_limiter.record_quote_action()

        success_count = sum(1 for success in results.values() if success)
        self.logger.info(
            f"Quote task completed: {success_count}/{len(results)} bots successful"
        )

        return success_count > 0

    async def _handle_follow_task(self, task: Task) -> bool:
        """Handle follow task"""
        username = task.payload.get("username")
        if not username:
            return False

        active_workers = self.worker_manager.get_active_workers()
        success_count = 0

        for worker in active_workers:
            if await worker.follow_user(username):
                success_count += 1

        self.logger.info(
            f"Follow task completed: {success_count}/{len(active_workers)} bots successful"
        )
        return success_count > 0

    async def _handle_sync_follows_task(self, task: Task) -> bool:
        """Handle mutual following sync task"""
        new_bot_id = task.payload.get("new_bot_id")
        await self.worker_manager._sync_mutual_following(new_bot_id)
        return True

    async def _cleanup_completed_tasks(self):
        """Clean up completed tasks"""
        while self.is_running:
            try:
                current_time = datetime.now()
                completed_tasks = []

                for task_id, task in self.active_tasks.items():
                    if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                        # Keep completed tasks for 1 hour
                        if current_time - task.completed_at > timedelta(hours=1):
                            completed_tasks.append(task_id)

                for task_id in completed_tasks:
                    del self.active_tasks[task_id]

                await asyncio.sleep(300)  # Cleanup every 5 minutes

            except Exception as e:
                self.logger.error(f"Error in cleanup task: {e}")
                await asyncio.sleep(60)

    async def _resume_rate_limited_workers(self):
        """Resume workers that are no longer rate limited - DISABLED"""
        while self.is_running:
            try:
                # Method disabled - worker_manager.resume_rate_limited_workers() not available
                # TODO: Re-enable when method is properly implemented
                await asyncio.sleep(60)  # Just sleep

            except Exception as e:
                self.logger.error(f"Error in resume task: {e}")
                await asyncio.sleep(60)

    async def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status"""
        return {
            "queue_size": self.task_queue.qsize(),
            "active_tasks": len(self.active_tasks),
            "pending_tasks": len(
                [
                    t
                    for t in self.active_tasks.values()
                    if t.status == TaskStatus.PENDING
                ]
            ),
            "in_progress_tasks": len(
                [
                    t
                    for t in self.active_tasks.values()
                    if t.status == TaskStatus.IN_PROGRESS
                ]
            ),
            "completed_tasks": len(
                [
                    t
                    for t in self.active_tasks.values()
                    if t.status == TaskStatus.COMPLETED
                ]
            ),
            "failed_tasks": len(
                [t for t in self.active_tasks.values() if t.status == TaskStatus.FAILED]
            ),
        }
