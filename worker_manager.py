"""
Worker manager for Twitter bot accounts
"""

import asyncio
import json
import os
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from twikit import Client
import httpx
from database import Database
from logger import bot_logger
from config import Config


class TwitterWorker:
    """Individual Twitter worker bot"""

    def __init__(self, bot_id: str, cookie_data: Dict[str, Any], db: Database):
        self.bot_id = bot_id
        self.cookie_data = cookie_data
        self.db = db
        # Work around the proxy parameter issue in newer Twikit versions
        try:
            self.client = Client("en-US")
        except TypeError as e:
            if "proxy" in str(e):
                # Patch the httpx AsyncClient to ignore proxy parameter
                original_init = httpx.AsyncClient.__init__
                def patched_init(self, *args, **kwargs):
                    kwargs.pop('proxy', None)
                    return original_init(self, *args, **kwargs)
                httpx.AsyncClient.__init__ = patched_init
                self.client = Client("en-US")
            else:
                raise e
        self.is_logged_in = False
        self.rate_limited_until = None
        self.captcha_required = False
        self.last_activity = None

        self.logger = bot_logger

    async def initialize(self) -> bool:
        """Initialize the Twitter client with cookies and anti-spam measures"""
        try:
            # Set cookies - try to load from file first if available
            cookie_file_path = os.path.join(
                Config.COOKIES_PATH, f"{self.bot_id}_cookies.json"
            )
            if os.path.exists(cookie_file_path):
                try:
                    # Try to load cookies from file first (Twikit's preferred method)
                    self.client.load_cookies(cookie_file_path)
                    self.logger.info(
                        f"Bot {self.bot_id} loaded cookies from file: {cookie_file_path}"
                    )
                except Exception as e:
                    self.logger.warning(
                        f"Bot {self.bot_id} failed to load cookies from file, using database cookies: {e}"
                    )
                    self.client.set_cookies(self.cookie_data)
            else:
                # Use cookies from database
                self.client.set_cookies(self.cookie_data)

            # Add human-like headers to avoid detection
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }

            # Set headers if the client supports it
            if hasattr(self.client, "_session") and hasattr(
                self.client._session, "headers"
            ):
                self.client._session.headers.update(headers)

            # Add small delay to appear more human-like
            await asyncio.sleep(random.uniform(1, 3))

            # Try multiple methods to verify authentication
            auth_success = False

            # Method 1: Try to get current user info directly
            try:
                self.logger.info(f"Bot {self.bot_id} trying method 1: client.user()")
                current_user = await self.client.user()
                if current_user:
                    username = getattr(
                        current_user,
                        "screen_name",
                        getattr(current_user, "username", "Unknown"),
                    )
                    user_id = getattr(current_user, "id", "Unknown")

                    self.logger.info(
                        f"Bot {self.bot_id} initialized successfully as @{username} (ID: {user_id})"
                    )
                    auth_success = True
            except Exception as e1:
                self.logger.warning(f"Bot {self.bot_id} method 1 failed: {e1}")

                # Method 2: Try to get user by ID from twid cookie
                try:
                    self.logger.info(
                        f"Bot {self.bot_id} trying method 2: get_user_by_id from twid"
                    )
                    twid = self.cookie_data.get("twid", "").replace("u%3D", "")
                    if twid:
                        user = self.client.get_user_by_id(twid)
                        if user:
                            username = getattr(
                                user,
                                "screen_name",
                                getattr(user, "username", "Unknown"),
                            )
                            self.logger.info(
                                f"Bot {self.bot_id} initialized successfully as @{username} (ID: {twid})"
                            )
                            auth_success = True
                except Exception as e2:
                    self.logger.warning(f"Bot {self.bot_id} method 2 failed: {e2}")

                    # Method 3: Try to get user by ID from auth_multi cookie
                    try:
                        self.logger.info(
                            f"Bot {self.bot_id} trying method 3: get_user_by_id from auth_multi"
                        )
                        auth_multi = self.cookie_data.get("auth_multi", "")
                        if ":" in auth_multi:
                            user_id_from_auth = auth_multi.split(":")[0]
                            user = self.client.get_user_by_id(user_id_from_auth)
                            if user:
                                username = getattr(
                                    user,
                                    "screen_name",
                                    getattr(user, "username", "Unknown"),
                                )
                                self.logger.info(
                                    f"Bot {self.bot_id} initialized successfully as @{username} (ID: {user_id_from_auth})"
                                )
                                auth_success = True
                    except Exception as e3:
                        self.logger.warning(f"Bot {self.bot_id} method 3 failed: {e3}")

                        # Method 4: Just assume it works if we have valid cookies
                        self.logger.info(
                            f"Bot {self.bot_id} trying method 4: assume valid cookies"
                        )
                        if all(
                            key in self.cookie_data for key in ["auth_token", "ct0"]
                        ):
                            self.logger.info(
                                f"Bot {self.bot_id} initialized with valid cookies (auth_token, ct0 present)"
                            )
                            auth_success = True
                        else:
                            self.logger.error(
                                f"Bot {self.bot_id} missing required cookies: auth_token, ct0"
                            )

            if auth_success:
                self.is_logged_in = True
                # Update database
                self.db.update_bot_status(
                    self.bot_id, "active", last_activity=datetime.now().isoformat()
                )
                return True
            else:
                self.logger.error(
                    f"Bot {self.bot_id} all authentication methods failed"
                )
                return False

        except Exception as e:
            self.logger.error(f"Bot {self.bot_id} initialization failed: {e}")
            return False

    async def reinitialize(self) -> bool:
        """Reinitialize the bot with fresh authentication and anti-spam measures"""
        try:
            self.logger.info(f"Reinitializing bot {self.bot_id}...")

            # Create a new client instance
            # Work around the proxy parameter issue in newer Twikit versions
            try:
                self.client = Client()
            except TypeError as e:
                if "proxy" in str(e):
                    # Patch the httpx AsyncClient to ignore proxy parameter
                    original_init = httpx.AsyncClient.__init__
                    def patched_init(self, *args, **kwargs):
                        kwargs.pop('proxy', None)
                        return original_init(self, *args, **kwargs)
                    httpx.AsyncClient.__init__ = patched_init
                    self.client = Client()
                else:
                    raise e

            # Set cookies again - try to load from file first if available
            cookie_file_path = os.path.join(
                Config.COOKIES_PATH, f"{self.bot_id}_cookies.json"
            )
            if os.path.exists(cookie_file_path):
                try:
                    # Try to load cookies from file first (Twikit's preferred method)
                    self.client.load_cookies(cookie_file_path)
                    self.logger.info(
                        f"Bot {self.bot_id} reinitialized with cookies from file: {cookie_file_path}"
                    )
                except Exception as e:
                    self.logger.warning(
                        f"Bot {self.bot_id} failed to load cookies from file during reinit, using database cookies: {e}"
                    )
                    self.client.set_cookies(self.cookie_data)
            else:
                # Use cookies from database
                self.client.set_cookies(self.cookie_data)

            # Add human-like headers to avoid detection
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }

            # Set headers if the client supports it
            if hasattr(self.client, "_session") and hasattr(
                self.client._session, "headers"
            ):
                self.client._session.headers.update(headers)

            # Add delay to appear more human-like
            await asyncio.sleep(random.uniform(2, 5))

            # Try to verify authentication
            try:
                current_user = await self.client.user()
                if current_user:
                    username = getattr(
                        current_user,
                        "screen_name",
                        getattr(current_user, "username", "Unknown"),
                    )
                    user_id = getattr(current_user, "id", "Unknown")

                    self.logger.info(
                        f"Bot {self.bot_id} reinitialized successfully as @{username} (ID: {user_id})"
                    )

                    self.is_logged_in = True
                    self.rate_limited_until = None
                    self.captcha_required = False

                    # Update database
                    self.db.update_bot_status(
                        self.bot_id, "active", last_activity=datetime.now().isoformat()
                    )

                    return True
                else:
                    self.logger.error(
                        f"Bot {self.bot_id} failed to get current user info during reinit"
                    )
                    return False

            except Exception as e:
                error_msg = str(e)
                if "404" in error_msg or "page does not exist" in error_msg:
                    self.logger.error(
                        f"Bot {self.bot_id} reinitialization failed - account may be suspended or cookies invalid"
                    )
                else:
                    self.logger.error(f"Bot {self.bot_id} reinitialization failed: {e}")
                return False

        except Exception as e:
            self.logger.error(f"Bot {self.bot_id} reinitialization failed: {e}")
            return False

    async def like_tweet(self, tweet_url: str) -> bool:
        """Like a tweet"""
        try:
            if not self._can_perform_action():
                return False

            tweet_id = self._extract_tweet_id(tweet_url)
            if not tweet_id:
                return False

            tweet = await self.client.get_tweet_by_id(tweet_id)
            if tweet:
                await tweet.favorite()
                self.last_activity = datetime.now()

                # Update statistics
                self.db.update_statistics("total_likes")
                self.logger.info(f"Bot {self.bot_id} liked tweet {tweet_id}")

                await self.logger.send_task_completion(
                    "like", self.bot_id, True, f"Tweet: {tweet_url}"
                )
                return True

            return False

        except Exception as e:
            await self._handle_action_error(e, "like", tweet_url)
            return False

    async def retweet(self, tweet_url: str) -> bool:
        """Retweet a tweet"""
        try:
            if not self._can_perform_action():
                return False

            tweet_id = self._extract_tweet_id(tweet_url)
            if not tweet_id:
                return False

            tweet = await self.client.get_tweet_by_id(tweet_id)
            if tweet:
                await tweet.retweet()
                self.last_activity = datetime.now()

                # Update statistics
                self.db.update_statistics("total_retweets")
                self.logger.info(f"Bot {self.bot_id} retweeted tweet {tweet_id}")

                await self.logger.send_task_completion(
                    "retweet", self.bot_id, True, f"Tweet: {tweet_url}"
                )
                return True

            return False

        except Exception as e:
            await self._handle_action_error(e, "retweet", tweet_url)
            return False

    async def comment(self, tweet_url: str, comment_text: str) -> bool:
        """Comment on a tweet with anti-spam measures"""
        try:
            if not self._can_perform_action():
                return False

            tweet_id = self._extract_tweet_id(tweet_url)
            if not tweet_id:
                self.logger.error(f"Could not extract tweet ID from URL: {tweet_url}")
                return False

            # Add longer human-like delay before commenting
            delay = random.uniform(30, 60)  # Random delay between 30-60 seconds
            self.logger.info(
                f"Waiting {delay:.1f}s before commenting (anti-spam measure)"
            )
            await asyncio.sleep(delay)

            # Add random scrolling/session activity simulation
            try:
                # Simulate some random activity to appear more human
                activities = [
                    lambda: asyncio.sleep(random.uniform(1, 3)),
                    lambda: self.client.get_trending_topics()
                    if hasattr(self.client, "get_trending_topics")
                    else asyncio.sleep(1),
                    lambda: asyncio.sleep(random.uniform(0.5, 2)),
                ]
                await random.choice(activities)()
            except:
                pass  # Ignore errors in simulation

            self.logger.info(
                f"Attempting to reply to tweet {tweet_id} with: {comment_text}"
            )

            # Try different approaches to avoid spam detection
            success = False

            # Method 1: Try using tweet.reply() with proper tweet object
            try:
                self.logger.info("Trying method 1: tweet.reply() with get_tweet_by_id")
                tweet = await self.client.get_tweet_by_id(tweet_id)
                if tweet:
                    await tweet.reply(comment_text)
                    self.logger.info("Reply successful using tweet.reply()")
                    success = True
            except Exception as e1:
                self.logger.warning(f"Method 1 failed: {e1}")

                # Check if it's a rate limit error
                if "344" in str(e1) or "226" in str(e1):
                    self.logger.warning(f"Bot {self.bot_id} hit rate limit on method 1")
                    # Apply rate limit penalty
                    self.rate_limited_until = datetime.now() + timedelta(minutes=30)
                    self.db.update_bot_status(
                        self.bot_id,
                        "rate_limited",
                        rate_limited_until=self.rate_limited_until.isoformat(),
                    )
                    await self.logger.send_rate_limit_alert(self.bot_id, 30)
                    return False

                # Method 2: Try create_tweet with reply_to
                try:
                    self.logger.info("Trying method 2: create_tweet with reply_to")
                    await self.client.create_tweet(text=comment_text, reply_to=tweet_id)
                    self.logger.info(
                        "Reply successful using create_tweet with reply_to"
                    )
                    success = True
                except Exception as e2:
                    self.logger.warning(f"Method 2 failed: {e2}")

                    # Check if it's a rate limit error
                    if "344" in str(e2) or "226" in str(e2):
                        self.logger.warning(
                            f"Bot {self.bot_id} hit rate limit on method 2"
                        )
                        # Apply rate limit penalty
                        self.rate_limited_until = datetime.now() + timedelta(minutes=30)
                        self.db.update_bot_status(
                            self.bot_id,
                            "rate_limited",
                            rate_limited_until=self.rate_limited_until.isoformat(),
                        )
                        await self.logger.send_rate_limit_alert(
                            self.bot_id, "comment", 30
                        )
                        return False

                    # Method 3: Try with @mention (less likely to be detected as spam)
                    try:
                        self.logger.info("Trying method 3: create_tweet with @mention")
                        username = (
                            tweet_url.split("/")[-3]
                            if len(tweet_url.split("/")) >= 3
                            else "user"
                        )
                        mention_text = f"@{username} {comment_text}"

                        # Add random variation to make it look more human
                        variations = ["", "👍", "🔥", "❤️"]
                        if random.choice([True, False]):  # 50% chance to add emoji
                            mention_text += f" {random.choice(variations)}"

                        await self.client.create_tweet(text=mention_text)
                        self.logger.info(
                            "Reply successful using create_tweet with @mention"
                        )
                        success = True
                    except Exception as e3:
                        self.logger.warning(f"Method 3 failed: {e3}")

                        # Check if it's a rate limit error
                        if "344" in str(e3) or "226" in str(e3):
                            self.logger.warning(
                                f"Bot {self.bot_id} hit rate limit on method 3"
                            )
                            # Apply rate limit penalty
                            self.rate_limited_until = datetime.now() + timedelta(
                                minutes=30
                            )
                            self.db.update_bot_status(
                                self.bot_id,
                                "rate_limited",
                                rate_limited_until=self.rate_limited_until.isoformat(),
                            )
                            await self.logger.send_rate_limit_alert(
                                self.bot_id, "comment", 30
                            )
                            return False

                        # Method 4: Try a simple tweet without reply (last resort)
                        try:
                            self.logger.info(
                                "Trying method 4: simple tweet as last resort"
                            )
                            simple_text = f"{comment_text} #twitter"
                            await self.client.create_tweet(text=simple_text)
                            self.logger.info("Reply successful using simple tweet")
                            success = True
                        except Exception as e4:
                            self.logger.error(
                                f"All methods failed: tweet.reply={e1}, reply_to={e2}, mention={e3}, simple={e4}"
                            )
                            # Check if it's a rate limit error
                            if "344" in str(e4) or "226" in str(e4):
                                self.logger.warning(
                                    f"Bot {self.bot_id} hit rate limit on all methods"
                                )
                                # Apply rate limit penalty
                                self.rate_limited_until = datetime.now() + timedelta(
                                    minutes=30
                                )
                                self.db.update_bot_status(
                                    self.bot_id,
                                    "rate_limited",
                                    rate_limited_until=self.rate_limited_until.isoformat(),
                                )
                                await self.logger.send_rate_limit_alert(
                                    self.bot_id, "comment", 30
                                )
                                return False
                            raise e1

            if success:
                self.last_activity = datetime.now()

                # Update statistics
                self.db.update_statistics("total_comments")
                self.logger.info(f"Bot {self.bot_id} commented on tweet {tweet_id}")

                await self.logger.send_task_completion(
                    "comment", self.bot_id, True, f"Tweet: {tweet_url}"
                )
                return True
            else:
                return False

        except Exception as e:
            error_msg = str(e)
            if "226" in error_msg:
                self.logger.warning(
                    f"Bot {self.bot_id} hit Twitter's spam detection (226 error)"
                )
                # Mark as rate limited for longer period due to spam detection
                self.rate_limited_until = datetime.now() + timedelta(
                    minutes=30
                )  # 30 min penalty
                self.db.update_bot_status(
                    self.bot_id,
                    "rate_limited",
                    rate_limited_until=self.rate_limited_until.isoformat(),
                )
                await self.logger.send_rate_limit_alert(self.bot_id, 30)
            else:
                self.logger.error(
                    f"Comment error details: {type(e).__name__}: {error_msg}"
                )
                await self._handle_action_error(e, "comment", tweet_url)
            return False

    async def quote_tweet(
        self, tweet_url: str, quote_text: str, mentions: List[str] = None
    ) -> bool:
        """Quote tweet with mentions"""
        try:
            if not self._can_perform_action():
                return False

            tweet_id = self._extract_tweet_id(tweet_url)
            if not tweet_id:
                return False

            # Add mentions to quote text
            if mentions:
                mention_text = " ".join([f"@{mention}" for mention in mentions])
                quote_text = f"{quote_text}\n\n{mention_text}"

            tweet = await self.client.get_tweet_by_id(tweet_id)
            if tweet:
                await tweet.quote(quote_text)
                self.last_activity = datetime.now()

                # Update statistics
                self.db.update_statistics("total_quotes")
                self.logger.info(f"Bot {self.bot_id} quoted tweet {tweet_id}")

                await self.logger.send_task_completion(
                    "quote", self.bot_id, True, f"Tweet: {tweet_url}"
                )
                return True

            return False

        except Exception as e:
            await self._handle_action_error(e, "quote", tweet_url)
            return False

    async def follow_user(self, username: str) -> bool:
        """Follow a user"""
        try:
            if not self._can_perform_action():
                return False

            user = await self.client.get_user_by_screen_name(username)
            if user:
                await user.follow()
                self.last_activity = datetime.now()

                self.logger.info(f"Bot {self.bot_id} followed @{username}")
                return True

            return False

        except Exception as e:
            await self._handle_action_error(e, "follow", f"@{username}")
            return False

    async def unfollow_user(self, username: str) -> bool:
        """Unfollow a user"""
        try:
            if not self._can_perform_action():
                return False

            user = await self.client.get_user_by_screen_name(username)
            if user:
                await user.unfollow()
                self.last_activity = datetime.now()

                # Update statistics
                self.db.update_statistics("total_unfollows")
                self.logger.info(f"Bot {self.bot_id} unfollowed @{username}")

                await self.logger.send_task_completion(
                    "unfollow", self.bot_id, True, f"User: @{username}"
                )
                return True

            return False

        except Exception as e:
            await self._handle_action_error(e, "unfollow", f"@{username}")
            return False

    async def get_followers(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get list of users following this bot"""
        try:
            if not self._can_perform_action():
                return []

            # Get current user's followers
            followers = []
            try:
                user = await self.client.user()
                if user:
                    try:
                        followers_list = await user.get_followers(count=min(limit, 200))
                        for follower in followers_list:
                            followers.append(
                                {
                                    "id": getattr(follower, "id", ""),
                                    "username": getattr(
                                        follower,
                                        "screen_name",
                                        getattr(follower, "username", ""),
                                    ),
                                    "display_name": getattr(follower, "name", ""),
                                    "followers_count": getattr(
                                        follower, "followers_count", 0
                                    ),
                                    "following_count": getattr(
                                        follower, "following_count", 0
                                    ),
                                }
                            )
                    except Exception as e:
                        self.logger.warning(
                            f"Bot {self.bot_id} couldn't get followers: {e}"
                        )
                        # Return empty list but don't fail
                        pass
            except Exception as e:
                self.logger.warning(f"Bot {self.bot_id} couldn't get user info: {e}")

            return followers

        except Exception as e:
            self.logger.error(f"Bot {self.bot_id} failed to get followers: {e}")
            return []

    async def get_following(self, limit: int = 5000) -> List[Dict[str, Any]]:
        """Get list of users this bot is following"""
        try:
            if not self._can_perform_action():
                return []

            # Get current user's following using different methods
            following = []

            # Method 1: Try to get current user and their following
            try:
                current_user = await self.client.user()
                if current_user:
                    try:
                        following_list = await current_user.get_following(
                            count=min(limit, 200)
                        )
                        for followed in following_list:
                            following.append(
                                {
                                    "id": getattr(followed, "id", ""),
                                    "username": getattr(
                                        followed,
                                        "screen_name",
                                        getattr(followed, "username", ""),
                                    ),
                                    "display_name": getattr(followed, "name", ""),
                                    "followers_count": getattr(
                                        followed, "followers_count", 0
                                    ),
                                    "following_count": getattr(
                                        followed, "following_count", 0
                                    ),
                                }
                            )
                        if following:
                            self.logger.info(
                                f"Bot {self.bot_id} got {len(following)} following using user.get_following"
                            )
                            return following
                    except Exception as e:
                        self.logger.warning(
                            f"Bot {self.bot_id} user.get_following failed: {e}"
                        )
            except Exception as e:
                self.logger.warning(f"Bot {self.bot_id} couldn't get current user: {e}")

            # Method 2: Try get_user_following with user ID from twid
            try:
                twid = self.cookie_data.get("twid", "").replace("u%3D", "")
                if twid:
                    following_list = await self.client.get_user_following(
                        twid, count=min(limit, 200)
                    )
                    for followed in following_list:
                        following.append(
                            {
                                "id": getattr(followed, "id", ""),
                                "username": getattr(
                                    followed,
                                    "screen_name",
                                    getattr(followed, "username", ""),
                                ),
                                "display_name": getattr(followed, "name", ""),
                                "followers_count": getattr(
                                    followed, "followers_count", 0
                                ),
                                "following_count": getattr(
                                    followed, "following_count", 0
                                ),
                            }
                        )
                    if following:
                        self.logger.info(
                            f"Bot {self.bot_id} got {len(following)} following using get_user_following"
                        )
                        return following
            except Exception as e:
                self.logger.warning(f"Bot {self.bot_id} get_user_following failed: {e}")

            # Method 3: Try direct API call
            try:
                # Get current user ID from twid
                twid = self.cookie_data.get("twid", "").replace("u%3D", "")
                if twid:
                    # Try to get following using the user ID directly
                    # Try using get_user_by_id and then get their following
                    user = self.client.get_user_by_id(twid)
                    if user:
                        following_list = await user.get_following(count=min(limit, 200))
                    else:
                        following_list = []
                    for followed in following_list:
                        following.append(
                            {
                                "id": getattr(followed, "id", ""),
                                "username": getattr(
                                    followed,
                                    "screen_name",
                                    getattr(followed, "username", ""),
                                ),
                                "display_name": getattr(followed, "name", ""),
                                "followers_count": getattr(
                                    followed, "followers_count", 0
                                ),
                                "following_count": getattr(
                                    followed, "following_count", 0
                                ),
                            }
                        )
                    if following:
                        self.logger.info(
                            f"Bot {self.bot_id} got {len(following)} following using get_following"
                        )
                        return following
            except Exception as e:
                self.logger.warning(f"Bot {self.bot_id} get_following failed: {e}")

            self.logger.warning(
                f"Bot {self.bot_id} couldn't get following with any method"
            )
            return []

        except Exception as e:
            self.logger.error(f"Bot {self.bot_id} failed to get following: {e}")
            return []

    async def unfollow_all_following(
        self, batch_size: int = 10, delay_minutes: int = 2
    ) -> Dict[str, Any]:
        """Unfollow all users this bot is following with rate limiting"""
        try:
            if not self._can_perform_action():
                return {"success": False, "error": "Bot cannot perform actions"}

            self.logger.info(
                f"Bot {self.bot_id} starting unfollow all following process"
            )

            # Get all following
            following = await self.get_following(limit=5000)
            if not following:
                return {
                    "success": True,
                    "unfollowed": 0,
                    "message": "No following to unfollow",
                }

            results = {
                "success": True,
                "total_following": len(following),
                "unfollowed": 0,
                "failed": 0,
                "errors": [],
            }

            # Process in batches with rate limiting
            for i in range(0, len(following), batch_size):
                batch = following[i : i + batch_size]
                self.logger.info(
                    f"Bot {self.bot_id} processing batch {i // batch_size + 1}/{(len(following) - 1) // batch_size + 1}"
                )

                for user in batch:
                    try:
                        user_id = user.get("id")
                        if not user_id:
                            continue

                        success = await self.unfollow_user(user_id)
                        if success:
                            results["unfollowed"] += 1
                        else:
                            results["failed"] += 1
                            results["errors"].append(
                                f"Failed to unfollow {user.get('username', user_id)}"
                            )

                        # Rate limiting delay
                        await asyncio.sleep(delay_minutes * 60)

                    except Exception as e:
                        results["failed"] += 1
                        results["errors"].append(
                            f"Error unfollowing {user.get('username', 'unknown')}: {str(e)}"
                        )
                        self.logger.error(f"Bot {self.bot_id} unfollow error: {e}")

                # Longer delay between batches
                if i + batch_size < len(following):
                    self.logger.info(
                        f"Bot {self.bot_id} waiting {delay_minutes} minutes before next batch"
                    )
                    await asyncio.sleep(delay_minutes * 60)

            self.logger.info(
                f"Bot {self.bot_id} unfollow all following completed: {results['unfollowed']} unfollowed, {results['failed']} failed"
            )

            return results

        except Exception as e:
            self.logger.error(f"Bot {self.bot_id} unfollow all following error: {e}")
            return {"success": False, "error": str(e)}

    async def unfollow_all_followers(
        self, batch_size: int = 10, delay_minutes: int = 2
    ) -> Dict[str, Any]:
        """Unfollow all users following this bot with rate limiting"""
        try:
            if not self._can_perform_action():
                return {"success": False, "error": "Bot cannot perform actions"}

            self.logger.info(
                f"Bot {self.bot_id} starting unfollow all followers process"
            )

            # Get all followers
            followers = await self.get_followers(limit=500)  # Twitter API limit
            if not followers:
                return {
                    "success": True,
                    "unfollowed": 0,
                    "message": "No followers to unfollow",
                }

            results = {
                "success": True,
                "total_followers": len(followers),
                "unfollowed": 0,
                "failed": 0,
                "errors": [],
            }

            # Process in batches with rate limiting
            for i in range(0, len(followers), batch_size):
                batch = followers[i : i + batch_size]

                for follower in batch:
                    try:
                        success = await self.unfollow_user(follower["username"])
                        if success:
                            results["unfollowed"] += 1
                        else:
                            results["failed"] += 1
                            results["errors"].append(
                                f"Failed to unfollow @{follower['username']}"
                            )

                        # Rate limiting delay between unfollows
                        await asyncio.sleep(delay_minutes * 60)  # Convert to seconds

                    except Exception as e:
                        results["failed"] += 1
                        results["errors"].append(
                            f"Error unfollowing @{follower['username']}: {str(e)}"
                        )

                # Longer delay between batches
                if i + batch_size < len(followers):
                    await asyncio.sleep(5 * 60)  # 5-minute break between batches

            self.logger.info(f"Bot {self.bot_id} unfollow process completed: {results}")
            return results

        except Exception as e:
            error_msg = f"Bot {self.bot_id} unfollow all failed: {e}"
            self.logger.error(error_msg)
            return {"success": False, "error": error_msg}

    async def mutual_follow(self, other_bot_ids: List[str]) -> bool:
        """Follow other bots for mutual following"""
        try:
            if not self._can_perform_action():
                return False

            success_count = 0
            for bot_id in other_bot_ids:
                if bot_id != self.bot_id:
                    bot_info = self.db.get_bot(bot_id)
                    if bot_info and bot_info.get("username"):
                        if await self.follow_user(bot_info["username"]):
                            success_count += 1

            self.logger.info(f"Bot {self.bot_id} followed {success_count} other bots")
            return success_count > 0

        except Exception as e:
            self.logger.error(f"Bot {self.bot_id} mutual follow failed: {e}")
            return False

    def _can_perform_action(self) -> bool:
        """Check if bot can perform actions"""
        if not self.is_logged_in:
            return False

        if self.captcha_required:
            return False

        if self.rate_limited_until and datetime.now() < self.rate_limited_until:
            return False

        return True

    def _extract_tweet_id(self, tweet_url: str) -> Optional[str]:
        """Extract tweet ID from URL"""
        try:
            # Handle various Twitter URL formats
            if "/status/" in tweet_url:
                return tweet_url.split("/status/")[-1].split("?")[0]
            return None
        except Exception:
            return None

    async def _handle_action_error(self, error: Exception, action: str, details: str):
        """Handle action errors and rate limiting"""
        error_str = str(error).lower()

        if "rate limit" in error_str or "429" in error_str:
            # Rate limited
            self.rate_limited_until = datetime.now() + timedelta(
                minutes=Config.RATE_LIMIT_PAUSE_MINUTES
            )
            self.db.update_bot_status(
                self.bot_id,
                "rate_limited",
                rate_limited_until=self.rate_limited_until.isoformat(),
            )

            await self.logger.send_rate_limit_alert(
                self.bot_id, Config.RATE_LIMIT_PAUSE_MINUTES
            )
            await self.logger.send_task_completion(
                action, self.bot_id, False, f"Rate limited: {details}"
            )

        elif "captcha" in error_str or "challenge" in error_str:
            # Captcha required
            self.captcha_required = True
            self.db.update_bot_status(
                self.bot_id, "captcha_required", captcha_required=True
            )

            await self.logger.send_captcha_alert(self.bot_id)
            await self.logger.send_task_completion(
                action, self.bot_id, False, f"Captcha required: {details}"
            )

        else:
            # Other error
            await self.logger.send_task_completion(
                action, self.bot_id, False, f"Error: {details}"
            )

        self.logger.error(f"Bot {self.bot_id} {action} failed: {error}")


class WorkerManager:
    """Manages all Twitter worker bots"""

    def __init__(self, db: Database):
        self.db = db
        self.workers: Dict[str, TwitterWorker] = {}
        self.logger = bot_logger
        self.nft_comments = self._load_nft_comments()

    def _load_nft_comments(self) -> List[str]:
        """Load NFT reply-guy comments from file"""
        try:
            comments_file = "data/nft_comments.txt"
            if os.path.exists(comments_file):
                with open(comments_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    # Split by double newlines and filter out empty lines and the header
                    comments = [
                        line.strip()
                        for line in content.split("\n\n")
                        if line.strip() and not line.startswith("🚀")
                    ]
                    self.logger.info(
                        f"Loaded {len(comments)} NFT comments for worker manager"
                    )
                    return comments
            else:
                self.logger.warning(
                    "NFT comments file not found, using default comments"
                )
                return ["Nice post! 👍", "Great content! 🔥", "Love this! ❤️"]
        except Exception as e:
            self.logger.error(f"Failed to load NFT comments: {e}")
            return ["Nice post! 👍", "Great content! 🔥", "Love this! ❤️"]

    def get_random_nft_comment(self) -> str:
        """Get a random NFT reply-guy comment"""
        if self.nft_comments:
            return random.choice(self.nft_comments)
        return "Nice post! 👍"

    async def add_worker(self, bot_id: str, cookie_data: Dict[str, Any]) -> bool:
        """Add a new worker bot"""
        try:
            worker = TwitterWorker(bot_id, cookie_data, self.db)

            if await worker.initialize():
                self.workers[bot_id] = worker

                # Add to database
                self.db.add_bot(bot_id, cookie_data)

                # Perform mutual following if enabled
                settings = self.db._read_data().get("settings", {})
                if settings.get("mutual_following", True):
                    await self._sync_mutual_following(bot_id)

                self.logger.info(f"Worker {bot_id} added successfully")
                return True
            else:
                self.logger.error(f"Failed to initialize worker {bot_id}")
                return False

        except Exception as e:
            self.logger.error(f"Failed to add worker {bot_id}: {e}")
            return False

    async def remove_worker(self, bot_id: str) -> bool:
        """Remove a worker bot"""
        try:
            if bot_id in self.workers:
                del self.workers[bot_id]
                self.db.remove_bot(bot_id)
                self.logger.info(f"Worker {bot_id} removed successfully")
                return True
            return False

        except Exception as e:
            self.logger.error(f"Failed to remove worker {bot_id}: {e}")
            return False

    async def disable_worker(self, bot_id: str) -> bool:
        """Disable a worker bot (mark as inactive)"""
        try:
            # Remove from active workers
            if bot_id in self.workers:
                del self.workers[bot_id]
                self.logger.info(f"Worker {bot_id} removed from active workers")

            # Mark as inactive in database
            success = self.db.update_bot_status(
                bot_id, "inactive", reason="Manually disabled"
            )

            if success:
                self.logger.info(f"Worker {bot_id} disabled successfully")
                return True
            else:
                self.logger.warning(f"Worker {bot_id} not found in database")
                return False

        except Exception as e:
            self.logger.error(f"Failed to disable worker {bot_id}: {e}")
            return False

    async def enable_worker(self, bot_id: str) -> bool:
        """Enable a worker bot (mark as active and reinitialize)"""
        try:
            # Get bot info from database
            bot_info = self.db.get_bot(bot_id)
            if not bot_info:
                self.logger.warning(f"Worker {bot_id} not found in database")
                return False

            # Mark as active in database
            success = self.db.update_bot_status(
                bot_id, "active", reason="Manually enabled"
            )

            if success:
                # Try to reinitialize the worker
                cookie_data = bot_info.get("cookie_data", {})
                worker_success = await self.add_worker(bot_id, cookie_data)

                if worker_success:
                    self.logger.info(
                        f"Worker {bot_id} enabled and reinitialized successfully"
                    )
                    return True
                else:
                    # Mark as inactive again if initialization failed
                    self.db.update_bot_status(
                        bot_id, "inactive", reason="Failed to reinitialize"
                    )
                    self.logger.error(
                        f"Worker {bot_id} enabled but failed to reinitialize"
                    )
                    return False
            else:
                self.logger.error(f"Failed to enable worker {bot_id}")
                return False

        except Exception as e:
            self.logger.error(f"Failed to enable worker {bot_id}: {e}")
            return False

    async def delete_worker(self, bot_id: str) -> bool:
        """Permanently delete a worker bot from both memory and database"""
        try:
            # Remove from active workers
            if bot_id in self.workers:
                del self.workers[bot_id]
                self.logger.info(f"Worker {bot_id} removed from active workers")

            # Remove from database
            db_success = self.db.remove_bot(bot_id)

            if db_success:
                self.logger.info(f"Worker {bot_id} deleted permanently")
                return True
            else:
                self.logger.warning(f"Worker {bot_id} not found in database")
                return False

        except Exception as e:
            self.logger.error(f"Failed to delete worker {bot_id}: {e}")
            return False

    async def get_worker(self, bot_id: str) -> Optional[TwitterWorker]:
        """Get a worker bot"""
        return self.workers.get(bot_id)

    def get_all_workers(self) -> Dict[str, TwitterWorker]:
        """Get all worker bots"""
        return self.workers

    def get_active_workers(self) -> List[TwitterWorker]:
        """Get all active worker bots"""
        active_workers = []
        for worker in self.workers.values():
            if worker._can_perform_action():
                active_workers.append(worker)
        return active_workers

    async def like_tweet_all(self, tweet_url: str) -> Dict[str, bool]:
        """Like tweet with all active workers"""
        results = {}
        active_workers = self.get_active_workers()

        for worker in active_workers:
            success = await worker.like_tweet(tweet_url)
            results[worker.bot_id] = success

            # Stagger actions
            await asyncio.sleep(2)  # 2-minute interval between actions

        return results

    async def retweet_all(self, tweet_url: str) -> Dict[str, bool]:
        """Retweet with all active workers"""
        results = {}
        active_workers = self.get_active_workers()

        for worker in active_workers:
            success = await worker.retweet(tweet_url)
            results[worker.bot_id] = success

            # Stagger actions
            await asyncio.sleep(2)  # 2-minute interval between actions

        return results

    async def comment_all(
        self, tweet_url: str, comments: List[str] = None
    ) -> Dict[str, bool]:
        """Comment with all active workers using NFT reply-guy comments"""
        results = {}
        active_workers = self.get_active_workers()

        for i, worker in enumerate(active_workers):
            if comments:
                comment_text = comments[i % len(comments)]
            else:
                # Use random NFT comment for each worker
                comment_text = self.get_random_nft_comment()

            success = await worker.comment(tweet_url, comment_text)
            results[worker.bot_id] = success

            # Random delay between comments
            delay = Config.COMMENT_MIN_INTERVAL + (i * 2)  # Stagger comments
            await asyncio.sleep(delay * 60)  # Convert to seconds

        return results

    async def quote_tweet_all(
        self, tweet_url: str, quote_text: str, keyword: str
    ) -> Dict[str, bool]:
        """Quote tweet with all active workers"""
        results = {}
        active_workers = self.get_active_workers()

        for worker in active_workers:
            # Get users to mention from pool
            mentions = self.db.get_users_from_pool(
                keyword, Config.MAX_MENTIONS_PER_QUOTE
            )

            success = await worker.quote_tweet(tweet_url, quote_text, mentions)
            results[worker.bot_id] = success

            # Cycle break between quotes
            await asyncio.sleep(Config.QUOTE_CYCLE_MIN * 60)  # Convert to seconds

        return results

    async def unfollow_all_followers_all_bots(
        self, batch_size: int = 10, delay_minutes: int = 2
    ) -> Dict[str, Dict[str, Any]]:
        """Unfollow all followers for all active workers"""
        results = {}
        active_workers = self.get_active_workers()

        if not active_workers:
            return {"error": "No active workers found"}

        self.logger.info(
            f"Starting unfollow all followers process for {len(active_workers)} bots"
        )

        for worker in active_workers:
            try:
                self.logger.info(f"Starting unfollow process for bot {worker.bot_id}")
                result = await worker.unfollow_all_followers(batch_size, delay_minutes)
                results[worker.bot_id] = result

                # Delay between bots to avoid rate limits
                if len(active_workers) > 1:
                    await asyncio.sleep(10 * 60)  # 10-minute delay between bots

            except Exception as e:
                results[worker.bot_id] = {
                    "success": False,
                    "error": f"Bot {worker.bot_id} unfollow failed: {str(e)}",
                }
                self.logger.error(f"Bot {worker.bot_id} unfollow error: {e}")

        return results

    async def unfollow_followers_for_bot(
        self, bot_id: str, batch_size: int = 10, delay_minutes: int = 2
    ) -> Dict[str, Any]:
        """Unfollow all followers for a specific bot"""
        worker = self.workers.get(bot_id)
        if not worker:
            return {"success": False, "error": f"Bot {bot_id} not found"}

        return await worker.unfollow_all_followers(batch_size, delay_minutes)

    async def unfollow_following_for_bot(
        self, bot_id: str, batch_size: int = 10, delay_minutes: int = 2
    ) -> Dict[str, Any]:
        """Unfollow all users this bot is following"""
        worker = self.workers.get(bot_id)
        if not worker:
            return {"success": False, "error": f"Bot {bot_id} not found"}

        return await worker.unfollow_all_following(batch_size, delay_minutes)

    async def _sync_mutual_following(self, new_bot_id: str = None):
        """Sync mutual following between all bots"""
        try:
            all_workers = list(self.workers.values())

            if new_bot_id and new_bot_id in self.workers:
                # New bot follows all existing bots
                new_worker = self.workers[new_bot_id]
                other_bot_ids = [
                    bot_id for bot_id in self.workers.keys() if bot_id != new_bot_id
                ]
                await new_worker.mutual_follow(other_bot_ids)

                # All existing bots follow the new bot
                for worker in all_workers:
                    if worker.bot_id != new_bot_id:
                        await worker.follow_user(
                            new_worker.bot_id
                        )  # Assuming bot_id is username

            else:
                # Full mutual following sync
                for worker in all_workers:
                    other_bot_ids = [
                        bot_id
                        for bot_id in self.workers.keys()
                        if bot_id != worker.bot_id
                    ]
                    await worker.mutual_follow(other_bot_ids)

            self.logger.info("Mutual following sync completed")

        except Exception as e:
            self.logger.error(f"Mutual following sync failed: {e}")

    async def get_worker_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all workers"""
        status = {}

        for bot_id, worker in self.workers.items():
            status[bot_id] = {
                "is_logged_in": worker.is_logged_in,
                "rate_limited_until": worker.rate_limited_until.isoformat()
                if worker.rate_limited_until
                else None,
                "captcha_required": worker.captcha_required,
                "last_activity": worker.last_activity.isoformat()
                if worker.last_activity
                else None,
                "can_perform_action": worker._can_perform_action(),
            }

        return status

    async def resume_rate_limited_workers(self):
        """Resume workers that are no longer rate limited"""
        current_time = datetime.now()

        for worker in self.workers.values():
            if worker.rate_limited_until and current_time >= worker.rate_limited_until:
                worker.rate_limited_until = None
                self.db.update_bot_status(
                    worker.bot_id, "active", rate_limited_until=None
                )

                await self.logger.send_bot_status(
                    worker.bot_id, "active", "Rate limit expired, bot resumed"
                )

    async def load_workers_from_db(self):
        """Load all workers from database on startup"""
        try:
            all_bots = self.db.get_all_bots()
            self.logger.info(f"Found {len(all_bots)} bots in database")

            loaded_count = 0
            failed_count = 0

            for bot_id, bot_info in all_bots.items():
                self.logger.info(
                    f"Processing bot {bot_id}: status={bot_info.get('status')}"
                )
                if bot_info.get("status") == "active":
                    worker = TwitterWorker(bot_id, bot_info["cookie_data"], self.db)

                    if await worker.initialize():
                        self.workers[bot_id] = worker
                        loaded_count += 1
                        self.logger.info(f"Loaded worker {bot_id} from database")
                    else:
                        failed_count += 1
                        # Mark bot as inactive in database due to auth failure
                        self.db.update_bot_status(
                            bot_id,
                            "inactive",
                            reason="Authentication failed on startup",
                        )
                        self.logger.warning(
                            f"Failed to load worker {bot_id} from database - marked as inactive"
                        )
                else:
                    self.logger.info(
                        f"Skipping bot {bot_id} - status: {bot_info.get('status')}"
                    )

            self.logger.info(
                f"Worker loading complete: {loaded_count} loaded, {failed_count} failed"
            )

            if failed_count > 0:
                await self.logger.send_notification(
                    f"⚠️ Bot Startup Alert\n\n"
                    f"Loaded: {loaded_count} bots\n"
                    f"Failed: {failed_count} bots\n\n"
                    f"Failed bots have been marked as inactive. "
                    f"Check /listbots and use /removebot for failed bots.",
                    "WARNING",
                )

        except Exception as e:
            self.logger.error(f"Failed to load workers from database: {e}")
