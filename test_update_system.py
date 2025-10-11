#!/usr/bin/env python3
"""
Test script for the update system
"""

import asyncio
import subprocess
import psutil
import requests
from datetime import datetime


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


def check_webhook_service():
    """Check if webhook service is running"""
    try:
        result = subprocess.run(
            ["sudo", "systemctl", "is-active", "webhook-listener.service"],
            capture_output=True,
            text=True,
        )
        return result.stdout.strip() == "active"
    except:
        return False


def check_webhook_health():
    """Check webhook health endpoint"""
    try:
        response = requests.get("http://localhost:8080/health", timeout=5)
        return response.status_code == 200
    except:
        return False


def test_git_pull():
    """Test git pull functionality"""
    try:
        result = subprocess.run(
            ["git", "pull", "origin", "main"],
            capture_output=True,
            text=True,
            cwd="/root/Twitter-bot",
        )
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)


def main():
    """Run system tests"""
    print("🧪 Testing Update System Components\n")

    # Test 1: Bot Process
    print("1. 🤖 Bot Process Check:")
    bot_pid = find_bot_process()
    if bot_pid:
        print(f"   ✅ Bot running (PID: {bot_pid})")
    else:
        print("   ❌ Bot not running")

    # Test 2: Webhook Service
    print("\n2. 🔄 Webhook Service Check:")
    service_running = check_webhook_service()
    if service_running:
        print("   ✅ Webhook service is active")
    else:
        print("   ❌ Webhook service is not active")

    # Test 3: Webhook Health
    print("\n3. 🏥 Webhook Health Check:")
    webhook_healthy = check_webhook_health()
    if webhook_healthy:
        print("   ✅ Webhook health endpoint responding")
    else:
        print("   ❌ Webhook health endpoint not responding")

    # Test 4: Git Pull
    print("\n4. 📥 Git Pull Test:")
    success, stdout, stderr = test_git_pull()
    if success:
        if "Already up to date" in stdout:
            print("   ✅ Git pull successful (already up to date)")
        else:
            print("   ✅ Git pull successful (changes pulled)")
    else:
        print(f"   ❌ Git pull failed: {stderr}")

    # Summary
    print("\n📊 Summary:")
    all_good = bot_pid and service_running and webhook_healthy and success
    if all_good:
        print("   🎉 All systems operational!")
    else:
        print("   ⚠️  Some issues detected. Check the webhook setup.")

    print(f"\n📅 Test completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
