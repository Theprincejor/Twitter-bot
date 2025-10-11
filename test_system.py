#!/usr/bin/env python3
"""
Test script for Twitter Bot System
"""

import asyncio
import sys
import os
from pathlib import Path

# Add current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from config import Config
from database import Database
from logger import bot_logger


async def test_system():
    """Test basic system functionality"""
    print("Testing Twitter Bot System...")

    # Test 1: Configuration
    print("\n1. Testing configuration...")
    config_status = Config.validate_config()
    if config_status["valid"]:
        print("Configuration is valid")
    else:
        print(f"Configuration issues: {config_status['issues']}")

    # Test 2: Database
    print("\n2. Testing database...")
    try:
        db = Database()
        print("Database initialized successfully")

        # Test adding a mock bot
        test_bot_data = {"auth_token": "test_token", "ct0": "test_ct0"}

        success = db.add_bot("test_bot_1", test_bot_data)
        if success:
            print("Bot added to database successfully")

            # Test retrieving bot
            bot_info = db.get_bot("test_bot_1")
            if bot_info:
                print("Bot retrieved from database successfully")
            else:
                print("Failed to retrieve bot from database")
        else:
            print("Failed to add bot to database")

    except Exception as e:
        print(f"Database test failed: {e}")

    # Test 3: Logger
    print("\n3. Testing logger...")
    try:
        bot_logger.info("Test log message")
        print("Logger initialized successfully")
    except Exception as e:
        print(f"Logger test failed: {e}")

    # Test 4: Directory structure
    print("\n4. Testing directory structure...")
    required_dirs = ["data", "data/cookies", "logs"]
    all_exist = True

    for dir_path in required_dirs:
        if os.path.exists(dir_path):
            print(f"Directory exists: {dir_path}")
        else:
            print(f"Directory missing: {dir_path}")
            all_exist = False

    if all_exist:
        print("All required directories exist")

    print("\nSystem test completed!")

    # Show next steps
    print("\nNext Steps:")
    print("1. Copy env.example to .env and configure your settings")
    print("2. Install dependencies: pip install -r requirements.txt")
    print("3. Add your Telegram bot token and admin IDs to .env")
    print("4. Run the system: python main.py")


if __name__ == "__main__":
    asyncio.run(test_system())
