# Auto-Update System Guide

## Overview
The Twitter bot includes an automatic update system that pulls changes from the GitHub repository whenever new commits are pushed. This document explains how the system works and how to handle local changes.

## How It Works

1. When you push changes to the GitHub repository, GitHub sends a webhook notification to your VPS.
2. The webhook listener (`webhook_listener.py`) receives this notification and processes it.
3. The system checks for local changes on the VPS before updating.
4. If local changes are detected, they are automatically backed up.
5. The system then forces an update to the latest commit from GitHub.
6. The bot is restarted to apply the changes.

## Local Changes Handling

Previously, the auto-update would fail if there were local changes on the VPS that would conflict with the incoming changes. This would result in a "Git pull failed" error.

The improved system now:

1. Detects local changes using `git status`
2. Creates a backup of modified files in the `local_backups` directory
3. Forces an update using `git fetch` and `git reset --hard`
4. Sends a notification indicating that local changes were backed up

## Recovering Backed-Up Changes

If you need to recover changes that were backed up during an auto-update:

1. Navigate to the `local_backups` directory in your project:
   ```
   cd /root/Twitter-bot/local_backups
   ```

2. Find the backup files, which are named with the original filename and a timestamp:
   ```
   ls -la
   ```

3. Compare the backed-up file with the current version:
   ```
   diff /root/Twitter-bot/local_backups/process_watchdog.py.20251012_123456.bak /root/Twitter-bot/process_watchdog.py
   ```

4. If you want to restore specific changes, you can manually merge them or use the backup file as a reference.

## Best Practices

To avoid conflicts between local changes and repository updates:

1. **Commit Local Changes**: If you make changes directly on the VPS, commit and push them to the repository.
2. **Use Feature Branches**: Make changes in feature branches and merge them to main when ready.
3. **Check Backup Directory**: Periodically check the `local_backups` directory to ensure no important changes are lost.

## Troubleshooting

If you encounter issues with the auto-update system:

1. Check the webhook listener logs:
   ```
   journalctl -u webhook-listener.service -n 100
   ```

2. Verify the webhook is properly configured in GitHub:
   - Go to your repository settings
   - Navigate to Webhooks
   - Ensure the webhook is pointing to `http://your-vps-ip:8080/webhook`
   - Check that the webhook is active and receiving events

3. If updates are still failing, you can manually update the bot:
   ```
   cd /root/Twitter-bot
   git fetch origin main
   git reset --hard origin/main
   systemctl restart twitter-bot.service