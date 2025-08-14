"""
Data Storage Module
Handles database operations and data integration for the utilities tracker.
"""

from .integration_service import IntegrationService
from .database_adapter import DatabaseAdapter

__all__ = ['IntegrationService', 'DatabaseAdapter']