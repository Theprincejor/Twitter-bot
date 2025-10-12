#!/bin/bash

# Quick Deployment Script for Self-Management System
# Run this on your VPS to deploy the complete self-management system

echo "🚀 Deploying Twitter Bot Self-Management System..."

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run as root (use sudo)"
    exit 1
fi

# Navigate to project directory
cd /root/Twitter-bot

echo "📦 Installing dependencies..."
pip3 install psutil requests

echo "🔧 Setting up services..."

# Stop existing services
systemctl stop twitter-bot.service 2>/dev/null || true
systemctl stop health-monitor.service 2>/dev/null || true
systemctl stop auth-monitor.service 2>/dev/null || true
systemctl stop process-watchdog.service 2>/dev/null || true
systemctl stop webhook-listener.service 2>/dev/null || true

# Copy service files
cp twitter-bot.service /etc/systemd/system/
cp health-monitor.service /etc/systemd/system/
cp auth-monitor.service /etc/systemd/system/
cp process-watchdog.service /etc/systemd/system/
cp webhook-listener.service /etc/systemd/system/

# Reload systemd
systemctl daemon-reload

# Enable services
systemctl enable twitter-bot.service
systemctl enable health-monitor.service
systemctl enable auth-monitor.service
systemctl enable process-watchdog.service
systemctl enable webhook-listener.service

# Set permissions
chmod +x main.py
chmod +x telegram_bot.py
chmod +x health_monitor.py
chmod +x auth_monitor.py
chmod +x process_watchdog.py
chmod +x webhook_listener.py

echo "🚀 Starting services..."

# Start services in order
systemctl start webhook-listener.service
sleep 2
systemctl start twitter-bot.service
sleep 2
systemctl start health-monitor.service
sleep 2
systemctl start auth-monitor.service
sleep 2
systemctl start process-watchdog.service

echo "✅ Deployment complete!"
echo ""
echo "📊 Service Status:"
systemctl is-active webhook-listener.service && echo "  ✅ Webhook Listener: Active" || echo "  ❌ Webhook Listener: Inactive"
systemctl is-active twitter-bot.service && echo "  ✅ Twitter Bot: Active" || echo "  ❌ Twitter Bot: Inactive"
systemctl is-active health-monitor.service && echo "  ✅ Health Monitor: Active" || echo "  ❌ Health Monitor: Inactive"
systemctl is-active auth-monitor.service && echo "  ✅ Auth Monitor: Active" || echo "  ❌ Auth Monitor: Inactive"
systemctl is-active process-watchdog.service && echo "  ✅ Process Watchdog: Active" || echo "  ❌ Process Watchdog: Inactive"

echo ""
echo "🎉 Your Twitter bot is now fully self-managing!"
echo ""
echo "📱 Try these Telegram commands:"
echo "  /status - Check system status"
echo "  /listbots - List all bots"
echo "  /update - Update and restart"
echo ""
echo "🔧 Management commands:"
echo "  systemctl status twitter-bot.service"
echo "  journalctl -u twitter-bot.service -f"
echo "  /root/twitter-bot-status.sh"
