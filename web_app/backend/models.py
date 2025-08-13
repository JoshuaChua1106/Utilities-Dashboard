"""
Database models for the Utilities Tracker web application.

This module defines SQLAlchemy models that work with both local SQLite 
and AWS RDS PostgreSQL databases through the adapter pattern.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List
import os
from sqlalchemy import create_engine, Column, String, DateTime, Numeric, Text, Boolean, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.sql import func

Base = declarative_base()


class Invoice(Base):
    """Invoice model representing utility bill data."""
    
    __tablename__ = 'invoices'
    
    # Primary key and identifiers
    id = Column(String, primary_key=True)
    provider_name = Column(String, nullable=False, index=True)
    service_type = Column(String, nullable=False, index=True)
    account_number = Column(String, nullable=True)
    
    # Financial data
    total_amount = Column(Numeric(10, 2), nullable=False)
    usage_quantity = Column(Numeric(10, 3), nullable=True)
    usage_rate = Column(Numeric(10, 4), nullable=True)
    service_charge = Column(Numeric(10, 2), nullable=True)
    
    # Date information
    invoice_date = Column(DateTime, nullable=False, index=True)
    billing_period_start = Column(DateTime, nullable=True)
    billing_period_end = Column(DateTime, nullable=True)
    
    # File and processing metadata
    file_path = Column(Text, nullable=True)
    processing_status = Column(String, nullable=False, default='processed')
    parsing_confidence = Column(Numeric(3, 2), nullable=True)
    validation_errors = Column(Text, nullable=True)
    raw_text = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    
    def to_dict(self) -> dict:
        """Convert invoice to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'provider_name': self.provider_name,
            'service_type': self.service_type,
            'account_number': self.account_number,
            'total_amount': float(self.total_amount) if self.total_amount else None,
            'usage_quantity': float(self.usage_quantity) if self.usage_quantity else None,
            'usage_rate': float(self.usage_rate) if self.usage_rate else None,
            'service_charge': float(self.service_charge) if self.service_charge else None,
            'invoice_date': self.invoice_date.isoformat() if self.invoice_date else None,
            'billing_period_start': self.billing_period_start.isoformat() if self.billing_period_start else None,
            'billing_period_end': self.billing_period_end.isoformat() if self.billing_period_end else None,
            'file_path': self.file_path,
            'processing_status': self.processing_status,
            'parsing_confidence': float(self.parsing_confidence) if self.parsing_confidence else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class ProcessingHistory(Base):
    """Processing history model for tracking batch operations."""
    
    __tablename__ = 'processing_history'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    provider_name = Column(String, nullable=False, index=True)
    processing_date = Column(DateTime, nullable=False, default=func.now(), index=True)
    invoices_found = Column(Integer, nullable=False, default=0)
    invoices_processed = Column(Integer, nullable=False, default=0)
    invoices_failed = Column(Integer, nullable=False, default=0)
    status = Column(String, nullable=False, default='completed')
    error_details = Column(Text, nullable=True)
    processing_time_seconds = Column(Integer, nullable=True)
    
    def to_dict(self) -> dict:
        """Convert processing history to dictionary."""
        return {
            'id': self.id,
            'provider_name': self.provider_name,
            'processing_date': self.processing_date.isoformat(),
            'invoices_found': self.invoices_found,
            'invoices_processed': self.invoices_processed,
            'invoices_failed': self.invoices_failed,
            'status': self.status,
            'error_details': self.error_details,
            'processing_time_seconds': self.processing_time_seconds
        }


class EmailTracking(Base):
    """Email tracking model for monitoring email processing."""
    
    __tablename__ = 'email_tracking'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    email_id = Column(String, unique=True, nullable=False)
    provider_name = Column(String, nullable=False, index=True)
    subject = Column(Text, nullable=True)
    sender = Column(String, nullable=True)
    received_date = Column(DateTime, nullable=True)
    processed = Column(Boolean, nullable=False, default=False)
    processed_date = Column(DateTime, nullable=True)
    attachment_count = Column(Integer, nullable=False, default=0)
    processing_status = Column(String, nullable=False, default='pending')


class DatabaseManager:
    """Database manager with adapter pattern for local SQLite and AWS RDS."""
    
    def __init__(self):
        """Initialize database connection based on environment."""
        self.engine = self._create_engine()
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
    def _create_engine(self):
        """Create database engine based on environment configuration."""
        if os.getenv('AWS_MODE', 'false').lower() == 'true':
            return self._create_rds_engine()
        else:
            return self._create_sqlite_engine()
    
    def _create_sqlite_engine(self):
        """Create SQLite engine for local development."""
        database_path = os.getenv('DATABASE_PATH', './data/invoices.db')
        database_url = f"sqlite:///{database_path}"
        return create_engine(database_url, connect_args={"check_same_thread": False})
    
    def _create_rds_engine(self):
        """Create PostgreSQL engine for AWS RDS."""
        # In production, these would come from AWS Parameter Store/Secrets Manager
        host = os.getenv('RDS_ENDPOINT', 'localhost')
        database = os.getenv('RDS_DATABASE', 'utilities_tracker')
        username = os.getenv('RDS_USERNAME', 'postgres')
        password = os.getenv('RDS_PASSWORD', 'password')
        port = os.getenv('RDS_PORT', '5432')
        
        database_url = f"postgresql://{username}:{password}@{host}:{port}/{database}"
        return create_engine(database_url, pool_pre_ping=True)
    
    def get_session(self) -> Session:
        """Get database session."""
        return self.SessionLocal()
    
    def create_tables(self):
        """Create all database tables."""
        Base.metadata.create_all(bind=self.engine)
    
    def health_check(self) -> dict:
        """Check database health and return status."""
        try:
            with self.get_session() as session:
                # Test basic query
                from sqlalchemy import text
                result = session.execute(text("SELECT 1")).fetchone()
                
                # Get some basic statistics
                invoice_count = session.query(func.count(Invoice.id)).scalar()
                latest_invoice = session.query(func.max(Invoice.invoice_date)).scalar()
                
                return {
                    'status': 'healthy',
                    'database_type': 'postgresql' if os.getenv('AWS_MODE') == 'true' else 'sqlite',
                    'connection': 'active',
                    'invoice_count': invoice_count,
                    'latest_invoice_date': latest_invoice.isoformat() if latest_invoice else None,
                    'timestamp': datetime.now().isoformat()
                }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }


# Global database manager instance
db_manager = DatabaseManager()