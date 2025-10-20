"""
Captcha solver module for Twitter Bot System
Handles Cloudflare challenges and captcha solving
"""

import asyncio
import json
from typing import Dict, Any, Optional
from config import Config
from logger import bot_logger


class CaptchaSolver:
    """Handles captcha solving and Cloudflare bypass"""

    def __init__(self):
        self.config = Config
        self.logger = bot_logger
        self.capsolver = None
        self.cloudscraper_session = None

        # Initialize captcha solver if configured
        if self.config.USE_CAPTCHA_SOLVER and self.config.CAPSOLVER_API_KEY:
            self._initialize_capsolver()

        # Initialize cloudscraper if configured
        if self.config.USE_CLOUDSCRAPER:
            self._initialize_cloudscraper()

    def _initialize_capsolver(self):
        """Initialize Capsolver for automatic captcha solving"""
        try:
            import capsolver
            
            # Set the API key
            capsolver.api_key = self.config.CAPSOLVER_API_KEY
            
            # Test the API key
            balance = capsolver.balance()
            if balance.get('errorId') == 0:
                self.capsolver = capsolver
                print(f"✅ Capsolver initialized successfully - Balance: ${balance.get('balance', 0)}")
            else:
                print(f"❌ Capsolver API key invalid: {balance}")
        except ImportError:
            print("⚠️ Capsolver not available - install capsolver package")
        except Exception as e:
            print(f"❌ Failed to initialize Capsolver: {e}")

    def _initialize_cloudscraper(self):
        """Initialize cloudscraper for Cloudflare bypass"""
        try:
            import cloudscraper

            self.cloudscraper_session = cloudscraper.create_scraper(
                browser={"browser": "chrome", "platform": "windows", "mobile": False}
            )
            print("✅ Cloudscraper initialized successfully")
        except ImportError:
            print("⚠️ Cloudscraper not available - install cloudscraper package")
        except Exception as e:
            print(f"❌ Failed to initialize Cloudscraper: {e}")

    def get_captcha_solver(self):
        """Get the captcha solver instance for Twikit Client"""
        if self.config.USE_CAPTCHA_SOLVER and self.capsolver:
            return self.capsolver
        return None

    async def test_cloudflare_bypass(self) -> Dict[str, Any]:
        """Test if Cloudflare bypass is working"""
        if not self.cloudscraper_session:
            return {
                "success": False,
                "error": "Cloudscraper not initialized",
                "recommendation": "Set USE_CLOUDSCRAPER=true in .env",
            }

        try:
            # Test with a simple request
            response = self.cloudscraper_session.get("https://twitter.com", timeout=10)

            if response.status_code == 200:
                return {
                    "success": True,
                    "status_code": response.status_code,
                    "message": "Cloudflare bypass working",
                }
            else:
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "error": f"Unexpected status code: {response.status_code}",
                }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "recommendation": "Check internet connection and Cloudflare settings",
            }

    async def get_cloudflare_cookies(
        self, url: str = "https://twitter.com"
    ) -> Dict[str, Any]:
        """Get Cloudflare cookies for bypassing protection"""
        if not self.cloudscraper_session:
            return {"success": False, "error": "Cloudscraper not initialized"}

        try:
            # Make request to get Cloudflare cookies
            response = self.cloudscraper_session.get(url, timeout=15)

            if response.status_code == 200:
                cookies = self.cloudscraper_session.cookies.get_dict()
                return {
                    "success": True,
                    "cookies": cookies,
                    "user_agent": self.cloudscraper_session.headers.get("User-Agent"),
                    "message": "Cloudflare cookies obtained successfully",
                }
            else:
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "error": f"Failed to get cookies, status: {response.status_code}",
                }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "recommendation": "Check network connectivity and URL accessibility",
            }

    def is_captcha_solver_available(self) -> bool:
        """Check if captcha solver is available and configured"""
        return (
            self.config.USE_CAPTCHA_SOLVER
            and self.config.CAPSOLVER_API_KEY
            and self.capsolver is not None
        )

    def is_cloudscraper_available(self) -> bool:
        """Check if cloudscraper is available and configured"""
        return self.config.USE_CLOUDSCRAPER and self.cloudscraper_session is not None

    def get_status(self) -> Dict[str, Any]:
        """Get captcha solver and cloudscraper status"""
        return {
            "captcha_solver": {
                "enabled": self.config.USE_CAPTCHA_SOLVER,
                "configured": bool(self.config.CAPSOLVER_API_KEY),
                "available": self.is_captcha_solver_available(),
            },
            "cloudscraper": {
                "enabled": self.config.USE_CLOUDSCRAPER,
                "available": self.is_cloudscraper_available(),
            },
            "recommendations": self._get_recommendations(),
        }

    def _get_recommendations(self) -> list:
        """Get recommendations for improving captcha/captcha handling"""
        recommendations = []

        if not self.config.USE_CAPTCHA_SOLVER:
            recommendations.append(
                "Enable captcha solver by setting USE_CAPTCHA_SOLVER=true"
            )

        if not self.config.CAPSOLVER_API_KEY:
            recommendations.append(
                "Set CAPSOLVER_API_KEY in .env file for automatic captcha solving"
            )

        if not self.config.USE_CLOUDSCRAPER:
            recommendations.append(
                "Enable cloudscraper by setting USE_CLOUDSCRAPER=true"
            )

        return recommendations


# Global instance
captcha_solver = CaptchaSolver()
