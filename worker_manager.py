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

        # Twitter account info (will be populated during initialization)
        self.twitter_user_id = None
        self.twitter_username = None

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
        client_kwargs = {"language": "en-US"}

        # Add proxy if supported and configured
        if "proxy" in params and proxy_url:
            client_kwargs["proxy"] = proxy_url
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
                if "httpx_kwargs" in params:
                    # Check if we have a custom SSL certificate for the proxy
                    import os

                    cert_path = Config.PROXY_SSL_CERT
                    if cert_path and os.path.exists(cert_path):
                        # Use the SSL certificate (e.g., Bright Data certificate)
                        client_kwargs["httpx_kwargs"] = {"verify": cert_path}
                        self.logger.info(
                            f"{self.bot_id}: Using SSL certificate: {cert_path}"
                        )
                    else:
                        # Use config setting
                        client_kwargs["httpx_kwargs"] = {
                            "verify": Config.PROXY_SSL_VERIFY
                        }
                        if not Config.PROXY_SSL_VERIFY:
                            self.logger.info(
                                f"{self.bot_id}: SSL verification disabled for proxy"
                            )
                        else:
                            self.logger.info(
                                f"{self.bot_id}: SSL verification enabled for proxy"
                            )

            except ImportError:
                self.logger.warning(f"{self.bot_id}: Could not configure SSL settings")

        # Add captcha solver if supported and configured
        if "captcha_solver" in params and captcha_solver_instance:
            client_kwargs["captcha_solver"] = captcha_solver_instance

        # Create client
        try:
            client = Client(**client_kwargs)
            return client
        except Exception as e:
            self.logger.error(f"{self.bot_id}: Failed to create client with proxy: {e}")
            # Fallback to basic client
            return Client("en-US")

    async def initialize(self) -> bool:
        """Initialize worker with cookie-based authentication"""
        try:
            self.logger.info(
                f"{self.bot_id}: Initializing worker with proxy support..."
            )

            # Use set_cookies() which accepts dict format directly
            if isinstance(self.cookie_data, dict):
                # Set cookies
                self.client.set_cookies(self.cookie_data)
                self.logger.info(f"{self.bot_id}: Cookies set via set_cookies() method")

                # CRITICAL: Manually set X-CSRF-Token header from ct0 cookie
                # Twitter API requires this header for all write operations (follow, like, tweet, etc)
                if "ct0" in self.cookie_data:
                    csrf_token = self.cookie_data["ct0"]
                    header_set = False

                    # Try multiple approaches to set the header (Twikit version compatibility)
                    # Approach 1: Try _base_headers (older Twikit versions)
                    if hasattr(self.client, "_base_headers"):
                        self.client._base_headers["X-Csrf-Token"] = csrf_token
                        self.client._base_headers["x-csrf-token"] = (
                            csrf_token  # lowercase variant
                        )
                        self.logger.info(f"{self.bot_id}: Set header via _base_headers")
                        header_set = True

                    # Approach 2: Try http.headers (some Twikit versions)
                    if hasattr(self.client, "http") and hasattr(
                        self.client.http, "headers"
                    ):
                        self.client.http.headers["X-Csrf-Token"] = csrf_token
                        self.client.http.headers["x-csrf-token"] = csrf_token
                        self.logger.info(f"{self.bot_id}: Set header via http.headers")
                        header_set = True

                    # Approach 3: Try _client (httpx AsyncClient - Twikit 1.3.x)
                    if hasattr(self.client, "_client"):
                        if hasattr(self.client._client, "headers"):
                            self.client._client.headers["X-Csrf-Token"] = csrf_token
                            self.client._client.headers["x-csrf-token"] = csrf_token
                            self.logger.info(
                                f"{self.bot_id}: Set header via _client.headers"
                            )
                            header_set = True

                    # Approach 4: Try request_client (alternative internal client name)
                    if hasattr(self.client, "request_client"):
                        if hasattr(self.client.request_client, "headers"):
                            self.client.request_client.headers["X-Csrf-Token"] = (
                                csrf_token
                            )
                            self.client.request_client.headers["x-csrf-token"] = (
                                csrf_token
                            )
                            self.logger.info(
                                f"{self.bot_id}: Set header via request_client.headers"
                            )
                            header_set = True

                    # Debug: Log all client attributes to help identify correct approach
                    client_attrs = [
                        attr for attr in dir(self.client) if not attr.startswith("__")
                    ]
                    self.logger.info(
                        f"{self.bot_id}: Available client attributes: {', '.join(client_attrs[:30])}"
                    )

                    # Additional debug: Check internal client structure
                    if hasattr(self.client, "_client"):
                        internal_client_type = type(self.client._client).__name__
                        self.logger.info(
                            f"{self.bot_id}: Internal client type: {internal_client_type}"
                        )
                        if hasattr(self.client._client, "headers"):
                            headers = dict(self.client._client.headers)
                            header_keys = list(headers.keys())
                            self.logger.info(
                                f"{self.bot_id}: Current headers: {header_keys}"
                            )

                    if header_set:
                        self.logger.info(
                            f"{self.bot_id}: ✅ X-CSRF-Token header configured (value: {csrf_token[:20]}...)"
                        )
                    else:
                        self.logger.warning(
                            f"{self.bot_id}: ⚠️ Could not set X-CSRF-Token header - "
                            f"tried all known methods. Write operations may fail."
                        )
                else:
                    self.logger.error(
                        f"{self.bot_id}: ❌ ct0 cookie missing - write operations will fail!"
                    )

                # Log cookie details (sanitized)
                from cookie_processor import CookieProcessor

                cookie_report = CookieProcessor.create_cookie_report(self.cookie_data)
                self.logger.debug(f"{self.bot_id}: {cookie_report}")
            else:
                self.logger.error(f"{self.bot_id}: Invalid cookie data format")
                return False

            # IMPORTANT: Wait a moment for cookies to be properly set
            await asyncio.sleep(1)

            # Check what IP we're using (for debugging)
            if Config.PROXY_URL:
                self.logger.info(
                    f"{self.bot_id}: Using proxy - requests should come from proxy IP"
                )
            else:
                self.logger.info(f"{self.bot_id}: No proxy configured - using VPS IP")

            # Skip authentication verification - Twitter v1.1 API endpoint is deprecated
            # The cookies are set, and we'll verify auth when we perform actual actions
            self.logger.info(f"{self.bot_id}: ✅ Cookies loaded successfully")
            self.logger.info(
                f"{self.bot_id}: ✅ Using Bright Data proxy with SSL certificate"
            )

            # Try to get the user's Twitter ID from cookies
            try:
                self.twitter_user_id = None
                self.twitter_username = None

                # Try to extract from twid cookie (format: u=1234567890 or u%3D1234567890)
                if "twid" in self.cookie_data:
                    import urllib.parse

                    twid = self.cookie_data["twid"]
                    # URL decode the twid value (u%3D becomes u=)
                    twid_decoded = urllib.parse.unquote(twid)
                    if "u=" in twid_decoded:
                        # Extract user ID from twid cookie
                        self.twitter_user_id = (
                            twid_decoded.split("u=")[1].split(";")[0].split("|")[0]
                        )
                        self.logger.info(
                            f"{self.bot_id}: Extracted Twitter user ID from cookies: {self.twitter_user_id}"
                        )

                # If we couldn't get it from cookies, we'll fetch it on first action
                if not self.twitter_user_id:
                    self.logger.info(
                        f"{self.bot_id}: User ID not in cookies - will fetch on first action"
                    )

            except Exception as e:
                self.logger.warning(
                    f"{self.bot_id}: Error extracting user info from cookies: {e}"
                )

            # Mark as logged in - real verification happens when performing actions
            self.is_logged_in = True

            try:
                # Log available action methods for debugging
                action_methods = [
                    m
                    for m in dir(self.client)
                    if m.startswith(("create_", "like_", "retweet", "quote", "follow"))
                ]
                self.logger.info(
                    f"{self.bot_id}: Available action methods: {len(action_methods)} found"
                )

                return True

            except Exception as e:
                error_msg = str(e)
                self.logger.warning(f"{self.bot_id}: Method check warning: {error_msg}")

                # Check for specific errors
                if "401" in error_msg or "Could not authenticate" in error_msg:
                    self.logger.error(
                        f"{self.bot_id}: ❌ Authentication rejected by Twitter"
                    )
                    self.logger.error(f"{self.bot_id}: Possible causes:")
                    self.logger.error(
                        f"{self.bot_id}:   1. Cookies are expired - export fresh cookies"
                    )
                    self.logger.error(
                        f"{self.bot_id}:   2. Cookies were exported from different IP than proxy"
                    )
                    self.logger.error(
                        f"{self.bot_id}:   3. Twitter detected automated behavior"
                    )
                    self.logger.error(
                        f"{self.bot_id}:   4. Account may be suspended or locked"
                    )
                elif "403" in error_msg or "Forbidden" in error_msg:
                    self.logger.error(
                        f"{self.bot_id}: ❌ Access forbidden - possible Cloudflare block"
                    )
                    self.logger.error(
                        f"{self.bot_id}: Verify proxy is working: {Config.PROXY_URL[:50]}..."
                    )
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
            # favorite_tweet may return a Response object (not a coroutine) in some Twikit versions
            result = await self.client.favorite_tweet(tweet_id)
            self.last_action_time = datetime.now()
            self.logger.info(f"{self.bot_id}: Liked tweet {tweet_id}")
            return True
        except TypeError as e:
            # If it's not a coroutine, call it without await
            if "can't be used in 'await' expression" in str(e):
                try:
                    result = self.client.favorite_tweet(tweet_id)
                    self.last_action_time = datetime.now()
                    self.logger.info(f"{self.bot_id}: Liked tweet {tweet_id}")
                    return True
                except Exception as e2:
                    self.logger.error(
                        f"{self.bot_id}: Failed to like tweet {tweet_id}: {e2}"
                    )
                    if "rate limit" in str(e2).lower():
                        self.mark_rate_limited()
                    return False
            else:
                raise
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
            # Try using the direct client.retweet() method instead of fetching tweet first
            # The fetch-then-retweet approach has issues with certain tweet formats
            await self.client.retweet(tweet_id)
            self.last_action_time = datetime.now()
            self.logger.info(f"{self.bot_id}: Retweeted tweet {tweet_id} successfully")
            return True

        except TypeError:
            # If it's not async, try without await
            try:
                self.client.retweet(tweet_id)
                self.last_action_time = datetime.now()
                self.logger.info(f"{self.bot_id}: Retweeted tweet {tweet_id} successfully (sync)")
                return True
            except Exception as sync_error:
                # Check for 404 in sync method too
                if "404" in str(sync_error):
                    self.logger.info(f"{self.bot_id}: Tweet {tweet_id} already retweeted (404)")
                    return True
                raise

        except Exception as e:
            error_str = str(e)

            # If it's a 404 error, tweet might already be retweeted - consider it success
            if "404" in error_str:
                self.logger.info(f"{self.bot_id}: Tweet {tweet_id} already retweeted (404)")
                return True

            # Log actual errors
            self.logger.error(f"{self.bot_id}: Failed to retweet {tweet_id}: {e}")

            # Handle rate limiting
            if "rate limit" in error_str.lower():
                self.mark_rate_limited()

            return False

    async def comment_on_tweet(self, tweet_id: str, text: str) -> bool:
        """Comment on a tweet with human-like warmup activity"""
        if not self._can_perform_action():
            self.logger.warning(f"{self.bot_id}: Cannot perform action")
            return False

        try:
            # WARMUP: Perform human-like activities before commenting to avoid error 226
            import random

            # 1. Fetch home timeline (looks like browsing)
            try:
                self.logger.info(f"{self.bot_id}: Warming up - fetching timeline...")
                await self.client.get_home_timeline(count=5)
                await asyncio.sleep(random.uniform(1.0, 2.5))
            except Exception as warmup_error:
                self.logger.warning(f"{self.bot_id}: Warmup timeline fetch failed: {warmup_error}")

            # 2. Get the tweet details (looks like reading before replying)
            try:
                self.logger.info(f"{self.bot_id}: Warming up - reading tweet {tweet_id}...")
                await self.client.get_tweet_by_id(tweet_id)
                await asyncio.sleep(random.uniform(1.5, 3.0))
            except Exception as read_error:
                self.logger.warning(f"{self.bot_id}: Warmup tweet read failed: {read_error}")

            # 3. Now post the comment
            self.logger.info(f"{self.bot_id}: Posting comment: {text[:50]}...")
            await self.client.create_tweet(text=text, reply_to=tweet_id)
            self.last_action_time = datetime.now()
            self.logger.info(f"{self.bot_id}: ✅ Successfully commented on tweet {tweet_id}")
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
            # follow_user returns a Response object, not a coroutine
            result = await self.client.follow_user(user_id)
            self.last_action_time = datetime.now()
            self.logger.info(f"{self.bot_id}: Followed user {user_id}")
            return True
        except TypeError as e:
            # If it's not a coroutine, call it without await
            if "can't be used in 'await' expression" in str(e):
                try:
                    result = self.client.follow_user(user_id)
                    self.last_action_time = datetime.now()
                    self.logger.info(f"{self.bot_id}: Followed user {user_id}")
                    return True
                except Exception as e2:
                    self.logger.error(
                        f"{self.bot_id}: Failed to follow user {user_id}: {e2}"
                    )
                    if "rate limit" in str(e2).lower():
                        self.mark_rate_limited()
                    return False
            else:
                raise
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
            "rate_limited_until": self.rate_limited_until.isoformat()
            if self.rate_limited_until
            else None,
            "captcha_required": self.captcha_required,
            "last_action_time": self.last_action_time.isoformat()
            if self.last_action_time
            else None,
            "status": "active" if self._can_perform_action() else "limited",
            "proxy_configured": bool(Config.PROXY_URL),
        }

    async def get_user_id(self) -> str:
        """Get the Twitter user ID, fetching it if not already available"""
        if self.twitter_user_id:
            return self.twitter_user_id

        try:
            # Fetch the user ID using twikit's user_id() method
            self.twitter_user_id = await self.client.user_id()
            self.logger.info(
                f"{self.bot_id}: Fetched Twitter user ID: {self.twitter_user_id}"
            )
            return self.twitter_user_id
        except Exception as e:
            self.logger.error(f"{self.bot_id}: Failed to fetch user ID: {e}")
            return None

    async def cleanup(self):
        """Cleanup worker resources"""
        try:
            # Close any open connections
            if hasattr(self.client, "close"):
                await self.client.close()
            self.logger.info(f"{self.bot_id}: Worker cleaned up")
        except Exception as e:
            self.logger.error(f"{self.bot_id}: Error during cleanup: {e}")


class WorkerManager:
    """Manages multiple Twitter bot workers with proxy support"""

    def __init__(self, db: Database, search_engine=None):
        self.db = db
        self.search_engine = search_engine
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

            # Ensure all_bots is a dictionary
            if not isinstance(all_bots, dict):
                self.logger.error(
                    f"get_all_bots returned non-dict type: {type(all_bots)}"
                )
                return

            for bot_id, bot_info in all_bots.items():
                if not isinstance(bot_info, dict):
                    self.logger.error(
                        f"Bot info for {bot_id} is not a dict: {type(bot_info)}"
                    )
                    continue

                if bot_info.get("status") == "active":
                    cookie_data = bot_info.get("cookies", {})

                    # Ensure cookie_data is a dictionary
                    if not isinstance(cookie_data, dict):
                        self.logger.error(
                            f"Cookie data for {bot_id} is not a dict: {type(cookie_data)}"
                        )
                        continue

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

            if not validation["valid"]:
                self.logger.error(
                    f"Cookie validation failed for {bot_id}: {validation['errors']}"
                )
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
            self.db.remove_bot(bot_id)

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
        available_workers = sum(
            1 for w in self.workers.values() if w._can_perform_action()
        )
        rate_limited_workers = sum(
            1 for w in self.workers.values() if w.rate_limited_until
        )
        captcha_required_workers = sum(
            1 for w in self.workers.values() if w.captcha_required
        )

        return {
            "total_workers": total_workers,
            "active_workers": active_workers,
            "available_workers": available_workers,
            "rate_limited_workers": rate_limited_workers,
            "captcha_required_workers": captcha_required_workers,
            "proxy_configured": bool(Config.PROXY_URL),
            "is_running": self.is_running,
        }

    async def resume_rate_limited_workers(self):
        """Resume workers that are no longer rate limited"""
        try:
            resumed_count = 0
            for worker in self.workers.values():
                if (
                    worker.rate_limited_until
                    and datetime.now() >= worker.rate_limited_until
                ):
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
            self.logger.info(
                f"🔄 Starting mutual following sync for bot: {new_bot_id or 'all bots'}"
            )

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

                self.logger.info(
                    f"Making {new_bot_id} follow all other bots and vice versa..."
                )

                for worker in all_workers:
                    if worker.bot_id == new_bot_id:
                        continue

                    try:
                        # Get user IDs (fetch if not already available)
                        new_user_id = await new_worker.get_user_id()
                        other_user_id = await worker.get_user_id()

                        if not new_user_id or not other_user_id:
                            self.logger.warning(
                                f"Missing user IDs: {new_bot_id}={new_user_id}, {worker.bot_id}={other_user_id}"
                            )
                            continue

                        # Make new bot follow this bot
                        try:
                            await new_worker.follow_user(other_user_id)
                            self.logger.info(
                                f"✅ {new_bot_id} followed {worker.bot_id} (ID: {other_user_id})"
                            )
                            follow_count += 1
                            await asyncio.sleep(2)  # Rate limiting between follows
                        except Exception as e:
                            error_msg = (
                                f"Error: {new_bot_id} following {worker.bot_id}: {e}"
                            )
                            self.logger.error(error_msg)
                            errors.append(error_msg)

                        # Make this bot follow the new bot
                        try:
                            await worker.follow_user(new_user_id)
                            self.logger.info(
                                f"✅ {worker.bot_id} followed {new_bot_id} (ID: {new_user_id})"
                            )
                            follow_count += 1
                            await asyncio.sleep(2)  # Rate limiting between follows
                        except Exception as e:
                            error_msg = (
                                f"Error: {worker.bot_id} following {new_bot_id}: {e}"
                            )
                            self.logger.error(error_msg)
                            errors.append(error_msg)

                    except Exception as e:
                        error_msg = f"Error in mutual follow between {new_bot_id} and {worker.bot_id}: {e}"
                        self.logger.error(error_msg)
                        errors.append(error_msg)
            else:
                # Make all bots follow each other
                self.logger.info(
                    f"Making all {len(all_workers)} bots follow each other..."
                )

                for i, worker1 in enumerate(all_workers):
                    for worker2 in all_workers[i + 1 :]:
                        try:
                            # Get user IDs (fetch if not already available)
                            user1_id = await worker1.get_user_id()
                            user2_id = await worker2.get_user_id()

                            if not user1_id or not user2_id:
                                self.logger.warning(
                                    f"Missing user IDs: {worker1.bot_id}={user1_id}, {worker2.bot_id}={user2_id}"
                                )
                                continue

                            # Bot 1 follows Bot 2
                            try:
                                await worker1.follow_user(user2_id)
                                self.logger.info(
                                    f"✅ {worker1.bot_id} followed {worker2.bot_id}"
                                )
                                follow_count += 1
                                await asyncio.sleep(2)
                            except Exception as e:
                                error_msg = f"Error: {worker1.bot_id} following {worker2.bot_id}: {e}"
                                self.logger.error(error_msg)
                                errors.append(error_msg)

                            # Bot 2 follows Bot 1
                            try:
                                await worker2.follow_user(user1_id)
                                self.logger.info(
                                    f"✅ {worker2.bot_id} followed {worker1.bot_id}"
                                )
                                follow_count += 1
                                await asyncio.sleep(2)
                            except Exception as e:
                                error_msg = f"Error: {worker2.bot_id} following {worker1.bot_id}: {e}"
                                self.logger.error(error_msg)
                                errors.append(error_msg)

                        except Exception as e:
                            error_msg = f"Error in mutual follow between {worker1.bot_id} and {worker2.bot_id}: {e}"
                            self.logger.error(error_msg)
                            errors.append(error_msg)

            if errors:
                self.logger.warning(
                    f"Mutual following completed with {len(errors)} errors"
                )
                self.logger.info(
                    f"✅ Successful follows: {follow_count}, ❌ Errors: {len(errors)}"
                )
            else:
                self.logger.info(
                    f"✅ Mutual following sync completed successfully - {follow_count} follow actions executed!"
                )

            return True

        except Exception as e:
            self.logger.error(f"Error syncing mutual following: {e}")
            return False

    async def like_tweet_all(self, tweet_url: str):
        """Make all active bots like a tweet"""
        try:
            # Extract tweet ID from URL
            import re

            tweet_id_match = re.search(r"/status/(\d+)", tweet_url)
            if not tweet_id_match:
                self.logger.error(f"Invalid tweet URL: {tweet_url}")
                return {"success": 0, "failed": 0, "errors": ["Invalid tweet URL"]}

            tweet_id = tweet_id_match.group(1)
            self.logger.info(f"Making all bots like tweet: {tweet_id}")

            results = {"success": 0, "failed": 0, "errors": []}

            for bot_id, worker in self.workers.items():
                try:
                    success = await worker.like_tweet(tweet_id)
                    if success:
                        results["success"] += 1
                        self.logger.info(f"✅ {bot_id} liked tweet {tweet_id}")
                    else:
                        results["failed"] += 1
                        results["errors"].append(f"{bot_id}: Failed to like")

                    # Rate limiting between likes
                    await asyncio.sleep(2)

                except Exception as e:
                    results["failed"] += 1
                    error_msg = f"{bot_id}: {str(e)}"
                    results["errors"].append(error_msg)
                    self.logger.error(f"❌ {bot_id} failed to like tweet: {e}")

            self.logger.info(
                f"Like task completed: {results['success']} succeeded, {results['failed']} failed"
            )
            return results

        except Exception as e:
            self.logger.error(f"Error in like_tweet_all: {e}")
            return {"success": 0, "failed": 0, "errors": [str(e)]}

    async def retweet_all(self, tweet_url: str):
        """Make all active bots retweet a tweet"""
        try:
            # Extract tweet ID from URL
            import re

            tweet_id_match = re.search(r"/status/(\d+)", tweet_url)
            if not tweet_id_match:
                self.logger.error(f"Invalid tweet URL: {tweet_url}")
                return {"success": 0, "failed": 0, "errors": ["Invalid tweet URL"]}

            tweet_id = tweet_id_match.group(1)
            self.logger.info(f"Making all bots retweet tweet: {tweet_id}")

            results = {"success": 0, "failed": 0, "errors": []}

            for bot_id, worker in self.workers.items():
                try:
                    success = await worker.retweet_tweet(tweet_id)
                    if success:
                        results["success"] += 1
                        self.logger.info(f"✅ {bot_id} retweeted tweet {tweet_id}")
                    else:
                        results["failed"] += 1
                        results["errors"].append(f"{bot_id}: Failed to retweet")

                    # Rate limiting between retweets
                    await asyncio.sleep(2)

                except Exception as e:
                    results["failed"] += 1
                    error_msg = f"{bot_id}: {str(e)}"
                    results["errors"].append(error_msg)
                    self.logger.error(f"❌ {bot_id} failed to retweet: {e}")

            self.logger.info(
                f"Retweet task completed: {results['success']} succeeded, {results['failed']} failed"
            )
            return results

        except Exception as e:
            self.logger.error(f"Error in retweet_all: {e}")
            return {"success": 0, "failed": 0, "errors": [str(e)]}

    async def comment_all(self, tweet_url: str, comments: List[str] = None):
        """Make all active bots comment on a tweet with human-like NFT comments"""
        try:
            # Extract tweet ID from URL
            import re
            import random

            tweet_id_match = re.search(r"/status/(\d+)", tweet_url)
            if not tweet_id_match:
                self.logger.error(f"Invalid tweet URL: {tweet_url}")
                return {"success": 0, "failed": 0, "errors": ["Invalid tweet URL"]}

            tweet_id = tweet_id_match.group(1)
            self.logger.info(f"Making all bots comment on tweet: {tweet_id}")

            results = {"success": 0, "failed": 0, "errors": []}

            for bot_id, worker in self.workers.items():
                try:
                    # Use NFT comments for more human-like behavior
                    if self.search_engine and hasattr(self.search_engine, 'get_random_nft_comment'):
                        comment_text = self.search_engine.get_random_nft_comment()
                        self.logger.info(f"{bot_id}: Using NFT comment: {comment_text[:50]}...")
                    elif comments:
                        comment_text = random.choice(comments)
                    else:
                        comment_text = "Great post!"

                    success = await worker.comment_on_tweet(tweet_id, comment_text)
                    if success:
                        results["success"] += 1
                        self.logger.info(f"✅ {bot_id} commented on tweet {tweet_id}")
                    else:
                        results["failed"] += 1
                        results["errors"].append(f"{bot_id}: Failed to comment")

                    # Human-like random delay between comments (2-5 seconds)
                    delay = random.uniform(2.0, 5.0)
                    self.logger.info(f"{bot_id}: Waiting {delay:.1f}s before next comment...")
                    await asyncio.sleep(delay)

                except Exception as e:
                    results["failed"] += 1
                    error_msg = f"{bot_id}: {str(e)}"
                    results["errors"].append(error_msg)
                    self.logger.error(f"❌ {bot_id} failed to comment: {e}")

            self.logger.info(
                f"Comment task completed: {results['success']} succeeded, {results['failed']} failed"
            )
            return results

        except Exception as e:
            self.logger.error(f"Error in comment_all: {e}")
            return {"success": 0, "failed": 0, "errors": [str(e)]}

    async def quote_tweet_all(self, tweet_url: str, quote_text: str, keyword: str):
        """Make all active bots quote tweet with mentions from keyword pool"""
        try:
            # Extract tweet ID from URL
            import re

            tweet_id_match = re.search(r"/status/(\d+)", tweet_url)
            if not tweet_id_match:
                self.logger.error(f"Invalid tweet URL: {tweet_url}")
                return {"success": 0, "failed": 0, "errors": ["Invalid tweet URL"]}

            tweet_id = tweet_id_match.group(1)
            self.logger.info(f"Making all bots quote tweet: {tweet_id}")

            results = {"success": 0, "failed": 0, "errors": []}

            for bot_id, worker in self.workers.items():
                try:
                    # Get users to mention from pool (max 3 per quote)
                    mentions = self.db.get_users_from_pool(keyword, 3) if keyword else []

                    # Build quote text with mentions
                    mention_text = " ".join([f"@{user}" for user in mentions])
                    full_quote = f"{quote_text} {mention_text}".strip()

                    success = await worker.quote_tweet(tweet_id, full_quote)
                    if success:
                        results["success"] += 1
                        self.logger.info(f"✅ {bot_id} quoted tweet {tweet_id}")
                    else:
                        results["failed"] += 1
                        results["errors"].append(f"{bot_id}: Failed to quote")

                    # Rate limiting between quotes
                    await asyncio.sleep(3)

                except Exception as e:
                    results["failed"] += 1
                    error_msg = f"{bot_id}: {str(e)}"
                    results["errors"].append(error_msg)
                    self.logger.error(f"❌ {bot_id} failed to quote tweet: {e}")

            self.logger.info(
                f"Quote task completed: {results['success']} succeeded, {results['failed']} failed"
            )
            return results

        except Exception as e:
            self.logger.error(f"Error in quote_tweet_all: {e}")
            return {"success": 0, "failed": 0, "errors": [str(e)]}
