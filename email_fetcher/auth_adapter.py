"""
Authentication adapter for handling OAuth2 flows with Gmail and Outlook.
Provides secure credential management and token refresh functionality.
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class AuthAdapter:
    """
    Handles OAuth2 authentication for email providers.
    Supports both Gmail and Outlook with automatic token refresh.
    """
    
    def __init__(self, credentials_path: str = "./config/credentials.json"):
        self.credentials_path = Path(credentials_path)
        self.credentials = self._load_credentials()
        self.aws_mode = os.getenv('AWS_MODE', 'false').lower() == 'true'
    
    def _load_credentials(self) -> Dict:
        """Load credentials from configuration file."""
        try:
            if self.credentials_path.exists():
                with open(self.credentials_path, 'r') as f:
                    return json.load(f)
            else:
                logger.warning(f"Credentials file not found: {self.credentials_path}")
                return {}
        except Exception as e:
            logger.error(f"Failed to load credentials: {e}")
            return {}
    
    def _save_credentials(self):
        """Save updated credentials back to file."""
        try:
            with open(self.credentials_path, 'w') as f:
                json.dump(self.credentials, f, indent=2)
            logger.debug("Credentials saved successfully")
        except Exception as e:
            logger.error(f"Failed to save credentials: {e}")
    
    def get_gmail_credentials(self) -> Optional[Dict]:
        """Get Gmail OAuth2 credentials from environment variables or file."""
        import os
        
        # First, try to get credentials from environment variables
        env_client_id = os.getenv('GMAIL_CLIENT_ID')
        env_client_secret = os.getenv('GMAIL_CLIENT_SECRET')
        env_refresh_token = os.getenv('GMAIL_REFRESH_TOKEN')
        
        if env_client_id and env_client_secret and env_refresh_token:
            logger.info("Using Gmail credentials from environment variables")
            gmail_creds = {
                'type': 'oauth2',
                'client_id': env_client_id,
                'client_secret': env_client_secret,
                'refresh_token': env_refresh_token,
                'access_token': None,
                'token_expires_at': None,
                'scopes': ['https://www.googleapis.com/auth/gmail.readonly']
            }
            
            # Check if we need to refresh the token
            if self._token_needs_refresh(gmail_creds):
                refreshed = self._refresh_gmail_token(gmail_creds)
                if not refreshed:
                    logger.error("Failed to refresh Gmail token from environment variables")
                    return None
            
            return gmail_creds
        
        # Fallback to file-based credentials
        if 'gmail' not in self.credentials:
            logger.error("Gmail credentials not configured in environment or file")
            return None
        
        gmail_creds = self.credentials['gmail']
        
        # Check if we need to refresh the token
        if self._token_needs_refresh(gmail_creds):
            refreshed = self._refresh_gmail_token(gmail_creds)
            if refreshed:
                self._save_credentials()
            else:
                logger.error("Failed to refresh Gmail token")
                return None
        
        return gmail_creds
    
    def get_outlook_credentials(self) -> Optional[Dict]:
        """Get Outlook OAuth2 credentials."""
        if 'outlook' not in self.credentials:
            logger.error("Outlook credentials not configured")
            return None
        
        outlook_creds = self.credentials['outlook']
        
        # Check if we need to refresh the token
        if self._token_needs_refresh(outlook_creds):
            refreshed = self._refresh_outlook_token(outlook_creds)
            if refreshed:
                self._save_credentials()
            else:
                logger.error("Failed to refresh Outlook token")
                return None
        
        return outlook_creds
    
    def _token_needs_refresh(self, creds: Dict) -> bool:
        """Check if access token needs to be refreshed."""
        if not creds.get('access_token'):
            return True
        
        expires_at = creds.get('token_expires_at')
        if not expires_at:
            return True
        
        # Parse expiration time
        try:
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at)
            elif isinstance(expires_at, (int, float)):
                expires_at = datetime.fromtimestamp(expires_at)
            
            # Refresh if token expires within 5 minutes
            return datetime.now() >= (expires_at - timedelta(minutes=5))
        except Exception as e:
            logger.error(f"Error parsing token expiration: {e}")
            return True
    
    def _refresh_gmail_token(self, creds: Dict) -> bool:
        """Refresh Gmail access token using refresh token."""
        try:
            import requests
            
            refresh_token = creds.get('refresh_token')
            client_id = creds.get('client_id')
            client_secret = creds.get('client_secret')
            
            if not all([refresh_token, client_id, client_secret]):
                logger.error("Missing required Gmail OAuth2 credentials")
                return False
            
            # Gmail token refresh endpoint
            token_url = "https://oauth2.googleapis.com/token"
            
            data = {
                'client_id': client_id,
                'client_secret': client_secret,
                'refresh_token': refresh_token,
                'grant_type': 'refresh_token'
            }
            
            response = requests.post(token_url, data=data)
            
            if response.status_code == 200:
                token_data = response.json()
                
                # Update credentials
                creds['access_token'] = token_data['access_token']
                creds['token_expires_at'] = (
                    datetime.now() + timedelta(seconds=token_data.get('expires_in', 3600))
                ).isoformat()
                
                logger.info("Gmail token refreshed successfully")
                return True
            else:
                logger.error(f"Gmail token refresh failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error refreshing Gmail token: {e}")
            return False
    
    def _refresh_outlook_token(self, creds: Dict) -> bool:
        """Refresh Outlook access token using refresh token."""
        try:
            import requests
            
            refresh_token = creds.get('refresh_token')
            client_id = creds.get('client_id')
            client_secret = creds.get('client_secret')
            tenant_id = creds.get('tenant_id', 'common')
            
            if not all([refresh_token, client_id, client_secret]):
                logger.error("Missing required Outlook OAuth2 credentials")
                return False
            
            # Outlook token refresh endpoint
            token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
            
            data = {
                'client_id': client_id,
                'client_secret': client_secret,
                'refresh_token': refresh_token,
                'grant_type': 'refresh_token',
                'scope': ' '.join(creds.get('scopes', ['https://graph.microsoft.com/Mail.Read']))
            }
            
            response = requests.post(token_url, data=data)
            
            if response.status_code == 200:
                token_data = response.json()
                
                # Update credentials
                creds['access_token'] = token_data['access_token']
                creds['token_expires_at'] = (
                    datetime.now() + timedelta(seconds=token_data.get('expires_in', 3600))
                ).isoformat()
                
                # Update refresh token if provided
                if 'refresh_token' in token_data:
                    creds['refresh_token'] = token_data['refresh_token']
                
                logger.info("Outlook token refreshed successfully")
                return True
            else:
                logger.error(f"Outlook token refresh failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error refreshing Outlook token: {e}")
            return False
    
    def validate_credentials(self, provider: str) -> Tuple[bool, str]:
        """
        Validate credentials for a specific provider.
        
        Args:
            provider: 'gmail' or 'outlook'
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            if provider == 'gmail':
                creds = self.get_gmail_credentials()
                if not creds:
                    return False, "Gmail credentials not available"
                
                # Test API call
                return self._test_gmail_connection(creds)
                
            elif provider == 'outlook':
                creds = self.get_outlook_credentials()
                if not creds:
                    return False, "Outlook credentials not available"
                
                # Test API call
                return self._test_outlook_connection(creds)
                
            else:
                return False, f"Unknown provider: {provider}"
                
        except Exception as e:
            logger.error(f"Error validating {provider} credentials: {e}")
            return False, str(e)
    
    def _test_gmail_connection(self, creds: Dict) -> Tuple[bool, str]:
        """Test Gmail API connection."""
        try:
            import requests
            
            headers = {
                'Authorization': f"Bearer {creds['access_token']}",
                'Content-Type': 'application/json'
            }
            
            # Simple test call to get user profile
            response = requests.get(
                'https://gmail.googleapis.com/gmail/v1/users/me/profile',
                headers=headers
            )
            
            if response.status_code == 200:
                return True, "Gmail connection successful"
            else:
                return False, f"Gmail API error: {response.status_code}"
                
        except Exception as e:
            return False, f"Gmail connection test failed: {e}"
    
    def _test_outlook_connection(self, creds: Dict) -> Tuple[bool, str]:
        """Test Outlook API connection."""
        try:
            import requests
            
            headers = {
                'Authorization': f"Bearer {creds['access_token']}",
                'Content-Type': 'application/json'
            }
            
            # Simple test call to get user profile
            response = requests.get(
                'https://graph.microsoft.com/v1.0/me',
                headers=headers
            )
            
            if response.status_code == 200:
                return True, "Outlook connection successful"
            else:
                return False, f"Outlook API error: {response.status_code}"
                
        except Exception as e:
            return False, f"Outlook connection test failed: {e}"
    
    def get_auth_status(self) -> Dict:
        """Get authentication status for all providers."""
        status = {
            'gmail': {'configured': False, 'valid': False, 'error': None},
            'outlook': {'configured': False, 'valid': False, 'error': None}
        }
        
        # Check Gmail
        if 'gmail' in self.credentials:
            status['gmail']['configured'] = True
            is_valid, error = self.validate_credentials('gmail')
            status['gmail']['valid'] = is_valid
            if not is_valid:
                status['gmail']['error'] = error
        
        # Check Outlook
        if 'outlook' in self.credentials:
            status['outlook']['configured'] = True
            is_valid, error = self.validate_credentials('outlook')
            status['outlook']['valid'] = is_valid
            if not is_valid:
                status['outlook']['error'] = error
        
        return status
    
    def setup_credentials_interactive(self, provider: str):
        """
        Interactive setup for OAuth2 credentials.
        This would be called during initial setup.
        """
        print(f"\n=== {provider.upper()} OAuth2 Setup ===")
        print("This feature requires manual OAuth2 setup.")
        print("Please follow the setup guide in the documentation.")
        print("For now, configure credentials manually in config/credentials.json")
        
        # In a real implementation, this would:
        # 1. Open browser to OAuth2 authorization URL
        # 2. Handle callback to get authorization code
        # 3. Exchange code for access/refresh tokens
        # 4. Save tokens to credentials file