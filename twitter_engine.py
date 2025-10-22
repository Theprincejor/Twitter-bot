"""
Twitter search engine and engagement logic
"""

import asyncio
import re
import random
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urlparse, parse_qs
from twikit import Client
from database import Database
from logger import bot_logger
from config import Config


class TwitterSearchEngine:
    """Twitter search and keyword tracking engine"""

    def __init__(self, db: Database):
        self.db = db
        self.logger = bot_logger
        self.search_cache: Dict[str, Dict[str, Any]] = {}
        self.cache_duration = timedelta(hours=1)  # Cache search results for 1 hour
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
                    self.logger.info(f"Loaded {len(comments)} NFT comments")
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

    async def search_tweets_by_keyword(
        self, keyword: str, limit: int = None
    ) -> List[Dict[str, Any]]:
        """Search for tweets containing a keyword"""
        try:
            limit = limit or Config.TWITTER_SEARCH_LIMIT

            # Check cache first
            cache_key = f"{keyword}_{limit}"
            if cache_key in self.search_cache:
                cached_data = self.search_cache[cache_key]
                if datetime.now() - cached_data["timestamp"] < self.cache_duration:
                    self.logger.info(
                        f"Using cached search results for keyword: {keyword}"
                    )
                    return cached_data["tweets"]

            # Perform search (Note: Twikit doesn't have direct search, so we'll use a workaround)
            # This is a simplified implementation - in practice, you might need to use Twitter API v2
            tweets = await self._perform_search(keyword, limit)

            # Cache results
            self.search_cache[cache_key] = {
                "tweets": tweets,
                "timestamp": datetime.now(),
            }

            self.logger.info(f"Found {len(tweets)} tweets for keyword: {keyword}")
            return tweets

        except Exception as e:
            self.logger.error(f"Search failed for keyword {keyword}: {e}")
            return []

    async def _perform_search(self, keyword: str, limit: int) -> List[Dict[str, Any]]:
        """Perform the actual search using Twikit search_tweet"""
        try:
            # Get a client from the database (use first active bot)
            bots = self.db.get_all_data().get('bots', {})
            client = None

            for bot_id, bot_data in bots.items():
                if bot_data.get('status') == 'active':
                    from worker_manager import TwitterWorker
                    # Create a temporary worker to get authenticated client
                    worker = TwitterWorker(bot_id, bot_data.get('cookies', {}), self.db)
                    if await worker.initialize():
                        client = worker.client
                        break

            if not client:
                self.logger.error("No active bot available for search")
                return []

            # Search for latest tweets using Twikit
            # Twikit limits to 20 tweets per request, so we need to paginate
            all_tweets = []
            cursor = None

            while len(all_tweets) < limit:
                tweets_needed = min(20, limit - len(all_tweets))

                try:
                    result = await client.search_tweet(keyword, product='Latest', count=tweets_needed, cursor=cursor)

                    # Convert Twikit Tweet objects to dict format
                    for tweet in result:
                        tweet_dict = {
                            "id": tweet.id,
                            "text": tweet.text,
                            "author": {
                                "username": tweet.user.screen_name,
                                "screen_name": tweet.user.screen_name,
                                "id": tweet.user.id,
                            },
                            "created_at": tweet.created_at if hasattr(tweet, 'created_at') else datetime.now().isoformat(),
                            "url": f"https://twitter.com/{tweet.user.screen_name}/status/{tweet.id}",
                        }
                        all_tweets.append(tweet_dict)

                    # Check if there are more results
                    if hasattr(result, 'next_cursor') and result.next_cursor and len(all_tweets) < limit:
                        cursor = result.next_cursor
                    else:
                        break

                except Exception as e:
                    self.logger.error(f"Error fetching tweets batch: {e}")
                    break

            self.logger.info(f"Found {len(all_tweets)} tweets for keyword '{keyword}'")
            return all_tweets[:limit]  # Ensure we don't exceed limit

        except Exception as e:
            self.logger.error(f"Search failed: {e}")
            return []

    async def extract_users_from_tweets(
        self, tweets: List[Dict[str, Any]]
    ) -> List[str]:
        """Extract unique usernames from tweets"""
        try:
            users = set()

            for tweet in tweets:
                author = tweet.get("author", {})
                username = author.get("username") or author.get("screen_name")

                if username and not username.startswith("mock_"):  # Skip mock users
                    users.add(username)

            user_list = list(users)
            self.logger.info(f"Extracted {len(user_list)} unique users from tweets")
            return user_list

        except Exception as e:
            self.logger.error(f"Failed to extract users from tweets: {e}")
            return []

    async def build_user_pool_for_keyword(
        self, keyword: str, limit: int = None
    ) -> bool:
        """Build a user pool for a keyword by searching and extracting users"""
        try:
            # Search for tweets
            tweets = await self.search_tweets_by_keyword(keyword, limit)

            if not tweets:
                self.logger.warning(f"No tweets found for keyword: {keyword}")
                return False

            # Extract users
            users = await self.extract_users_from_tweets(tweets)

            if not users:
                self.logger.warning(f"No users extracted for keyword: {keyword}")
                return False

            # Add users to pool
            success = self.db.add_users_to_pool(keyword, users)

            if success:
                self.logger.info(f"Built user pool for '{keyword}': {len(users)} users")
                await self.logger.send_notification(
                    f"🔍 User pool built for keyword {keyword}\n👥 Found {len(users)} users",
                    send_telegram=True,
                )

            return success

        except Exception as e:
            self.logger.error(f"Failed to build user pool for {keyword}: {e}")
            return False

    def get_user_pool_status(self, keyword: str) -> Dict[str, Any]:
        """Get status of user pool for a keyword"""
        try:
            data = self.db._read_data()
            pool = data.get("users_pool", {}).get(keyword, {})

            return {
                "keyword": keyword,
                "available_users": len(pool.get("users", [])),
                "used_users": len(pool.get("used_users", [])),
                "total_users": len(pool.get("users", []))
                + len(pool.get("used_users", [])),
                "created_at": pool.get("created_at"),
                "is_empty": len(pool.get("users", [])) == 0,
            }

        except Exception as e:
            self.logger.error(f"Failed to get user pool status for {keyword}: {e}")
            return {}

    def refresh_user_pool(self, keyword: str, limit: int = None) -> bool:
        """Refresh user pool by searching for new users"""
        try:
            # Clear existing pool
            data = self.db._read_data()
            if keyword in data.get("users_pool", {}):
                data["users_pool"][keyword] = {
                    "users": [],
                    "used_users": [],
                    "created_at": datetime.now().isoformat(),
                }
                self.db._write_data(data)

            # Build new pool
            return asyncio.create_task(self.build_user_pool_for_keyword(keyword, limit))

        except Exception as e:
            self.logger.error(f"Failed to refresh user pool for {keyword}: {e}")
            return False


class TwitterEngagementEngine:
    """Main engagement engine for Twitter actions"""

    def __init__(self, db: Database, search_engine: TwitterSearchEngine):
        self.db = db
        self.search_engine = search_engine
        self.logger = bot_logger

        # Engagement statistics
        self.stats = {
            "total_engagements": 0,
            "successful_engagements": 0,
            "failed_engagements": 0,
            "last_engagement": None,
        }

    async def engage_with_post(
        self, post_url: str, actions: List[str] = None
    ) -> Dict[str, Any]:
        """Engage with a specific post"""
        try:
            if not actions:
                actions = ["like", "comment", "retweet"]

            # Validate URL
            if not self._validate_twitter_url(post_url):
                raise ValueError("Invalid Twitter URL")

            results = {
                "url": post_url,
                "actions": {},
                "success": False,
                "timestamp": datetime.now().isoformat(),
            }

            # Perform each action
            for action in actions:
                if action == "like":
                    results["actions"]["like"] = await self._like_post(post_url)
                elif action == "comment":
                    results["actions"]["comment"] = await self._comment_post(post_url)
                elif action == "retweet":
                    results["actions"]["retweet"] = await self._retweet_post(post_url)
                elif action == "quote":
                    results["actions"]["quote"] = await self._quote_post(post_url)

            # Calculate overall success
            successful_actions = sum(
                1 for success in results["actions"].values() if success
            )
            results["success"] = successful_actions > 0

            # Update statistics
            self.stats["total_engagements"] += 1
            if results["success"]:
                self.stats["successful_engagements"] += 1
            else:
                self.stats["failed_engagements"] += 1
            self.stats["last_engagement"] = datetime.now()

            self.logger.info(
                f"Post engagement completed: {successful_actions}/{len(actions)} actions successful"
            )
            return results

        except Exception as e:
            self.logger.error(f"Failed to engage with post {post_url}: {e}")
            return {
                "url": post_url,
                "error": str(e),
                "success": False,
                "timestamp": datetime.now().isoformat(),
            }

    async def engage_with_keyword(
        self, keyword: str, quote_text: str, mention_count: int = 3
    ) -> Dict[str, Any]:
        """Engage with tweets containing a keyword"""
        try:
            # Build user pool if needed
            pool_status = self.search_engine.get_user_pool_status(keyword)
            if pool_status.get("is_empty", True):
                await self.search_engine.build_user_pool_for_keyword(keyword)

            # Search for recent tweets
            tweets = await self.search_engine.search_tweets_by_keyword(keyword)

            if not tweets:
                return {
                    "keyword": keyword,
                    "success": False,
                    "error": "No tweets found",
                    "timestamp": datetime.now().isoformat(),
                }

            results = {
                "keyword": keyword,
                "tweets_processed": 0,
                "successful_quotes": 0,
                "mentions_used": 0,
                "timestamp": datetime.now().isoformat(),
            }

            # Process tweets (limit to avoid rate limits)
            for tweet in tweets[:5]:  # Process max 5 tweets
                tweet_url = tweet.get("url")
                if not tweet_url:
                    continue

                # Get users to mention
                mentions = self.db.get_users_from_pool(keyword, mention_count)

                # Quote the tweet with mentions
                success = await self._quote_post(tweet_url, quote_text, mentions)

                results["tweets_processed"] += 1
                if success:
                    results["successful_quotes"] += 1
                    results["mentions_used"] += len(mentions)

                # Wait between quotes to avoid rate limits
                await asyncio.sleep(30)

            results["success"] = results["successful_quotes"] > 0

            self.logger.info(
                f"Keyword engagement completed: {results['successful_quotes']}/{results['tweets_processed']} quotes successful"
            )
            return results

        except Exception as e:
            self.logger.error(f"Failed to engage with keyword {keyword}: {e}")
            return {
                "keyword": keyword,
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    def _validate_twitter_url(self, url: str) -> bool:
        """Validate if URL is a valid Twitter/X URL"""
        try:
            parsed = urlparse(url)
            return parsed.netloc in [
                "twitter.com",
                "x.com",
                "www.twitter.com",
                "www.x.com",
            ]
        except Exception:
            return False

    def _extract_tweet_id(self, url: str) -> Optional[str]:
        """Extract tweet ID from URL"""
        try:
            # Handle various URL formats
            if "/status/" in url:
                return url.split("/status/")[-1].split("?")[0]
            return None
        except Exception:
            return None

    async def _like_post(self, post_url: str) -> bool:
        """Like a post (placeholder - would integrate with worker manager)"""
        # This would integrate with the worker manager and scheduler
        # For now, return a placeholder
        self.logger.info(f"Would like post: {post_url}")
        return True

    async def _comment_post(self, post_url: str, comment_text: str = None) -> bool:
        """Comment on a post with NFT reply-guy style"""
        # Use NFT comment if no specific comment provided
        if not comment_text:
            comment = self.get_random_nft_comment()
        else:
            comment = comment_text

        self.logger.info(f"Would comment '{comment}' on post: {post_url}")
        return True

    async def _retweet_post(self, post_url: str) -> bool:
        """Retweet a post (placeholder - would integrate with worker manager)"""
        # This would integrate with the worker manager and scheduler
        # For now, return a placeholder
        self.logger.info(f"Would retweet post: {post_url}")
        return True

    async def _quote_post(
        self, post_url: str, quote_text: str, mentions: List[str] = None
    ) -> bool:
        """Quote a post with mentions (placeholder - would integrate with worker manager)"""
        # This would integrate with the worker manager and scheduler
        # For now, return a placeholder
        mention_text = ""
        if mentions:
            mention_text = f" Mentioning: {', '.join(mentions)}"

        self.logger.info(f"Would quote post '{quote_text}'{mention_text}: {post_url}")
        return True

    def get_engagement_stats(self) -> Dict[str, Any]:
        """Get engagement statistics"""
        db_stats = self.db.get_statistics()

        # Calculate total actions, filtering out None values
        total_actions = 0
        if isinstance(db_stats, dict):
            total_actions = sum(
                v for v in db_stats.values() 
                if isinstance(v, (int, float)) and v is not None
            )

        return {
            "engine_stats": self.stats,
            "database_stats": db_stats,
            "total_actions": total_actions,
        }

    async def cleanup_old_data(self, days: int = 7):
        """Clean up old engagement data"""
        try:
            # This would clean up old logs, cache, etc.
            self.logger.info(f"Cleaning up data older than {days} days")

            # Clear old search cache
            cutoff_time = datetime.now() - timedelta(days=days)
            old_keys = []

            for key, data in self.search_engine.search_cache.items():
                if data["timestamp"] < cutoff_time:
                    old_keys.append(key)

            for key in old_keys:
                del self.search_engine.search_cache[key]

            self.logger.info(f"Cleaned up {len(old_keys)} old cache entries")

        except Exception as e:
            self.logger.error(f"Failed to cleanup old data: {e}")
