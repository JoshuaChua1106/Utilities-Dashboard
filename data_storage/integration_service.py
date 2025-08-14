"""
Integration service that coordinates email fetching, PDF parsing, and database storage.
Provides the complete end-to-end automation pipeline.
"""

import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path
import sys
import os

# Add project root to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from email_fetcher.email_service import EmailService
from pdf_parser.pdf_service import PDFService

logger = logging.getLogger(__name__)


class IntegrationService:
    """
    Main integration service that coordinates the complete utility invoice processing pipeline.
    Handles email fetching, PDF parsing, and database integration.
    """
    
    def __init__(self, config_path: str = "./config", db_path: str = "./data/invoices.db"):
        self.config_path = Path(config_path)
        self.db_path = db_path
        
        # Initialize component services
        self.email_service = EmailService(config_path)
        self.pdf_service = PDFService(config_path, db_path)
        
        self._init_integration_tables()
    
    def _init_integration_tables(self):
        """Initialize integration tracking tables."""
        try:
            conn = sqlite3.connect(self.db_path)
            
            # Table for batch processing operations
            conn.execute('''
                CREATE TABLE IF NOT EXISTS batch_operations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    operation_type TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    status TEXT DEFAULT 'running',
                    total_emails INTEGER DEFAULT 0,
                    emails_processed INTEGER DEFAULT 0,
                    pdfs_downloaded INTEGER DEFAULT 0,
                    pdfs_parsed INTEGER DEFAULT 0,
                    invoices_created INTEGER DEFAULT 0,
                    errors_count INTEGER DEFAULT 0,
                    error_summary TEXT,
                    provider_filter TEXT,
                    days_back INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            conn.close()
            logger.info("Integration tables initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize integration tables: {e}")
    
    def run_full_sync(self, provider: str = None, days_back: int = 30) -> Dict:
        """
        Run the complete sync pipeline: fetch emails -> download PDFs -> parse invoices.
        
        Args:
            provider: Specific provider to sync, or None for all providers
            days_back: Number of days to search back
            
        Returns:
            Complete sync results
        """
        batch_id = self._start_batch_operation('full_sync', provider, days_back)
        
        try:
            logger.info(f"Starting full sync - Provider: {provider or 'ALL'}, Days back: {days_back}")
            
            # Step 1: Fetch emails and download PDFs
            if provider:
                email_results = {provider: self.email_service.fetch_invoices_for_provider(provider, days_back)}
            else:
                email_results = self.email_service.fetch_invoices_all_providers(days_back)
            
            # Count totals
            total_emails = sum(len(invoices) for invoices in email_results.values())
            pdfs_downloaded = sum(1 for invoices in email_results.values() for inv in invoices if inv.get('pdf_path'))
            
            self._update_batch_progress(batch_id, {
                'total_emails': total_emails,
                'emails_processed': total_emails,
                'pdfs_downloaded': pdfs_downloaded
            })
            
            # Step 2: Parse downloaded PDFs
            pdf_files = []
            for provider_name, invoices in email_results.items():
                for invoice in invoices:
                    if invoice.get('pdf_path'):
                        pdf_files.append({
                            'path': invoice['pdf_path'],
                            'provider': provider_name,
                            'email_id': invoice.get('email_id')
                        })
            
            parsing_results = self.pdf_service.process_multiple_pdfs(pdf_files)
            
            # Step 3: Update batch operation with final results
            final_stats = {
                'pdfs_parsed': parsing_results['successful'],
                'invoices_created': parsing_results['successful'],
                'errors_count': parsing_results['failed'],
                'status': 'completed',
                'end_time': datetime.now().isoformat()
            }
            
            if parsing_results['failed'] > 0:
                # Collect error summary
                errors = []
                for file_result in parsing_results['file_results']:
                    if not file_result.get('success') and file_result.get('errors'):
                        errors.extend(file_result['errors'])
                final_stats['error_summary'] = '; '.join(errors[:5])  # First 5 errors
            
            self._update_batch_progress(batch_id, final_stats)
            
            # Step 4: Export to CSV for Power BI
            csv_export_result = self._export_to_csv()
            
            result = {
                'success': True,
                'batch_id': batch_id,
                'email_fetch': {
                    'providers_processed': len(email_results),
                    'total_emails_found': total_emails,
                    'pdfs_downloaded': pdfs_downloaded
                },
                'pdf_parsing': parsing_results,
                'csv_export': csv_export_result,
                'summary': {
                    'total_new_invoices': parsing_results['successful'],
                    'processing_errors': parsing_results['failed'],
                    'providers_synced': list(email_results.keys())
                }
            }
            
            logger.info(f"Full sync completed - {parsing_results['successful']} new invoices processed")
            return result
            
        except Exception as e:
            logger.error(f"Full sync failed: {e}")
            
            self._update_batch_progress(batch_id, {
                'status': 'failed',
                'error_summary': str(e),
                'end_time': datetime.now().isoformat()
            })
            
            return {
                'success': False,
                'batch_id': batch_id,
                'error': str(e)
            }
    
    def run_email_sync_only(self, provider: str = None, days_back: int = 7) -> Dict:
        """
        Run email sync without PDF parsing (for testing or incremental updates).
        
        Args:
            provider: Specific provider to sync
            days_back: Number of days to search back
            
        Returns:
            Email sync results
        """
        batch_id = self._start_batch_operation('email_sync_only', provider, days_back)
        
        try:
            if provider:
                results = {provider: self.email_service.fetch_invoices_for_provider(provider, days_back)}
            else:
                results = self.email_service.fetch_invoices_all_providers(days_back)
            
            total_emails = sum(len(invoices) for invoices in results.values())
            pdfs_downloaded = sum(1 for invoices in results.values() for inv in invoices if inv.get('pdf_path'))
            
            self._update_batch_progress(batch_id, {
                'total_emails': total_emails,
                'emails_processed': total_emails,
                'pdfs_downloaded': pdfs_downloaded,
                'status': 'completed',
                'end_time': datetime.now().isoformat()
            })
            
            return {
                'success': True,
                'batch_id': batch_id,
                'results': results,
                'summary': {
                    'total_emails_found': total_emails,
                    'pdfs_downloaded': pdfs_downloaded,
                    'providers_processed': list(results.keys())
                }
            }
            
        except Exception as e:
            logger.error(f"Email sync failed: {e}")
            
            self._update_batch_progress(batch_id, {
                'status': 'failed',
                'error_summary': str(e),
                'end_time': datetime.now().isoformat()
            })
            
            return {
                'success': False,
                'batch_id': batch_id,
                'error': str(e)
            }
    
    def run_pdf_parsing_only(self, provider: str = None) -> Dict:
        """
        Parse existing PDFs without fetching new emails.
        
        Args:
            provider: Specific provider to process
            
        Returns:
            PDF parsing results
        """
        batch_id = self._start_batch_operation('pdf_parsing_only', provider, 0)
        
        try:
            # Get unprocessed PDFs from email tracking
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if provider:
                cursor.execute('''
                    SELECT pdf_path, provider_name, email_id FROM email_tracking
                    WHERE pdf_path IS NOT NULL AND provider_name = ?
                    AND email_id NOT IN (
                        SELECT DISTINCT email_id FROM pdf_processing WHERE email_id IS NOT NULL
                    )
                ''', (provider,))
            else:
                cursor.execute('''
                    SELECT pdf_path, provider_name, email_id FROM email_tracking
                    WHERE pdf_path IS NOT NULL
                    AND email_id NOT IN (
                        SELECT DISTINCT email_id FROM pdf_processing WHERE email_id IS NOT NULL
                    )
                ''')
            
            unprocessed_pdfs = []
            for row in cursor.fetchall():
                unprocessed_pdfs.append({
                    'path': row[0],
                    'provider': row[1],
                    'email_id': row[2]
                })
            
            conn.close()
            
            if not unprocessed_pdfs:
                self._update_batch_progress(batch_id, {
                    'status': 'completed',
                    'end_time': datetime.now().isoformat()
                })
                
                return {
                    'success': True,
                    'batch_id': batch_id,
                    'message': 'No unprocessed PDFs found',
                    'pdfs_processed': 0
                }
            
            # Process PDFs
            results = self.pdf_service.process_multiple_pdfs(unprocessed_pdfs)
            
            self._update_batch_progress(batch_id, {
                'pdfs_parsed': results['successful'],
                'invoices_created': results['successful'],
                'errors_count': results['failed'],
                'status': 'completed',
                'end_time': datetime.now().isoformat()
            })
            
            # Export to CSV
            csv_export_result = self._export_to_csv()
            
            return {
                'success': True,
                'batch_id': batch_id,
                'parsing_results': results,
                'csv_export': csv_export_result,
                'summary': {
                    'pdfs_found': len(unprocessed_pdfs),
                    'successfully_parsed': results['successful'],
                    'parsing_failures': results['failed']
                }
            }
            
        except Exception as e:
            logger.error(f"PDF parsing only failed: {e}")
            
            self._update_batch_progress(batch_id, {
                'status': 'failed',
                'error_summary': str(e),
                'end_time': datetime.now().isoformat()
            })
            
            return {
                'success': False,
                'batch_id': batch_id,
                'error': str(e)
            }
    
    def _start_batch_operation(self, operation_type: str, provider: str = None, days_back: int = 0) -> int:
        """Start a new batch operation and return its ID."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO batch_operations 
                (operation_type, start_time, provider_filter, days_back)
                VALUES (?, ?, ?, ?)
            ''', (operation_type, datetime.now().isoformat(), provider, days_back))
            
            batch_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            logger.info(f"Started batch operation: {operation_type} (ID: {batch_id})")
            return batch_id
            
        except Exception as e:
            logger.error(f"Failed to start batch operation: {e}")
            return 0
    
    def _update_batch_progress(self, batch_id: int, updates: Dict):
        """Update batch operation progress."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Build update query dynamically
            set_clauses = []
            values = []
            
            for field, value in updates.items():
                set_clauses.append(f"{field} = ?")
                values.append(value)
            
            values.append(batch_id)
            
            update_sql = f"UPDATE batch_operations SET {', '.join(set_clauses)} WHERE id = ?"
            cursor.execute(update_sql, values)
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to update batch progress: {e}")
    
    def _export_to_csv(self) -> Dict:
        """Export invoice data to CSV for Power BI integration."""
        try:
            import pandas as pd
            
            conn = sqlite3.connect(self.db_path)
            
            # Query all invoice data
            query = '''
                SELECT 
                    provider_name,
                    service_type,
                    invoice_date,
                    total_amount,
                    usage_quantity,
                    usage_rate,
                    service_charge,
                    billing_period_start,
                    billing_period_end,
                    processing_status,
                    created_at,
                    updated_at
                FROM invoices
                ORDER BY invoice_date DESC
            '''
            
            df = pd.read_sql_query(query, conn)
            conn.close()
            
            # Export to CSV
            csv_path = "./data/invoices.csv"
            df.to_csv(csv_path, index=False)
            
            # Also create a summary export
            summary_path = "./data/exports/invoice_summary.csv"
            Path("./data/exports").mkdir(exist_ok=True)
            
            # Create summary by provider and month
            if not df.empty:
                df['invoice_date'] = pd.to_datetime(df['invoice_date'])
                df['year_month'] = df['invoice_date'].dt.to_period('M')
                
                summary = df.groupby(['provider_name', 'service_type', 'year_month']).agg({
                    'total_amount': ['sum', 'mean', 'count'],
                    'usage_quantity': 'sum'
                }).round(2)
                
                summary.to_csv(summary_path)
            
            return {
                'success': True,
                'main_export': csv_path,
                'summary_export': summary_path,
                'records_exported': len(df),
                'export_time': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"CSV export failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_sync_history(self, limit: int = 20) -> List[Dict]:
        """Get recent sync operation history."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM batch_operations
                ORDER BY start_time DESC
                LIMIT ?
            ''', (limit,))
            
            columns = [description[0] for description in cursor.description]
            history = []
            
            for row in cursor.fetchall():
                history.append(dict(zip(columns, row)))
            
            conn.close()
            return history
            
        except Exception as e:
            logger.error(f"Error getting sync history: {e}")
            return []
    
    def get_system_status(self) -> Dict:
        """Get comprehensive system status."""
        try:
            # Get component statuses
            email_status = self.email_service.get_service_status()
            pdf_stats = self.pdf_service.get_processing_statistics()
            
            # Get recent sync history
            recent_syncs = self.get_sync_history(5)
            
            # Get database statistics
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM invoices")
            total_invoices = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM email_tracking")
            total_emails_tracked = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM pdf_processing")
            total_pdfs_processed = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                'email_service': email_status,
                'pdf_processing': pdf_stats,
                'database': {
                    'total_invoices': total_invoices,
                    'total_emails_tracked': total_emails_tracked,
                    'total_pdfs_processed': total_pdfs_processed
                },
                'recent_operations': recent_syncs,
                'system_health': {
                    'database_accessible': True,
                    'email_auth_valid': any(
                        status.get('valid', False) 
                        for status in email_status.get('authentication', {}).values()
                    ),
                    'templates_loaded': len(pdf_stats.get('available_providers', [])) > 0
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return {
                'error': str(e),
                'system_health': {
                    'database_accessible': False,
                    'email_auth_valid': False,
                    'templates_loaded': False
                }
            }
    
    def cleanup_old_data(self, days_to_keep: int = 365) -> Dict:
        """Clean up old processing data to keep database size manageable."""
        try:
            cutoff_date = (datetime.now() - timedelta(days=days_to_keep)).isoformat()
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Clean up old batch operations
            cursor.execute("DELETE FROM batch_operations WHERE start_time < ?", (cutoff_date,))
            deleted_batches = cursor.rowcount
            
            # Clean up old PDF processing records (keep the data, just the processing logs)
            cursor.execute("DELETE FROM pdf_processing WHERE processing_date < ?", (cutoff_date,))
            deleted_pdf_logs = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            return {
                'success': True,
                'deleted_batch_operations': deleted_batches,
                'deleted_pdf_processing_logs': deleted_pdf_logs,
                'cutoff_date': cutoff_date
            }
            
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }