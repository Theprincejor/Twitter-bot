#!/usr/bin/env python3
"""
GitHub Webhook Listener for Auto-Updates
"""

import json
import subprocess
import logging
import os
import signal
import psutil
from datetime import datetime
from flask import Flask, request, jsonify
from telegram import Bot
import asyncio

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
TELEGRAM_TOKEN = "8350919686:AAG-VPxwYixmm-wpt0Gih37cx2d9mEoyTj4"
ADMIN_CHAT_ID = "1724099455"  # Replace with your actual user ID
PROJECT_PATH = "/root/Twitter-bot"
WEBHOOK_SECRET = "your-secret-key-here"  # Optional: for security


async def send_telegram_notification(message):
    """Send notification to Telegram admin"""
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        await bot.send_message(chat_id=ADMIN_CHAT_ID, text=message)
    except Exception as e:
        logger.error(f"Failed to send Telegram notification: {e}")


def find_bot_process():
    """Find the running bot process"""
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            cmdline = " ".join(proc.info["cmdline"])
            if proc.info["name"] in ["python", "python3"] and (
                "telegram_bot.py" in cmdline or "main.py" in cmdline
            ):
                return proc.info["pid"]
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


def update_and_restart_bot():
    """Update and restart the bot with local changes backup"""
    try:
        # Check for local changes
        status_result = subprocess.run(
            ["/usr/bin/git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            cwd=PROJECT_PATH,
        )
        
        local_changes = []
        backup_info = ""
        
        # If there are local changes, back them up
        if status_result.stdout.strip():
            logger.info("Local changes detected, creating backups...")
            
            # Create backup directory if it doesn't exist
            backup_dir = os.path.join(PROJECT_PATH, "local_backups")
            os.makedirs(backup_dir, exist_ok=True)
            
            # Parse modified files from git status
            for line in status_result.stdout.strip().split("\n"):
                if line.strip():
                    # Extract filename (works for modified, added, etc.)
                    status_code = line[:2].strip()
                    file_path = line[3:].strip()
                    
                    # Only backup modified files that exist
                    if os.path.exists(os.path.join(PROJECT_PATH, file_path)):
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        backup_filename = f"{file_path}.{timestamp}.bak"
                        backup_path = os.path.join(backup_dir, backup_filename)
                        
                        # Create directory structure if needed
                        os.makedirs(os.path.dirname(backup_path), exist_ok=True)
                        
                        # Copy the file to backup
                        try:
                            subprocess.run(
                                ["cp", os.path.join(PROJECT_PATH, file_path), backup_path],
                                check=True
                            )
                            local_changes.append(file_path)
                            logger.info(f"Backed up {file_path} to {backup_path}")
                        except Exception as e:
                            logger.error(f"Failed to backup {file_path}: {e}")
            
            if local_changes:
                backup_info = f"Local changes were backed up: {', '.join(local_changes[:3])}"
                if len(local_changes) > 3:
                    backup_info += f" and {len(local_changes) - 3} more files"
        
        # Force update using fetch and reset
        fetch_result = subprocess.run(
            ["/usr/bin/git", "fetch", "origin", "main"],
            capture_output=True,
            text=True,
            cwd=PROJECT_PATH,
        )
        
        if fetch_result.returncode != 0:
            return False, "Git fetch failed", fetch_result.stderr
        
        # Get current commit hash before reset
        before_commit = subprocess.run(
            ["/usr/bin/git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=PROJECT_PATH,
        ).stdout.strip()
        
        # Reset to origin/main
        reset_result = subprocess.run(
            ["/usr/bin/git", "reset", "--hard", "origin/main"],
            capture_output=True,
            text=True,
            cwd=PROJECT_PATH,
        )
        
        if reset_result.returncode != 0:
            return False, "Git reset failed", reset_result.stderr
        
        # Get new commit hash after reset
        after_commit = subprocess.run(
            ["/usr/bin/git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=PROJECT_PATH,
        ).stdout.strip()
        
        # If commit hasn't changed, we're already up to date
        if before_commit == after_commit:
            return True, "Bot is already up to date", "Already up to date"
        
        # Get commit log between old and new
        log_result = subprocess.run(
            ["/usr/bin/git", "log", "--oneline", f"{before_commit}..{after_commit}"],
            capture_output=True,
            text=True,
            cwd=PROJECT_PATH,
        )
        
        update_message = log_result.stdout
        
        # Add backup info to the output
        if backup_info:
            update_message = f"{backup_info}\n\n{update_message}"
        
        # Find and kill existing bot process
        bot_pid = find_bot_process()
        if bot_pid:
            os.kill(bot_pid, signal.SIGTERM)
            logger.info(f"Killed bot process {bot_pid}")

        # Wait a moment for process to die
        import time
        time.sleep(2)

        # Start new bot process
        subprocess.Popen(["python3", "telegram_bot.py"], cwd=PROJECT_PATH)
        logger.info("Started new bot process")

        return True, "Bot updated and restarted", update_message
    except Exception as e:
        return False, f"Error during update: {str(e)}", ""


@app.route("/webhook", methods=["POST"])
def github_webhook():
    """Handle GitHub webhook"""
    try:
        # Check Content-Type
        content_type = request.headers.get("Content-Type", "")
        logger.info(f"Received webhook with Content-Type: {content_type}")

        # Get the payload - handle both JSON and form data
        if "application/json" in content_type:
            payload = request.json
        elif "application/x-www-form-urlencoded" in content_type:
            # GitHub sends payload in form data as 'payload' field
            payload_str = request.form.get("payload")
            if payload_str:
                try:
                    payload = json.loads(payload_str)
                except json.JSONDecodeError:
                    payload = None
            else:
                payload = None
        else:
            # Try to parse as JSON anyway
            try:
                payload = request.get_json(force=True)
            except:
                payload = None

        if not payload:
            logger.error(f"No payload received. Content-Type: {content_type}")
            return jsonify(
                {"error": "No payload received", "content_type": content_type}
            ), 400

        # Check if it's a push to main branch
        if (
            payload.get("ref") == "refs/heads/main"
            and payload.get("commits")
            and len(payload["commits"]) > 0
        ):
            logger.info("GitHub push detected, updating bot...")

            # Update the bot
            success, message, output = update_and_restart_bot()

            if success:
                notification = f"🔄 **Bot Auto-Updated!**\n\n"
                notification += f"📝 **Commits:** {len(payload['commits'])}\n"
                notification += f"👤 **Author:** {payload['pusher']['name']}\n"
                
                # Check if local changes were backed up
                if "Local changes were backed up" in output:
                    notification += f"⚠️ **Local changes detected and backed up**\n"
                
                notification += f"📄 **Changes:**\n```\n{output[:300]}\n```"

                # Send notification
                asyncio.run(send_telegram_notification(notification))

                return jsonify(
                    {
                        "status": "success",
                        "message": message,
                        "commits": len(payload["commits"]),
                    }
                )
            else:
                error_msg = f"❌ **Auto-Update Failed**\n\n```\n{output[:300]}\n```"
                asyncio.run(send_telegram_notification(error_msg))

                return jsonify({"status": "error", "message": message}), 500

        return jsonify({"status": "ignored", "message": "Not a main branch push"})

    except Exception as e:
        logger.error(f"Webhook error: {e}")
        error_msg = f"❌ **Webhook Error**\n\n```\n{str(e)}\n```"
        asyncio.run(send_telegram_notification(error_msg))
        return jsonify({"error": str(e)}), 500


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify(
        {
            "status": "healthy",
            "service": "github-webhook-listener",
            "bot_running": find_bot_process() is not None,
        }
    )


@app.route("/status", methods=["GET"])
def webhook_status():
    """Get webhook and bot status"""
    bot_pid = find_bot_process()
    return jsonify(
        {
            "webhook_status": "running",
            "bot_running": bot_pid is not None,
            "bot_pid": bot_pid,
            "project_path": PROJECT_PATH,
        }
    )


if __name__ == "__main__":
    logger.info("Starting GitHub webhook listener...")
    app.run(host="0.0.0.0", port=8080, debug=False)
