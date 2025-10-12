#!/usr/bin/env python3
"""
Database Initializer Script
Ensures the database.json file exists and has a valid structure
"""

import json
import os
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Default database structure
DEFAULT_DB_STRUCTURE = {
    "users": {},
    "settings": {},
    "stats": {},
    "last_update": None
}

def initialize_database(db_path="data/database.json"):
    """
    Initialize the database file if it doesn't exist or is invalid
    
    Args:
        db_path (str): Path to the database file
    
    Returns:
        bool: True if initialization was successful, False otherwise
    """
    try:
        # Get absolute path
        db_path = os.path.abspath(db_path)
        db_dir = os.path.dirname(db_path)
        
        # Ensure directory exists
        if not os.path.exists(db_dir):
            logger.info(f"Creating database directory: {db_dir}")
            os.makedirs(db_dir, exist_ok=True)
        
        # Check if file exists and is valid JSON
        if os.path.exists(db_path) and os.path.getsize(db_path) > 0:
            try:
                with open(db_path, 'r', encoding='utf-8') as f:
                    json.load(f)
                logger.info(f"Database file exists and is valid: {db_path}")
                return True
            except json.JSONDecodeError:
                # File exists but is not valid JSON
                logger.warning(f"Database file exists but is not valid JSON: {db_path}")
                # Create backup of invalid file
                backup_path = f"{db_path}.bak"
                logger.info(f"Creating backup of invalid database: {backup_path}")
                with open(db_path, 'r', encoding='utf-8') as src:
                    with open(backup_path, 'w', encoding='utf-8') as dst:
                        dst.write(src.read())
        else:
            # File doesn't exist or is empty
            logger.info(f"Database file doesn't exist or is empty: {db_path}")
        
        # Create new database file with default structure
        logger.info(f"Creating new database file with default structure: {db_path}")
        with open(db_path, 'w', encoding='utf-8') as f:
            json.dump(DEFAULT_DB_STRUCTURE, f, indent=2)
        
        logger.info(f"Database initialization complete: {db_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        return False

if __name__ == "__main__":
    # When run directly, initialize the database
    initialize_database()