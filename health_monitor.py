#!/usr/bin/env python3
"""
Health Monitor and Auto-Recovery System for Twitter Bot
Monitors system health and automatically recovers from failures
"""

import asyncio
import json
import os
import signal
import subprocess
import time
import psutil
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import requests
from telegram import Bot
from telegram.error import TelegramError

from config import Config
from logger import bot_logger

class HealthMonitor:
    """Comprehensive health monitoring and auto-recovery system"""
    
    def __init__(self):
        self.config = Config
        self.logger = bot_logger
        self.project_path = "/root/Twitter-bot"
        self.bot_process_name = "telegram_bot.py"
        self.webhook_process_name = "webhook_listener.py"
        
        # Health check intervals (seconds)
        self.check_interval = 30  # Check every 30 seconds
        self.auth_check_interval = 300  # Check auth every 5 minutes
        self.restart_cooldown = 60  # Wait 1 minute between restarts
        
        # Tracking
        self.last_restart_time = {}
        self.consecutive_failures = {}
        self.max_consecutive_failures = 3
        
        # Telegram bot for notifications
        self.telegram_bot = None
        self.admin_chat_id = self.config.ADMIN_CHAT_ID
        
    async def initialize(self):
        """Initialize the health monitor"""
        try:
            self.telegram_bot = Bot(token=self.config.TELEGRAM_TOKEN)
            self.logger.info("Health Monitor initialized successfully")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize health monitor: {e}")
            return False
    
    async def send_notification(self, message: str, level: str = "INFO"):
        """Send notification to admin"""
        try:
            if self.telegram_bot and self.admin_chat_id:
                emoji = "🟢" if level == "INFO" else "🟡" if level == "WARNING" else "🔴"
                await self.telegram_bot.send_message(
                    chat_id=self.admin_chat_id,
                    text=f"{emoji} **Health Monitor**\n\n{message}"
                )
        except Exception as e:
            self.logger.error(f"Failed to send notification: {e}")
    
    def find_process(self, process_name: str) -> Optional[psutil.Process]:
        """Find a running process by name"""
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['cmdline'] and any(process_name in cmd for cmd in proc.info['cmdline']):
                        return proc
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            return None
        except Exception as e:
            self.logger.error(f"Error finding process {process_name}: {e}")
            return None
    
    def is_process_healthy(self, process: psutil.Process) -> Tuple[bool, str]:
        """Check if a process is healthy"""
        try:
            # Check if process is running
            if not process.is_running():
                return False, "Process not running"
            
            # Check CPU usage (shouldn't be stuck at 100%)
            cpu_percent = process.cpu_percent()
            if cpu_percent > 95:
                return False, f"High CPU usage: {cpu_percent}%"
            
            # Check memory usage
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            if memory_mb > 1000:  # More than 1GB
                return False, f"High memory usage: {memory_mb:.1f}MB"
            
            # Check if process is responsive (not zombie)
            if process.status() == psutil.STATUS_ZOMBIE:
                return False, "Process is zombie"
            
            return True, "Healthy"
            
        except Exception as e:
            return False, f"Health check error: {e}"
    
    async def check_bot_health(self) -> Dict[str, any]:
        """Check the main bot process health"""
        bot_process = self.find_process(self.bot_process_name)
        
        if not bot_process:
            return {
                "status": "not_running",
                "pid": None,
                "message": "Bot process not found"
            }
        
        is_healthy, health_message = self.is_process_healthy(bot_process)
        
        return {
            "status": "healthy" if is_healthy else "unhealthy",
            "pid": bot_process.pid,
            "message": health_message,
            "cpu_percent": bot_process.cpu_percent(),
            "memory_mb": bot_process.memory_info().rss / 1024 / 1024
        }
    
    async def check_webhook_health(self) -> Dict[str, any]:
        """Check webhook listener health"""
        webhook_process = self.find_process(self.webhook_process_name)
        
        if not webhook_process:
            return {
                "status": "not_running",
                "pid": None,
                "message": "Webhook process not found"
            }
        
        is_healthy, health_message = self.is_process_healthy(webhook_process)
        
        # Also check if webhook endpoint is responding
        webhook_responding = False
        try:
            response = requests.get("http://localhost:8080/health", timeout=5)
            webhook_responding = response.status_code == 200
        except:
            webhook_responding = False
        
        return {
            "status": "healthy" if is_healthy and webhook_responding else "unhealthy",
            "pid": webhook_process.pid,
            "message": health_message,
            "webhook_responding": webhook_responding
        }
    
    async def check_twitter_auth(self) -> Dict[str, any]:
        """Check Twitter authentication status"""
        try:
            # Check database for bot statuses
            db_path = os.path.join(self.project_path, "data", "database.json")
            if not os.path.exists(db_path):
                return {"status": "error", "message": "Database not found"}
            
            with open(db_path, 'r') as f:
                data = json.load(f)
            
            bots = data.get('bots', {})
            auth_status = {}
            
            for bot_id, bot_data in bots.items():
                if bot_data.get('status') == 'active':
                    # Check if bot has valid cookies
                    cookies = bot_data.get('cookies', {})
                    has_auth_token = 'auth_token' in cookies
                    has_ct0 = 'ct0' in cookies
                    
                    auth_status[bot_id] = {
                        "has_auth_token": has_auth_token,
                        "has_ct0": has_ct0,
                        "status": "valid" if has_auth_token and has_ct0 else "invalid"
                    }
            
            return {
                "status": "checked",
                "bots": auth_status,
                "total_bots": len(bots),
                "active_bots": len([b for b in bots.values() if b.get('status') == 'active'])
            }
            
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    async def restart_bot_process(self) -> Tuple[bool, str]:
        """Restart the main bot process"""
        try:
            # Check cooldown
            now = time.time()
            last_restart = self.last_restart_time.get('bot', 0)
            if now - last_restart < self.restart_cooldown:
                return False, f"Restart cooldown active (wait {self.restart_cooldown - (now - last_restart):.0f}s)"
            
            # Kill existing process
            bot_process = self.find_process(self.bot_process_name)
            if bot_process:
                self.logger.info(f"Killing existing bot process {bot_process.pid}")
                bot_process.terminate()
                time.sleep(2)
                
                # Force kill if still running
                if bot_process.is_running():
                    bot_process.kill()
                    time.sleep(1)
            
            # Start new process
            self.logger.info("Starting new bot process")
            subprocess.Popen(
                ["python3", self.bot_process_name],
                cwd=self.project_path,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            self.last_restart_time['bot'] = now
            self.consecutive_failures['bot'] = 0
            
            return True, "Bot process restarted successfully"
            
        except Exception as e:
            self.consecutive_failures['bot'] = self.consecutive_failures.get('bot', 0) + 1
            return False, f"Failed to restart bot: {e}"
    
    async def restart_webhook_process(self) -> Tuple[bool, str]:
        """Restart the webhook listener process"""
        try:
            # Check cooldown
            now = time.time()
            last_restart = self.last_restart_time.get('webhook', 0)
            if now - last_restart < self.restart_cooldown:
                return False, f"Restart cooldown active (wait {self.restart_cooldown - (now - last_restart):.0f}s)"
            
            # Kill existing process
            webhook_process = self.find_process(self.webhook_process_name)
            if webhook_process:
                self.logger.info(f"Killing existing webhook process {webhook_process.pid}")
                webhook_process.terminate()
                time.sleep(2)
                
                # Force kill if still running
                if webhook_process.is_running():
                    webhook_process.kill()
                    time.sleep(1)
            
            # Start new process
            self.logger.info("Starting new webhook process")
            subprocess.Popen(
                ["python3", self.webhook_process_name],
                cwd=self.project_path,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            self.last_restart_time['webhook'] = now
            self.consecutive_failures['webhook'] = 0
            
            return True, "Webhook process restarted successfully"
            
        except Exception as e:
            self.consecutive_failures['webhook'] = self.consecutive_failures.get('webhook', 0) + 1
            return False, f"Failed to restart webhook: {e}"
    
    async def perform_health_check(self) -> Dict[str, any]:
        """Perform comprehensive health check"""
        self.logger.info("Performing health check...")
        
        # Check bot process
        bot_health = await self.check_bot_health()
        
        # Check webhook process
        webhook_health = await self.check_webhook_health()
        
        # Check Twitter auth (less frequently)
        auth_health = await self.check_twitter_auth()
        
        health_report = {
            "timestamp": datetime.now().isoformat(),
            "bot": bot_health,
            "webhook": webhook_health,
            "auth": auth_health,
            "system": {
                "cpu_percent": psutil.cpu_percent(),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage('/').percent
            }
        }
        
        return health_report
    
    async def handle_failure(self, component: str, health_data: Dict[str, any]):
        """Handle component failure"""
        consecutive_failures = self.consecutive_failures.get(component, 0) + 1
        self.consecutive_failures[component] = consecutive_failures
        
        self.logger.warning(f"{component} failure #{consecutive_failures}: {health_data.get('message', 'Unknown error')}")
        
        # Don't restart if too many consecutive failures
        if consecutive_failures > self.max_consecutive_failures:
            await self.send_notification(
                f"🚨 **{component.title()} Critical Failure**\n\n"
                f"Failed {consecutive_failures} times consecutively.\n"
                f"Manual intervention required!\n\n"
                f"Error: {health_data.get('message', 'Unknown')}",
                "CRITICAL"
            )
            return False
        
        # Attempt restart
        if component == 'bot':
            success, message = await self.restart_bot_process()
        elif component == 'webhook':
            success, message = await self.restart_webhook_process()
        else:
            return False
        
        if success:
            await self.send_notification(
                f"🔄 **{component.title()} Auto-Recovery**\n\n"
                f"Successfully restarted after failure.\n"
                f"Reason: {health_data.get('message', 'Unknown')}",
                "WARNING"
            )
            return True
        else:
            await self.send_notification(
                f"❌ **{component.title()} Recovery Failed**\n\n"
                f"Failed to restart: {message}\n"
                f"Failure count: {consecutive_failures}",
                "ERROR"
            )
            return False
    
    async def run_monitoring_loop(self):
        """Main monitoring loop"""
        self.logger.info("Starting health monitoring loop...")
        await self.send_notification("🟢 **Health Monitor Started**\n\nMonitoring system health and auto-recovery enabled.")
        
        last_auth_check = 0
        
        while True:
            try:
                # Perform health check
                health_report = await self.perform_health_check()
                
                # Check bot health
                if health_report['bot']['status'] != 'healthy':
                    await self.handle_failure('bot', health_report['bot'])
                
                # Check webhook health
                if health_report['webhook']['status'] != 'healthy':
                    await self.handle_failure('webhook', health_report['webhook'])
                
                # Check auth periodically
                now = time.time()
                if now - last_auth_check > self.auth_check_interval:
                    auth_status = health_report['auth']
                    if auth_status['status'] == 'checked':
                        invalid_bots = [bot_id for bot_id, bot_data in auth_status['bots'].items() 
                                      if bot_data['status'] == 'invalid']
                        if invalid_bots:
                            await self.send_notification(
                                f"⚠️ **Authentication Alert**\n\n"
                                f"Invalid authentication for bots: {', '.join(invalid_bots)}\n"
                                f"Consider updating cookies.",
                                "WARNING"
                            )
                    last_auth_check = now
                
                # Log health status
                self.logger.info(f"Health check complete - Bot: {health_report['bot']['status']}, "
                               f"Webhook: {health_report['webhook']['status']}")
                
                # Wait for next check
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(self.check_interval)
    
    async def start(self):
        """Start the health monitor"""
        if await self.initialize():
            await self.run_monitoring_loop()
        else:
            self.logger.error("Failed to initialize health monitor")

async def main():
    """Main entry point"""
    monitor = HealthMonitor()
    await monitor.start()

if __name__ == "__main__":
    asyncio.run(main())
