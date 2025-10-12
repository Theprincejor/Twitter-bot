#!/usr/bin/env python3
"""
Twitter Authentication Monitor and Auto-Refresh System
Monitors Twitter authentication status and automatically refreshes cookies when needed
"""

import asyncio
import json
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import requests
from telegram import Bot
from telegram.error import TelegramError

from config import Config
from logger import bot_logger

class TwitterAuthMonitor:
    """Monitors and manages Twitter authentication for all bots"""
    
    def __init__(self):
        self.config = Config
        self.logger = bot_logger
        self.project_path = "/root/Twitter-bot"
        self.db_path = os.path.join(self.project_path, "data", "database.json")
        
        # Monitoring intervals
        self.check_interval = 300  # Check every 5 minutes
        self.refresh_interval = 3600  # Refresh every hour
        self.warning_threshold = 1800  # Warn 30 minutes before expiry
        
        # Tracking
        self.last_check_time = {}
        self.last_refresh_time = {}
        self.auth_warnings_sent = {}
        
        # Telegram bot for notifications
        self.telegram_bot = None
        self.admin_chat_id = self.config.ADMIN_CHAT_ID
        
    async def initialize(self):
        """Initialize the auth monitor"""
        try:
            self.telegram_bot = Bot(token=self.config.TELEGRAM_TOKEN)
            self.logger.info("Twitter Auth Monitor initialized successfully")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize auth monitor: {e}")
            return False
    
    async def send_notification(self, message: str, level: str = "INFO"):
        """Send notification to admin"""
        try:
            if self.telegram_bot and self.admin_chat_id:
                emoji = "🟢" if level == "INFO" else "🟡" if level == "WARNING" else "🔴"
                await self.telegram_bot.send_message(
                    chat_id=self.admin_chat_id,
                    text=f"{emoji} **Auth Monitor**\n\n{message}"
                )
        except Exception as e:
            self.logger.error(f"Failed to send notification: {e}")
    
    def load_database(self) -> Dict:
        """Load the database"""
        try:
            if not os.path.exists(self.db_path):
                return {}
            
            with open(self.db_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load database: {e}")
            return {}
    
    def save_database(self, data: Dict):
        """Save the database"""
        try:
            with open(self.db_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save database: {e}")
    
    def check_cookie_validity(self, cookies: Dict) -> Tuple[bool, str, int]:
        """Check if cookies are valid and estimate expiry time"""
        try:
            # Check for required cookies
            required_cookies = ['auth_token', 'ct0']
            for cookie in required_cookies:
                if cookie not in cookies or not cookies[cookie]:
                    return False, f"Missing {cookie}", 0
            
            # Check auth_token format (should be a long string)
            auth_token = cookies['auth_token']
            if len(auth_token) < 50:
                return False, "Invalid auth_token format", 0
            
            # Check ct0 format (should be a hex string)
            ct0 = cookies['ct0']
            if len(ct0) != 32 or not all(c in '0123456789abcdef' for c in ct0.lower()):
                return False, "Invalid ct0 format", 0
            
            # Estimate expiry time (cookies typically last 24-48 hours)
            # We'll assume 24 hours from now as a conservative estimate
            estimated_expiry = int(time.time()) + (24 * 3600)
            
            return True, "Valid", estimated_expiry
            
        except Exception as e:
            return False, f"Validation error: {e}", 0
    
    def test_twitter_auth(self, cookies: Dict) -> Tuple[bool, str]:
        """Test Twitter authentication with actual API call"""
        try:
            # Create session with cookies
            session = requests.Session()
            
            # Set cookies
            for name, value in cookies.items():
                session.cookies.set(name, value)
            
            # Test with a simple API call
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json',
                'Accept-Language': 'en-US,en;q=0.9',
                'X-Twitter-Active-User': 'yes',
                'X-Twitter-Auth-Type': 'OAuth2Session',
                'X-Csrf-Token': cookies.get('ct0', ''),
            }
            
            # Try to get user info
            response = session.get(
                'https://twitter.com/i/api/1.1/account/verify_credentials.json',
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                return True, "Authentication successful"
            elif response.status_code == 401:
                return False, "Authentication failed (401)"
            elif response.status_code == 403:
                return False, "Rate limited or blocked (403)"
            else:
                return False, f"Unexpected response: {response.status_code}"
                
        except Exception as e:
            return False, f"Test error: {e}"
    
    async def check_bot_auth(self, bot_id: str, bot_data: Dict) -> Dict:
        """Check authentication for a specific bot"""
        try:
            cookies = bot_data.get('cookies', {})
            
            # Basic cookie validation
            is_valid_format, format_message, estimated_expiry = self.check_cookie_validity(cookies)
            
            if not is_valid_format:
                return {
                    "bot_id": bot_id,
                    "status": "invalid_format",
                    "message": format_message,
                    "needs_refresh": True,
                    "estimated_expiry": 0
                }
            
            # Test actual authentication
            is_auth_working, auth_message = self.test_twitter_auth(cookies)
            
            if not is_auth_working:
                return {
                    "bot_id": bot_id,
                    "status": "auth_failed",
                    "message": auth_message,
                    "needs_refresh": True,
                    "estimated_expiry": estimated_expiry
                }
            
            # Check if cookies are close to expiry
            now = int(time.time())
            time_until_expiry = estimated_expiry - now
            
            if time_until_expiry < self.warning_threshold:
                return {
                    "bot_id": bot_id,
                    "status": "expiring_soon",
                    "message": f"Cookies expire in {time_until_expiry // 60} minutes",
                    "needs_refresh": True,
                    "estimated_expiry": estimated_expiry
                }
            
            return {
                "bot_id": bot_id,
                "status": "valid",
                "message": "Authentication working",
                "needs_refresh": False,
                "estimated_expiry": estimated_expiry
            }
            
        except Exception as e:
            return {
                "bot_id": bot_id,
                "status": "error",
                "message": f"Check error: {e}",
                "needs_refresh": True,
                "estimated_expiry": 0
            }
    
    async def refresh_bot_cookies(self, bot_id: str) -> Tuple[bool, str]:
        """Attempt to refresh cookies for a bot (placeholder for future implementation)"""
        try:
            # This is a placeholder for future cookie refresh implementation
            # For now, we'll just mark the bot as needing manual intervention
            
            self.logger.warning(f"Bot {bot_id} needs cookie refresh - manual intervention required")
            
            # Update bot status to inactive
            data = self.load_database()
            if 'bots' in data and bot_id in data['bots']:
                data['bots'][bot_id]['status'] = 'inactive'
                data['bots'][bot_id]['last_auth_check'] = datetime.now().isoformat()
                data['bots'][bot_id]['auth_issue'] = 'Cookies expired - manual refresh needed'
                self.save_database(data)
            
            return False, "Manual cookie refresh required"
            
        except Exception as e:
            return False, f"Refresh error: {e}"
    
    async def perform_auth_check(self) -> Dict:
        """Perform comprehensive authentication check"""
        self.logger.info("Performing authentication check...")
        
        data = self.load_database()
        bots = data.get('bots', {})
        
        auth_report = {
            "timestamp": datetime.now().isoformat(),
            "total_bots": len(bots),
            "active_bots": 0,
            "valid_auth": 0,
            "needs_refresh": 0,
            "bot_status": {}
        }
        
        for bot_id, bot_data in bots.items():
            if bot_data.get('status') == 'active':
                auth_report['active_bots'] += 1
                
                # Check authentication
                auth_status = await self.check_bot_auth(bot_id, bot_data)
                auth_report['bot_status'][bot_id] = auth_status
                
                if auth_status['status'] == 'valid':
                    auth_report['valid_auth'] += 1
                elif auth_status['needs_refresh']:
                    auth_report['needs_refresh'] += 1
                    
                    # Attempt refresh if needed
                    if auth_status['status'] in ['auth_failed', 'expiring_soon']:
                        refresh_success, refresh_message = await self.refresh_bot_cookies(bot_id)
                        auth_report['bot_status'][bot_id]['refresh_attempted'] = refresh_success
                        auth_report['bot_status'][bot_id]['refresh_message'] = refresh_message
        
        return auth_report
    
    async def handle_auth_issues(self, auth_report: Dict):
        """Handle authentication issues and send notifications"""
        try:
            for bot_id, bot_status in auth_report['bot_status'].items():
                if bot_status['needs_refresh']:
                    # Check if we've already sent a warning for this bot
                    last_warning = self.auth_warnings_sent.get(bot_id, 0)
                    now = time.time()
                    
                    # Only send warning once per hour per bot
                    if now - last_warning > 3600:
                        await self.send_notification(
                            f"⚠️ **Authentication Issue - Bot {bot_id}**\n\n"
                            f"Status: {bot_status['status']}\n"
                            f"Message: {bot_status['message']}\n"
                            f"Action Required: Manual cookie refresh needed",
                            "WARNING"
                        )
                        self.auth_warnings_sent[bot_id] = now
            
            # Send summary if there are multiple issues
            if auth_report['needs_refresh'] > 0:
                total_issues = auth_report['needs_refresh']
                total_active = auth_report['active_bots']
                
                if total_issues == total_active:
                    await self.send_notification(
                        f"🚨 **Critical Authentication Alert**\n\n"
                        f"All {total_active} active bots have authentication issues!\n"
                        f"Manual intervention required immediately.",
                        "CRITICAL"
                    )
                elif total_issues > total_active // 2:
                    await self.send_notification(
                        f"⚠️ **Multiple Authentication Issues**\n\n"
                        f"{total_issues} out of {total_active} bots need attention.\n"
                        f"Consider updating cookies for affected bots.",
                        "WARNING"
                    )
                    
        except Exception as e:
            self.logger.error(f"Error handling auth issues: {e}")
    
    async def run_monitoring_loop(self):
        """Main monitoring loop"""
        self.logger.info("Starting Twitter authentication monitoring loop...")
        await self.send_notification("🟢 **Auth Monitor Started**\n\nMonitoring Twitter authentication for all bots.")
        
        while True:
            try:
                # Perform authentication check
                auth_report = await self.perform_auth_check()
                
                # Handle any issues found
                await self.handle_auth_issues(auth_report)
                
                # Log summary
                self.logger.info(f"Auth check complete - Valid: {auth_report['valid_auth']}, "
                               f"Needs refresh: {auth_report['needs_refresh']}")
                
                # Wait for next check
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                self.logger.error(f"Error in auth monitoring loop: {e}")
                await asyncio.sleep(self.check_interval)
    
    async def start(self):
        """Start the auth monitor"""
        if await self.initialize():
            await self.run_monitoring_loop()
        else:
            self.logger.error("Failed to initialize auth monitor")

async def main():
    """Main entry point"""
    monitor = TwitterAuthMonitor()
    await monitor.start()

if __name__ == "__main__":
    asyncio.run(main())
