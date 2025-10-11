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
            if proc.info["name"] == "python" and "main.py" in " ".join(
                proc.info["cmdline"]
            ):
                return proc.info["pid"]
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


def update_and_restart_bot():
    """Update and restart the bot"""
    try:
        # Pull latest changes
        result = subprocess.run(
            ["git", "pull", "origin", "main"],
            capture_output=True,
            text=True,
            cwd=PROJECT_PATH,
        )

        if result.returncode == 0:
            if "Already up to date" in result.stdout:
                return True, "Bot is already up to date", result.stdout

            # Find and kill existing bot process
            bot_pid = find_bot_process()
            if bot_pid:
                os.kill(bot_pid, signal.SIGTERM)
                logger.info(f"Killed bot process {bot_pid}")

            # Wait a moment for process to die
            import time

            time.sleep(2)

            # Start new bot process
            subprocess.Popen(["python", "main.py"], cwd=PROJECT_PATH)
            logger.info("Started new bot process")

            return True, "Bot updated and restarted", result.stdout
        else:
            return False, "Git pull failed", result.stderr

    except Exception as e:
        return False, f"Error during update: {str(e)}", ""


@app.route("/webhook", methods=["POST"])
def github_webhook():
    """Handle GitHub webhook"""
    try:
        # Get the payload
        payload = request.json

        if not payload:
            return jsonify({"error": "No payload received"}), 400

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
                if "already up to date" in message.lower():
                    notification = (
                        "📋 **Repository Check**\n\n✅ Bot is already up to date!"
                    )
                else:
                    notification = f"🔄 **Bot Auto-Updated!**\n\n"
                    notification += f"📝 **Commits:** {len(payload['commits'])}\n"
                    notification += f"👤 **Author:** {payload['pusher']['name']}\n"
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
