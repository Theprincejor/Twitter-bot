"""
Database management with JSON file storage and encryption
"""

import json
import os
import base64
from typing import Dict, List, Any, Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import logging
from config import Config
from database_initializer import initialize_database


class Database:
    """Database manager for storing bot data with encryption"""

    def __init__(self, db_path: str = None, encryption_key: str = None):
        self.db_path = db_path or Config.DATABASE_PATH
        self.encryption_key = encryption_key or Config.ENCRYPTION_KEY
        self.logger = logging.getLogger(__name__)

        # Ensure data directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        # Initialize encryption
        self.cipher = self._init_encryption()

        # Initialize database
        self._init_database()

    def _init_encryption(self) -> Fernet:
        """Initialize encryption cipher"""
        try:
            # Generate key from password using PBKDF2
            password = self.encryption_key.encode()
            salt = b"twitter_bot_salt"  # In production, use random salt
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(password))
            return Fernet(key)
        except Exception as e:
            self.logger.error(f"Failed to initialize encryption: {e}")
            raise

    def _init_database(self):
        """Initialize database with default structure"""
        # Use the database initializer to ensure the database file is valid
        if not os.path.exists(self.db_path) or os.path.getsize(self.db_path) == 0:
            self.logger.info("Database file doesn't exist or is empty. Creating new database.")
            default_data = {
                "bots": {},
                "users_pool": {},
                "tasks": [],
                "settings": {
                    "mutual_following": True,
                    "auto_engagement": True,
                    "created_at": None,
                },
                "statistics": {
                    "total_likes": 0,
                    "total_comments": 0,
                    "total_retweets": 0,
                    "total_quotes": 0,
                    "last_updated": None,
                },
            }
            self._write_data(default_data)
        else:
            # Check if the database file is valid
            try:
                with open(self.db_path, "rb") as f:
                    encrypted_data = f.read()
                if encrypted_data:
                    # Try to decrypt and parse the data to validate
                    decrypted = self.cipher.decrypt(encrypted_data)
                    json.loads(decrypted)  # Validate JSON structure
                    self.logger.debug("Database file validated successfully")
            except Exception as e:
                # Only treat as corrupted if there's an actual error (not empty)
                error_msg = str(e)
                if error_msg and error_msg.strip():
                    self.logger.error(f"Database file is corrupted: {e}")
                    self.logger.info("Initializing database with default structure")
                    # Create a backup of the corrupted file
                    backup_path = f"{self.db_path}.corrupted"
                    try:
                        os.rename(self.db_path, backup_path)
                        self.logger.info(f"Corrupted database backed up to {backup_path}")
                    except Exception as backup_error:
                        self.logger.error(f"Failed to backup corrupted database: {backup_error}")
                
                # Initialize with default data
                default_data = {
                    "bots": {},
                    "users_pool": {},
                    "tasks": [],
                    "settings": {
                        "mutual_following": True,
                        "auto_engagement": True,
                        "created_at": None,
                    },
                    "statistics": {
                        "total_likes": 0,
                        "total_comments": 0,
                        "total_retweets": 0,
                        "total_quotes": 0,
                        "last_updated": None,
                    },
                }
                self._write_data(default_data)

    def _read_data(self) -> Dict[str, Any]:
        """Read and decrypt database data"""
        try:
            if not os.path.exists(self.db_path):
                self.logger.warning("Database file doesn't exist. Creating new database.")
                self._init_database()
                return {}

            with open(self.db_path, "rb") as f:
                encrypted_data = f.read()

            if not encrypted_data:
                self.logger.warning("Database file is empty. Initializing with default structure.")
                self._init_database()
                return {}

            try:
                decrypted_data = self.cipher.decrypt(encrypted_data)
                try:
                    return json.loads(decrypted_data.decode())
                except json.JSONDecodeError as json_error:
                    self.logger.error(f"JSON parsing error: {json_error}")
                    
                    # Check if it's the specific error we're looking for
                    if "Expecting value: line 1 column 1 (char 0)" in str(json_error):
                        self.logger.warning("Database file contains invalid JSON. Initializing with default structure.")
                        
                        # Create a backup of the corrupted file
                        backup_path = f"{self.db_path}.json_error"
                        try:
                            os.rename(self.db_path, backup_path)
                            self.logger.info(f"Corrupted database backed up to {backup_path}")
                        except Exception as backup_error:
                            self.logger.error(f"Failed to backup corrupted database: {backup_error}")
                        
                        # Initialize with default structure
                        self._init_database()
                    
                    return {}
            except Exception as decrypt_error:
                self.logger.error(f"Failed to decrypt database: {decrypt_error}")
                self.logger.warning("Database file is corrupted. Initializing with default structure.")
                
                # Create a backup of the corrupted file
                backup_path = f"{self.db_path}.decrypt_error"
                try:
                    os.rename(self.db_path, backup_path)
                    self.logger.info(f"Corrupted database backed up to {backup_path}")
                except Exception as backup_error:
                    self.logger.error(f"Failed to backup corrupted database: {backup_error}")
                
                # Initialize with default structure
                self._init_database()
                return {}

        except Exception as e:
            self.logger.error(f"Failed to read database: {e}")
            
            # Check if it's the specific error we're looking for
            if "Expecting value: line 1 column 1 (char 0)" in str(e):
                self.logger.warning("Database file contains invalid JSON. Initializing with default structure.")
                
                # Create a backup of the corrupted file
                backup_path = f"{self.db_path}.error"
                try:
                    os.rename(self.db_path, backup_path)
                    self.logger.info(f"Corrupted database backed up to {backup_path}")
                except Exception as backup_error:
                    self.logger.error(f"Failed to backup corrupted database: {backup_error}")
                
                # Initialize with default structure
                self._init_database()
            
            return {}

    def _write_data(self, data: Dict[str, Any]):
        """Encrypt and write database data"""
        try:
            json_data = json.dumps(data, indent=2)
            encrypted_data = self.cipher.encrypt(json_data.encode())

            with open(self.db_path, "wb") as f:
                f.write(encrypted_data)

            self.logger.debug("Database updated successfully")

        except Exception as e:
            self.logger.error(f"Failed to write database: {e}")
            raise

    # Bot Management Methods
    def add_bot(self, bot_id: str, cookie_data: Dict[str, Any]) -> bool:
        """Add a new bot to the database"""
        try:
            data = self._read_data()

            # Ensure bots key exists
            if "bots" not in data:
                data["bots"] = {}

            bot_info = {
                "id": bot_id,
                "cookie_data": cookie_data,
                "status": "active",
                "added_at": None,  # Will be set by caller
                "last_activity": None,
                "rate_limited_until": None,
                "captcha_required": False,
                "stats": {
                    "likes": 0,
                    "comments": 0,
                    "retweets": 0,
                    "quotes": 0,
                    "follows": 0,
                },
            }

            data["bots"][bot_id] = bot_info
            self._write_data(data)

            self.logger.info(f"Bot {bot_id} added successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to add bot {bot_id}: {e}")
            return False

    def remove_bot(self, bot_id: str) -> bool:
        """Remove a bot from the database"""
        try:
            data = self._read_data()
            if bot_id in data["bots"]:
                del data["bots"][bot_id]
                self._write_data(data)
                self.logger.info(f"Bot {bot_id} removed successfully")
                return True
            return False

        except Exception as e:
            self.logger.error(f"Failed to remove bot {bot_id}: {e}")
            return False

    def get_bot(self, bot_id: str) -> Optional[Dict[str, Any]]:
        """Get bot information"""
        data = self._read_data()
        return data.get("bots", {}).get(bot_id)

    def get_all_bots(self) -> Dict[str, Any]:
        """Get all bots"""
        data = self._read_data()
        return data.get("bots", {})

    def update_bot_status(self, bot_id: str, status: str, **kwargs) -> bool:
        """Update bot status and other properties"""
        try:
            data = self._read_data()
            if bot_id in data["bots"]:
                bot = data["bots"][bot_id]
                bot["status"] = status

                for key, value in kwargs.items():
                    bot[key] = value

                self._write_data(data)
                return True
            return False

        except Exception as e:
            self.logger.error(f"Failed to update bot {bot_id} status: {e}")
            return False

    # User Pool Management
    def add_users_to_pool(self, keyword: str, users: List[str]) -> bool:
        """Add users to the pool for a keyword"""
        try:
            data = self._read_data()
            if "users_pool" not in data:
                data["users_pool"] = {}

            if keyword not in data["users_pool"]:
                data["users_pool"][keyword] = {
                    "users": [],
                    "used_users": [],
                    "created_at": None,
                }

            # Add new users that aren't already used
            pool = data["users_pool"][keyword]
            for user in users:
                if user not in pool["users"] and user not in pool["used_users"]:
                    pool["users"].append(user)

            self._write_data(data)
            return True

        except Exception as e:
            self.logger.error(f"Failed to add users to pool for {keyword}: {e}")
            return False

    def get_users_from_pool(self, keyword: str, count: int = 3) -> List[str]:
        """Get users from pool for a keyword"""
        try:
            data = self._read_data()
            if keyword not in data.get("users_pool", {}):
                return []

            pool = data["users_pool"][keyword]
            available_users = pool["users"][:count]

            if available_users:
                # Move users from available to used
                for user in available_users:
                    pool["users"].remove(user)
                    pool["used_users"].append(user)

                self._write_data(data)

            return available_users

        except Exception as e:
            self.logger.error(f"Failed to get users from pool for {keyword}: {e}")
            return []

    # Task Management
    def add_task(self, task: Dict[str, Any]) -> bool:
        """Add a new task to the queue"""
        try:
            data = self._read_data()
            if "tasks" not in data:
                data["tasks"] = []

            task["id"] = len(data["tasks"]) + 1
            task["created_at"] = None  # Will be set by caller
            data["tasks"].append(task)

            self._write_data(data)
            return True

        except Exception as e:
            self.logger.error(f"Failed to add task: {e}")
            return False

    def get_pending_tasks(self) -> List[Dict[str, Any]]:
        """Get all pending tasks"""
        data = self._read_data()
        tasks = data.get("tasks", [])
        return [task for task in tasks if task.get("status") != "completed"]

    def update_task_status(self, task_id: int, status: str) -> bool:
        """Update task status"""
        try:
            data = self._read_data()
            tasks = data.get("tasks", [])

            for task in tasks:
                if task.get("id") == task_id:
                    task["status"] = status
                    task["updated_at"] = None  # Will be set by caller
                    break

            self._write_data(data)
            return True

        except Exception as e:
            self.logger.error(f"Failed to update task {task_id}: {e}")
            return False

    # Statistics
    def update_statistics(self, action: str, count: int = 1) -> bool:
        """Update global statistics"""
        try:
            data = self._read_data()
            if "statistics" not in data:
                data["statistics"] = {
                    "total_likes": 0,
                    "total_comments": 0,
                    "total_retweets": 0,
                    "total_quotes": 0,
                    "last_updated": None,
                }

            stats = data["statistics"]
            if action in stats:
                stats[action] += count
                stats["last_updated"] = None  # Will be set by caller

            self._write_data(data)
            return True

        except Exception as e:
            self.logger.error(f"Failed to update statistics for {action}: {e}")
            return False

    def get_statistics(self) -> Dict[str, Any]:
        """Get global statistics"""
        data = self._read_data()
        return data.get("statistics", {})

    # Generic accessors used by other modules
    def get_all_data(self) -> Dict[str, Any]:
        """Return the entire decrypted database content."""
        return self._read_data()

    def set_data(self, key: str, value: Any) -> bool:
        """Set a top-level key in the database and persist changes."""
        try:
            data = self._read_data()
            data[key] = value
            self._write_data(data)
            return True
        except Exception as e:
            self.logger.error(f"Failed to set data for key '{key}': {e}")
            return False

    def backup_database(self, backup_path: str = None) -> bool:
        """Create a backup of the database"""
        try:
            if not backup_path:
                backup_path = f"{self.db_path}.backup"

            data = self._read_data()
            with open(backup_path, "w") as f:
                json.dump(data, f, indent=2)

            self.logger.info(f"Database backed up to {backup_path}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to backup database: {e}")
            return False
