"""
Logging system for both Telegram notifications and file logging
"""

import logging
import logging.handlers
import os
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any
from telegram import Bot
from telegram.error import TelegramError
from config import Config


class TelegramLogger:
    """Custom logging handler for Telegram notifications"""

    def __init__(self, bot_token: str, admin_ids: list):
        self.bot_token = bot_token
        self.admin_ids = admin_ids
        self.bot = Bot(token=bot_token)
        self.logger = logging.getLogger(__name__)

    async def send_notification(self, message: str, level: str = "INFO") -> bool:
        """Send notification to Telegram admins"""
        try:
            if not self.admin_ids:
                return False

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # Escape special characters for Telegram
            escaped_message = (
                message.replace("*", "\\*")
                .replace("_", "\\_")
                .replace("[", "\\[")
                .replace("]", "\\]")
            )
            formatted_message = (
                f"🤖 Twitter Bot [{level}]\n📅 {timestamp}\n\n{escaped_message}"
            )

            for admin_id in self.admin_ids:
                if admin_id.strip():
                    await self.bot.send_message(
                        chat_id=admin_id.strip(),
                        text=formatted_message
                    )

            return True

        except TelegramError as e:
            self.logger.error(f"Failed to send Telegram notification: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error sending Telegram notification: {e}")
            return False


class BotLogger:
    """Main logging class for the Twitter bot system"""

    def __init__(self, name: str = "TwitterBot"):
        self.name = name
        self.telegram_logger = None
        self.setup_logging()

    def setup_logging(self):
        """Setup logging configuration"""
        # Create logger
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(getattr(logging, Config.LOG_LEVEL.upper()))

        # Clear existing handlers
        self.logger.handlers.clear()

        # Create formatters
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        console_formatter = logging.Formatter("%(levelname)s - %(message)s")

        # File handler with rotation
        os.makedirs(os.path.dirname(Config.LOG_FILE_PATH), exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            Config.LOG_FILE_PATH,
            maxBytes=Config.MAX_LOG_SIZE_MB * 1024 * 1024,
            backupCount=Config.LOG_BACKUP_COUNT,
        )
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(logging.DEBUG)

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(logging.INFO)

        # Add handlers
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

        # Initialize Telegram logger
        if Config.TELEGRAM_TOKEN and Config.TELEGRAM_ADMIN_IDS:
            self.telegram_logger = TelegramLogger(
                Config.TELEGRAM_TOKEN, Config.TELEGRAM_ADMIN_IDS
            )

    def info(self, message: str, send_telegram: bool = False):
        """Log info message"""
        self.logger.info(message)
        if send_telegram and self.telegram_logger:
            asyncio.create_task(self.telegram_logger.send_notification(message, "INFO"))

    def warning(self, message: str, send_telegram: bool = True):
        """Log warning message"""
        self.logger.warning(message)
        if send_telegram and self.telegram_logger:
            asyncio.create_task(
                self.telegram_logger.send_notification(message, "WARNING")
            )

    def error(self, message: str, send_telegram: bool = True):
        """Log error message"""
        self.logger.error(message)
        if send_telegram and self.telegram_logger:
            asyncio.create_task(
                self.telegram_logger.send_notification(message, "ERROR")
            )

    def debug(self, message: str, send_telegram: bool = False):
        """Log debug message"""
        self.logger.debug(message)
        if send_telegram and self.telegram_logger:
            asyncio.create_task(
                self.telegram_logger.send_notification(message, "DEBUG")
            )

    def critical(self, message: str, send_telegram: bool = True):
        """Log critical message"""
        self.logger.critical(message)
        if send_telegram and self.telegram_logger:
            asyncio.create_task(
                self.telegram_logger.send_notification(message, "CRITICAL")
            )

    async def send_notification(self, message: str, level: str = "INFO"):
        """Send notification to Telegram (convenience method)"""
        if self.telegram_logger:
            await self.telegram_logger.send_notification(message, level)

    async def send_bot_status(self, bot_id: str, status: str, details: str = ""):
        """Send bot status update to Telegram"""
        if not self.telegram_logger:
            return

        emoji_map = {
            "active": "✅",
            "rate_limited": "⏰",
            "captcha": "🔒",
            "error": "❌",
            "paused": "⏸️",
        }

        emoji = emoji_map.get(status, "🤖")
        message = f"{emoji} Bot {bot_id} is now {status.upper()}\n\n{details}"

        await self.telegram_logger.send_notification(message, "INFO")

    async def send_task_completion(
        self, task_type: str, bot_id: str, success: bool, details: str = ""
    ):
        """Send task completion notification"""
        if not self.telegram_logger:
            return

        emoji = "✅" if success else "❌"
        status = "completed" if success else "failed"

        message = f"{emoji} Task {task_type} {status} by bot {bot_id}\n\n{details}"

        await self.telegram_logger.send_notification(message, "INFO")

    async def send_rate_limit_alert(self, bot_id: str, retry_after: int):
        """Send rate limit alert"""
        if not self.telegram_logger:
            return

        message = (
            f"⏰ Bot {bot_id} hit rate limit\n🔄 Will retry in {retry_after} minutes"
        )

        await self.telegram_logger.send_notification(message, "WARNING")

    async def send_captcha_alert(self, bot_id: str):
        """Send captcha required alert"""
        if not self.telegram_logger:
            return

        message = f"🔒 Bot {bot_id} requires captcha verification\n⏸️ Bot paused until manual intervention"

        await self.telegram_logger.send_notification(message, "CRITICAL")

    def get_recent_logs(self, lines: int = 50) -> str:
        """Get recent log entries"""
        try:
            if not os.path.exists(Config.LOG_FILE_PATH):
                return "No log file found"

            with open(Config.LOG_FILE_PATH, "r") as f:
                all_lines = f.readlines()
                recent_lines = (
                    all_lines[-lines:] if len(all_lines) > lines else all_lines
                )
                return "".join(recent_lines)

        except Exception as e:
            self.logger.error(f"Failed to read recent logs: {e}")
            return f"Error reading logs: {e}"


# Global logger instance
bot_logger = BotLogger()
