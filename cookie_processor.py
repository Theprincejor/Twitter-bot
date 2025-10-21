"""
Cookie Processor - Enhanced with better validation and processing
"""

import json
from typing import Dict, Any, List
from datetime import datetime
from logger import bot_logger


class CookieProcessor:
    """Process and validate Twitter cookies for Twikit"""
    
    # Required cookies for Twitter authentication
    REQUIRED_COOKIES = ['auth_token', 'ct0']
    
    # Optional but recommended cookies
    OPTIONAL_COOKIES = [
        'guest_id',
        'guest_id_ads',
        'guest_id_marketing',
        'personalization_id',
        'kdt',
        'twid',
        'auth_multi'
    ]
    
    # All possible cookie names we should handle
    ALL_COOKIE_NAMES = REQUIRED_COOKIES + OPTIONAL_COOKIES
    
    @staticmethod
    def process_cookies(raw_cookies: Any) -> Dict[str, str]:
        """
        Process raw cookie data into Twikit format
        
        Args:
            raw_cookies: Can be list (browser export) or dict (processed)
            
        Returns:
            Dict of cookie name -> value
        """
        try:
            if isinstance(raw_cookies, dict):
                # Already processed or in key-value format
                return CookieProcessor._process_dict_cookies(raw_cookies)
            
            elif isinstance(raw_cookies, list):
                # Browser export format (array of cookie objects)
                return CookieProcessor._process_list_cookies(raw_cookies)
            
            else:
                bot_logger.error(f"Invalid cookie data type: {type(raw_cookies)}")
                return {}
                
        except Exception as e:
            bot_logger.error(f"Failed to process cookies: {e}")
            return {}
    
    @staticmethod
    def _process_list_cookies(cookie_list: List[Dict[str, Any]]) -> Dict[str, str]:
        """Process browser-exported cookie array"""
        processed = {}
        
        for cookie in cookie_list:
            if not isinstance(cookie, dict):
                continue
            
            # Get cookie name and value
            name = cookie.get('name', '')
            value = cookie.get('value', '')
            
            # Only include cookies we care about
            if name in CookieProcessor.ALL_COOKIE_NAMES and value:
                processed[name] = value
                
                # Log cookie info (without exposing full value)
                bot_logger.debug(f"Processed cookie: {name} = {value[:10]}...")
        
        return processed
    
    @staticmethod
    def _process_dict_cookies(cookie_dict: Dict[str, Any]) -> Dict[str, str]:
        """Process already-formatted cookie dictionary"""
        processed = {}
        
        for name, value in cookie_dict.items():
            # Only include cookies we care about
            if name in CookieProcessor.ALL_COOKIE_NAMES and value:
                # Ensure value is string
                processed[name] = str(value)
        
        return processed
    
    @staticmethod
    def validate_cookies(cookies: Dict[str, str]) -> Dict[str, Any]:
        """
        Validate cookie data for Twitter authentication
        
        Returns:
            Dict with validation results
        """
        validation = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'missing': [],
            'present': []
        }
        
        # Check required cookies
        for cookie_name in CookieProcessor.REQUIRED_COOKIES:
            if cookie_name not in cookies or not cookies[cookie_name]:
                validation['valid'] = False
                validation['missing'].append(cookie_name)
                validation['errors'].append(f"Missing required cookie: {cookie_name}")
            else:
                validation['present'].append(cookie_name)
                
                # Validate cookie values
                value = cookies[cookie_name]
                
                # Check auth_token format
                if cookie_name == 'auth_token':
                    if len(value) < 40:
                        validation['valid'] = False
                        validation['errors'].append(f"auth_token seems too short: {len(value)} chars")
                    elif not value.replace('-', '').replace('_', '').isalnum():
                        validation['warnings'].append("auth_token contains unexpected characters")
                
                # Check ct0 format
                elif cookie_name == 'ct0':
                    if len(value) < 32:
                        validation['valid'] = False
                        validation['errors'].append(f"ct0 seems too short: {len(value)} chars")
        
        # Check optional cookies
        for cookie_name in CookieProcessor.OPTIONAL_COOKIES:
            if cookie_name not in cookies or not cookies[cookie_name]:
                validation['warnings'].append(f"Optional cookie missing: {cookie_name}")
            else:
                validation['present'].append(cookie_name)
        
        # Additional validation: Check for token mismatch
        if 'auth_token' in cookies and 'ct0' in cookies:
            # Ensure both are present and non-empty
            auth_token = cookies['auth_token']
            ct0 = cookies['ct0']
            
            if not auth_token or not ct0:
                validation['valid'] = False
                validation['errors'].append("auth_token or ct0 is empty")
        
        # Log validation results
        if validation['valid']:
            bot_logger.info(f"Cookie validation passed: {len(validation['present'])} cookies present")
        else:
            bot_logger.error(f"Cookie validation failed: {validation['errors']}")
        
        return validation
    
    @staticmethod
    def format_cookies_for_twikit(cookies: Dict[str, str]) -> Dict[str, str]:
        """
        Format cookies specifically for Twikit's requirements
        
        Twikit expects a simple dict of cookie_name: cookie_value
        """
        formatted = {}
        
        for name, value in cookies.items():
            if name in CookieProcessor.ALL_COOKIE_NAMES:
                # Ensure value is a string and cleaned
                formatted[name] = str(value).strip()
        
        return formatted
    
    @staticmethod
    def extract_user_info_from_cookies(cookies: Dict[str, str]) -> Dict[str, Any]:
        """
        Extract user information from cookies
        
        Returns:
            Dict with extracted user info
        """
        user_info = {}
        
        # Extract user ID from twid cookie if present
        if 'twid' in cookies:
            twid = cookies['twid']
            # Format: u%3D1234567890
            if '%3D' in twid:
                user_id = twid.split('%3D')[1]
                user_info['user_id'] = user_id
            elif '=' in twid:
                user_id = twid.split('=')[1]
                user_info['user_id'] = user_id
        
        # Add auth token info
        if 'auth_token' in cookies:
            user_info['auth_token_length'] = len(cookies['auth_token'])
            user_info['auth_token_preview'] = cookies['auth_token'][:10] + "..."
        
        # Add ct0 info
        if 'ct0' in cookies:
            user_info['ct0_length'] = len(cookies['ct0'])
            user_info['ct0_preview'] = cookies['ct0'][:10] + "..."
        
        return user_info
    
    @staticmethod
    def check_cookie_freshness(cookies: Dict[str, str]) -> Dict[str, Any]:
        """
        Check if cookies are likely still fresh
        
        Note: Without expiration dates, we can only do basic checks
        """
        freshness = {
            'likely_fresh': True,
            'warnings': []
        }
        
        # Check if required cookies exist
        if 'auth_token' not in cookies:
            freshness['likely_fresh'] = False
            freshness['warnings'].append("Missing auth_token - cookies expired or invalid")
        
        if 'ct0' not in cookies:
            freshness['likely_fresh'] = False
            freshness['warnings'].append("Missing ct0 - cookies expired or invalid")
        
        # Check cookie lengths (fresh cookies should have minimum lengths)
        if 'auth_token' in cookies:
            if len(cookies['auth_token']) < 40:
                freshness['likely_fresh'] = False
                freshness['warnings'].append("auth_token too short - may be corrupted")
        
        if 'ct0' in cookies:
            if len(cookies['ct0']) < 32:
                freshness['likely_fresh'] = False
                freshness['warnings'].append("ct0 too short - may be corrupted")
        
        return freshness
    
    @staticmethod
    def save_cookies_to_file(cookies: Dict[str, str], filepath: str) -> bool:
        """Save cookies to a JSON file"""
        try:
            with open(filepath, 'w') as f:
                json.dump(cookies, f, indent=2)
            bot_logger.info(f"Cookies saved to {filepath}")
            return True
        except Exception as e:
            bot_logger.error(f"Failed to save cookies to {filepath}: {e}")
            return False
    
    @staticmethod
    def load_cookies_from_file(filepath: str) -> Dict[str, str]:
        """Load cookies from a JSON file"""
        try:
            with open(filepath, 'r') as f:
                raw_cookies = json.load(f)
            
            # Process cookies
            processed = CookieProcessor.process_cookies(raw_cookies)
            
            bot_logger.info(f"Cookies loaded from {filepath}")
            return processed
            
        except Exception as e:
            bot_logger.error(f"Failed to load cookies from {filepath}: {e}")
            return {}
    
    @staticmethod
    def compare_cookies(cookies1: Dict[str, str], cookies2: Dict[str, str]) -> Dict[str, Any]:
        """
        Compare two sets of cookies to check if they're from the same account
        
        Returns:
            Dict with comparison results
        """
        comparison = {
            'same_account': False,
            'differences': [],
            'similarities': []
        }
        
        # Compare auth_token (most important)
        if cookies1.get('auth_token') == cookies2.get('auth_token'):
            comparison['same_account'] = True
            comparison['similarities'].append('Same auth_token')
        else:
            comparison['differences'].append('Different auth_token')
        
        # Compare user ID from twid
        user1 = CookieProcessor.extract_user_info_from_cookies(cookies1)
        user2 = CookieProcessor.extract_user_info_from_cookies(cookies2)
        
        if user1.get('user_id') == user2.get('user_id') and user1.get('user_id'):
            comparison['similarities'].append(f"Same user ID: {user1.get('user_id')}")
        elif user1.get('user_id') and user2.get('user_id'):
            comparison['differences'].append(
                f"Different user IDs: {user1.get('user_id')} vs {user2.get('user_id')}"
            )
        
        return comparison
    
    @staticmethod
    def sanitize_cookies_for_logging(cookies: Dict[str, str]) -> Dict[str, str]:
        """
        Create a sanitized version of cookies safe for logging
        
        Replaces sensitive values with previews
        """
        sanitized = {}
        
        for name, value in cookies.items():
            if len(value) > 20:
                # Show first 10 and last 5 characters
                sanitized[name] = f"{value[:10]}...{value[-5:]}"
            else:
                sanitized[name] = f"{value[:5]}..."
        
        return sanitized
    
    @staticmethod
    def create_cookie_report(cookies: Dict[str, str]) -> str:
        """
        Create a detailed report about the cookies
        
        Returns:
            Formatted string report
        """
        report = []
        report.append("🍪 Cookie Analysis Report")
        report.append("=" * 50)
        
        # Validation
        validation = CookieProcessor.validate_cookies(cookies)
        report.append(f"\n✅ Valid: {validation['valid']}")
        report.append(f"📊 Total Cookies: {len(cookies)}")
        report.append(f"✓ Required Present: {len([c for c in CookieProcessor.REQUIRED_COOKIES if c in cookies])}/{len(CookieProcessor.REQUIRED_COOKIES)}")
        report.append(f"✓ Optional Present: {len([c for c in CookieProcessor.OPTIONAL_COOKIES if c in cookies])}/{len(CookieProcessor.OPTIONAL_COOKIES)}")
        
        # User info
        user_info = CookieProcessor.extract_user_info_from_cookies(cookies)
        if user_info:
            report.append("\n👤 User Information:")
            for key, value in user_info.items():
                report.append(f"   • {key}: {value}")
        
        # Freshness check
        freshness = CookieProcessor.check_cookie_freshness(cookies)
        report.append(f"\n🔄 Freshness: {'✅ Likely Fresh' if freshness['likely_fresh'] else '❌ Possibly Expired'}")
        
        # Errors and warnings
        if validation['errors']:
            report.append("\n❌ Errors:")
            for error in validation['errors']:
                report.append(f"   • {error}")
        
        if validation['warnings']:
            report.append("\n⚠️ Warnings:")
            for warning in validation['warnings']:
                report.append(f"   • {warning}")
        
        # Cookie list
        report.append("\n📋 Cookies Present:")
        sanitized = CookieProcessor.sanitize_cookies_for_logging(cookies)
        for name, value in sanitized.items():
            report.append(f"   • {name}: {value}")
        
        report.append("\n" + "=" * 50)
        
        return "\n".join(report)


# Convenience functions
def process_cookies(raw_cookies: Any) -> Dict[str, str]:
    """Convenience wrapper for CookieProcessor.process_cookies"""
    return CookieProcessor.process_cookies(raw_cookies)


def validate_cookies(cookies: Dict[str, str]) -> Dict[str, Any]:
    """Convenience wrapper for CookieProcessor.validate_cookies"""
    return CookieProcessor.validate_cookies(cookies)
