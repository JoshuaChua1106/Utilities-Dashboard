"""
Main email fetcher service for utility invoice automation.
Handles Gmail and Outlook integration with provider-specific search logic.
"""

import os
import json
import logging
import base64
import email
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import sqlite3

from .auth_adapter import AuthAdapter
from .storage_adapter import StorageAdapter

logger = logging.getLogger(__name__)


class EmailService:
    """
    Core email fetching service with support for multiple providers.
    Handles OAuth2 authentication, email search, and PDF download.
    """
    
    def __init__(self, config_path: str = "./config"):
        self.config_path = Path(config_path)
        self.providers_config = self._load_providers_config()
        self.auth_adapter = AuthAdapter(self.config_path / "credentials.json")
        self.storage_adapter = StorageAdapter({
            'local_storage_path': './data/invoices'
        })
        self.db_path = "./data/invoices.db"
        self._init_email_tracking()
    
    def _load_providers_config(self) -> Dict:
        """Load provider configuration."""
        try:
            providers_file = self.config_path / "providers.json"
            with open(providers_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load providers config: {e}")
            return {}
    
    def _init_email_tracking(self):
        """Initialize email tracking database table."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS email_tracking (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email_id TEXT UNIQUE NOT NULL,
                    provider_name TEXT NOT NULL,
                    subject TEXT,
                    sender TEXT,
                    received_date TEXT,
                    processed_date TEXT,
                    pdf_path TEXT,
                    processing_status TEXT DEFAULT 'pending',
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
            conn.close()
            logger.info("Email tracking table initialized")
        except Exception as e:
            logger.error(f"Failed to initialize email tracking: {e}")
    
    def fetch_invoices_all_providers(self, days_back: int = 30) -> Dict[str, List[Dict]]:
        """
        Fetch invoices from all configured providers.
        
        Args:
            days_back: Number of days to search back
            
        Returns:
            Dictionary with provider names as keys and lists of fetched invoices
        """
        results = {}
        
        # Get global search configuration
        global_config = self.providers_config.get('global_settings', {})
        search_config = global_config.get('search_configuration', {})
        default_days = search_config.get('date_range_days', days_back)
        
        for provider_name, provider_config in self.providers_config.get('providers', {}).items():
            logger.info(f"Fetching invoices for {provider_name}")
            
            try:
                invoices = self.fetch_invoices_for_provider(provider_name, default_days)
                results[provider_name] = invoices
                logger.info(f"Found {len(invoices)} invoices for {provider_name}")
                
            except Exception as e:
                logger.error(f"Failed to fetch invoices for {provider_name}: {e}")
                results[provider_name] = []
        
        return results
    
    def fetch_invoices_for_provider(self, provider_name: str, days_back: int = 30) -> List[Dict]:
        """
        Fetch invoices for a specific provider.
        
        Args:
            provider_name: Name of the utility provider
            days_back: Number of days to search back
            
        Returns:
            List of invoice dictionaries
        """
        if provider_name not in self.providers_config.get('providers', {}):
            raise ValueError(f"Provider {provider_name} not configured")
        
        provider_config = self.providers_config['providers'][provider_name]
        email_patterns = provider_config.get('email_patterns', {})
        
        # Try Gmail first, then Outlook
        invoices = []
        
        try:
            gmail_invoices = self._fetch_gmail_invoices(provider_name, email_patterns, days_back)
            invoices.extend(gmail_invoices)
            logger.info(f"Found {len(gmail_invoices)} Gmail invoices for {provider_name}")
        except Exception as e:
            logger.warning(f"Gmail fetch failed for {provider_name}: {e}")
        
        try:
            outlook_invoices = self._fetch_outlook_invoices(provider_name, email_patterns, days_back)
            invoices.extend(outlook_invoices)
            logger.info(f"Found {len(outlook_invoices)} Outlook invoices for {provider_name}")
        except Exception as e:
            logger.warning(f"Outlook fetch failed for {provider_name}: {e}")
        
        # Remove duplicates based on email ID
        unique_invoices = []
        seen_ids = set()
        
        for invoice in invoices:
            email_id = invoice.get('email_id')
            if email_id and email_id not in seen_ids:
                unique_invoices.append(invoice)
                seen_ids.add(email_id)
        
        return unique_invoices
    
    def _fetch_gmail_invoices(self, provider_name: str, email_patterns: Dict, days_back: int) -> List[Dict]:
        """Fetch invoices from Gmail."""
        creds = self.auth_adapter.get_gmail_credentials()
        if not creds:
            raise Exception("Gmail credentials not available")
        
        try:
            import requests
            
            headers = {
                'Authorization': f"Bearer {creds['access_token']}",
                'Content-Type': 'application/json'
            }
            
            # Build search query
            query = self._build_gmail_search_query(email_patterns, days_back)
            
            # Search for emails
            search_url = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
            params = {'q': query, 'maxResults': 50}
            
            response = requests.get(search_url, headers=headers, params=params)
            
            if response.status_code != 200:
                raise Exception(f"Gmail search failed: {response.status_code} - {response.text}")
            
            search_results = response.json()
            messages = search_results.get('messages', [])
            
            invoices = []
            for message in messages:
                try:
                    invoice = self._process_gmail_message(message['id'], headers, provider_name)
                    if invoice:
                        invoices.append(invoice)
                except Exception as e:
                    logger.error(f"Failed to process Gmail message {message['id']}: {e}")
            
            return invoices
            
        except Exception as e:
            logger.error(f"Gmail fetch error: {e}")
            raise
    
    def _build_gmail_search_query(self, email_patterns: Dict, days_back: int) -> str:
        """Build Gmail search query from email patterns."""
        query_parts = []
        
        # Add sender filters
        from_patterns = email_patterns.get('from', [])
        if from_patterns:
            from_queries = [f"from:{pattern}" for pattern in from_patterns]
            query_parts.append(f"({' OR '.join(from_queries)})")
        
        # Add subject keyword filters
        subject_keywords = email_patterns.get('subject_keywords', [])
        if subject_keywords:
            subject_queries = [f'subject:"{keyword}"' for keyword in subject_keywords]
            query_parts.append(f"({' OR '.join(subject_queries)})")
        
        # Add attachment filter
        attachment_types = email_patterns.get('attachment_types', [])
        if '.pdf' in attachment_types:
            query_parts.append("has:attachment filename:pdf")
        
        # Add date filter
        start_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y/%m/%d')
        query_parts.append(f"after:{start_date}")
        
        # Exclude marketing emails
        exclude_keywords = email_patterns.get('exclude_keywords', [])
        for keyword in exclude_keywords:
            query_parts.append(f'-subject:"{keyword}"')
        
        return ' '.join(query_parts)
    
    def _process_gmail_message(self, message_id: str, headers: Dict, provider_name: str) -> Optional[Dict]:
        """Process a Gmail message and download PDF attachments."""
        try:
            import requests
            
            # Get message details
            message_url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}"
            response = requests.get(message_url, headers=headers)
            
            if response.status_code != 200:
                logger.error(f"Failed to get message {message_id}: {response.status_code}")
                return None
            
            message_data = response.json()
            
            # Extract message metadata
            payload = message_data.get('payload', {})
            headers_list = payload.get('headers', [])
            
            subject = None
            sender = None
            date_received = None
            
            for header in headers_list:
                name = header.get('name', '').lower()
                value = header.get('value', '')
                
                if name == 'subject':
                    subject = value
                elif name == 'from':
                    sender = value
                elif name == 'date':
                    date_received = value
            
            # Check if already processed
            if self._is_email_already_processed(message_id):
                logger.debug(f"Email {message_id} already processed, skipping")
                return None
            
            # Look for PDF attachments
            pdf_path = self._download_gmail_attachments(message_data, headers, provider_name)
            
            if pdf_path:
                # Record in email tracking
                self._record_email_processing(
                    email_id=message_id,
                    provider_name=provider_name,
                    subject=subject,
                    sender=sender,
                    received_date=date_received,
                    pdf_path=pdf_path,
                    status='downloaded'
                )
                
                return {
                    'email_id': message_id,
                    'provider': provider_name,
                    'subject': subject,
                    'sender': sender,
                    'date_received': date_received,
                    'pdf_path': pdf_path,
                    'source': 'gmail'
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error processing Gmail message {message_id}: {e}")
            return None
    
    def _download_gmail_attachments(self, message_data: Dict, headers: Dict, provider_name: str) -> Optional[str]:
        """Download PDF attachments from Gmail message."""
        try:
            import requests
            
            payload = message_data.get('payload', {})
            parts = payload.get('parts', [payload])  # Handle single part messages
            
            for part in parts:
                filename = None
                attachment_id = None
                
                # Check if this part has an attachment
                if 'body' in part and 'attachmentId' in part['body']:
                    attachment_id = part['body']['attachmentId']
                    
                    # Get filename from headers
                    if 'filename' in part:
                        filename = part['filename']
                    elif 'headers' in part:
                        for header in part.get('headers', []):
                            if header.get('name', '').lower() == 'content-disposition':
                                value = header.get('value', '')
                                if 'filename=' in value:
                                    filename = value.split('filename=')[1].strip('"')
                
                # Check if it's a PDF
                if filename and filename.lower().endswith('.pdf') and attachment_id:
                    # Download the attachment
                    attachment_url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_data['id']}/attachments/{attachment_id}"
                    response = requests.get(attachment_url, headers=headers)
                    
                    if response.status_code == 200:
                        attachment_data = response.json()
                        pdf_data = base64.urlsafe_b64decode(attachment_data['data'])
                        
                        # Save PDF using storage adapter
                        pdf_path = self.storage_adapter.save_pdf(pdf_data, filename, provider_name)
                        logger.info(f"Downloaded PDF: {filename} -> {pdf_path}")
                        return pdf_path
                    else:
                        logger.error(f"Failed to download attachment: {response.status_code}")
            
            return None
            
        except Exception as e:
            logger.error(f"Error downloading Gmail attachments: {e}")
            return None
    
    def _fetch_outlook_invoices(self, provider_name: str, email_patterns: Dict, days_back: int) -> List[Dict]:
        """Fetch invoices from Outlook (placeholder)."""
        # For now, return empty list - Outlook implementation can be added later
        logger.info("Outlook integration not yet implemented")
        return []
    
    def _is_email_already_processed(self, email_id: str) -> bool:
        """Check if email has already been processed."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM email_tracking WHERE email_id = ?", (email_id,))
            result = cursor.fetchone()
            conn.close()
            return result is not None
        except Exception as e:
            logger.error(f"Error checking email processing status: {e}")
            return False
    
    def _record_email_processing(self, email_id: str, provider_name: str, subject: str,
                                 sender: str, received_date: str, pdf_path: str, status: str):
        """Record email processing in tracking database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO email_tracking 
                (email_id, provider_name, subject, sender, received_date, pdf_path, processing_status, processed_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                email_id, provider_name, subject, sender, received_date,
                pdf_path, status, datetime.now().isoformat()
            ))
            
            conn.commit()
            conn.close()
            logger.debug(f"Recorded email processing: {email_id}")
            
        except Exception as e:
            logger.error(f"Error recording email processing: {e}")
    
    def get_processing_history(self, provider: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """Get email processing history."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if provider:
                cursor.execute('''
                    SELECT * FROM email_tracking 
                    WHERE provider_name = ? 
                    ORDER BY processed_date DESC 
                    LIMIT ?
                ''', (provider, limit))
            else:
                cursor.execute('''
                    SELECT * FROM email_tracking 
                    ORDER BY processed_date DESC 
                    LIMIT ?
                ''', (limit,))
            
            columns = [description[0] for description in cursor.description]
            results = []
            
            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))
            
            conn.close()
            return results
            
        except Exception as e:
            logger.error(f"Error getting processing history: {e}")
            return []
    
    def get_service_status(self) -> Dict:
        """Get service status including authentication and recent activity."""
        auth_status = self.auth_adapter.get_auth_status()
        
        # Get recent processing stats
        recent_history = self.get_processing_history(limit=50)
        
        status = {
            'authentication': auth_status,
            'recent_activity': {
                'total_processed': len(recent_history),
                'successful': len([h for h in recent_history if h['processing_status'] == 'downloaded']),
                'failed': len([h for h in recent_history if h['processing_status'] == 'error']),
                'last_fetch': recent_history[0]['processed_date'] if recent_history else None
            },
            'storage': {
                'local_files': len(self.storage_adapter.list_files()),
                'aws_mode': os.getenv('AWS_MODE', 'false').lower() == 'true'
            }
        }
        
        return status
    
    def manual_sync(self, provider: Optional[str] = None, days_back: int = 7) -> Dict:
        """
        Manually trigger sync for one or all providers.
        
        Args:
            provider: Specific provider name, or None for all
            days_back: Number of days to search back
            
        Returns:
            Sync results summary
        """
        start_time = datetime.now()
        
        if provider:
            if provider not in self.providers_config.get('providers', {}):
                return {'error': f'Provider {provider} not configured'}
            
            results = {provider: self.fetch_invoices_for_provider(provider, days_back)}
        else:
            results = self.fetch_invoices_all_providers(days_back)
        
        # Calculate summary
        total_found = sum(len(invoices) for invoices in results.values())
        providers_processed = len(results)
        processing_time = (datetime.now() - start_time).total_seconds()
        
        return {
            'success': True,
            'providers_processed': providers_processed,
            'total_invoices_found': total_found,
            'processing_time_seconds': processing_time,
            'results': results,
            'timestamp': start_time.isoformat()
        }