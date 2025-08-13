#!/usr/bin/env python3
"""
Local Database Initialization Script

This script initializes the local SQLite database with the required schema
and optionally loads sample data for development and testing.
"""

import os
import sys
import sqlite3
import json
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Local imports (will be available after project structure is complete)
# from data_storage.models import create_tables
# from data_storage.sample_data import generate_sample_invoices


def create_database_schema(db_path: str):
    """Create the database schema for invoices."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create invoices table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS invoices (
        id TEXT PRIMARY KEY,
        provider_name TEXT NOT NULL,
        service_type TEXT NOT NULL CHECK (service_type IN ('Electricity', 'Gas', 'Water')),
        invoice_date DATE NOT NULL,
        total_amount DECIMAL(10,2) NOT NULL,
        usage_quantity DECIMAL(10,3),
        usage_rate DECIMAL(10,4),
        service_charge DECIMAL(10,2),
        billing_period_start DATE,
        billing_period_end DATE,
        file_path TEXT,
        processing_status TEXT DEFAULT 'processed',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        account_number TEXT,
        raw_text TEXT,
        parsing_confidence DECIMAL(3,2),
        validation_errors TEXT
    )
    ''')
    
    # Create processing_history table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS processing_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        provider_name TEXT NOT NULL,
        processing_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        invoices_found INTEGER DEFAULT 0,
        invoices_processed INTEGER DEFAULT 0,
        invoices_failed INTEGER DEFAULT 0,
        status TEXT DEFAULT 'completed',
        error_details TEXT,
        processing_time_seconds INTEGER
    )
    ''')
    
    # Create email_tracking table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS email_tracking (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email_id TEXT UNIQUE NOT NULL,
        provider_name TEXT NOT NULL,
        subject TEXT,
        sender TEXT,
        received_date TIMESTAMP,
        processed BOOLEAN DEFAULT FALSE,
        processed_date TIMESTAMP,
        attachment_count INTEGER DEFAULT 0,
        processing_status TEXT DEFAULT 'pending'
    )
    ''')
    
    # Create indexes for performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_invoices_provider ON invoices(provider_name)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_invoices_date ON invoices(invoice_date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_invoices_service_type ON invoices(service_type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_processing_history_date ON processing_history(processing_date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_email_tracking_provider ON email_tracking(provider_name)')
    
    conn.commit()
    conn.close()
    
    print(f"✅ Database schema created successfully at: {db_path}")


def generate_sample_data(db_path: str, num_months: int = 24):
    """Generate sample invoice data for development and testing."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    providers = [
        {'name': 'EnergyAustralia', 'service': 'Electricity', 'avg_amount': 250, 'avg_usage': 1200},
        {'name': 'Origin Energy', 'service': 'Gas', 'avg_amount': 120, 'avg_usage': 800},
        {'name': 'Sydney Water', 'service': 'Water', 'avg_amount': 180, 'avg_usage': 150}
    ]
    
    sample_invoices = []
    base_date = datetime.now().replace(day=1) - timedelta(days=30 * num_months)
    
    for month in range(num_months):
        invoice_date = base_date + timedelta(days=30 * month)
        
        for provider in providers:
            # Generate realistic variations
            amount_variation = 0.8 + (0.4 * (month % 12) / 12)  # Seasonal variation
            usage_variation = 0.7 + (0.6 * (month % 12) / 12)
            
            invoice_id = f"{provider['name'].lower().replace(' ', '_')}_{invoice_date.strftime('%Y%m')}"
            total_amount = round(provider['avg_amount'] * amount_variation, 2)
            usage_quantity = round(provider['avg_usage'] * usage_variation, 1)
            usage_rate = round(total_amount / usage_quantity * 0.7, 4) if usage_quantity > 0 else 0
            service_charge = round(total_amount * 0.3, 2)
            
            billing_start = invoice_date.replace(day=1)
            billing_end = (billing_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            
            sample_invoices.append((
                invoice_id,
                provider['name'],
                provider['service'],
                invoice_date.strftime('%Y-%m-%d'),
                total_amount,
                usage_quantity,
                usage_rate,
                service_charge,
                billing_start.strftime('%Y-%m-%d'),
                billing_end.strftime('%Y-%m-%d'),
                f"./data/invoices/{provider['name'].lower().replace(' ', '_')}/{invoice_id}.pdf",
                'processed',
                datetime.now().isoformat(),
                datetime.now().isoformat(),
                f"ACC{12345 + hash(provider['name']) % 10000}",
                f"Sample invoice text for {provider['name']}",
                0.95,
                None
            ))
    
    # Insert sample data
    cursor.executemany('''
    INSERT OR REPLACE INTO invoices (
        id, provider_name, service_type, invoice_date, total_amount,
        usage_quantity, usage_rate, service_charge, billing_period_start,
        billing_period_end, file_path, processing_status, created_at,
        updated_at, account_number, raw_text, parsing_confidence, validation_errors
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', sample_invoices)
    
    # Add sample processing history
    history_entries = []
    for i in range(12):  # Last 12 months
        history_date = datetime.now() - timedelta(days=30 * i)
        for provider in providers:
            history_entries.append((
                provider['name'],
                history_date.isoformat(),
                1,  # invoices_found
                1,  # invoices_processed
                0,  # invoices_failed
                'completed',
                None,
                15  # processing_time_seconds
            ))
    
    cursor.executemany('''
    INSERT INTO processing_history (
        provider_name, processing_date, invoices_found, invoices_processed,
        invoices_failed, status, error_details, processing_time_seconds
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', history_entries)
    
    conn.commit()
    conn.close()
    
    print(f"✅ Sample data generated: {len(sample_invoices)} invoices across {num_months} months")


def export_sample_csv(db_path: str, csv_path: str):
    """Export sample data to CSV for Power BI testing."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT 
        provider_name,
        service_type,
        invoice_date,
        total_amount,
        usage_quantity,
        usage_rate,
        service_charge,
        billing_period_start,
        billing_period_end
    FROM invoices
    ORDER BY invoice_date DESC
    ''')
    
    results = cursor.fetchall()
    
    # Write CSV
    with open(csv_path, 'w') as f:
        f.write("Provider,ServiceType,InvoiceDate,TotalAmount,UsageQuantity,UsageRate,ServiceCharge,BillingStart,BillingEnd\n")
        for row in results:
            f.write(','.join(str(item) if item is not None else '' for item in row) + '\n')
    
    conn.close()
    print(f"✅ Sample CSV exported: {csv_path}")


def setup_directories():
    """Create necessary directories for local development."""
    directories = [
        'data',
        'data/invoices',
        'data/invoices/energy_australia',
        'data/invoices/origin_energy', 
        'data/invoices/sydney_water',
        'data/processed',
        'data/exports',
        'data/backups',
        'logs',
        'tests/sample_invoices'
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
    
    print("✅ Directory structure created")


def main():
    """Initialize local development environment."""
    print("🚀 Initializing Utilities Tracker Local Development Environment")
    print("=" * 60)
    
    # Setup directories
    setup_directories()
    
    # Database setup
    db_path = './data/invoices.db'
    print(f"\n📊 Setting up database: {db_path}")
    create_database_schema(db_path)
    
    # Generate sample data
    print("\n🔄 Generating sample data...")
    generate_sample_data(db_path, num_months=24)
    
    # Export CSV for Power BI
    csv_path = './data/invoices.csv'
    print(f"\n📈 Exporting sample data to CSV: {csv_path}")
    export_sample_csv(db_path, csv_path)
    
    # Copy example configurations
    print("\n⚙️ Setting up configuration files...")
    config_files = [
        ('config/providers.example.json', 'config/providers.json'),
        ('config/credentials.example.json', 'config/credentials.json'),
        ('.env.example', '.env')
    ]
    
    for src, dst in config_files:
        if not Path(dst).exists() and Path(src).exists():
            import shutil
            shutil.copy(src, dst)
            print(f"   Copied {src} → {dst}")
        else:
            print(f"   ⚠️  {dst} already exists or {src} not found")
    
    print("\n" + "=" * 60)
    print("✅ Local development environment initialized successfully!")
    print("\nNext steps:")
    print("1. Edit config/credentials.json with your email API credentials")
    print("2. Edit config/providers.json with your utility provider settings")
    print("3. Edit .env file with your specific configuration")
    print("4. Run: python email_fetcher/fetch_invoices.py --mode=test")
    print("5. Run: python web_app/backend/app.py")
    print("6. Open Power BI and connect to ./data/invoices.csv")
    print("\n🎉 Happy coding!")


if __name__ == '__main__':
    main()