#!/usr/bin/env python3
"""
Setup script for Twitter Bot System
"""

import os
import sys
import subprocess
from pathlib import Path


def create_directories():
    """Create necessary directories"""
    directories = ["data", "data/cookies", "logs"]

    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"✅ Created directory: {directory}")


def create_env_file():
    """Create .env file from template"""
    if os.path.exists(".env"):
        print("⚠️  .env file already exists, skipping creation")
        return

    if os.path.exists("env.example"):
        import shutil

        shutil.copy("env.example", ".env")
        print("✅ Created .env file from template")
        print("📝 Please edit .env file with your configuration")
    else:
        print("❌ env.example file not found")


def install_dependencies():
    """Install Python dependencies"""
    try:
        print("📦 Installing dependencies...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"]
        )
        print("✅ Dependencies installed successfully")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False
    return True


def main():
    """Main setup function"""
    print("🚀 Setting up Twitter Bot System...\n")

    # Create directories
    print("📁 Creating directories...")
    create_directories()

    # Create .env file
    print("\n⚙️  Setting up configuration...")
    create_env_file()

    # Install dependencies
    print("\n📦 Installing dependencies...")
    if install_dependencies():
        print("\n🎉 Setup completed successfully!")
        print("\n📋 Next Steps:")
        print("1. Edit .env file with your Telegram bot token and admin IDs")
        print("2. Run test: python test_system.py")
        print("3. Start the system: python main.py")
    else:
        print("\n❌ Setup failed. Please check the errors above.")


if __name__ == "__main__":
    main()
