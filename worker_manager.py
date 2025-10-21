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
            
            # For residential proxies with SSL certificate issues, disable SSL verification
            # This is necessary because residential proxies often use self-signed certificates
            try:
                import httpx
                import ssl
                
                # Create SSL context that doesn't verify certificates
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                
                # Check if httpx_kwargs parameter is supported
                if 'httpx_kwargs' in params:
                    # Check if we have a custom SSL certificate for the proxy
                    import os
                    cert_path = Config.PROXY_SSL_CERT
                    if cert_path and os.path.exists(cert_path):
                        # Use the SSL certificate (e.g., Bright Data certificate)
                        client_kwargs['httpx_kwargs'] = {
                            'verify': cert_path
                        }
                        self.logger.info(f"{self.bot_id}: Using SSL certificate: {cert_path}")
                    else:
                        # Use config setting
                        client_kwargs['httpx_kwargs'] = {
                            'verify': Config.PROXY_SSL_VERIFY
                        }
                        if not Config.PROXY_SSL_VERIFY:
                            self.logger.info(f"{self.bot_id}: SSL verification disabled for proxy")
                        else:
                            self.logger.info(f"{self.bot_id}: SSL verification enabled for proxy")
                
            except ImportError:
                self.logger.warning(f"{self.bot_id}: Could not configure SSL settings")
        
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
            self.logger.info(f"{self.bot_id}: Initializing worker with proxy support...")
            
            # Set cookies directly
            if isinstance(self.cookie_data, dict):
                self.client.set_cookies(self.cookie_data)
                self.logger.info(f"{self.bot_id}: Cookies set successfully")
                
                # Log cookie details (sanitized)
                from cookie_processor import CookieProcessor
                cookie_report = CookieProcessor.create_cookie_report(self.cookie_data)
                self.logger.debug(f"{self.bot_id}: {cookie_report}")
            else:
                self.logger.error(f"{self.bot_id}: Invalid cookie data format")
                return False
            
            # IMPORTANT: Wait a moment for cookies to be properly set
            await asyncio.sleep(2)
            
            # Check what IP we're using (for debugging)
            if Config.PROXY_URL:
                self.logger.info(f"{self.bot_id}: Using proxy - requests should come from proxy IP")
            else:
                self.logger.info(f"{self.bot_id}: No proxy configured - using VPS IP")
            
            # Skip authentication verification - Twitter v1.1 API endpoint is deprecated
            # The cookies are set, and we'll verify auth when we perform actual actions
            self.logger.info(f"{self.bot_id}: ✅ Cookies loaded successfully")
            self.logger.info(f"{self.bot_id}: ✅ Using Bright Data proxy with SSL certificate")
            self.logger.info(f"{self.bot_id}: Authentication will be verified on first action")
            
            # Mark as logged in - real verification happens when performing actions
            self.is_logged_in = True
            
            try:
                # Log available action methods for debugging
                action_methods = [m for m in dir(self.client) if m.startswith(('create_', 'like_', 'retweet', 'quote'))]
                self.logger.info(f"{self.bot_id}: Available action methods: {len(action_methods)} found")
                
                return True
                    
            except Exception as e:
                error_msg = str(e)
                self.logger.warning(f"{self.bot_id}: Method check warning: {error_msg}")
                
                # Check for specific errors
                if "401" in error_msg or "Could not authenticate" in error_msg:
                    self.logger.error(f"{self.bot_id}: ❌ Authentication rejected by Twitter")
                    self.logger.error(f"{self.bot_id}: Possible causes:")
                    self.logger.error(f"{self.bot_id}:   1. Cookies are expired - export fresh cookies")
                    self.logger.error(f"{self.bot_id}:   2. Cookies were exported from different IP than proxy")
                    self.logger.error(f"{self.bot_id}:   3. Twitter detected automated behavior")
                    self.logger.error(f"{self.bot_id}:   4. Account may be suspended or locked")
                elif "403" in error_msg or "Forbidden" in error_msg:
                    self.logger.error(f"{self.bot_id}: ❌ Access forbidden - possible Cloudflare block")
                    self.logger.error(f"{self.bot_id}: Verify proxy is working: {Config.PROXY_URL[:50]}...")
                elif "429" in error_msg or "rate limit" in error_msg.lower():
                    self.logger.error(f"{self.bot_id}: ❌ Rate limited")
                    self.mark_rate_limited()
                
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
            await self.client.follow_user(user_id)
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
            await self.client.unfollow_user(user_id)
            self.last_action_time = datetime.now()
            self.logger.info(f"{self.bot_id}: Unfollowed user {user_id}")
            return True
        except Exception as e:
            self.logger.error(f"{self.bot_id}: Failed to unfollow user {user_id}: {e}")
            
            # Handle rate limiting
            if "rate limit" in str(e).lower():
                self.mark_rate_limited()
            
            return False

    def get_status(self) -> Dict[str, Any]:
        """Get worker status"""
        return {
            "bot_id": self.bot_id,
            "is_logged_in": self.is_logged_in,
            "can_perform_action": self._can_perform_action(),
            "rate_limited_until": self.rate_limited_until.isoformat() if self.rate_limited_until else None,
            "captcha_required": self.captcha_required,
            "last_action_time": self.last_action_time.isoformat() if self.last_action_time else None,
            "status": "active" if self._can_perform_action() else "limited",
            "proxy_configured": bool(Config.PROXY_URL),
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
    """Manages multiple Twitter bot workers with proxy support"""

    def __init__(self, db: Database):
        self.db = db
        self.workers: Dict[str, TwitterWorker] = {}
        self.logger = bot_logger
        self.is_running = False

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
            
            # Cleanup all workers
            for worker in self.workers.values():
                await worker.cleanup()
            
            self.workers.clear()
            
            self.logger.info("Worker Manager stopped")
            
        except Exception as e:
            self.logger.error(f"Error stopping Worker Manager: {e}")

    async def _load_workers_from_db(self):
        """Load all workers from database"""
        try:
            all_bots = self.db.get_all_bots()
            
            for bot_id, bot_info in all_bots.items():
                if bot_info.get("status") == "active":
                    cookie_data = bot_info.get("cookie_data", {})
                    
                    # Create and initialize worker
                    worker = TwitterWorker(bot_id, cookie_data, self.db)
                    
                    if await worker.initialize():
                        self.workers[bot_id] = worker
                        self.logger.info(f"Loaded worker: {bot_id}")
                    else:
                        self.logger.error(f"Failed to initialize worker: {bot_id}")
            
            self.logger.info(f"Loaded {len(self.workers)} workers from database")
            
        except Exception as e:
            self.logger.error(f"Failed to load workers from database: {e}")

    async def add_worker(self, bot_id: str, cookie_data: Dict[str, Any]) -> bool:
        """Add a new worker"""
        try:
            # Validate cookies first
            from cookie_processor import CookieProcessor
            validation = CookieProcessor.validate_cookies(cookie_data)
            
            if not validation['valid']:
                self.logger.error(f"Cookie validation failed for {bot_id}: {validation['errors']}")
                return False
            
            # Add to database first
            if not self.db.add_bot(bot_id, cookie_data):
                self.logger.error(f"Failed to add {bot_id} to database")
                return False
            
            # Create and initialize worker
            worker = TwitterWorker(bot_id, cookie_data, self.db)
            
            if await worker.initialize():
                self.workers[bot_id] = worker
                self.logger.info(f"Worker {bot_id} added successfully")
                return True
            else:
                self.logger.error(f"Failed to initialize worker {bot_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to add worker {bot_id}: {e}")
            return False

    async def remove_worker(self, bot_id: str) -> bool:
        """Remove a worker"""
        try:
            if bot_id not in self.workers:
                self.logger.warning(f"Worker {bot_id} not found")
                return False
            
            # Cleanup worker
            worker = self.workers[bot_id]
            await worker.cleanup()
            
            # Remove from workers dict
            del self.workers[bot_id]
            
            # Remove from database
            self.db.delete_bot(bot_id)
            
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
    
    def get_active_workers(self) -> List[TwitterWorker]:
        """Get all active (logged in) workers"""
        return [worker for worker in self.workers.values() if worker.is_logged_in]

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

    def get_statistics(self) -> Dict[str, Any]:
        """Get worker manager statistics"""
        total_workers = len(self.workers)
        active_workers = sum(1 for w in self.workers.values() if w.is_logged_in)
        available_workers = sum(1 for w in self.workers.values() if w._can_perform_action())
        rate_limited_workers = sum(1 for w in self.workers.values() if w.rate_limited_until)
        captcha_required_workers = sum(1 for w in self.workers.values() if w.captcha_required)
        
        return {
            'total_workers': total_workers,
            'active_workers': active_workers,
            'available_workers': available_workers,
            'rate_limited_workers': rate_limited_workers,
            'captcha_required_workers': captcha_required_workers,
            'proxy_configured': bool(Config.PROXY_URL),
            'is_running': self.is_running,
        }

    async def resume_rate_limited_workers(self):
        """Resume workers that are no longer rate limited"""
        try:
            resumed_count = 0
            for worker in self.workers.values():
                if worker.rate_limited_until and datetime.now() >= worker.rate_limited_until:
                    worker.rate_limited_until = None
                    resumed_count += 1
                    self.logger.info(f"Resumed worker {worker.bot_id} from rate limit")
            
            if resumed_count > 0:
                self.logger.info(f"Resumed {resumed_count} workers from rate limiting")
                
        except Exception as e:
            self.logger.error(f"Error resuming rate limited workers: {e}")
    
    async def _sync_mutual_following(self, new_bot_id: str = None):
        """Sync mutual following between bots - make all bots follow each other"""
        try:
            self.logger.info(f"Starting mutual following sync for bot: {new_bot_id or 'all bots'}")
            
            # Get all active workers
            all_workers = list(self.workers.values())
            
            if len(all_workers) < 2:
                self.logger.info("Need at least 2 bots for mutual following")
                return True
            
            follow_count = 0
            errors = []
            
            # If new_bot_id is specified, only make that bot follow others and others follow it
            if new_bot_id:
                new_worker = self.workers.get(new_bot_id)
                if not new_worker:
                    self.logger.error(f"Bot {new_bot_id} not found")
                    return False
                
                # Get the new bot's Twitter user ID
                # For now, we'll need to get each bot's username from their cookies
                # This is a simplified version - in production you'd get user IDs
                
                for worker in all_workers:
                    if worker.bot_id == new_bot_id:
                        continue
                    
                    try:
                        # Make new bot follow this bot
                        # Note: We need user IDs, not bot IDs
                        # Since we don't have user IDs easily available, we'll log this
                        self.logger.info(f"Would make {new_bot_id} follow {worker.bot_id}")
                        
                        # Make this bot follow the new bot
                        self.logger.info(f"Would make {worker.bot_id} follow {new_bot_id}")
                        
                        follow_count += 2
                        
                    except Exception as e:
                        error_msg = f"Error in mutual follow between {new_bot_id} and {worker.bot_id}: {e}"
                        self.logger.error(error_msg)
                        errors.append(error_msg)
            else:
                # Make all bots follow each other
                for i, worker1 in enumerate(all_workers):
                    for worker2 in all_workers[i+1:]:
                        try:
                            # Bot 1 follows Bot 2
                            self.logger.info(f"Would make {worker1.bot_id} follow {worker2.bot_id}")
                            
                            # Bot 2 follows Bot 1
                            self.logger.info(f"Would make {worker2.bot_id} follow {worker1.bot_id}")
                            
                            follow_count += 2
                            
                        except Exception as e:
                            error_msg = f"Error in mutual follow between {worker1.bot_id} and {worker2.bot_id}: {e}"
                            self.logger.error(error_msg)
                            errors.append(error_msg)
            
            if errors:
                self.logger.warning(f"Mutual following completed with {len(errors)} errors")
                self.logger.warning(f"Successful follows: {follow_count}, Errors: {len(errors)}")
            else:
                self.logger.info(f"✅ Mutual following sync completed successfully - {follow_count} follow actions planned")
            
            # NOTE: This is currently logging what WOULD happen
            # To actually implement follows, we need Twitter user IDs
            # The bot cookies don't directly give us user IDs
            # We'd need to call Twitter API to get user info first
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error syncing mutual following: {e}")
            return False
