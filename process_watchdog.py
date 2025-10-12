#!/usr/bin/env python3
"""
Process Watchdog - Ultimate Self-Management System
Monitors all components and ensures continuous operation
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

class ProcessWatchdog:
    """Ultimate process watchdog for complete self-management"""
    
    def __init__(self):
        self.config = Config
        self.logger = bot_logger
        self.project_path = "/root/Twitter-bot"
        
        # Process definitions
        self.processes = {
            'webhook': {
                'name': 'webhook_listener.py',
                'service': 'webhook-listener.service',
                'port': 8080,
                'health_endpoint': '/health',
                'restart_delay': 5,
                'max_restarts': 5,
                'restart_window': 300  # 5 minutes
            },
            'bot': {
                'name': 'main.py',
                'service': 'twitter-bot.service',
                'port': None,
                'health_endpoint': None,
                'restart_delay': 10,
                'max_restarts': 3,
                'restart_window': 600  # 10 minutes
            },
            'health_monitor': {
                'name': 'health_monitor.py',
                'service': 'health-monitor.service',
                'port': None,
                'health_endpoint': None,
                'restart_delay': 15,
                'max_restarts': 3,
                'restart_window': 600
            },
            'auth_monitor': {
                'name': 'auth_monitor.py',
                'service': 'auth-monitor.service',
                'port': None,
                'health_endpoint': None,
                'restart_delay': 20,
                'max_restarts': 3,
                'restart_window': 600
            }
        }
        
        # Monitoring intervals
        self.check_interval = 15  # Check every 15 seconds
        self.detailed_check_interval = 3600  # Detailed check every hour (was 60 seconds)
        
        # Tracking
        self.restart_counts = {}
        self.restart_windows = {}
        self.last_health_check = {}
        self.process_cache = {}
        
        # Telegram bot for notifications
        self.telegram_bot = None
        self.admin_chat_id = self.config.TELEGRAM_ADMIN_IDS[0] if self.config.TELEGRAM_ADMIN_IDS else None
        
    async def initialize(self):
        """Initialize the watchdog"""
        try:
            self.telegram_bot = Bot(token=self.config.TELEGRAM_TOKEN)
            self.logger.info("Process Watchdog initialized successfully")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize watchdog: {e}")
            return False
    
    async def send_notification(self, message: str, level: str = "INFO"):
        """Send notification to admin"""
        try:
            if self.telegram_bot and self.admin_chat_id:
                emoji = "🟢" if level == "INFO" else "🟡" if level == "WARNING" else "🔴"
                await self.telegram_bot.send_message(
                    chat_id=self.admin_chat_id,
                    text=f"{emoji} **Process Watchdog**\n\n{message}"
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
            if not process.is_running():
                return False, "Process not running"
            
            # Check CPU usage
            cpu_percent = process.cpu_percent()
            if cpu_percent > 95:
                return False, f"High CPU usage: {cpu_percent}%"
            
            # Check memory usage
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            if memory_mb > 2000:  # More than 2GB
                return False, f"High memory usage: {memory_mb:.1f}MB"
            
            # Check process status
            if process.status() == psutil.STATUS_ZOMBIE:
                return False, "Process is zombie"
            
            return True, "Healthy"
            
        except Exception as e:
            return False, f"Health check error: {e}"
    
    def check_service_status(self, service_name: str) -> Tuple[bool, str]:
        """Check systemd service status"""
        try:
            result = subprocess.run(
                ['systemctl', 'is-active', service_name],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                return True, "Active"
            else:
                return False, f"Inactive: {result.stderr.strip()}"
                
        except Exception as e:
            return False, f"Service check error: {e}"
    
    def check_port_health(self, port: int, endpoint: str = None) -> Tuple[bool, str]:
        """Check if a port is responding"""
        try:
            if endpoint:
                url = f"http://localhost:{port}{endpoint}"
                response = requests.get(url, timeout=5)
                return response.status_code == 200, f"HTTP {response.status_code}"
            else:
                # Just check if port is open
                import socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                result = sock.connect_ex(('localhost', port))
                sock.close()
                return result == 0, "Port open" if result == 0 else "Port closed"
                
        except Exception as e:
            return False, f"Port check error: {e}"
    
    async def check_process_health(self, process_key: str) -> Dict:
        """Check health of a specific process"""
        process_config = self.processes[process_key]
        
        # Find process
        process = self.find_process(process_config['name'])
        
        health_data = {
            'process_key': process_key,
            'process_name': process_config['name'],
            'service_name': process_config['service'],
            'timestamp': datetime.now().isoformat(),
            'process_running': False,
            'process_healthy': False,
            'service_active': False,
            'port_healthy': True,
            'pid': None,
            'cpu_percent': 0,
            'memory_mb': 0,
            'status_message': '',
            'overall_health': 'unhealthy'
        }
        
        # Check if process is running
        if process:
            health_data['process_running'] = True
            health_data['pid'] = process.pid
            
            # Check process health
            is_healthy, health_message = self.is_process_healthy(process)
            health_data['process_healthy'] = is_healthy
            health_data['status_message'] = health_message
            
            if is_healthy:
                health_data['cpu_percent'] = process.cpu_percent()
                health_data['memory_mb'] = process.memory_info().rss / 1024 / 1024
        
        # Check service status
        service_active, service_message = self.check_service_status(process_config['service'])
        health_data['service_active'] = service_active
        if not service_active:
            health_data['status_message'] += f" | Service: {service_message}"
        
        # Check port health if applicable
        if process_config['port']:
            port_healthy, port_message = self.check_port_health(
                process_config['port'], 
                process_config.get('health_endpoint')
            )
            health_data['port_healthy'] = port_healthy
            if not port_healthy:
                health_data['status_message'] += f" | Port: {port_message}"
        
        # Determine overall health
        if health_data['process_running'] and health_data['process_healthy'] and health_data['service_active'] and health_data['port_healthy']:
            health_data['overall_health'] = 'healthy'
        elif health_data['process_running'] or health_data['service_active']:
            health_data['overall_health'] = 'degraded'
        else:
            health_data['overall_health'] = 'unhealthy'
        
        return health_data
    
    def can_restart(self, process_key: str) -> Tuple[bool, str]:
        """Check if we can restart a process (rate limiting)"""
        now = time.time()
        restart_window = self.processes[process_key]['restart_window']
        max_restarts = self.processes[process_key]['max_restarts']
        
        # Initialize tracking if needed
        if process_key not in self.restart_counts:
            self.restart_counts[process_key] = []
            self.restart_windows[process_key] = now
        
        # Clean old restart records
        self.restart_counts[process_key] = [
            restart_time for restart_time in self.restart_counts[process_key]
            if now - restart_time < restart_window
        ]
        
        # Check if we can restart
        if len(self.restart_counts[process_key]) >= max_restarts:
            time_until_reset = restart_window - (now - self.restart_counts[process_key][0])
            return False, f"Rate limited - {time_until_reset:.0f}s until reset"
        
        return True, "Can restart"
    
    async def restart_process(self, process_key: str) -> Tuple[bool, str]:
        """Restart a specific process"""
        try:
            process_config = self.processes[process_key]
            
            # Check if we can restart
            can_restart, restart_message = self.can_restart(process_key)
            if not can_restart:
                return False, restart_message
            
            self.logger.info(f"Restarting {process_key} process...")
            
            # Stop the service
            subprocess.run(['systemctl', 'stop', process_config['service']], timeout=10)
            await asyncio.sleep(2)
            
            # Start the service
            result = subprocess.run(['systemctl', 'start', process_config['service']], timeout=10)
            
            if result.returncode == 0:
                # Record restart
                self.restart_counts[process_key].append(time.time())
                
                # Wait for restart delay
                await asyncio.sleep(process_config['restart_delay'])
                
                return True, f"{process_key} restarted successfully"
            else:
                return False, f"Failed to start service: {result.stderr}"
                
        except Exception as e:
            return False, f"Restart error: {e}"
    
    async def perform_health_check(self) -> Dict:
        """Perform comprehensive health check of all processes"""
        self.logger.info("Performing comprehensive health check...")
        
        health_report = {
            "timestamp": datetime.now().isoformat(),
            "processes": {},
            "overall_status": "healthy",
            "issues": [],
            "recommendations": []
        }
        
        # Check each process
        for process_key in self.processes.keys():
            health_data = await self.check_process_health(process_key)
            health_report["processes"][process_key] = health_data
            
            # Track issues
            if health_data['overall_health'] != 'healthy':
                health_report["issues"].append({
                    "process": process_key,
                    "status": health_data['overall_health'],
                    "message": health_data['status_message']
                })
        
        # Determine overall status
        unhealthy_count = len([p for p in health_report["processes"].values() if p['overall_health'] == 'unhealthy'])
        degraded_count = len([p for p in health_report["processes"].values() if p['overall_health'] == 'degraded'])
        
        if unhealthy_count > 0:
            health_report["overall_status"] = "unhealthy"
        elif degraded_count > 0:
            health_report["overall_status"] = "degraded"
        else:
            health_report["overall_status"] = "healthy"
        
        return health_report
    
    async def handle_issues(self, health_report: Dict):
        """Handle detected issues"""
        try:
            for issue in health_report["issues"]:
                process_key = issue["process"]
                status = issue["status"]
                
                if status == "unhealthy":
                    # Attempt restart
                    restart_success, restart_message = await self.restart_process(process_key)
                    
                    if restart_success:
                        await self.send_notification(
                            f"🔄 **Auto-Recovery: {process_key.title()}**\n\n"
                            f"Process was unhealthy and has been restarted.\n"
                            f"Issue: {issue['message']}",
                            "WARNING"
                        )
                    else:
                        await self.send_notification(
                            f"❌ **Recovery Failed: {process_key.title()}**\n\n"
                            f"Failed to restart process.\n"
                            f"Issue: {issue['message']}\n"
                            f"Error: {restart_message}",
                            "ERROR"
                        )
                elif status == "degraded":
                    # Log warning but don't restart yet
                    self.logger.warning(f"{process_key} is degraded: {issue['message']}")
                    
        except Exception as e:
            self.logger.error(f"Error handling issues: {e}")
    
    async def run_monitoring_loop(self):
        """Main monitoring loop"""
        self.logger.info("Starting Process Watchdog monitoring loop...")
        await self.send_notification("🟢 **Process Watchdog Started**\n\nMonitoring all system components for automatic recovery.")
        
        last_detailed_check = 0
        
        while True:
            try:
                # Perform health check
                health_report = await self.perform_health_check()
                
                # Handle issues
                await self.handle_issues(health_report)
                
                # Detailed check periodically
                now = time.time()
                if now - last_detailed_check > self.detailed_check_interval:
                    # Send detailed status report
                    healthy_count = len([p for p in health_report["processes"].values() if p['overall_health'] == 'healthy'])
                    total_count = len(health_report["processes"])
                    
                    await self.send_notification(
                        f"📊 **System Status Report**\n\n"
                        f"Overall Status: {health_report['overall_status'].upper()}\n"
                        f"Healthy Processes: {healthy_count}/{total_count}\n"
                        f"Issues Detected: {len(health_report['issues'])}",
                        "INFO"
                    )
                    
                    last_detailed_check = now
                
                # Log summary
                self.logger.info(f"Health check complete - Status: {health_report['overall_status']}, "
                               f"Issues: {len(health_report['issues'])}")
                
                # Wait for next check
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(self.check_interval)
    
    async def start(self):
        """Start the watchdog"""
        if await self.initialize():
            await self.run_monitoring_loop()
        else:
            self.logger.error("Failed to initialize watchdog")

async def main():
    """Main entry point"""
    watchdog = ProcessWatchdog()
    await watchdog.start()

if __name__ == "__main__":
    asyncio.run(main())
