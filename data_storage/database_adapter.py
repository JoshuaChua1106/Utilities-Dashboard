"""
Database adapter for handling database operations across local and AWS environments.
Provides abstraction layer for SQLite and PostgreSQL operations.
"""

import os
import sqlite3
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class DatabaseAdapter:
    """
    Handles database operations with support for both SQLite and PostgreSQL.
    Automatically switches between backends based on environment configuration.
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.aws_mode = os.getenv('AWS_MODE', 'false').lower() == 'true'
        self.db_path = self.config.get('db_path', './data/invoices.db')
        
        if self.aws_mode:
            logger.info("Database adapter initialized for AWS PostgreSQL mode")
        else:
            logger.info(f"Database adapter initialized for local SQLite mode: {self.db_path}")
    
    def get_connection(self):
        """Get database connection based on environment."""
        if self.aws_mode:
            return self._get_postgres_connection()
        else:
            return self._get_sqlite_connection()
    
    def _get_sqlite_connection(self):
        """Get SQLite connection."""
        try:
            return sqlite3.connect(self.db_path)
        except Exception as e:
            logger.error(f"Failed to connect to SQLite: {e}")
            raise
    
    def _get_postgres_connection(self):
        """Get PostgreSQL connection (placeholder)."""
        # This will be implemented when AWS deployment is approved
        raise NotImplementedError("PostgreSQL connection not yet implemented - use local mode")
    
    def execute_query(self, query: str, params: tuple = None) -> List[Dict]:
        """
        Execute a query and return results as list of dictionaries.
        
        Args:
            query: SQL query string
            params: Query parameters
            
        Returns:
            List of dictionaries representing rows
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            # Get column names
            columns = [description[0] for description in cursor.description] if cursor.description else []
            
            # Fetch all rows and convert to dictionaries
            rows = cursor.fetchall()
            results = []
            
            for row in rows:
                results.append(dict(zip(columns, row)))
            
            conn.close()
            return results
            
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise
    
    def execute_non_query(self, query: str, params: tuple = None) -> int:
        """
        Execute a non-query (INSERT, UPDATE, DELETE) and return affected rows.
        
        Args:
            query: SQL query string
            params: Query parameters
            
        Returns:
            Number of affected rows
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            affected_rows = cursor.rowcount
            conn.commit()
            conn.close()
            
            return affected_rows
            
        except Exception as e:
            logger.error(f"Non-query execution failed: {e}")
            raise
    
    def health_check(self) -> Dict:
        """Perform database health check."""
        try:
            # Simple connectivity test
            conn = self.get_connection()
            cursor = conn.cursor()
            
            if self.aws_mode:
                cursor.execute("SELECT 1")
            else:
                cursor.execute("SELECT 1")
            
            result = cursor.fetchone()
            conn.close()
            
            return {
                'status': 'healthy',
                'database_type': 'postgresql' if self.aws_mode else 'sqlite',
                'connection': 'successful',
                'test_query': 'passed'
            }
            
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                'status': 'unhealthy',
                'database_type': 'postgresql' if self.aws_mode else 'sqlite',
                'connection': 'failed',
                'error': str(e)
            }