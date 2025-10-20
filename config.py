import os
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    TELEGRAM_TOKEN = os.getenv(
        "TELEGRAM_TOKEN", "8350919686:AAG-VPxwYixmm-wpt0Gih37cx2d9mEoyTj4"
    )
    TELEGRAM_ADMIN_IDS = (
        os.getenv("TELEGRAM_ADMIN_IDS", "").split(",")
        if os.getenv("TELEGRAM_ADMIN_IDS")
        else []
    )
    DATABASE_PATH = os.getenv("DATABASE_PATH", "data/database.json")
    COOKIES_PATH = os.getenv("COOKIES_PATH", "data/cookies/")
    ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "your-secret-key-here")
    LIKE_INTERVAL_MINUTES = int(os.getenv("LIKE_INTERVAL_MINUTES", "2"))
    LIKE_BREAK_MINUTES = int(os.getenv("LIKE_BREAK_MINUTES", "10"))
    COMMENT_MIN_INTERVAL = int(os.getenv("COMMENT_MIN_INTERVAL", "10"))
    COMMENT_MAX_INTERVAL = int(os.getenv("COMMENT_MAX_INTERVAL", "30"))
    QUOTE_CYCLE_MIN = int(os.getenv("QUOTE_CYCLE_MIN", "10"))
    QUOTE_CYCLE_MAX = int(os.getenv("QUOTE_CYCLE_MAX", "20"))
    RATE_LIMIT_PAUSE_MINUTES = int(os.getenv("RATE_LIMIT_PAUSE_MINUTES", "20"))
    TWITTER_SEARCH_LIMIT = int(os.getenv("TWITTER_SEARCH_LIMIT", "100"))
    MAX_MENTIONS_PER_QUOTE = int(os.getenv("MAX_MENTIONS_PER_QUOTE", "3"))
    LOG_FILE_PATH = os.getenv("LOG_FILE_PATH", "logs/bot.log")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    MAX_LOG_SIZE_MB = int(os.getenv("MAX_LOG_SIZE_MB", "10"))
    LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "5"))
    MAX_WORKERS = int(os.getenv("MAX_WORKERS", "50"))
    TASK_QUEUE_SIZE = int(os.getenv("TASK_QUEUE_SIZE", "1000"))

    # Captcha solver configuration
    CAPSOLVER_API_KEY = os.getenv("CAPSOLVER_API_KEY", "")
    CAPSOLVER_MAX_ATTEMPTS = int(os.getenv("CAPSOLVER_MAX_ATTEMPTS", "3"))
    CAPSOLVER_RESULT_INTERVAL = float(os.getenv("CAPSOLVER_RESULT_INTERVAL", "1.0"))
    USE_CAPTCHA_SOLVER = os.getenv("USE_CAPTCHA_SOLVER", "false").lower() == "true"

    # Cloudflare bypass configuration
    USE_CLOUDSCRAPER = os.getenv("USE_CLOUDSCRAPER", "false").lower() == "true"
    CLOUDSCRAPER_DELAY = int(os.getenv("CLOUDSCRAPER_DELAY", "2"))
    
    # Proxy configuration
    PROXY_URL = os.getenv("PROXY_URL", "")

    @classmethod
    def validate_config(cls) -> Dict[str, Any]:
        issues = []
        if not cls.TELEGRAM_TOKEN:
            issues.append("TELEGRAM_TOKEN is required")
        if cls.ENCRYPTION_KEY == "your-secret-key-here":
            issues.append("ENCRYPTION_KEY should be changed from default value")
        if not cls.TELEGRAM_ADMIN_IDS:
            issues.append("TELEGRAM_ADMIN_IDS should be set")
        return {"valid": len(issues) == 0, "issues": issues}

    @classmethod
    def get_rate_limits(cls) -> Dict[str, int]:
        return {
            "like_interval": cls.LIKE_INTERVAL_MINUTES,
            "like_break": cls.LIKE_BREAK_MINUTES,
            "comment_min": cls.COMMENT_MIN_INTERVAL,
            "comment_max": cls.COMMENT_MAX_INTERVAL,
            "quote_min": cls.QUOTE_CYCLE_MIN,
            "quote_max": cls.QUOTE_CYCLE_MAX,
            "rate_limit_pause": cls.RATE_LIMIT_PAUSE_MINUTES,
        }
