#!/bin/bash

# Enhanced Setup Script for Twitter Bot Auto-Management System
# This script sets up complete self-managing infrastructure

set -e

echo "🚀 Setting up Twitter Bot Auto-Management System..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_DIR="/root/Twitter-bot"
SERVICE_DIR="/etc/systemd/system"

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    print_error "Please run as root (use sudo)"
    exit 1
fi

# Check if project directory exists
if [ ! -d "$PROJECT_DIR" ]; then
    print_error "Project directory $PROJECT_DIR not found!"
    exit 1
fi

cd "$PROJECT_DIR"

print_status "Installing system dependencies..."

# Install required packages
apt update
apt install -y python3-pip python3-venv curl wget git htop

# Install Python dependencies
print_status "Installing Python dependencies..."
pip3 install -r requirements.txt

# Install additional monitoring dependencies
pip3 install psutil requests

print_status "Setting up systemd services..."

# Stop existing services if running
systemctl stop twitter-bot.service 2>/dev/null || true
systemctl stop health-monitor.service 2>/dev/null || true
systemctl stop auth-monitor.service 2>/dev/null || true
systemctl stop process-watchdog.service 2>/dev/null || true
systemctl stop webhook-listener.service 2>/dev/null || true

# Copy service files
cp twitter-bot.service "$SERVICE_DIR/"
cp health-monitor.service "$SERVICE_DIR/"
cp auth-monitor.service "$SERVICE_DIR/"
cp process-watchdog.service "$SERVICE_DIR/"
cp webhook-listener.service "$SERVICE_DIR/"

# Reload systemd
systemctl daemon-reload

# Enable services
systemctl enable twitter-bot.service
systemctl enable health-monitor.service
systemctl enable auth-monitor.service
systemctl enable process-watchdog.service
systemctl enable webhook-listener.service

print_status "Configuring file permissions..."

# Set proper permissions
chmod +x main.py
chmod +x telegram_bot.py
chmod +x health_monitor.py
chmod +x auth_monitor.py
chmod +x process_watchdog.py
chmod +x webhook_listener.py

# Ensure log directory exists
mkdir -p logs
chmod 755 logs

# Ensure data directory exists
mkdir -p data
chmod 755 data

print_status "Setting up log rotation..."

# Create logrotate configuration
cat > /etc/logrotate.d/twitter-bot << EOF
$PROJECT_DIR/logs/*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 644 root root
    postrotate
        systemctl reload twitter-bot.service 2>/dev/null || true
        systemctl reload health-monitor.service 2>/dev/null || true
    endscript
}
EOF

print_status "Creating startup script..."

# Create startup script
cat > /root/start-twitter-bot.sh << 'EOF'
#!/bin/bash

echo "🚀 Starting Twitter Bot Auto-Management System..."

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

echo "✅ All services started!"
echo ""
echo "Service Status:"
systemctl status webhook-listener.service --no-pager -l
echo ""
systemctl status twitter-bot.service --no-pager -l
echo ""
systemctl status health-monitor.service --no-pager -l
echo ""
systemctl status auth-monitor.service --no-pager -l
echo ""
systemctl status process-watchdog.service --no-pager -l
EOF

chmod +x /root/start-twitter-bot.sh

print_status "Creating stop script..."

# Create stop script
cat > /root/stop-twitter-bot.sh << 'EOF'
#!/bin/bash

echo "🛑 Stopping Twitter Bot Auto-Management System..."

systemctl stop process-watchdog.service
systemctl stop auth-monitor.service
systemctl stop health-monitor.service
systemctl stop twitter-bot.service
systemctl stop webhook-listener.service

echo "✅ All services stopped!"
EOF

chmod +x /root/stop-twitter-bot.sh

print_status "Creating status script..."

# Create status script
cat > /root/twitter-bot-status.sh << 'EOF'
#!/bin/bash

echo "📊 Twitter Bot System Status"
echo "=============================="
echo ""

echo "🔧 Service Status:"
systemctl is-active webhook-listener.service && echo "  ✅ Webhook Listener: Active" || echo "  ❌ Webhook Listener: Inactive"
systemctl is-active twitter-bot.service && echo "  ✅ Twitter Bot: Active" || echo "  ❌ Twitter Bot: Inactive"
systemctl is-active health-monitor.service && echo "  ✅ Health Monitor: Active" || echo "  ❌ Health Monitor: Inactive"
systemctl is-active auth-monitor.service && echo "  ✅ Auth Monitor: Active" || echo "  ❌ Auth Monitor: Inactive"
systemctl is-active process-watchdog.service && echo "  ✅ Process Watchdog: Active" || echo "  ❌ Process Watchdog: Inactive"
echo ""

echo "🖥️  Process Status:"
ps aux | grep -E "(webhook_listener|telegram_bot|health_monitor|auth_monitor|process_watchdog)" | grep -v grep || echo "  No processes found"
echo ""

echo "🌐 Webhook Endpoints:"
curl -s http://localhost:8080/health >/dev/null && echo "  ✅ Webhook Health: OK" || echo "  ❌ Webhook Health: Failed"
echo ""

echo "💾 System Resources:"
echo "  CPU: $(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)%"
echo "  Memory: $(free | grep Mem | awk '{printf "%.1f%%", $3/$2 * 100.0}')"
echo "  Disk: $(df -h / | awk 'NR==2{printf "%s", $5}')"
echo ""

echo "📝 Recent Logs (last 5 lines):"
echo "Twitter Bot:"
journalctl -u twitter-bot.service -n 5 --no-pager | tail -5
echo ""
echo "Health Monitor:"
journalctl -u health-monitor.service -n 5 --no-pager | tail -5
echo ""
echo "Auth Monitor:"
journalctl -u auth-monitor.service -n 5 --no-pager | tail -5
echo ""
echo "Process Watchdog:"
journalctl -u process-watchdog.service -n 5 --no-pager | tail -5
EOF

chmod +x /root/twitter-bot-status.sh

print_status "Setting up firewall rules..."

# Configure firewall for webhook
ufw allow 8080/tcp comment "Twitter Bot Webhook"
ufw --force enable

print_status "Testing system components..."

# Test Python imports
python3 -c "import telegram; print('✅ Telegram: OK')" || print_warning "Telegram import failed"
python3 -c "import psutil; print('✅ PSUtil: OK')" || print_warning "PSUtil import failed"
python3 -c "import requests; print('✅ Requests: OK')" || print_warning "Requests import failed"

print_status "Starting services..."

# Start services
systemctl start webhook-listener.service
sleep 3
systemctl start twitter-bot.service
sleep 3
systemctl start health-monitor.service
sleep 3
systemctl start auth-monitor.service
sleep 3
systemctl start process-watchdog.service

print_status "Verifying services..."

# Check service status
sleep 5

if systemctl is-active --quiet webhook-listener.service; then
    print_success "Webhook Listener: Active"
else
    print_error "Webhook Listener: Failed to start"
fi

if systemctl is-active --quiet twitter-bot.service; then
    print_success "Twitter Bot: Active"
else
    print_error "Twitter Bot: Failed to start"
fi

if systemctl is-active --quiet health-monitor.service; then
    print_success "Health Monitor: Active"
else
    print_error "Health Monitor: Failed to start"
fi

if systemctl is-active --quiet auth-monitor.service; then
    print_success "Auth Monitor: Active"
else
    print_error "Auth Monitor: Failed to start"
fi

if systemctl is-active --quiet process-watchdog.service; then
    print_success "Process Watchdog: Active"
else
    print_error "Process Watchdog: Failed to start"
fi

print_status "Testing webhook endpoint..."

# Test webhook health
sleep 2
if curl -s http://localhost:8080/health >/dev/null; then
    print_success "Webhook Health Check: OK"
else
    print_warning "Webhook Health Check: Failed (may need time to start)"
fi

echo ""
echo "🎉 Setup Complete!"
echo "=================="
echo ""
echo "📋 Management Commands:"
echo "  Start:   /root/start-twitter-bot.sh"
echo "  Stop:    /root/stop-twitter-bot.sh"
echo "  Status:  /root/twitter-bot-status.sh"
echo ""
echo "🔧 Service Commands:"
echo "  systemctl status twitter-bot.service"
echo "  systemctl status health-monitor.service"
echo "  systemctl status webhook-listener.service"
echo ""
echo "📊 Monitoring:"
echo "  journalctl -u twitter-bot.service -f"
echo "  journalctl -u health-monitor.service -f"
echo "  journalctl -u webhook-listener.service -f"
echo ""
echo "🌐 Webhook Endpoints:"
echo "  Health: http://$(curl -s ifconfig.me):8080/health"
echo "  Status: http://$(curl -s ifconfig.me):8080/status"
echo ""
echo "📱 Telegram Commands:"
echo "  /update  - Update and restart bot"
echo "  /restart - Restart bot"
echo "  /status  - Check system status"
echo ""
print_success "Your Twitter Bot is now fully self-managing!"
print_warning "Remember to configure your Telegram admin ID in config.py"
print_warning "Remember to set up GitHub webhook: http://$(curl -s ifconfig.me):8080/webhook"
