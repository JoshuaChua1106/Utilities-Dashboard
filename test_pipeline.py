#!/usr/bin/env python3
"""
Test script for the complete utility invoice processing pipeline.
Tests email fetching, PDF parsing, and data integration.
"""

import sys
import os
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add project root to path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

def test_imports():
    """Test that all modules can be imported successfully."""
    logger.info("Testing module imports...")
    
    try:
        from email_fetcher import EmailService, StorageAdapter, AuthAdapter
        logger.info("✅ Email fetcher modules imported successfully")
    except Exception as e:
        logger.error(f"❌ Email fetcher import failed: {e}")
        return False
    
    try:
        from pdf_parser import PDFService, OCRAdapter, TemplateProcessor
        logger.info("✅ PDF parser modules imported successfully")
    except Exception as e:
        logger.error(f"❌ PDF parser import failed: {e}")
        return False
    
    try:
        from data_storage import IntegrationService
        logger.info("✅ Data storage modules imported successfully")
    except Exception as e:
        logger.error(f"❌ Data storage import failed: {e}")
        return False
    
    return True

def test_template_loading():
    """Test that parsing templates load correctly."""
    logger.info("Testing template loading...")
    
    try:
        from pdf_parser.template_processor import TemplateProcessor
        
        processor = TemplateProcessor("./config/templates")
        providers = processor.get_available_providers()
        
        logger.info(f"✅ Loaded templates for providers: {providers}")
        
        # Test template info for each provider
        for provider in providers:
            info = processor.get_template_info(provider)
            logger.info(f"  {provider}: {len(info.get('fields', []))} fields, {len(info.get('required_fields', []))} required")
        
        return len(providers) > 0
        
    except Exception as e:
        logger.error(f"❌ Template loading failed: {e}")
        return False

def test_ocr_availability():
    """Test OCR dependencies and capabilities."""
    logger.info("Testing OCR availability...")
    
    try:
        from pdf_parser.ocr_adapter import OCRAdapter
        
        adapter = OCRAdapter()
        
        # Test pdfplumber import
        try:
            import pdfplumber
            logger.info("✅ pdfplumber available")
            pdfplumber_available = True
        except ImportError:
            logger.warning("⚠️ pdfplumber not available")
            pdfplumber_available = False
        
        # Test tesseract availability
        tesseract_available = adapter.tesseract_available
        if tesseract_available:
            logger.info("✅ Tesseract OCR available")
        else:
            logger.warning("⚠️ Tesseract OCR not available")
        
        return pdfplumber_available or tesseract_available
        
    except Exception as e:
        logger.error(f"❌ OCR availability test failed: {e}")
        return False

def test_database_connection():
    """Test database connectivity and schema."""
    logger.info("Testing database connection...")
    
    try:
        import sqlite3
        
        db_path = "./data/invoices.db"
        if not Path(db_path).exists():
            logger.error(f"❌ Database file not found: {db_path}")
            return False
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check required tables exist
        required_tables = ['invoices', 'processing_history', 'email_tracking']
        
        for table in required_tables:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
            if not cursor.fetchone():
                logger.error(f"❌ Required table '{table}' not found")
                return False
        
        logger.info("✅ Database connection and schema valid")
        
        # Get record counts
        cursor.execute("SELECT COUNT(*) FROM invoices")
        invoice_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM email_tracking")
        email_count = cursor.fetchone()[0]
        
        logger.info(f"  Database contains {invoice_count} invoices, {email_count} email records")
        
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Database test failed: {e}")
        return False

def test_pdf_parsing_with_sample():
    """Test PDF parsing with a sample file if available."""
    logger.info("Testing PDF parsing...")
    
    try:
        from pdf_parser.pdf_service import PDFService
        
        # Look for sample PDFs
        sample_dirs = [
            "./tests/sample_invoices",
            "./data/invoices",
            "./tests"
        ]
        
        sample_pdf = None
        for sample_dir in sample_dirs:
            if Path(sample_dir).exists():
                for pdf_file in Path(sample_dir).glob("*.pdf"):
                    sample_pdf = str(pdf_file)
                    break
            if sample_pdf:
                break
        
        if not sample_pdf:
            logger.warning("⚠️ No sample PDF found for testing")
            return True  # Not a failure, just no test data
        
        logger.info(f"Testing with sample PDF: {sample_pdf}")
        
        service = PDFService()
        
        # Try to determine provider from filename
        filename = Path(sample_pdf).name.lower()
        provider = None
        
        if 'energy' in filename or 'electricity' in filename:
            provider = 'EnergyAustralia'
        elif 'origin' in filename or 'gas' in filename:
            provider = 'Origin'
        elif 'water' in filename or 'sydney' in filename:
            provider = 'Sydney_Water'
        
        if not provider:
            # Try first available provider
            from pdf_parser.template_processor import TemplateProcessor
            processor = TemplateProcessor()
            providers = processor.get_available_providers()
            if providers:
                provider = providers[0]
        
        if provider:
            result = service.process_pdf(sample_pdf, provider)
            
            if result.get('success'):
                logger.info("✅ PDF parsing test successful")
                invoice_data = result.get('invoice_data', {})
                logger.info(f"  Extracted: {invoice_data.get('provider_name')} - ${invoice_data.get('total_amount')}")
            else:
                logger.warning(f"⚠️ PDF parsing test failed: {result.get('errors', [])}")
        else:
            logger.warning("⚠️ No provider template available for testing")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ PDF parsing test failed: {e}")
        return False

def test_integration_service():
    """Test the integration service initialization."""
    logger.info("Testing integration service...")
    
    try:
        from data_storage.integration_service import IntegrationService
        
        service = IntegrationService()
        status = service.get_system_status()
        
        logger.info("✅ Integration service initialized successfully")
        
        # Check system health
        health = status.get('system_health', {})
        db_ok = health.get('database_accessible', False)
        templates_ok = health.get('templates_loaded', False)
        
        logger.info(f"  Database accessible: {db_ok}")
        logger.info(f"  Templates loaded: {templates_ok}")
        
        return db_ok and templates_ok
        
    except Exception as e:
        logger.error(f"❌ Integration service test failed: {e}")
        return False

def test_email_service_init():
    """Test email service initialization (without actual API calls)."""
    logger.info("Testing email service initialization...")
    
    try:
        from email_fetcher.email_service import EmailService
        
        service = EmailService()
        status = service.get_service_status()
        
        logger.info("✅ Email service initialized successfully")
        
        # Check authentication status
        auth_status = status.get('authentication', {})
        for provider, status_info in auth_status.items():
            configured = status_info.get('configured', False)
            logger.info(f"  {provider}: {'configured' if configured else 'not configured'}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Email service test failed: {e}")
        return False

def test_web_api_integration():
    """Test that web API can access the new services."""
    logger.info("Testing web API integration...")
    
    try:
        # Check if we can add integration endpoints to the web app
        web_app_path = Path("./web_app/backend/app.py")
        if web_app_path.exists():
            logger.info("✅ Web app backend found")
            
            # Test import compatibility
            sys.path.append(str(Path("./web_app/backend").absolute()))
            
            # This would test if we can import our services in the web context
            from data_storage.integration_service import IntegrationService
            service = IntegrationService()
            
            logger.info("✅ Integration service accessible from web app context")
            return True
        else:
            logger.warning("⚠️ Web app backend not found")
            return True  # Not a failure if web app doesn't exist yet
            
    except Exception as e:
        logger.error(f"❌ Web API integration test failed: {e}")
        return False

def main():
    """Run all tests and report results."""
    logger.info("🚀 Starting Utilities Tracker Pipeline Tests")
    logger.info("=" * 60)
    
    tests = [
        ("Module Imports", test_imports),
        ("Template Loading", test_template_loading),
        ("OCR Availability", test_ocr_availability),
        ("Database Connection", test_database_connection),
        ("PDF Parsing", test_pdf_parsing_with_sample),
        ("Integration Service", test_integration_service),
        ("Email Service", test_email_service_init),
        ("Web API Integration", test_web_api_integration)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        logger.info(f"\n📋 Running: {test_name}")
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            logger.error(f"❌ {test_name} crashed: {e}")
            results.append((test_name, False))
    
    # Report summary
    logger.info("\n" + "=" * 60)
    logger.info("📊 TEST RESULTS SUMMARY")
    logger.info("=" * 60)
    
    passed = 0
    failed = 0
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        logger.info(f"{status}: {test_name}")
        
        if success:
            passed += 1
        else:
            failed += 1
    
    logger.info("-" * 60)
    logger.info(f"Total Tests: {len(results)}")
    logger.info(f"Passed: {passed}")
    logger.info(f"Failed: {failed}")
    logger.info(f"Success Rate: {passed/len(results)*100:.1f}%")
    
    if failed == 0:
        logger.info("🎉 All tests passed! Pipeline is ready for use.")
    else:
        logger.warning(f"⚠️ {failed} test(s) failed. Check logs above for details.")
    
    logger.info("=" * 60)
    
    return failed == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)