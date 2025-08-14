"""
Main PDF parsing service for utility invoice processing.
Coordinates OCR extraction, template parsing, and database integration.
"""

import os
import logging
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path

from .ocr_adapter import OCRAdapter
from .template_processor import TemplateProcessor

logger = logging.getLogger(__name__)


class PDFService:
    """
    Core PDF processing service that coordinates text extraction and data parsing.
    Handles the complete pipeline from PDF file to structured database records.
    """
    
    def __init__(self, config_path: str = "./config", db_path: str = "./data/invoices.db"):
        self.config_path = Path(config_path)
        self.db_path = db_path
        self.ocr_adapter = OCRAdapter()
        self.template_processor = TemplateProcessor(self.config_path / "templates")
        self._init_processing_tables()
    
    def _init_processing_tables(self):
        """Initialize processing-related database tables."""
        try:
            conn = sqlite3.connect(self.db_path)
            
            # Table for PDF processing history
            conn.execute('''
                CREATE TABLE IF NOT EXISTS pdf_processing (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT UNIQUE NOT NULL,
                    provider_name TEXT,
                    processing_date TEXT,
                    ocr_method TEXT,
                    ocr_confidence REAL,
                    parsing_confidence REAL,
                    extracted_text_length INTEGER,
                    parsing_success BOOLEAN,
                    error_message TEXT,
                    invoice_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (invoice_id) REFERENCES invoices (id)
                )
            ''')
            
            conn.commit()
            conn.close()
            logger.info("PDF processing tables initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize PDF processing tables: {e}")
    
    def process_pdf(self, pdf_path: str, provider: str, email_id: str = None) -> Dict:
        """
        Process a PDF file through the complete extraction and parsing pipeline.
        
        Args:
            pdf_path: Path to the PDF file
            provider: Provider name for template selection
            email_id: Optional email ID for tracking
            
        Returns:
            Processing result with extracted data and metadata
        """
        start_time = datetime.now()
        
        result = {
            'success': False,
            'pdf_path': pdf_path,
            'provider': provider,
            'email_id': email_id,
            'processing_time': 0.0,
            'ocr_result': None,
            'parsing_result': None,
            'invoice_data': None,
            'errors': [],
            'warnings': []
        }
        
        try:
            # Check if file exists
            if not Path(pdf_path).exists():
                raise FileNotFoundError(f"PDF file not found: {pdf_path}")
            
            # Check if already processed
            if self._is_pdf_already_processed(pdf_path):
                logger.info(f"PDF already processed: {pdf_path}")
                existing_result = self._get_existing_processing_result(pdf_path)
                if existing_result:
                    return existing_result
            
            # Step 1: Extract text using OCR
            logger.info(f"Extracting text from {pdf_path}")
            ocr_result = self.ocr_adapter.extract_text(pdf_path)
            result['ocr_result'] = ocr_result
            
            if ocr_result.get('error'):
                result['errors'].append(f"OCR extraction failed: {ocr_result['error']}")
                return result
            
            extracted_text = ocr_result.get('text', '')
            if not extracted_text or len(extracted_text.strip()) < 10:
                result['errors'].append("Insufficient text extracted from PDF")
                return result
            
            # Step 2: Parse extracted text using template
            logger.info(f"Parsing text for provider: {provider}")
            parsing_result = self.template_processor.parse_invoice(extracted_text, provider)
            result['parsing_result'] = parsing_result
            
            if parsing_result.get('validation_errors'):
                result['errors'].extend(parsing_result['validation_errors'])
            
            if parsing_result.get('parsing_warnings'):
                result['warnings'].extend(parsing_result['parsing_warnings'])
            
            # Step 3: Prepare invoice data for database
            invoice_data = self._prepare_invoice_data(parsing_result, pdf_path, email_id)
            result['invoice_data'] = invoice_data
            
            # Step 4: Save to database if data is valid
            if invoice_data and not result['errors']:
                invoice_id = self._save_invoice_to_database(invoice_data)
                if invoice_id:
                    result['invoice_id'] = invoice_id
                    result['success'] = True
                    logger.info(f"Successfully processed PDF: {pdf_path} -> Invoice ID: {invoice_id}")
                else:
                    result['errors'].append("Failed to save invoice to database")
            
            # Record processing history
            processing_time = (datetime.now() - start_time).total_seconds()
            result['processing_time'] = processing_time
            
            self._record_processing_history(
                pdf_path=pdf_path,
                provider=provider,
                ocr_result=ocr_result,
                parsing_result=parsing_result,
                success=result['success'],
                error_message='; '.join(result['errors']) if result['errors'] else None,
                invoice_id=result.get('invoice_id')
            )
            
        except Exception as e:
            logger.error(f"PDF processing failed for {pdf_path}: {e}")
            result['errors'].append(str(e))
            result['processing_time'] = (datetime.now() - start_time).total_seconds()
        
        return result
    
    def process_multiple_pdfs(self, pdf_files: List[Dict]) -> Dict:
        """
        Process multiple PDF files in batch.
        
        Args:
            pdf_files: List of dicts with 'path' and 'provider' keys
            
        Returns:
            Batch processing results
        """
        start_time = datetime.now()
        
        results = {
            'total_files': len(pdf_files),
            'successful': 0,
            'failed': 0,
            'processing_time': 0.0,
            'file_results': [],
            'summary': {}
        }
        
        for file_info in pdf_files:
            pdf_path = file_info.get('path')
            provider = file_info.get('provider')
            email_id = file_info.get('email_id')
            
            if not pdf_path or not provider:
                results['file_results'].append({
                    'path': pdf_path,
                    'success': False,
                    'error': 'Missing path or provider information'
                })
                results['failed'] += 1
                continue
            
            try:
                file_result = self.process_pdf(pdf_path, provider, email_id)
                results['file_results'].append(file_result)
                
                if file_result['success']:
                    results['successful'] += 1
                else:
                    results['failed'] += 1
            
            except Exception as e:
                logger.error(f"Batch processing error for {pdf_path}: {e}")
                results['file_results'].append({
                    'path': pdf_path,
                    'success': False,
                    'error': str(e)
                })
                results['failed'] += 1
        
        results['processing_time'] = (datetime.now() - start_time).total_seconds()
        
        # Generate summary
        providers = {}
        for file_result in results['file_results']:
            provider = file_result.get('provider', 'Unknown')
            if provider not in providers:
                providers[provider] = {'successful': 0, 'failed': 0}
            
            if file_result.get('success'):
                providers[provider]['successful'] += 1
            else:
                providers[provider]['failed'] += 1
        
        results['summary'] = {
            'by_provider': providers,
            'success_rate': results['successful'] / results['total_files'] if results['total_files'] > 0 else 0.0
        }
        
        logger.info(f"Batch processing complete: {results['successful']}/{results['total_files']} successful")
        return results
    
    def _prepare_invoice_data(self, parsing_result: Dict, pdf_path: str, email_id: str = None) -> Dict:
        """Prepare parsed data for database insertion."""
        try:
            extracted_data = parsing_result.get('extracted_data', {})
            
            # Map parsed fields to database columns
            invoice_data = {
                'provider_name': parsing_result.get('provider_name'),
                'service_type': parsing_result.get('service_type'),
                'invoice_date': extracted_data.get('invoice_date'),
                'total_amount': extracted_data.get('total_amount'),
                'usage_quantity': extracted_data.get('usage_quantity'),
                'usage_rate': extracted_data.get('usage_rate'),
                'service_charge': extracted_data.get('service_charge'),
                'billing_period_start': extracted_data.get('billing_period_start'),
                'billing_period_end': extracted_data.get('billing_period_end'),
                'file_path': pdf_path,
                'processing_status': 'parsed',
                'email_id': email_id,
                'parsing_confidence': parsing_result.get('parsing_confidence', 0.0),
                'account_number': extracted_data.get('account_number')
            }
            
            # Filter out None values
            invoice_data = {k: v for k, v in invoice_data.items() if v is not None}
            
            return invoice_data
            
        except Exception as e:
            logger.error(f"Error preparing invoice data: {e}")
            return {}
    
    def _save_invoice_to_database(self, invoice_data: Dict) -> Optional[int]:
        """Save invoice data to the database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check for duplicates based on provider, amount, and date
            cursor.execute('''
                SELECT id FROM invoices 
                WHERE provider_name = ? AND total_amount = ? AND invoice_date = ?
            ''', (
                invoice_data.get('provider_name'),
                invoice_data.get('total_amount'),
                invoice_data.get('invoice_date')
            ))
            
            existing = cursor.fetchone()
            if existing:
                logger.warning(f"Duplicate invoice found: {invoice_data.get('provider_name')} - ${invoice_data.get('total_amount')}")
                conn.close()
                return existing[0]
            
            # Prepare insert statement
            columns = list(invoice_data.keys())
            placeholders = ['?' for _ in columns]
            values = list(invoice_data.values())
            
            insert_sql = f'''
                INSERT INTO invoices ({', '.join(columns)})
                VALUES ({', '.join(placeholders)})
            '''
            
            cursor.execute(insert_sql, values)
            invoice_id = cursor.lastrowid
            
            conn.commit()
            conn.close()
            
            logger.info(f"Saved invoice to database: ID {invoice_id}")
            return invoice_id
            
        except Exception as e:
            logger.error(f"Failed to save invoice to database: {e}")
            return None
    
    def _is_pdf_already_processed(self, pdf_path: str) -> bool:
        """Check if PDF has already been processed."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM pdf_processing WHERE file_path = ?", (pdf_path,))
            result = cursor.fetchone()
            conn.close()
            return result is not None
        except Exception as e:
            logger.error(f"Error checking PDF processing status: {e}")
            return False
    
    def _get_existing_processing_result(self, pdf_path: str) -> Optional[Dict]:
        """Get existing processing result for a PDF."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM pdf_processing WHERE file_path = ?
                ORDER BY processing_date DESC LIMIT 1
            ''', (pdf_path,))
            
            row = cursor.fetchone()
            if row:
                columns = [description[0] for description in cursor.description]
                result_data = dict(zip(columns, row))
                
                # Convert to expected format
                return {
                    'success': result_data.get('parsing_success', False),
                    'pdf_path': pdf_path,
                    'provider': result_data.get('provider_name'),
                    'processing_time': 0.0,  # Not stored in history
                    'invoice_id': result_data.get('invoice_id'),
                    'cached': True
                }
            
            conn.close()
            return None
            
        except Exception as e:
            logger.error(f"Error getting existing processing result: {e}")
            return None
    
    def _record_processing_history(self, pdf_path: str, provider: str, ocr_result: Dict,
                                  parsing_result: Dict, success: bool, error_message: str = None,
                                  invoice_id: int = None):
        """Record processing history in database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO pdf_processing
                (file_path, provider_name, processing_date, ocr_method, ocr_confidence,
                 parsing_confidence, extracted_text_length, parsing_success, error_message, invoice_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                pdf_path,
                provider,
                datetime.now().isoformat(),
                ocr_result.get('method', 'unknown'),
                ocr_result.get('confidence', 0.0),
                parsing_result.get('parsing_confidence', 0.0),
                len(ocr_result.get('text', '')),
                success,
                error_message,
                invoice_id
            ))
            
            conn.commit()
            conn.close()
            logger.debug(f"Recorded processing history for: {pdf_path}")
            
        except Exception as e:
            logger.error(f"Error recording processing history: {e}")
    
    def get_processing_statistics(self) -> Dict:
        """Get processing statistics and health metrics."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Overall statistics
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_processed,
                    SUM(CASE WHEN parsing_success = 1 THEN 1 ELSE 0 END) as successful,
                    AVG(ocr_confidence) as avg_ocr_confidence,
                    AVG(parsing_confidence) as avg_parsing_confidence,
                    AVG(extracted_text_length) as avg_text_length
                FROM pdf_processing
            ''')
            
            overall_stats = cursor.fetchone()
            
            # Statistics by provider
            cursor.execute('''
                SELECT 
                    provider_name,
                    COUNT(*) as total,
                    SUM(CASE WHEN parsing_success = 1 THEN 1 ELSE 0 END) as successful,
                    AVG(parsing_confidence) as avg_confidence
                FROM pdf_processing
                GROUP BY provider_name
            ''')
            
            provider_stats = {}
            for row in cursor.fetchall():
                provider_stats[row[0]] = {
                    'total': row[1],
                    'successful': row[2],
                    'success_rate': row[2] / row[1] if row[1] > 0 else 0.0,
                    'avg_confidence': row[3] or 0.0
                }
            
            # Recent processing activity
            cursor.execute('''
                SELECT processing_date, parsing_success, provider_name
                FROM pdf_processing
                ORDER BY processing_date DESC
                LIMIT 10
            ''')
            
            recent_activity = []
            for row in cursor.fetchall():
                recent_activity.append({
                    'date': row[0],
                    'success': bool(row[1]),
                    'provider': row[2]
                })
            
            conn.close()
            
            return {
                'overall': {
                    'total_processed': overall_stats[0] or 0,
                    'successful': overall_stats[1] or 0,
                    'success_rate': (overall_stats[1] or 0) / (overall_stats[0] or 1),
                    'avg_ocr_confidence': overall_stats[2] or 0.0,
                    'avg_parsing_confidence': overall_stats[3] or 0.0,
                    'avg_text_length': overall_stats[4] or 0.0
                },
                'by_provider': provider_stats,
                'recent_activity': recent_activity,
                'available_providers': self.template_processor.get_available_providers()
            }
            
        except Exception as e:
            logger.error(f"Error getting processing statistics: {e}")
            return {}
    
    def reprocess_failed_pdfs(self, provider: str = None) -> Dict:
        """Reprocess PDFs that previously failed."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if provider:
                cursor.execute('''
                    SELECT file_path, provider_name FROM pdf_processing
                    WHERE parsing_success = 0 AND provider_name = ?
                ''', (provider,))
            else:
                cursor.execute('''
                    SELECT file_path, provider_name FROM pdf_processing
                    WHERE parsing_success = 0
                ''')
            
            failed_files = [{'path': row[0], 'provider': row[1]} for row in cursor.fetchall()]
            conn.close()
            
            if not failed_files:
                return {
                    'message': 'No failed PDFs found to reprocess',
                    'reprocessed': 0
                }
            
            logger.info(f"Reprocessing {len(failed_files)} failed PDFs")
            results = self.process_multiple_pdfs(failed_files)
            
            return {
                'message': f'Reprocessed {len(failed_files)} failed PDFs',
                'results': results
            }
            
        except Exception as e:
            logger.error(f"Error reprocessing failed PDFs: {e}")
            return {'error': str(e)}
    
    def test_template_with_sample(self, provider: str, sample_pdf_path: str) -> Dict:
        """Test a template with a sample PDF for debugging purposes."""
        try:
            # Extract text
            ocr_result = self.ocr_adapter.extract_text(sample_pdf_path)
            
            if ocr_result.get('error'):
                return {'error': f'OCR failed: {ocr_result["error"]}'}
            
            # Test template
            template_test = self.template_processor.test_template(provider, ocr_result['text'])
            
            # Add OCR information
            template_test['ocr_result'] = {
                'method': ocr_result.get('method'),
                'confidence': ocr_result.get('confidence'),
                'text_length': len(ocr_result.get('text', '')),
                'text_preview': ocr_result.get('text', '')[:500] + '...' if len(ocr_result.get('text', '')) > 500 else ocr_result.get('text', '')
            }
            
            return template_test
            
        except Exception as e:
            logger.error(f"Template testing failed: {e}")
            return {'error': str(e)}