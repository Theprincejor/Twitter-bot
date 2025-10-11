#!/bin/bash
# Setup script for GitHub webhook listener

echo "🔧 Setting up GitHub Webhook Listener..."

# Install required dependencies
echo "📦 Installing dependencies..."
pip install flask psutil

# Copy service file to systemd
echo "⚙️ Setting up systemd service..."
sudo cp webhook-listener.service /etc/systemd/system/

# Reload systemd and enable service
sudo systemctl daemon-reload
sudo systemctl enable webhook-listener.service

# Start the webhook service
echo "🚀 Starting webhook listener service..."
sudo systemctl start webhook-listener.service

# Check status
echo "📊 Checking service status..."
sudo systemctl status webhook-listener.service --no-pager

echo ""
echo "✅ Webhook listener setup complete!"
echo ""
echo "📋 Next steps:"
echo "1. Update ADMIN_CHAT_ID in webhook_listener.py with your Telegram user ID"
echo "2. Configure GitHub webhook:"
echo "   - Go to your GitHub repo → Settings → Webhooks"
echo "   - Add webhook URL: http://152.114.193.126:8080/webhook"
echo "   - Select 'Just the push event'"
echo "3. Test with: curl http://152.114.193.126:8080/health"
echo ""
echo "🎯 Available endpoints:"
echo "   - /webhook - GitHub webhook endpoint"
echo "   - /health - Health check"
echo "   - /status - Detailed status"
echo ""
echo "🧪 Test the system:"
echo "   - python test_update_system.py"
