"""
Worker Manager - Enhanced with proper proxy support
"""

import asyncio
import inspect
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from twikit import Client
from config import Config
from database import Database
from logger import bot_logger


class TwitterWorker:
    """Individual Twitter bot worker with proxy support"""

    def __init__(self, bot_id: str, cookie_data: Dict[str, Any], db: Database):
        self.bot_id = bot_id
        self.cookie_data = cookie_data
        self.db = db
        self.logger = bot_logger
        
        # Initialize client with proxy support
        self.client = self._create_client_with_proxy()
        
        self.is_logged_in = False
        self.rate_limited_until = None
        self.captcha_required = False
        self.last_action_time = None

    def _create_client_with_proxy(self):
        """Create Twikit client with proper proxy configuration"""
        # Get proxy configuration
        proxy_url = Config.PROXY_URL
        
        # Get captcha solver if available
        captcha_solver_instance = None
        if Config.USE_CAPTCHA_SOLVER and Config.CAPSOLVER_API_KEY:
            try:
                from twikit._captcha.capsolver import Capsolver as TwikitCapsolver
                captcha_solver_instance = TwikitCapsolver(
                    api_key=Config.CAPSOLVER_API_KEY,
                    max_attempts=Config.CAPSOLVER_MAX_ATTEMPTS,
                    get_result_interval=Config.CAPSOLVER_RESULT_INTERVAL,
                )
                self.logger.info(f"{self.bot_id}: Captcha solver configured")
            except ImportError:
                self.logger.warning(f"{self.bot_id}: Twikit Capsolver not available")
        
        # Detect supported Client parameters
        client_sig = inspect.signature(Client.__init__)
        params = client_sig.parameters
        
        # Build client kwargs
        client_kwargs = {
            'language': 'en-US'
        }
        
        # Add proxy if supported and configured
        if 'proxy' in params and proxy_url:
            client_kwargs['proxy'] = proxy_url
            self.logger.info(f"{self.bot_id}: Using proxy: {proxy_url[:50]}...")
        
        # Add captcha solver if supported and configured
        if 'captcha_solver' in params and captcha_solver_instance:
            client_kwargs['captcha_solver'] = captcha_solver_instance
        
        # Create client
        try:
            client = Client(**client_kwargs)
            return client
        except Exception as e:
            self.logger.error(f"{self.bot_id}: Failed to create client with proxy: {e}")
            # Fallback to basic client
            return Client('en-US')

    async def initialize(self) -> bool:
        """Initialize worker with cookie-based authentication"""
        try:
            self.logger.info(f"{self.bot_id}: Initializing worker...")
            
            # Set cookies directly
            if isinstance(self.cookie_data, dict):
                self.client.set_cookies(self.cookie_data)
                self.logger.info(f"{self.bot_id}: Cookies set successfully")
            else:
                self.logger.error(f"{self.bot_id}: Invalid cookie data format")
                return False
            
            # Verify authentication by getting user info
            try:
                user = await self.client.user()
                if user:
                    username = getattr(user, 'screen_name', getattr(user, 'username', 'Unknown'))
                    self.logger.info(f"{self.bot_id}: Authenticated as @{username}")
                    self.is_logged_in = True
                    return True
                else:
                    self.logger.error(f"{self.bot_id}: Failed to verify authentication")
                    return False
            except Exception as e:
                self.logger.error(f"{self.bot_id}: Authentication verification failed: {e}")
                return False
            
        except Exception as e:
            self.logger.error(f"{self.bot_id}: Initialization failed: {e}")
            return False

    async def reinitialize(self) -> bool:
        """Reinitialize the worker (recreate client and re-authenticate)"""
        try:
            self.logger.info(f"{self.bot_id}: Reinitializing worker...")
            
            # Recreate client with proxy
            self.client = self._create_client_with_proxy()
            
            # Re-authenticate
            return await self.initialize()
            
        except Exception as e:
            self.logger.error(f"{self.bot_id}: Reinitialization failed: {e}")
            return False

    def _can_perform_action(self) -> bool:
        """Check if worker can perform an action"""
        # Check if rate limited
        if self.rate_limited_until:
            if datetime.now() < self.rate_limited_until:
                return False
            else:
                # Rate limit expired
                self.rate_limited_until = None
        
        # Check if captcha required
        if self.captcha_required:
            return False
        
        # Check if logged in
        if not self.is_logged_in:
            return False
        
        return True

    def mark_rate_limited(self, duration_minutes: int = None):
        """Mark worker as rate limited"""
        if duration_minutes is None:
            duration_minutes = Config.RATE_LIMIT_PAUSE_MINUTES
        
        self.rate_limited_until = datetime.now() + timedelta(minutes=duration_minutes)
        self.logger.warning(
            f"{self.bot_id}: Rate limited until {self.rate_limited_until.strftime('%H:%M:%S')}"
        )

    def mark_captcha_required(self):
        """Mark worker as requiring captcha"""
        self.captcha_required = True
        self.logger.warning(f"{self.bot_id}: Captcha required")

    def clear_captcha_required(self):
        """Clear captcha requirement"""
        self.captcha_required = False
        self.logger.info(f"{self.bot_id}: Captcha cleared")

    async def like_tweet(self, tweet_id: str) -> bool:
        """Like a tweet"""
        if not self._can_perform_action():
            self.logger.warning(f"{self.bot_id}: Cannot perform action")
            return False
        
        try:
            await self.client.favorite_tweet(tweet_id)
            self.last_action_time = datetime.now()
            self.logger.info(f"{self.bot_id}: Liked tweet {tweet_id}")
            return True
        except Exception as e:
            self.logger.error(f"{self.bot_id}: Failed to like tweet {tweet_id}: {e}")
            
            # Handle rate limiting
            if "rate limit" in str(e).lower():
                self.mark_rate_limited()
            
            return False

    async def retweet_tweet(self, tweet_id: str) -> bool:
        """Retweet a tweet"""
        if not self._can_perform_action():
            self.logger.warning(f"{self.bot_id}: Cannot perform action")
            return False
        
        try:
            await self.client.retweet(tweet_id)
            self.last_action_time = datetime.now()
            self.logger.info(f"{self.bot_id}: Retweeted tweet {tweet_id}")
            return True
        except Exception as e:
            self.logger.error(f"{self.bot_id}: Failed to retweet {tweet_id}: {e}")
            
            # Handle rate limiting
            if "rate limit" in str(e).lower():
                self.mark_rate_limited()
            
            return False

    async def comment_on_tweet(self, tweet_id: str, text: str) -> bool:
        """Comment on a tweet"""
        if not self._can_perform_action():
            self.logger.warning(f"{self.bot_id}: Cannot perform action")
            return False
        
        try:
            await self.client.create_tweet(text=text, reply_to=tweet_id)
            self.last_action_time = datetime.now()
            self.logger.info(f"{self.bot_id}: Commented on tweet {tweet_id}")
            return True
        except Exception as e:
            self.logger.error(f"{self.bot_id}: Failed to comment on {tweet_id}: {e}")
            
            # Handle rate limiting
            if "rate limit" in str(e).lower():
                self.mark_rate_limited()
            
            return False

    async def quote_tweet(self, tweet_id: str, text: str) -> bool:
        """Quote tweet"""
        if not self._can_perform_action():
            self.logger.warning(f"{self.bot_id}: Cannot perform action")
            return False
        
        try:
            await self.client.create_tweet(text=text, quote=tweet_id)
            self.last_action_time = datetime.now()
            self.logger.info(f"{self.bot_id}: Quoted tweet {tweet_id}")
            return True
        except Exception as e:
            self.logger.error(f"{self.bot_id}: Failed to quote tweet {tweet_id}: {e}")
            
            # Handle rate limiting
            if "rate limit" in str(e).lower():
                self.mark_rate_limited()
            
            return False

    async def follow_user(self, user_id: str) -> bool:
        """Follow a user"""
        if not self._can_perform_action():
            self.logger.warning(f"{self.bot_id}: Cannot perform action")
            return False
        
        try:
            await self.client.follow(user_id)
            self.last_action_time = datetime.now()
            self.logger.info(f"{self.bot_id}: Followed user {user_id}")
            return True
        except Exception as e:
            self.logger.error(f"{self.bot_id}: Failed to follow user {user_id}: {e}")
            
            # Handle rate limiting
            if "rate limit" in str(e).lower():
                self.mark_rate_limited()
            
            return False

    async def unfollow_user(self, user_id: str) -> bool:
        """Unfollow a user"""
        if not self._can_perform_action():
            self.logger.warning(f"{self.bot_id}: Cannot perform action")
            return False
        
        try:
            await self.client.unfollow(user_id)
            self.last_action_time = datetime.now()
            self.logger.info(f"{self.bot_id}: Unfollowed user {user_id}")
            return True
        except Exception as e:
            self.logger.error(f"{self.bot_id}: Failed to unfollow user {user_id}: {e}")
            
            # Handle rate limiting
            if "rate limit" in str(e).lower():
                self.mark_rate_limited()
            
            return False

    async def get_user_info(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user information"""
        try:
            user = await self.client.get_user_by_screen_name(username)
            if user:
                return {
                    'id': getattr(user, 'id', None),
                    'username': getattr(user, 'screen_name', None),
                    'name': getattr(user, 'name', None),
                    'followers_count': getattr(user, 'followers_count', 0),
                    'following_count': getattr(user, 'friends_count', 0),
                    'tweets_count': getattr(user, 'statuses_count', 0),
                    'verified': getattr(user, 'verified', False),
                    'description': getattr(user, 'description', ''),
                }
            return None
        except Exception as e:
            self.logger.error(f"{self.bot_id}: Failed to get user info for {username}: {e}")
            return None

    async def get_tweet_info(self, tweet_id: str) -> Optional[Dict[str, Any]]:
        """Get tweet information"""
        try:
            tweet = await self.client.get_tweet_by_id(tweet_id)
            if tweet:
                return {
                    'id': getattr(tweet, 'id', None),
                    'text': getattr(tweet, 'text', ''),
                    'author_id': getattr(tweet, 'user_id', None),
                    'author_username': getattr(tweet, 'user', {}).get('screen_name', '') if hasattr(tweet, 'user') else '',
                    'created_at': getattr(tweet, 'created_at', None),
                    'retweet_count': getattr(tweet, 'retweet_count', 0),
                    'favorite_count': getattr(tweet, 'favorite_count', 0),
                    'reply_count': getattr(tweet, 'reply_count', 0),
                }
            return None
        except Exception as e:
            self.logger.error(f"{self.bot_id}: Failed to get tweet info for {tweet_id}: {e}")
            return None

    def get_status(self) -> Dict[str, Any]:
        """Get worker status"""
        return {
            'bot_id': self.bot_id,
            'is_logged_in': self.is_logged_in,
            'rate_limited_until': self.rate_limited_until.isoformat() if self.rate_limited_until else None,
            'captcha_required': self.captcha_required,
            'last_action_time': self.last_action_time.isoformat() if self.last_action_time else None,
            'proxy_configured': bool(Config.PROXY_URL),
        }

    async def cleanup(self):
        """Cleanup worker resources"""
        try:
            # Close any open connections
            if hasattr(self.client, 'close'):
                await self.client.close()
            self.logger.info(f"{self.bot_id}: Worker cleaned up")
        except Exception as e:
            self.logger.error(f"{self.bot_id}: Error during cleanup: {e}")


class WorkerManager:
    """Manager for all Twitter workers with proxy support"""

    def __init__(self, db: Database):
        self.db = db
        self.logger = bot_logger
        self.workers: Dict[str, TwitterWorker] = {}
        self.is_running = False
        self.worker_tasks: Dict[str, asyncio.Task] = {}

    async def start(self):
        """Start the worker manager"""
        try:
            self.logger.info("Starting Worker Manager...")
            self.is_running = True
            
            # Load existing workers from database
            await self._load_workers_from_db()
            
            self.logger.info(f"Worker Manager started with {len(self.workers)} workers")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start Worker Manager: {e}")
            return False

    async def stop(self):
        """Stop the worker manager"""
        try:
            self.logger.info("Stopping Worker Manager...")
            self.is_running = False
            
            # Stop all worker tasks
            for task in self.worker_tasks.values():
                if not task.done():
                    task.cancel()
            
            # Wait for tasks to complete
            if self.worker_tasks:
                await asyncio.gather(*self.worker_tasks.values(), return_exceptions=True)
            
            # Cleanup all workers
            for worker in self.workers.values():
                await worker.cleanup()
            
            self.workers.clear()
            self.worker_tasks.clear()
            
            self.logger.info("Worker Manager stopped")
            
        except Exception as e:
            self.logger.error(f"Error stopping Worker Manager: {e}")

    async def _load_workers_from_db(self):
        """Load workers from database"""
        try:
            bots = self.db.get_all_bots()
            for bot_id, bot_data in bots.items():
                if bot_data.get('cookie_data'):
                    await self.add_worker(
                        bot_id=bot_id,
                        cookie_data=bot_data['cookie_data'],
                        auto_start=True
                    )
        except Exception as e:
            self.logger.error(f"Failed to load workers from database: {e}")

    async def add_worker(self, bot_id: str, cookie_data: Dict[str, Any], auto_start: bool = True) -> bool:
        """Add a new worker"""
        try:
            if bot_id in self.workers:
                self.logger.warning(f"Worker {bot_id} already exists")
                return False
            
            # Create worker
            worker = TwitterWorker(bot_id, cookie_data, self.db)
            
            # Initialize worker
            if auto_start:
                success = await worker.initialize()
                if not success:
                    self.logger.error(f"Failed to initialize worker {bot_id}")
                    return False
            
            # Add to workers dict
            self.workers[bot_id] = worker
            
            # Save to database
            await self.db.save_bot(bot_id, cookie_data)
            
            self.logger.info(f"Worker {bot_id} added successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to add worker {bot_id}: {e}")
            return False

    async def remove_worker(self, bot_id: str) -> bool:
        """Remove a worker"""
        try:
            if bot_id not in self.workers:
                self.logger.warning(f"Worker {bot_id} not found")
                return False
            
            # Stop worker task if running
            if bot_id in self.worker_tasks:
                task = self.worker_tasks[bot_id]
                if not task.done():
                    task.cancel()
                del self.worker_tasks[bot_id]
            
            # Cleanup worker
            worker = self.workers[bot_id]
            await worker.cleanup()
            
            # Remove from workers dict
            del self.workers[bot_id]
            
            # Remove from database
            await self.db.delete_bot(bot_id)
            
            self.logger.info(f"Worker {bot_id} removed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to remove worker {bot_id}: {e}")
            return False

    async def restart_worker(self, bot_id: str) -> bool:
        """Restart a worker"""
        try:
            if bot_id not in self.workers:
                self.logger.warning(f"Worker {bot_id} not found")
                return False
            
            worker = self.workers[bot_id]
            
            # Reinitialize worker
            success = await worker.reinitialize()
            if not success:
                self.logger.error(f"Failed to restart worker {bot_id}")
                return False
            
            self.logger.info(f"Worker {bot_id} restarted successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to restart worker {bot_id}: {e}")
            return False

    def get_worker(self, bot_id: str) -> Optional[TwitterWorker]:
        """Get a worker by ID"""
        return self.workers.get(bot_id)

    def get_all_workers(self) -> List[TwitterWorker]:
        """Get all workers"""
        return list(self.workers.values())

    def get_available_worker(self) -> Optional[TwitterWorker]:
        """Get an available worker (not rate limited, no captcha required)"""
        for worker in self.workers.values():
            if worker._can_perform_action():
                return worker
        return None

    def get_worker_status(self, bot_id: str) -> Optional[Dict[str, Any]]:
        """Get worker status"""
        worker = self.workers.get(bot_id)
        if worker:
            return worker.get_status()
        return None

    def get_all_worker_statuses(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all workers"""
        return {bot_id: worker.get_status() for bot_id, worker in self.workers.items()}

    async def execute_task(self, task_type: str, task_data: Dict[str, Any]) -> bool:
        """Execute a task using an available worker"""
        try:
            # Get available worker
            worker = self.get_available_worker()
            if not worker:
                self.logger.warning("No available workers for task execution")
                return False
            
            # Execute task based on type
            if task_type == "like":
                return await worker.like_tweet(task_data.get('tweet_id'))
            elif task_type == "retweet":
                return await worker.retweet_tweet(task_data.get('tweet_id'))
            elif task_type == "comment":
                return await worker.comment_on_tweet(
                    task_data.get('tweet_id'), 
                    task_data.get('text', '')
                )
            elif task_type == "quote":
                return await worker.quote_tweet(
                    task_data.get('tweet_id'), 
                    task_data.get('text', '')
                )
            elif task_type == "follow":
                return await worker.follow_user(task_data.get('user_id'))
            elif task_type == "unfollow":
                return await worker.unfollow_user(task_data.get('user_id'))
            else:
                self.logger.error(f"Unknown task type: {task_type}")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to execute task {task_type}: {e}")
            return False

    def get_statistics(self) -> Dict[str, Any]:
        """Get worker manager statistics"""
        total_workers = len(self.workers)
        active_workers = sum(1 for w in self.workers.values() if w.is_logged_in)
        rate_limited_workers = sum(1 for w in self.workers.values() if w.rate_limited_until)
        captcha_required_workers = sum(1 for w in self.workers.values() if w.captcha_required)
        
        return {
            'total_workers': total_workers,
            'active_workers': active_workers,
            'rate_limited_workers': rate_limited_workers,
            'captcha_required_workers': captcha_required_workers,
            'proxy_configured': bool(Config.PROXY_URL),
            'is_running': self.is_running,
        }

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on all workers"""
        health_status = {
            'healthy_workers': 0,
            'unhealthy_workers': 0,
            'worker_details': {}
        }
        
        for bot_id, worker in self.workers.items():
            try:
                # Check if worker can perform actions
                can_act = worker._can_perform_action()
                
                # Try to get user info to verify connection
                user_info = await worker.get_user_info('twitter')  # Simple test
                
                worker_healthy = can_act and worker.is_logged_in
                
                if worker_healthy:
                    health_status['healthy_workers'] += 1
                else:
                    health_status['unhealthy_workers'] += 1
                
                health_status['worker_details'][bot_id] = {
                    'healthy': worker_healthy,
                    'can_perform_action': can_act,
                    'is_logged_in': worker.is_logged_in,
                    'rate_limited': bool(worker.rate_limited_until),
                    'captcha_required': worker.captcha_required,
                }
                
            except Exception as e:
                health_status['unhealthy_workers'] += 1
                health_status['worker_details'][bot_id] = {
                    'healthy': False,
                    'error': str(e)
                }
        
        return health_status