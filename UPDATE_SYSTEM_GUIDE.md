# 🚀 Enhanced Update & Restart System

## 📋 Overview

Your Twitter bot now has a comprehensive update and restart system with both manual and automatic capabilities!

## 🎯 Features

### **Interactive Update Menu**
When you use `/update`, you get an interactive menu with options:

- **🔄 Update & Restart Bot** - Pull latest code and restart bot
- **🔄 Restart Bot Only** - Restart without updating
- **🔄 Restart System** - Restart webhook service
- **📋 Check Status** - View system status
- **❌ Cancel** - Cancel operation

### **System Status Monitoring**
The status check shows:
- 🤖 Bot process status and PID
- 🔄 Webhook service status
- 🏥 Webhook health endpoint status
- 📅 Last check timestamp

### **Multiple Restart Options**
- **Bot Restart**: Restarts just the Twitter bot process
- **System Restart**: Restarts the webhook listener service
- **Full Update**: Pulls code + restarts bot

## 🎮 How to Use

### **Via Telegram Commands**
```
/update    - Interactive update menu
/restart   - Quick bot restart
```

### **Via Interactive UI**
1. Send `/start` to get the main menu
2. Click **"System"** → **"Update & Restart"** buttons
3. Choose your action from the options

### **Via GitHub Webhooks**
- Push code to GitHub → Automatic update
- Get Telegram notifications about updates

## 🔧 System Components

### **Files Created/Modified**
- `telegram_bot.py` - Enhanced with update system
- `webhook_listener.py` - GitHub webhook listener
- `webhook-listener.service` - Systemd service
- `setup_webhook.sh` - Automated setup
- `test_update_system.py` - System testing
- `UPDATE_SYSTEM_GUIDE.md` - This guide

### **Service Architecture**
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Telegram Bot  │    │  Webhook Listener│    │  GitHub Webhook │
│                 │    │                  │    │                 │
│ • Manual updates│◄──►│ • Auto-updates   │◄──►│ • Push events   │
│ • Status checks │    │ • Process mgmt   │    │ • Notifications │
│ • System restart│    │ • Health checks  │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## 🚀 Deployment Steps

### **1. Push Changes to GitHub**
```bash
git add .
git commit -m "Add enhanced update & restart system"
git push origin main
```

### **2. Deploy to VPS**
```bash
# SSH to your VPS
ssh root@152.114.193.126

# Navigate to bot directory
cd /root/Twitter-bot

# Pull latest changes
git pull origin main

# Run setup script
chmod +x setup_webhook.sh
./setup_webhook.sh
```

### **3. Configure GitHub Webhook**
1. Go to GitHub repo → Settings → Webhooks
2. Add webhook: `http://152.114.193.126:8080/webhook`
3. Select "Just the push event"

### **4. Test the System**
```bash
# Test all components
python3 test_update_system.py

# Test webhook health
curl http://152.114.193.126:8080/health

# Test manual update via Telegram
/update
```

## 🎯 Usage Examples

### **Scenario 1: Quick Bot Restart**
```
You: /restart
Bot: ✅ Bot restarted successfully!
```

### **Scenario 2: Update with Changes**
```
You: /update → "🔄 Update & Restart Bot"
Bot: ✅ Update Complete
     Bot updated and restarted successfully!
     Changes: [git output]
```

### **Scenario 3: Check System Health**
```
You: /update → "📋 Check Status"
Bot: 📊 System Status
     🤖 Bot Process: 🟢 Running (PID: 1234)
     🔄 Webhook Service: 🟢 Active
     🏥 Webhook Health: 🟢 Healthy
```

### **Scenario 4: Automatic Update**
```
[You push code to GitHub]
GitHub → Webhook → VPS → Bot Update → Telegram Notification
You: 🔄 Bot Auto-Updated!
     📝 Commits: 3
     👤 Author: Your Name
     📄 Changes: [summary]
```

## 🛠️ Management Commands

### **Service Management**
```bash
# Check service status
sudo systemctl status webhook-listener.service

# View logs
sudo journalctl -u webhook-listener.service -f

# Restart service
sudo systemctl restart webhook-listener.service

# Stop service
sudo systemctl stop webhook-listener.service
```

### **Testing Commands**
```bash
# Test system components
python3 test_update_system.py

# Test webhook endpoints
curl http://localhost:8080/health
curl http://localhost:8080/status
```

## 🔍 Troubleshooting

### **Bot Won't Restart**
- Check if process is running: `ps aux | grep python`
- Verify file permissions in `/root/Twitter-bot`
- Check logs: `sudo journalctl -u webhook-listener.service`

### **Webhook Not Working**
- Verify service is active: `sudo systemctl status webhook-listener.service`
- Check port 8080: `sudo netstat -tlnp | grep :8080`
- Test health endpoint: `curl http://localhost:8080/health`

### **Git Pull Fails**
- Check GitHub authentication
- Verify repository permissions
- Test manual git pull: `git pull origin main`

## 🎉 Benefits

✅ **One-Click Updates** - Interactive menu for easy management  
✅ **Automatic Deployment** - GitHub webhooks for hands-off updates  
✅ **System Monitoring** - Real-time status of all components  
✅ **Multiple Restart Types** - Bot, service, or full system restart  
✅ **Error Handling** - Graceful error handling with notifications  
✅ **Health Checks** - Monitor system health and uptime  
✅ **Process Management** - Proper process lifecycle management  

## 🔐 Security Notes

- Webhook endpoint is public (consider adding authentication)
- Service runs as root (consider creating dedicated user)
- Monitor logs for unauthorized access attempts

---

**Your Twitter bot now has enterprise-grade update and restart capabilities!** 🚀

The system is production-ready and will make managing your bot much easier and more reliable.
