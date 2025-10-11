"""
Cookie processor for Twitter Bot System
Processes browser cookie exports to Twikit-compatible format
"""

import json
import os
from typing import Dict, List, Any, Optional


class CookieProcessor:
    """Process and clean browser cookie exports for Twikit"""

    # Essential cookies that Twikit needs for authentication
    ESSENTIAL_COOKIES = {
        "auth_token",  # Primary authentication token
        "ct0",  # CSRF token
        "auth_multi",  # Multi-factor authentication token
        "guest_id",  # Guest identifier
        "personalization_id",  # Personalization token
        "kdt",  # Session token
        "twid",  # Twitter user ID
    }

    @staticmethod
    def process_cookie_file(input_path: str, output_path: str = None) -> Dict[str, Any]:
        """
        Process a browser cookie export file to Twikit format

        Args:
            input_path: Path to the raw cookie JSON file
            output_path: Path to save the processed cookies (optional)

        Returns:
            Dict containing processed cookies
        """
        try:
            # Read the raw cookie file
            with open(input_path, "r", encoding="utf-8") as f:
                raw_cookies = json.load(f)

            # Process the cookies
            processed_cookies = CookieProcessor.process_cookies(raw_cookies)

            # Save processed cookies if output path provided
            if output_path:
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(processed_cookies, f, indent=2)
                print(f"Processed cookies saved to: {output_path}")

            return processed_cookies

        except Exception as e:
            print(f"Error processing cookie file: {e}")
            return {}

    @staticmethod
    def process_cookies(raw_cookies: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Process raw cookie list to Twikit format with enhanced cleaning and validation

        Args:
            raw_cookies: List of raw cookie objects from browser export

        Returns:
            Dict with processed cookies in Twikit format
        """
        processed = {}

        for cookie in raw_cookies:
            cookie_name = cookie.get("name", "").lower()

            # Only include essential cookies
            if cookie_name in CookieProcessor.ESSENTIAL_COOKIES:
                cookie_value = cookie.get("value", "")

                # Enhanced cookie value cleaning
                cookie_value = CookieProcessor._clean_cookie_value(cookie_value)

                processed[cookie_name] = cookie_value

        return processed

    @staticmethod
    def _clean_cookie_value(value: str) -> str:
        """Clean and normalize cookie values"""
        if not value:
            return value

        # Remove quotes if present (both single and double)
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]

        # URL decode common patterns
        if "u%3D" in value:
            value = value.replace("u%3D", "u=")
        if "v1%" in value:
            value = value.replace("v1%", "v1%")
        
        # Fix twid cookie format - remove "u=" prefix if present (both encoded and decoded)
        if value.startswith("u="):
            value = value[2:]  # Remove "u=" prefix
        elif value.startswith("u%3D"):
            value = value[4:]  # Remove "u%3D" prefix (URL encoded "u=")

        return value

    @staticmethod
    def validate_cookies(cookies: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate that required cookies are present and detect token mismatches

        Args:
            cookies: Processed cookies dict

        Returns:
            Dict with validation results including token mismatch detection
        """
        validation = {
            "valid": True,
            "missing": [],
            "present": [],
            "warnings": [],
            "errors": [],
        }

        # Required cookies for Twikit
        required_cookies = ["auth_token", "ct0"]

        for cookie_name in required_cookies:
            if cookie_name in cookies and cookies[cookie_name]:
                validation["present"].append(cookie_name)
            else:
                validation["missing"].append(cookie_name)
                validation["valid"] = False

        # Optional but recommended cookies
        optional_cookies = [
            "guest_id",
            "personalization_id",
            "kdt",
            "twid",
            "auth_multi",
        ]
        for cookie_name in optional_cookies:
            if cookie_name in cookies and cookies[cookie_name]:
                validation["present"].append(cookie_name)
            else:
                validation["warnings"].append(f"Optional cookie missing: {cookie_name}")

        # Token mismatch detection
        if "auth_token" in cookies and "auth_multi" in cookies:
            auth_token = cookies["auth_token"]
            auth_multi = cookies["auth_multi"]

            if auth_token and auth_multi:
                # Extract token from auth_multi (format: user_id:token)
                if ":" in auth_multi:
                    user_id, auth_multi_token = auth_multi.split(":", 1)

                    # Check if tokens match
                    if auth_token != auth_multi_token:
                        validation["valid"] = False
                        validation["errors"].append(
                            f"Token mismatch detected! "
                            f"auth_token: {auth_token[:10]}... "
                            f"auth_multi token: {auth_multi_token[:10]}... "
                            f"These cookies are from different sessions!"
                        )
                    else:
                        validation["warnings"].append(
                            "✅ Token validation passed - cookies are from same session"
                        )

        return validation

    @staticmethod
    def create_twikit_cookie_dict(cookies: Dict[str, Any]) -> Dict[str, str]:
        """
        Create cookie dict in format expected by Twikit

        Args:
            cookies: Processed cookies dict

        Returns:
            Dict in Twikit cookie format
        """
        twikit_cookies = {}

        for name, value in cookies.items():
            if name in CookieProcessor.ESSENTIAL_COOKIES:
                twikit_cookies[name] = value

        return twikit_cookies

    @staticmethod
    def batch_process_cookies(
        input_dir: str, output_dir: str = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Process multiple cookie files in a directory

        Args:
            input_dir: Directory containing raw cookie JSON files
            output_dir: Directory to save processed cookies (optional)

        Returns:
            Dict mapping filenames to processed cookies
        """
        if not os.path.exists(input_dir):
            print(f"Input directory not found: {input_dir}")
            return {}

        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

        results = {}

        for filename in os.listdir(input_dir):
            if filename.endswith(".json"):
                input_path = os.path.join(input_dir, filename)

                output_path = None
                if output_dir:
                    output_filename = f"processed_{filename}"
                    output_path = os.path.join(output_dir, output_filename)

                processed = CookieProcessor.process_cookie_file(input_path, output_path)
                results[filename] = processed

        return results


def main():
    """Example usage of CookieProcessor"""

    # Example: Process a single cookie file
    raw_cookies = [
        {
            "name": "auth_token",
            "value": "36b904ed14a7b5f46f4359dc76dd1785b21bf5ac",
            "domain": ".x.com",
            "hostOnly": False,
            "path": "/",
            "secure": True,
            "httpOnly": True,
            "sameSite": "no_restriction",
            "session": False,
            "expirationDate": 1794745406.824,
        },
        {
            "name": "ct0",
            "value": "a1c6170598ce04b321b9d8c91851b5007d480c9a77993852ca6c7c16b5e8d74e856dd62a5dafde24bcde13cefab5ce3bac53f5296fb7bd96705dbcec714bffb070595b7571bc780ec347d6d1b9f7a81d",
            "domain": ".x.com",
            "hostOnly": False,
            "path": "/",
            "secure": True,
            "httpOnly": False,
            "sameSite": "lax",
            "session": False,
            "expirationDate": 1794745407.136,
        },
    ]

    # Process the cookies
    processed = CookieProcessor.process_cookies(raw_cookies)
    print("Processed cookies:", processed)

    # Validate the cookies
    validation = CookieProcessor.validate_cookies(processed)
    print("Validation result:", validation)

    # Create Twikit format
    twikit_cookies = CookieProcessor.create_twikit_cookie_dict(processed)
    print("Twikit format:", twikit_cookies)


if __name__ == "__main__":
    main()
