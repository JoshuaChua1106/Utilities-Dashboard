"""
Email Fetcher Module
Handles automated email fetching and PDF download for utility invoices.
"""

from .email_service import EmailService
from .storage_adapter import StorageAdapter
from .auth_adapter import AuthAdapter

__all__ = ['EmailService', 'StorageAdapter', 'AuthAdapter']