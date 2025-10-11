#!/usr/bin/env python3
"""
Test script for Telegram notifications
"""

import asyncio
from telegram import Bot

# Configuration
TELEGRAM_TOKEN = "8350919686:AAG-VPxwYixmm-wpt0Gih37cx2d9mEoyTj4"
ADMIN_CHAT_ID = "1724099455"

async def test_notification():
    """Test sending a notification to Telegram"""
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        
        # Test message
        message = "🧪 **Webhook Test**\n\n✅ Notification system is working!\n\nThis is a test from your VPS webhook listener."
        
        # Send the message
        await bot.send_message(chat_id=ADMIN_CHAT_ID, text=message)
        print("✅ Test notification sent successfully!")
        
    except Exception as e:
        print(f"❌ Failed to send notification: {e}")

if __name__ == "__main__":
    asyncio.run(test_notification())
