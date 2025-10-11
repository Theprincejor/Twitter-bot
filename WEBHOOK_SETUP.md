# GitHub Webhook Auto-Update Setup

This guide will help you set up automatic updates for your Twitter bot using GitHub webhooks.

## 🚀 Quick Setup

### 1. Deploy Files to VPS

Upload the following files to your VPS:
- `webhook_listener.py`
- `webhook-listener.service`
- `setup_webhook.sh`

### 2. Run Setup Script

```bash
# Make setup script executable
chmod +x setup_webhook.sh

# Run the setup script
./setup_webhook.sh
```

### 3. Configure Telegram Admin ID

Edit `webhook_listener.py` and replace `YOUR_TELEGRAM_USER_ID` with your actual Telegram user ID:

```python
ADMIN_CHAT_ID = "123456789"  # Your actual Telegram user ID
```

### 4. Configure GitHub Webhook

1. Go to your GitHub repository
2. Click **Settings** → **Webhooks**
3. Click **Add webhook**
4. Fill in the details:
   - **Payload URL**: `http://152.114.193.126:8080/webhook`
   - **Content type**: `application/json`
   - **Events**: Select "Just the push event"
   - **Active**: ✅ Checked
5. Click **Add webhook**

## 🎯 Features

### Manual Updates (Telegram Commands)
- `/update` - Pull latest code and restart bot
- `/restart` - Restart bot without updating

### Automatic Updates (GitHub Webhook)
- Automatically pulls code when you push to GitHub
- Kills old bot process and starts new one
- Sends Telegram notifications about updates
- Handles errors gracefully

### Webhook Endpoints
- `http://152.114.193.126:8080/webhook` - GitHub webhook endpoint
- `http://152.114.193.126:8080/health` - Health check
- `http://152.114.193.126:8080/status` - Detailed status

## 🔧 Management Commands

### Check Service Status
```bash
sudo systemctl status webhook-listener.service
```

### View Logs
```bash
sudo journalctl -u webhook-listener.service -f
```

### Restart Service
```bash
sudo systemctl restart webhook-listener.service
```

### Stop Service
```bash
sudo systemctl stop webhook-listener.service
```

## 🧪 Testing

### Test Webhook Health
```bash
curl http://152.114.193.126:8080/health
```

### Test Webhook Status
```bash
curl http://152.114.193.126:8080/status
```

### Test Manual Update
Send `/update` to your Telegram bot

## 📱 Telegram Notifications

You'll receive notifications for:
- ✅ Successful auto-updates
- ❌ Failed updates
- 🔄 Webhook errors
- 📋 Repository checks

## 🛠️ Troubleshooting

### Service Won't Start
```bash
# Check logs
sudo journalctl -u webhook-listener.service

# Check if port 8080 is available
sudo netstat -tlnp | grep :8080
```

### Webhook Not Working
1. Check if service is running: `sudo systemctl status webhook-listener.service`
2. Check GitHub webhook configuration
3. Verify firewall allows port 8080
4. Check logs for errors

### Bot Not Restarting
1. Check if bot process is found: `ps aux | grep python`
2. Verify file permissions
3. Check project path in `webhook_listener.py`

## 🔒 Security Notes

- The webhook endpoint is public (no authentication)
- Consider adding IP restrictions or webhook secret verification
- Monitor logs for unauthorized access attempts

## 📝 Configuration

Key settings in `webhook_listener.py`:
- `TELEGRAM_TOKEN` - Your bot token
- `ADMIN_CHAT_ID` - Your Telegram user ID
- `PROJECT_PATH` - Path to your bot directory
- `WEBHOOK_SECRET` - Optional webhook secret (not implemented)

## 🎉 You're All Set!

Now every time you push code to GitHub:
1. GitHub sends webhook to your VPS
2. Webhook listener pulls latest code
3. Bot process is restarted
4. You get a Telegram notification

You can also manually update using `/update` or `/restart` commands in Telegram!
