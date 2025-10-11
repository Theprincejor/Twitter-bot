"""
Main Telegram bot command center
"""

import asyncio
import json
import os
import shutil
from datetime import datetime
from typing import Dict, Any, List, Optional
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from telegram.error import TelegramError

from config import Config
from database import Database
from worker_manager import WorkerManager, TwitterWorker
from scheduler import TaskScheduler, TaskType
from twitter_engine import TwitterSearchEngine, TwitterEngagementEngine
from logger import bot_logger


class TwitterBotTelegram:
    """Main Telegram bot for Twitter automation system"""

    def __init__(self):
        self.config = Config
        self.db = Database()
        self.worker_manager = WorkerManager(self.db)
        self.scheduler = TaskScheduler(self.worker_manager, self.db)
        self.search_engine = TwitterSearchEngine(self.db)
        self.engagement_engine = TwitterEngagementEngine(self.db, self.search_engine)
        self.logger = bot_logger

        # Telegram bot setup
        self.application = (
            Application.builder().token(self.config.TELEGRAM_TOKEN).build()
        )
        self.setup_handlers()

        # System status
        self.is_running = False

    def setup_handlers(self):
        """Setup Telegram command handlers"""

        # Command handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(CommandHandler("logs", self.logs_command))

        # Bot management commands
        self.application.add_handler(CommandHandler("addbot", self.addbot_command))
        self.application.add_handler(
            CommandHandler("addbotjson", self.addbotjson_command)
        )
        self.application.add_handler(
            CommandHandler("addbotlogin", self.addbotlogin_command)
        )
        self.application.add_handler(
            CommandHandler("removebot", self.removebot_command)
        )
        self.application.add_handler(CommandHandler("listbots", self.listbots_command))
        self.application.add_handler(
            CommandHandler("syncfollows", self.syncfollows_command)
        )

        # Engagement commands
        self.application.add_handler(CommandHandler("post", self.post_command))
        self.application.add_handler(CommandHandler("quote", self.quote_command))
        self.application.add_handler(CommandHandler("like", self.like_command))
        self.application.add_handler(CommandHandler("retweet", self.retweet_command))
        self.application.add_handler(CommandHandler("comment", self.comment_command))
        self.application.add_handler(CommandHandler("unfollow", self.unfollow_command))

        # Search and pool management
        self.application.add_handler(CommandHandler("search", self.search_command))
        self.application.add_handler(CommandHandler("pool", self.pool_command))
        self.application.add_handler(CommandHandler("refresh", self.refresh_command))

        # System commands
        self.application.add_handler(CommandHandler("stats", self.stats_command))
        self.application.add_handler(CommandHandler("queue", self.queue_command))
        self.application.add_handler(CommandHandler("backup", self.backup_command))
        self.application.add_handler(CommandHandler("test", self.test_command))
        self.application.add_handler(CommandHandler("reinit", self.reinit_command))
        self.application.add_handler(CommandHandler("version", self.version_command))
        self.application.add_handler(
            CommandHandler("testlogin", self.testlogin_command)
        )
        self.application.add_handler(
            CommandHandler("reactivate", self.reactivate_command)
        )
        self.application.add_handler(
            CommandHandler("checkduplicates", self.checkduplicates_command)
        )
        self.application.add_handler(CommandHandler("cleanup", self.cleanup_command))

        # Bot management commands
        self.application.add_handler(CommandHandler("disable", self.disable_command))
        self.application.add_handler(CommandHandler("enable", self.enable_command))
        self.application.add_handler(CommandHandler("delete", self.delete_command))
        self.application.add_handler(
            CommandHandler("savecookies", self.savecookies_command)
        )

        # File upload handler for cookie files
        self.application.add_handler(
            MessageHandler(
                filters.Document.MimeType("application/json"), self.handle_cookie_upload
            )
        )

        # Text message handler for deletion confirmation
        self.application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND, self.handle_deletion_confirmation
            )
        )

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text(" Access denied. You are not an admin.")
            return

        welcome_text = """
Twitter Bot System

Welcome to your Twitter automation command center!

Available Commands:
• `/help` - Show all commands
• `/addbot <cookie_file>` - Add new worker bot
• `/post <url>` - Engage with post (like, comment, retweet)
• `/quote <keyword> "<message>"` - Quote tweets with mentions
• `/status` - Show system status
• `/logs` - View recent logs
• `/test` - Test bot authentication and functionality
• `/reinit` - Reinitialize bot authentication
• `/version` - Check Twikit version and capabilities
• `/testlogin` - Test if login is blocked by Cloudflare
• `/reactivate` - Reactivate inactive bots
• `/checkduplicates` - Check for duplicate auth tokens
• `/cleanup` - Remove inactive/failed bots
• `/savecookies` - Save all bot cookies to files

🔧Bot Management:
• `/listbots` - List all worker bots
• `/syncfollows` - Sync mutual following
• `/removebot <bot_id>` - Remove worker bot

Monitoring:
• `/stats` - Show statistics
• `/queue` - Show task queue status
• `/pool <keyword>` - Show user pool status

Type `/help` for detailed command information.
        """

        await update.message.reply_text(welcome_text)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text(" Access denied. You are not an admin.")
            return

        help_text = """
📖 Twitter Bot Commands Reference

Bot Management:
• `/addbot <cookie_file>` - Add new worker bot from uploaded cookie file
• `/addbotjson <json_data>` - Add bot directly with JSON cookie data
• `/addbotlogin <username> <password> [email]` - Add bot via username/password login
• `/removebot <bot_id>` - Remove worker bot
• `/disable <bot_id>` - Disable a bot (mark as inactive)
• `/enable <bot_id>` - Enable a disabled bot
• `/delete <bot_id>` - Permanently delete a bot
• `/listbots` - List all worker bots and their status
• `/syncfollows` - Sync mutual following between all bots

🎯 Engagement Commands:
• `/post <url>` - Like, comment, and retweet a specific post
• `/like <url>` - Like a specific post
• `/retweet <url>` - Retweet a specific post
• `/comment <url> "<text>"` - Comment on a specific post
• `/quote <keyword> "<message>"` - Quote tweets containing keyword with mentions
• `/unfollow <bot_id>` - Unfollow all followers for a specific bot
• `/unfollow all` - Unfollow all followers for all bots

Search & Pools:
• `/search <keyword>` - Search for tweets with keyword
• `/pool <keyword>` - Show user pool status for keyword
• `/refresh <keyword>` - Refresh user pool for keyword

Monitoring:
• `/status` - Show system status and bot health
• `/stats` - Show engagement statistics
• `/queue` - Show task queue status
• `/logs` - View recent system logs
• `/backup` - Create database backup

💡 Tips:
• Upload cookie files as JSON documents
• Use quotes around messages with spaces
• Check `/status` regularly for bot health
• Monitor `/logs` for errors and notifications
        """

        await update.message.reply_text(help_text)

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text(" Access denied. You are not an admin.")
            return

        try:
            # Get worker status
            worker_status = await self.worker_manager.get_worker_status()

            # Get queue status
            queue_status = await self.scheduler.get_queue_status()

            # Get statistics
            stats = self.engagement_engine.get_engagement_stats()

            status_text = f"""System Status

Workers: {len(worker_status)} bots
Queue: {queue_status["pending_tasks"]} pending, {queue_status["in_progress_tasks"]} in progress
Total Actions: {stats.get("total_actions", 0)}

Bot Status:
"""

            for bot_id, status in worker_status.items():
                status_indicator = "✓" if status["can_perform_action"] else "✗"
                rate_limit = ""
                if status["rate_limited_until"]:
                    rate_limit = " (Rate Limited)"
                elif status["captcha_required"]:
                    rate_limit = " (Captcha Required)"

                status_text += f"{status_indicator} {bot_id}{rate_limit}\n"

            status_text += (
                f"\nLast Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )

            await update.message.reply_text(status_text)

        except Exception as e:
            await update.message.reply_text(f" Error getting status: {str(e)}")

    async def addbot_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /addbot command"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text(" Access denied. You are not an admin.")
            return

        if not context.args:
            await update.message.reply_text(
                " Please provide a cookie file name.\n"
                "Usage: `/addbot cookie.json`\n"
                "Upload the cookie file first, then use this command with the filename."
            )
            return

        cookie_filename = context.args[0]
        cookie_path = os.path.join(Config.COOKIES_PATH, cookie_filename)

        if not os.path.exists(cookie_path):
            await update.message.reply_text(
                f" Cookie file not found: {cookie_filename}"
            )
            return

        try:
            # Load cookie data
            with open(cookie_path, "r") as f:
                cookie_data = json.load(f)

            # Ensure cookies are processed (in case file wasn't processed during upload)
            processed_cookies = self._process_raw_cookies(cookie_data)
            if not processed_cookies:
                await update.message.reply_text(
                    f" Failed to process cookie file: {cookie_filename}"
                )
                return

            # Generate bot ID
            bot_id = f"bot_{len(self.worker_manager.get_all_workers()) + 1}"

            # Add worker with processed cookies
            success = await self.worker_manager.add_worker(bot_id, processed_cookies)

            if success:
                await update.message.reply_text(f" Bot {bot_id} added successfully!")

                # Schedule mutual following sync
                await self.scheduler.add_task(
                    TaskType.SYNC_FOLLOWS, {"new_bot_id": bot_id}, priority=2
                )
            else:
                await update.message.reply_text(f" Failed to add bot {bot_id}")

        except Exception as e:
            await update.message.reply_text(f" Error adding bot: {str(e)}")

    async def addbotjson_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /addbotjson command - add bot directly with JSON data"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("Access denied. You are not an admin.")
            return

        if not context.args:
            await update.message.reply_text(
                "Please provide JSON cookie data.\n"
                "Usage: `/addbotjson [your_cookie_json_array]`\n\n"
                "Note: For large JSON data, use file upload instead:\n"
                "1. Save your cookies as a .json file\n"
                "2. Upload the file to this bot\n"
                "3. Use `/addbot filename.json`\n\n"
                "Example:\n"
                '`/addbotjson [{"name":"auth_token","value":"..."},{"name":"ct0","value":"..."}]`'
            )
            return

        try:
            # Join all arguments to reconstruct the JSON
            json_text = " ".join(context.args)

            # Parse the JSON
            raw_cookie_data = json.loads(json_text)

            # Process cookies
            processed_cookies = self._process_raw_cookies(raw_cookie_data)
            if not processed_cookies:
                await update.message.reply_text("Failed to process cookie data")
                return

            # Enhanced validation with token mismatch detection
            from cookie_processor import CookieProcessor

            validation = CookieProcessor.validate_cookies(processed_cookies)

            if not validation["valid"]:
                error_message = "❌ Invalid cookie data!\n\n"

                if validation["missing"]:
                    error_message += f"Missing required cookies: {', '.join(validation['missing'])}\n\n"

                if validation["errors"]:
                    error_message += f"Critical errors:\n"
                    for error in validation["errors"]:
                        error_message += f"• {error}\n"
                    error_message += "\n"

                if validation["warnings"]:
                    error_message += "Warnings:\n"
                    for warning in validation["warnings"]:
                        error_message += f"• {warning}\n"

                await update.message.reply_text(error_message)
                return

            # Check for duplicate cookies (same auth_token)
            if "auth_token" in processed_cookies:
                auth_token = processed_cookies["auth_token"]
                existing_bots = self.db.get_all_bots()

                for bot_id, bot_info in existing_bots.items():
                    existing_cookies = bot_info.get("cookie_data", {})
                    if existing_cookies.get("auth_token") == auth_token:
                        await update.message.reply_text(
                            f"❌ Duplicate cookie data detected!\n\n"
                            f"This auth_token is already used by bot: `{bot_id}`\n\n"
                            f"Each bot must have unique authentication cookies.\n"
                            f"Please export fresh cookies from a different account or remove the existing bot first."
                        )
                        return

            # Generate bot ID
            bot_id = f"bot_{len(self.worker_manager.get_all_workers()) + 1}"

            # Add worker
            success = await self.worker_manager.add_worker(bot_id, processed_cookies)

            if success:
                cookie_count = len(processed_cookies)
                await update.message.reply_text(
                    f"Bot {bot_id} added successfully!\n"
                    f"Cookies processed: {cookie_count}\n"
                    f"Required cookies: ✅\n"
                    f"Bot is now active and ready to use!"
                )

                # Schedule mutual following sync
                await self.scheduler.add_task(
                    TaskType.SYNC_FOLLOWS, {"new_bot_id": bot_id}, priority=2
                )
            else:
                await update.message.reply_text(f"Failed to add bot {bot_id}")

        except json.JSONDecodeError:
            await update.message.reply_text(
                "Invalid JSON format. Please check your cookie data.\n\n"
                "For large JSON data, try this instead:\n"
                "1. Save your cookies as a .json file\n"
                "2. Upload the file to this bot\n"
                "3. Use `/addbot filename.json`"
            )
        except Exception as e:
            await update.message.reply_text(f"Error adding bot: {str(e)}")

    async def handle_cookie_upload(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle cookie file uploads"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text(" Access denied. You are not an admin.")
            return

        try:
            # Get file info
            file = await context.bot.get_file(update.message.document.file_id)

            # Create cookies directory
            os.makedirs(Config.COOKIES_PATH, exist_ok=True)

            # Download file
            filename = update.message.document.file_name
            file_path = os.path.join(Config.COOKIES_PATH, filename)

            await file.download_to_drive(file_path)

            # Load and process JSON
            with open(file_path, "r") as f:
                raw_cookie_data = json.load(f)

            # Process cookies (handles both raw browser export and processed format)
            processed_cookies = self._process_raw_cookies(raw_cookie_data)

            # Enhanced validation with token mismatch detection
            from cookie_processor import CookieProcessor

            validation = CookieProcessor.validate_cookies(processed_cookies)

            if not validation["valid"]:
                os.remove(file_path)

                error_message = "❌ Invalid cookie file!\n\n"

                if validation["missing"]:
                    error_message += f"Missing required cookies: {', '.join(validation['missing'])}\n\n"

                if validation["errors"]:
                    error_message += f"Critical errors:\n"
                    for error in validation["errors"]:
                        error_message += f"• {error}\n"
                    error_message += "\n"

                if validation["warnings"]:
                    error_message += "Warnings:\n"
                    for warning in validation["warnings"]:
                        error_message += f"• {warning}\n"

                await update.message.reply_text(error_message)
                return

            # Check for duplicate cookies (same auth_token)
            if "auth_token" in processed_cookies:
                auth_token = processed_cookies["auth_token"]
                existing_bots = self.db.get_all_bots()

                for bot_id, bot_info in existing_bots.items():
                    existing_cookies = bot_info.get("cookie_data", {})
                    if existing_cookies.get("auth_token") == auth_token:
                        os.remove(file_path)
                        await update.message.reply_text(
                            f"❌ Duplicate cookie file detected!\n\n"
                            f"This auth_token is already used by bot: `{bot_id}`\n\n"
                            f"Each bot must have unique authentication cookies.\n"
                            f"Please export fresh cookies from a different account or remove the existing bot first."
                        )
                        return

            # Save processed cookies back to file
            with open(file_path, "w") as f:
                json.dump(processed_cookies, f, indent=2)

            # Prepare success message with validation results
            cookie_count = len(processed_cookies)
            success_message = f"✅ Cookie file processed successfully!\n\n"
            success_message += f"Cookies Found: {cookie_count}\n"
            success_message += (
                f"Required: {len(validation['present'])}/{len(['auth_token', 'ct0'])}\n"
            )

            if validation["warnings"]:
                success_message += f"\n⚠️ Warnings:\n"
                for warning in validation["warnings"]:
                    success_message += f"• {warning}\n"

            success_message += (
                f"\nUse `/addbot {filename}` to add this bot to the system."
            )

            await update.message.reply_text(success_message)

        except Exception as e:
            await update.message.reply_text(f" Error uploading cookie file: {str(e)}")

    async def post_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /post command"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text(" Access denied. You are not an admin.")
            return

        if not context.args:
            await update.message.reply_text(
                " Please provide a Twitter URL.\n"
                "Usage: `/post https://twitter.com/user/status/123456789`",
            )
            return

        url = context.args[0]

        try:
            # Add engagement tasks
            tasks_added = []

            # Like task
            task_id = await self.scheduler.add_task(TaskType.LIKE, {"tweet_url": url})
            tasks_added.append(f"Like: {task_id}")

            # Comment task (with delay)
            task_id = await self.scheduler.add_task(
                TaskType.COMMENT,
                {
                    "tweet_url": url,
                    "comments": ["Nice post! 👍", "Great content! ", "Amazing! ✨"],
                },
                delay_minutes=5,
            )
            tasks_added.append(f"Comment: {task_id}")

            # Retweet task (with delay)
            task_id = await self.scheduler.add_task(
                TaskType.RETWEET, {"tweet_url": url}, delay_minutes=10
            )
            tasks_added.append(f"Retweet: {task_id}")

            await update.message.reply_text(
                f" Post engagement scheduled!\n\n"
                f"📝 Tasks Added:\n" + "\n".join(tasks_added) + "\n\n"
                f"🔗 URL: {url}"
            )

        except Exception as e:
            await update.message.reply_text(
                f" Error scheduling post engagement: {str(e)}"
            )

    async def quote_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /quote command"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text(" Access denied. You are not an admin.")
            return

        if len(context.args) < 2:
            await update.message.reply_text(
                "Please provide keyword and message.\n"
                'Usage: `/quote keyword "message text"`',
            )
            return

        keyword = context.args[0]
        message = " ".join(context.args[1:])

        # Remove quotes if present
        if message.startswith('"') and message.endswith('"'):
            message = message[1:-1]

        try:
            # Build user pool first
            await update.message.reply_text(
                f" Building user pool for keyword: {keyword}"
            )

            pool_built = await self.search_engine.build_user_pool_for_keyword(keyword)

            if not pool_built:
                await update.message.reply_text(
                    f" Failed to build user pool for keyword: {keyword}"
                )
                return

            # Add quote task
            task_id = await self.scheduler.add_task(
                TaskType.QUOTE,
                {
                    "keyword": keyword,
                    "quote_text": message,
                    "mention_count": Config.MAX_MENTIONS_PER_QUOTE,
                },
            )

            await update.message.reply_text(
                f" Quote campaign scheduled!\n\n"
                f"Keyword: {keyword}\n"
                f"💬 Message: {message}\n"
                f"Task ID: {task_id}"
            )

        except Exception as e:
            await update.message.reply_text(
                f" Error scheduling quote campaign: {str(e)}"
            )

    async def listbots_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /listbots command"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text(" Access denied. You are not an admin.")
            return

        try:
            workers = self.worker_manager.get_all_workers()
            worker_status = await self.worker_manager.get_worker_status()

            if not workers:
                await update.message.reply_text(
                    "📭 No bots configured yet.\nUse `/addbot` to add your first bot."
                )
                return

            text = "Configured Bots:\n\n"

            for bot_id, worker in workers.items():
                status = worker_status.get(bot_id, {})
                emoji = "" if status.get("can_perform_action") else ""

                text += f"{emoji} {bot_id}\n"
                text += f"   Status: {status.get('status', 'unknown')}\n"

                if status.get("rate_limited_until"):
                    text += f"   Rate Limited Until: {status['rate_limited_until']}\n"

                if status.get("captcha_required"):
                    text += f"    Captcha Required\n"

                text += "\n"

            await update.message.reply_text(
                text,
            )

        except Exception as e:
            await update.message.reply_text(f" Error listing bots: {str(e)}")

    async def logs_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /logs command"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text(" Access denied. You are not an admin.")
            return

        try:
            lines = 20
            if context.args:
                try:
                    lines = int(context.args[0])
                    lines = min(lines, 50)  # Max 50 lines
                except ValueError:
                    pass

            logs = self.logger.get_recent_logs(lines)

            if not logs or logs.strip() == "":
                await update.message.reply_text("📭 No logs available.")
                return

            # Split long messages
            if len(logs) > 4000:
                logs = logs[-4000:]  # Take last 4000 characters

            await update.message.reply_text(
                f"Recent Logs:\n\n```\n{logs}\n```",
            )

        except Exception as e:
            await update.message.reply_text(f" Error getting logs: {str(e)}")

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text(" Access denied. You are not an admin.")
            return

        try:
            stats = self.engagement_engine.get_engagement_stats()
            db_stats = stats.get("database_stats", {})

            text = "Engagement Statistics\n\n"

            if isinstance(db_stats, dict):
                text += f"👍 Likes: {db_stats.get('total_likes', 0)}\n"
                text += f"💬 Comments: {db_stats.get('total_comments', 0)}\n"
                text += f"🔄 Retweets: {db_stats.get('total_retweets', 0)}\n"
                text += f"💭 Quotes: {db_stats.get('total_quotes', 0)}\n"

            text += (
                f"\nActive Workers: {len(self.worker_manager.get_active_workers())}\n"
            )
            text += f"📅 Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

            await update.message.reply_text(
                text,
            )

        except Exception as e:
            await update.message.reply_text(f" Error getting statistics: {str(e)}")

    async def queue_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /queue command"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text(" Access denied. You are not an admin.")
            return

        try:
            queue_status = await self.scheduler.get_queue_status()

            text = "🔄 Task Queue Status\n\n"
            text += f"Queue Size: {queue_status['queue_size']}\n"
            text += f"⏳ Pending: {queue_status['pending_tasks']}\n"
            text += f"🔄 In Progress: {queue_status['in_progress_tasks']}\n"
            text += f"Completed: {queue_status['completed_tasks']}\n"
            text += f"Failed: {queue_status['failed_tasks']}\n"
            text += f"Total Active: {queue_status['active_tasks']}"

            await update.message.reply_text(
                text,
            )

        except Exception as e:
            await update.message.reply_text(f" Error getting queue status: {str(e)}")

    async def addbotlogin_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /addbotlogin command for username/password login"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("Access denied. You are not an admin.")
            return

        if not context.args or len(context.args) < 2:
            await update.message.reply_text(
                "Please provide username and password.\n"
                "Usage: `/addbotlogin <username> <password> [email]`\n\n"
                "Example:\n"
                "`/addbotlogin myusername mypassword123`\n"
                "`/addbotlogin myusername mypassword123 email@example.com`\n\n"
                "Note: This will automatically save cookies after successful login."
            )
            return

        username = context.args[0]
        password = context.args[1]
        email = context.args[2] if len(context.args) > 2 else None

        try:
            await update.message.reply_text(
                f"Attempting to login with username: {username}\n"
                "This may take a few moments...\n"
                "Note: If login fails, your Twikit version might not support the cookies_file parameter."
            )

            # Generate bot ID
            bot_id = f"bot_{len(self.worker_manager.get_all_workers()) + 1}"

            # Create cookie file path
            cookie_file_path = os.path.join(
                Config.COOKIES_PATH, f"{bot_id}_cookies.json"
            )
            os.makedirs(os.path.dirname(cookie_file_path), exist_ok=True)

            # Create a temporary client for login with anti-detection measures
            from twikit import Client
            import httpx

            # Work around the proxy parameter issue in newer Twikit versions
            try:
                temp_client = Client(language="en-US")
            except TypeError as e:
                if "proxy" in str(e):
                    # Patch the httpx AsyncClient to ignore proxy parameter
                    original_init = httpx.AsyncClient.__init__

                    def patched_init(self, *args, **kwargs):
                        kwargs.pop("proxy", None)
                        return original_init(self, *args, **kwargs)

                    httpx.AsyncClient.__init__ = patched_init
                    temp_client = Client(language="en-US")
                else:
                    raise e

            # Add delay to appear more human-like
            import asyncio
            import random

            await asyncio.sleep(random.uniform(2, 5))

            # Attempt login with username/password
            login_result = await temp_client.login(
                auth_info_1=username,
                auth_info_2=email,  # Optional email
                password=password,
                cookies_file=cookie_file_path,  # Auto-save cookies to file
            )

            # Check if login was successful
            if login_result:
                # Get cookies from the logged-in client
                cookies = temp_client.get_cookies()

                if not cookies or not cookies.get("auth_token"):
                    await update.message.reply_text(
                        f"Login failed: No valid cookies received\n"
                        "Please check your credentials and try again."
                    )
                    return

                # Add bot to database
                success = self.db.add_bot(bot_id, cookies)

                if success:
                    # Initialize worker
                    worker_success = await self.worker_manager.add_bot(bot_id, cookies)

                    if worker_success:
                        await update.message.reply_text(
                            f"Bot {bot_id} added successfully via login!\n"
                            f"Username: {username}\n"
                            f"Cookies saved to: {cookie_file_path}\n"
                            f"Bot is now active and ready to use!"
                        )

                        # Schedule mutual following sync
                        await self.scheduler.add_task(
                            TaskType.SYNC_FOLLOWS, {"new_bot_id": bot_id}, priority=2
                        )
                    else:
                        await update.message.reply_text(
                            f"Bot {bot_id} added to database but failed to initialize.\n"
                            "Check logs for details."
                        )
                else:
                    await update.message.reply_text(
                        f"Failed to add bot {bot_id} to database"
                    )
            else:
                await update.message.reply_text(
                    f"Login failed for username: {username}\n"
                    "Please check your credentials and try again."
                )

        except Exception as e:
            error_msg = str(e)
            # Truncate long error messages for Telegram
            if len(error_msg) > 1000:
                error_msg = error_msg[:1000] + "..."

            # Check for specific error types
            if (
                "403" in error_msg
                or "Cloudflare" in error_msg
                or "blocked" in error_msg
            ):
                await update.message.reply_text(
                    "Login blocked by Cloudflare protection.\n"
                    "This is common with automated login attempts.\n"
                    "Try using the cookie upload method instead:\n"
                    "1. Export cookies from your browser\n"
                    "2. Use /addbot or /addbotjson commands"
                )
            elif "cookies_file" in error_msg:
                await update.message.reply_text(
                    "Your Twikit version doesn't support automatic cookie saving.\n"
                    "Login successful but cookies not saved to file.\n"
                    "Use /savecookies to save cookies manually."
                )
            else:
                await update.message.reply_text(
                    f"Login error: {error_msg}\n"
                    "Please check your credentials and try again."
                )

    async def savecookies_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /savecookies command to save bot cookies to files"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("Access denied. You are not an admin.")
            return

        try:
            workers = self.worker_manager.get_all_workers()
            if not workers:
                await update.message.reply_text("No bots found to save cookies for.")
                return

            saved_count = 0
            for bot_id, worker in workers.items():
                try:
                    # Get cookies from the worker's client
                    cookies = worker.client.get_cookies()

                    # Create cookie file path
                    cookie_file_path = os.path.join(
                        Config.COOKIES_PATH, f"{bot_id}_cookies.json"
                    )
                    os.makedirs(os.path.dirname(cookie_file_path), exist_ok=True)

                    # Save cookies to file using Twikit's method
                    worker.client.save_cookies(cookie_file_path)
                    saved_count += 1

                except Exception as e:
                    self.logger.error(f"Failed to save cookies for bot {bot_id}: {e}")

            await update.message.reply_text(
                f"Cookies saved for {saved_count}/{len(workers)} bots to {Config.COOKIES_PATH}"
            )

        except Exception as e:
            await update.message.reply_text(f"Error saving cookies: {str(e)}")

    async def version_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /version command to check Twikit version"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("Access denied. You are not an admin.")
            return

        try:
            import twikit

            version_info = f"Twikit Version: {twikit.__version__}\n"

            # Check if cookies_file parameter is supported
            import inspect

            login_signature = inspect.signature(twikit.Client.login)
            cookies_file_supported = "cookies_file" in login_signature.parameters

            # Check if user_agent parameter is supported in Client.__init__
            client_signature = inspect.signature(twikit.Client.__init__)
            user_agent_supported = "user_agent" in client_signature.parameters

            version_info += (
                f"Cookies File Support: {'Yes' if cookies_file_supported else 'No'}\n"
            )
            version_info += (
                f"User Agent Support: {'Yes' if user_agent_supported else 'No'}\n"
            )
            version_info += (
                f"Login Parameters: {list(login_signature.parameters.keys())}\n"
            )
            version_info += (
                f"Client Init Parameters: {list(client_signature.parameters.keys())}"
            )

            await update.message.reply_text(version_info)

        except Exception as e:
            await update.message.reply_text(f"Error checking version: {str(e)}")

    async def testlogin_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /testlogin command to test if login is blocked"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("Access denied. You are not an admin.")
            return

        try:
            await update.message.reply_text("Testing login connectivity...")

            from twikit import Client
            import httpx

            # Work around the proxy parameter issue in newer Twikit versions
            try:
                temp_client = Client(language="en-US")
            except TypeError as e:
                if "proxy" in str(e):
                    # Patch the httpx AsyncClient to ignore proxy parameter
                    original_init = httpx.AsyncClient.__init__

                    def patched_init(self, *args, **kwargs):
                        kwargs.pop("proxy", None)
                        return original_init(self, *args, **kwargs)

                    httpx.AsyncClient.__init__ = patched_init
                    temp_client = Client(language="en-US")
                else:
                    raise e

            # Try a simple request to test connectivity
            import asyncio

            await asyncio.sleep(2)

            # This will fail but we can see what type of error we get
            try:
                await temp_client.login(
                    auth_info_1="test_user",
                    auth_info_2="test@example.com",
                    password="test_password",
                )
            except Exception as e:
                error_msg = str(e)
                if (
                    "403" in error_msg
                    or "Cloudflare" in error_msg
                    or "blocked" in error_msg
                ):
                    await update.message.reply_text(
                        "❌ Login is BLOCKED by Cloudflare\n"
                        "Recommendation: Use cookie upload method instead\n"
                        "Commands: /addbot or /addbotjson"
                    )
                elif "cookies_file" in error_msg:
                    await update.message.reply_text(
                        "⚠️ Twikit version issue detected\n"
                        "Your version doesn't support cookies_file parameter\n"
                        "Use /version to check details"
                    )
                else:
                    await update.message.reply_text(
                        f"✅ Login connectivity OK\n"
                        f"Error type: {type(e).__name__}\n"
                        f"Note: This is expected with test credentials"
                    )

        except Exception as e:
            await update.message.reply_text(f"Test failed: {str(e)}")

    # Additional command handlers (simplified for brevity)
    async def removebot_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /removebot command"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text(" Access denied. You are not an admin.")
            return

        if not context.args:
            await update.message.reply_text(
                " Please provide bot ID.\nUsage: `/removebot <bot_id>`",
            )
            return

        bot_id = context.args[0]
        success = await self.worker_manager.remove_worker(bot_id)

        if success:
            await update.message.reply_text(f" Bot {bot_id} removed successfully!")
        else:
            await update.message.reply_text(f" Failed to remove bot {bot_id}")

    async def syncfollows_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /syncfollows command"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text(" Access denied. You are not an admin.")
            return

        await update.message.reply_text("🔄 Syncing mutual follows...")

        task_id = await self.scheduler.add_task(TaskType.SYNC_FOLLOWS, {}, priority=2)

        await update.message.reply_text(
            f" Mutual follow sync scheduled!\n Task ID: {task_id}"
        )

    async def pool_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /pool command"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text(" Access denied. You are not an admin.")
            return

        if not context.args:
            await update.message.reply_text(
                " Please provide keyword.\nUsage: `/pool <keyword>`",
            )
            return

        keyword = context.args[0]
        pool_status = self.search_engine.get_user_pool_status(keyword)

        if not pool_status:
            await update.message.reply_text(f" No pool found for keyword: {keyword}")
            return

        text = f"User Pool: {keyword}\n\n"
        text += f"Available: {pool_status['available_users']}\n"
        text += f"🔄 Used: {pool_status['used_users']}\n"
        text += f"Total: {pool_status['total_users']}\n"

        if pool_status.get("created_at"):
            text += f"📅 Created: {pool_status['created_at']}"

        await update.message.reply_text(
            text,
        )

    async def backup_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /backup command"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text(" Access denied. You are not an admin.")
            return

        try:
            backup_path = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            success = self.db.backup_database(backup_path)

            if success:
                await update.message.reply_text(
                    f" Database backed up successfully!\n File: {backup_path}"
                )
            else:
                await update.message.reply_text(" Failed to create backup")

        except Exception as e:
            await update.message.reply_text(f" Error creating backup: {str(e)}")

    async def test_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /test command - test bot authentication and basic functionality"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text(" Access denied. You are not an admin.")
            return

        await update.message.reply_text(
            "Testing bot authentication and functionality..."
        )

        try:
            # Get the first active worker for testing
            active_workers = self.worker_manager.get_active_workers()
            if not active_workers:
                await update.message.reply_text("No active workers found for testing.")
                return

            worker = active_workers[0]
            test_results = []

            # Test 1: Check if bot is logged in
            test_results.append(f"✓ Bot logged in: {worker.is_logged_in}")

            # Test 2: Check rate limiting status
            can_perform = worker._can_perform_action()
            test_results.append(f"✓ Can perform actions: {can_perform}")

            # Test 3: Try to get user info
            try:
                # Try to get current user info
                user_info = await worker.client.user()
                if user_info:
                    username = getattr(
                        user_info,
                        "screen_name",
                        getattr(user_info, "username", "Unknown"),
                    )
                    test_results.append(f"✓ User info retrieved: @{username}")
                else:
                    test_results.append("✗ Failed to get user info")
            except Exception as e:
                test_results.append(f"✗ User info error: {str(e)}")

            # Test 4: Try to create a simple test tweet
            test_text = f"Test tweet from bot {worker.bot_id} at {datetime.now().strftime('%H:%M:%S')}"
            try:
                await worker.client.create_tweet(text=test_text)
                test_results.append("✓ Test tweet created successfully")
            except Exception as e:
                test_results.append(f"✗ Test tweet failed: {str(e)}")

            # Format results
            result_text = "Bot Test Results:\n\n" + "\n".join(test_results)
            await update.message.reply_text(result_text)

        except Exception as e:
            await update.message.reply_text(f"Test failed with error: {str(e)}")

    async def reinit_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /reinit command - reinitialize bot authentication"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text(" Access denied. You are not an admin.")
            return

        await update.message.reply_text("Reinitializing bot authentication...")

        try:
            # Get all workers
            workers = self.worker_manager.get_all_workers()
            if not workers:
                await update.message.reply_text("No workers found to reinitialize.")
                return

            results = []
            for bot_id, worker in workers.items():
                try:
                    success = await worker.reinitialize()
                    if success:
                        results.append(f"✓ {bot_id}: Reinitialized successfully")
                    else:
                        results.append(f"✗ {bot_id}: Reinitialization failed")
                except Exception as e:
                    results.append(f"✗ {bot_id}: Error - {str(e)}")

            result_text = "Reinitialization Results:\n\n" + "\n".join(results)
            await update.message.reply_text(result_text)

        except Exception as e:
            await update.message.reply_text(
                f"Reinitialization failed with error: {str(e)}"
            )

    async def reactivate_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /reactivate command - reactivate inactive bots"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text(" Access denied. You are not an admin.")
            return

        await update.message.reply_text("Reactivating inactive bots...")

        try:
            # Get all bots from database
            all_bots = self.db.get_all_bots()
            inactive_bots = []

            for bot_id, bot_info in all_bots.items():
                if bot_info.get("status") == "inactive":
                    inactive_bots.append(bot_id)

            if not inactive_bots:
                await update.message.reply_text("No inactive bots found.")
                return

            results = []
            for bot_id in inactive_bots:
                try:
                    # Mark bot as active in database
                    self.db.update_bot_status(bot_id, "active")

                    # Create and initialize worker
                    bot_info = all_bots[bot_id]
                    worker = TwitterWorker(bot_id, bot_info["cookie_data"], self.db)

                    if await worker.initialize():
                        self.worker_manager.workers[bot_id] = worker
                        results.append(f"✓ {bot_id}: Reactivated successfully")
                    else:
                        results.append(f"✗ {bot_id}: Failed to initialize")

                except Exception as e:
                    results.append(f"✗ {bot_id}: Error - {str(e)}")

            result_text = "Reactivation Results:\n\n" + "\n".join(results)
            await update.message.reply_text(result_text)

        except Exception as e:
            await update.message.reply_text(f"Reactivation failed with error: {str(e)}")

    async def checkduplicates_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /checkduplicates command - check for duplicate auth tokens"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text(" Access denied. You are not an admin.")
            return

        try:
            all_bots = self.db.get_all_bots()

            if not all_bots:
                await update.message.reply_text("No bots found in database.")
                return

            # Check for duplicate auth_tokens
            auth_tokens = {}
            duplicates = []

            for bot_id, bot_info in all_bots.items():
                cookies = bot_info.get("cookie_data", {})
                auth_token = cookies.get("auth_token")

                if auth_token:
                    if auth_token in auth_tokens:
                        duplicates.append(
                            {
                                "auth_token": auth_token[:10] + "...",
                                "bots": [auth_tokens[auth_token], bot_id],
                            }
                        )
                    else:
                        auth_tokens[auth_token] = bot_id

            if duplicates:
                message = "❌ Duplicate auth tokens found:\n\n"
                for dup in duplicates:
                    message += f"Token: `{dup['auth_token']}`\n"
                    message += (
                        f"Used by: {', '.join([f'`{bot}`' for bot in dup['bots']])}\n\n"
                    )

                message += (
                    "These bots share the same authentication and may conflict.\n"
                )
                message += (
                    "Consider removing duplicate bots or using different accounts."
                )

                await update.message.reply_text(
                    message,
                )
            else:
                await update.message.reply_text(
                    "✅ No duplicate auth tokens found.\n\n"
                    f"Checked {len(all_bots)} bots - all have unique authentication."
                )

        except Exception as e:
            await update.message.reply_text(f"Error checking duplicates: {str(e)}")

    async def cleanup_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /cleanup command - remove inactive/failed bots"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text(" Access denied. You are not an admin.")
            return

        try:
            all_bots = self.db.get_all_bots()

            if not all_bots:
                await update.message.reply_text("No bots found in database.")
                return

            inactive_bots = []
            for bot_id, bot_info in all_bots.items():
                if bot_info.get("status") == "inactive":
                    inactive_bots.append(bot_id)

            if not inactive_bots:
                await update.message.reply_text("No inactive bots found to clean up.")
                return

            # Remove inactive bots
            removed_count = 0
            for bot_id in inactive_bots:
                try:
                    success = await self.worker_manager.remove_worker(bot_id)
                    if success:
                        removed_count += 1
                except Exception as e:
                    self.logger.error(f"Failed to remove bot {bot_id}: {e}")

            await update.message.reply_text(
                f"🧹 Cleanup completed!\n\n"
                f"Removed {removed_count}/{len(inactive_bots)} inactive bots.\n"
                f"System is now cleaner and ready for fresh bots."
            )

        except Exception as e:
            await update.message.reply_text(f"Error during cleanup: {str(e)}")

    async def disable_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Disable a bot (mark as inactive)"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("Access denied. You are not an admin.")
            return

        if not context.args:
            await update.message.reply_text(
                "Please provide a bot ID.\nUsage: /disable <bot_id>"
            )
            return

        bot_id = context.args[0]

        try:
            success = await self.worker_manager.disable_worker(bot_id)

            if success:
                await update.message.reply_text(f"Bot {bot_id} disabled successfully.")
            else:
                await update.message.reply_text(
                    f"Failed to disable bot {bot_id}. Bot may not exist."
                )

        except Exception as e:
            await update.message.reply_text(f"Error disabling bot {bot_id}: {str(e)}")

    async def enable_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Enable a bot (mark as active and reinitialize)"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("Access denied. You are not an admin.")
            return

        if not context.args:
            await update.message.reply_text(
                "Please provide a bot ID.\nUsage: /enable <bot_id>"
            )
            return

        bot_id = context.args[0]

        try:
            success = await self.worker_manager.enable_worker(bot_id)

            if success:
                await update.message.reply_text(
                    f"Bot {bot_id} enabled and reinitialized successfully."
                )
            else:
                await update.message.reply_text(
                    f"Failed to enable bot {bot_id}. Bot may not exist or cookies may be invalid."
                )

        except Exception as e:
            await update.message.reply_text(f"Error enabling bot {bot_id}: {str(e)}")

    async def delete_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Permanently delete a bot"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("Access denied. You are not an admin.")
            return

        if not context.args:
            await update.message.reply_text(
                "Please provide a bot ID.\nUsage: /delete <bot_id>"
            )
            return

        bot_id = context.args[0]

        try:
            # Confirm deletion
            confirm_text = (
                f"⚠️ WARNING: This will permanently delete bot {bot_id}!\n\n"
                f"This action cannot be undone.\n"
                f"Reply with 'YES' to confirm deletion."
            )
            await update.message.reply_text(confirm_text)

            # Store the pending deletion for confirmation
            context.user_data["pending_deletion"] = bot_id

        except Exception as e:
            await update.message.reply_text(
                f"Error preparing deletion of bot {bot_id}: {str(e)}"
            )

    async def handle_deletion_confirmation(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle deletion confirmation"""
        if not self._is_admin(update.effective_user.id):
            return

        pending_deletion = context.user_data.get("pending_deletion")
        if not pending_deletion:
            return

        if update.message.text.upper() == "YES":
            try:
                success = await self.worker_manager.delete_worker(pending_deletion)

                if success:
                    await update.message.reply_text(
                        f"Bot {pending_deletion} deleted permanently."
                    )
                else:
                    await update.message.reply_text(
                        f"Failed to delete bot {pending_deletion}. Bot may not exist."
                    )

                # Clear pending deletion
                del context.user_data["pending_deletion"]

            except Exception as e:
                await update.message.reply_text(
                    f"Error deleting bot {pending_deletion}: {str(e)}"
                )
                del context.user_data["pending_deletion"]
        else:
            # User didn't confirm, cancel deletion
            await update.message.reply_text(
                f"Deletion of bot {pending_deletion} cancelled."
            )
            del context.user_data["pending_deletion"]

    # Placeholder methods for other commands
    async def like_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /like command"""
        await self._handle_single_action(update, context, TaskType.LIKE, "like")

    async def retweet_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /retweet command"""
        await self._handle_single_action(update, context, TaskType.RETWEET, "retweet")

    async def comment_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /comment command"""
        await self._handle_single_action(update, context, TaskType.COMMENT, "comment")

    async def unfollow_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /unfollow command"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("Access denied. You are not an admin.")
            return

        if not context.args:
            await update.message.reply_text(
                "Please provide bot ID or 'all'.\n"
                "Usage: /unfollow <bot_id> or /unfollow all\n"
                "Examples:\n"
                "• /unfollow bot_1 - Unfollow all followers for bot_1\n"
                "• /unfollow all - Unfollow all followers for all bots"
            )
            return

        target = context.args[0].lower()

        try:
            if target == "all":
                await update.message.reply_text(
                    "Starting unfollow process for ALL bots...\n"
                    "This will unfollow all followers for each bot.\n"
                    "Process will be slow to respect rate limits."
                )

                # Start unfollow process for all bots
                results = await self.worker_manager.unfollow_all_followers_all_bots()

                if "error" in results:
                    await update.message.reply_text(f"Error: {results['error']}")
                    return

                # Format results
                summary_text = "Unfollow Process Completed\n\n"
                total_unfollowed = 0
                total_failed = 0

                for bot_id, result in results.items():
                    if result.get("success"):
                        unfollowed = result.get("unfollowed", 0)
                        failed = result.get("failed", 0)
                        total_unfollowed += unfollowed
                        total_failed += failed

                        summary_text += f"{bot_id}:\n"
                        summary_text += f"  Unfollowed: {unfollowed}\n"
                        summary_text += f"  Failed: {failed}\n\n"
                    else:
                        summary_text += f"{bot_id}: Error - {result.get('error', 'Unknown error')}\n\n"

                summary_text += f"Total Results:\n"
                summary_text += f"  Total Unfollowed: {total_unfollowed}\n"
                summary_text += f"  Total Failed: {total_failed}"

                await update.message.reply_text(summary_text)

            else:
                # Unfollow for specific bot
                bot_id = target
                await update.message.reply_text(
                    f"Starting unfollow process for bot {bot_id}...\n"
                    "This will unfollow all followers for this bot.\n"
                    "Process will be slow to respect rate limits."
                )

                result = await self.worker_manager.unfollow_following_for_bot(bot_id)

                if result.get("success"):
                    unfollowed = result.get("unfollowed", 0)
                    failed = result.get("failed", 0)
                    total = result.get("total_following", 0)

                    response_text = f"Unfollow Process Completed for {bot_id}\n\n"
                    response_text += f"Total Following: {total}\n"
                    response_text += f"Successfully Unfollowed: {unfollowed}\n"
                    response_text += f"Failed: {failed}\n"

                    if result.get("errors"):
                        response_text += f"\nErrors:\n"
                        for error in result["errors"][:5]:  # Show first 5 errors
                            response_text += f"• {error}\n"
                        if len(result["errors"]) > 5:
                            response_text += (
                                f"... and {len(result['errors']) - 5} more errors"
                            )

                    await update.message.reply_text(response_text)
                else:
                    await update.message.reply_text(
                        f"Error: {result.get('error', 'Unknown error')}"
                    )

        except Exception as e:
            await update.message.reply_text(
                f"Error executing unfollow command: {str(e)}"
            )

    async def search_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /search command"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text(" Access denied. You are not an admin.")
            return

        if not context.args:
            await update.message.reply_text(
                " Please provide keyword.\nUsage: `/search <keyword>`",
            )
            return

        keyword = context.args[0]
        await update.message.reply_text(
            f" Searching for tweets with keyword: {keyword}"
        )

        tweets = await self.search_engine.search_tweets_by_keyword(keyword)
        await update.message.reply_text(
            f" Found {len(tweets)} tweets for keyword: {keyword}"
        )

    async def refresh_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /refresh command"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text(" Access denied. You are not an admin.")
            return

        if not context.args:
            await update.message.reply_text(
                " Please provide keyword.\nUsage: `/refresh <keyword>`",
            )
            return

        keyword = context.args[0]
        await update.message.reply_text(
            f"🔄 Refreshing user pool for keyword: {keyword}"
        )

        success = await self.search_engine.build_user_pool_for_keyword(keyword)

        if success:
            await update.message.reply_text(
                f" User pool refreshed for keyword: {keyword}"
            )
        else:
            await update.message.reply_text(
                f" Failed to refresh user pool for keyword: {keyword}"
            )

    async def _handle_single_action(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        task_type: TaskType,
        action_name: str,
    ):
        """Handle single action commands"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text(" Access denied. You are not an admin.")
            return

        if not context.args:
            await update.message.reply_text(
                f" Please provide a Twitter URL.\n"
                f"Usage: `/{action_name} https://twitter.com/user/status/123456789`",
            )
            return

        url = context.args[0]

        try:
            task_id = await self.scheduler.add_task(task_type, {"tweet_url": url})

            await update.message.reply_text(
                f"{action_name.title()} task scheduled!\nURL: {url}\nTask ID: {task_id}"
            )

        except Exception as e:
            await update.message.reply_text(
                f" Error scheduling {action_name}: {str(e)}"
            )

    def _is_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        return str(user_id) in self.config.TELEGRAM_ADMIN_IDS

    def _validate_cookie_data(self, cookie_data: Dict[str, Any]) -> bool:
        """Validate cookie data structure"""
        # Handle both raw browser export format and processed format
        if isinstance(cookie_data, list):
            # Raw browser export format - process it
            from cookie_processor import CookieProcessor

            processed = CookieProcessor.process_cookies(cookie_data)
            return (
                len(processed) >= 2 and "auth_token" in processed and "ct0" in processed
            )
        elif isinstance(cookie_data, dict):
            # Already processed format
            required_fields = ["auth_token", "ct0"]
            return all(field in cookie_data for field in required_fields)
        return False

    def _process_raw_cookies(self, cookie_data: Any) -> Dict[str, Any]:
        """Process raw browser cookie export to Twikit format"""
        if isinstance(cookie_data, list):
            # Raw browser export format
            from cookie_processor import CookieProcessor

            return CookieProcessor.process_cookies(cookie_data)
        elif isinstance(cookie_data, dict):
            # Already processed
            return cookie_data
        else:
            return {}

    async def start_system(self):
        """Start the entire system"""
        try:
            self.logger.info("Starting Twitter Bot System...")

            # Validate configuration
            config_status = self.config.validate_config()
            if not config_status["valid"]:
                self.logger.error(f"Configuration issues: {config_status['issues']}")
                return False

            # Load workers from database
            await self.worker_manager.load_workers_from_db()

            # Start scheduler
            await self.scheduler.start()

            # Start Telegram bot
            await self.application.initialize()
            await self.application.start()

            # Start polling for updates with timeout
            try:
                await asyncio.wait_for(
                    self.application.updater.start_polling(), timeout=10.0
                )
            except asyncio.TimeoutError:
                self.logger.warning("Telegram polling timeout, but continuing...")
                # Continue anyway - polling might still work

            self.is_running = True
            self.logger.info("Twitter Bot System started successfully!")

            # Send startup notification
            try:
                await self.logger.send_notification(
                    "Twitter Bot System Started\n\n"
                    f" Workers: {len(self.worker_manager.get_all_workers())}\n"
                    f" Config: Valid\n"
                    f" Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    "INFO",
                )
            except Exception as e:
                self.logger.warning(f"Failed to send startup notification: {e}")

            return True

        except Exception as e:
            self.logger.error(f"Failed to start system: {e}")
            return False

    async def stop_system(self):
        """Stop the entire system"""
        try:
            self.logger.info("Stopping Twitter Bot System...")

            # Stop scheduler
            await self.scheduler.stop()

            # Stop Telegram bot
            await self.application.updater.stop()
            await self.application.stop()

            self.is_running = False
            self.logger.info("Twitter Bot System stopped successfully!")

        except Exception as e:
            self.logger.error(f"Error stopping system: {e}")


async def main():
    """Main entry point"""
    bot = TwitterBotTelegram()

    try:
        await bot.start_system()

        # Keep the bot running
        while bot.is_running:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        print("\nShutting down...")
        await bot.stop_system()

    except Exception as e:
        print(f"Fatal error: {e}")
        await bot.stop_system()


if __name__ == "__main__":
    asyncio.run(main())
