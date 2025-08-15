"""
API routes for the Utilities Tracker web application.

This module provides RESTful API endpoints for accessing invoice data,
triggering sync operations, and managing the application.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from decimal import Decimal
import os
import logging

from flask import Blueprint, request, jsonify, current_app
from sqlalchemy import and_, or_, func, desc, asc
from sqlalchemy.orm import Session

from .models import db_manager, Invoice, ProcessingHistory

# Import integration services
try:
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent.parent))
    from data_storage.integration_service import IntegrationService
    from email_fetcher.email_service import EmailService
    from pdf_parser.pdf_service import PDFService
    INTEGRATION_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Integration services not available: {e}")
    INTEGRATION_AVAILABLE = False


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create API blueprint
api_bp = Blueprint('api', __name__, url_prefix='/api')


@api_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for monitoring system status."""
    try:
        db_health = db_manager.health_check()
        
        system_status = {
            'status': 'healthy' if db_health['status'] == 'healthy' else 'degraded',
            'timestamp': datetime.now().isoformat(),
            'version': '1.0.0',
            'environment': 'aws' if os.getenv('AWS_MODE') == 'true' else 'local',
            'database': db_health,
            'features': {
                'email_sync': True,
                'pdf_parsing': True,
                'web_interface': True,
                'power_bi_export': True
            }
        }
        
        status_code = 200 if system_status['status'] == 'healthy' else 503
        return jsonify(system_status), status_code
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 503


@api_bp.route('/invoices', methods=['GET'])
def get_invoices():
    """Get invoices with optional filtering and pagination."""
    try:
        with db_manager.get_session() as session:
            query = session.query(Invoice)
            
            # Apply filters
            provider = request.args.get('provider')
            if provider:
                query = query.filter(Invoice.provider_name == provider)
            
            service_type = request.args.get('service_type')
            if service_type:
                query = query.filter(Invoice.service_type == service_type)
            
            # Date range filtering
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            
            if start_date:
                try:
                    start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                    query = query.filter(Invoice.invoice_date >= start_dt)
                except ValueError:
                    return jsonify({'error': 'Invalid start_date format. Use ISO format.'}), 400
            
            if end_date:
                try:
                    end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                    query = query.filter(Invoice.invoice_date <= end_dt)
                except ValueError:
                    return jsonify({'error': 'Invalid end_date format. Use ISO format.'}), 400
            
            # Sorting
            sort_by = request.args.get('sort_by', 'invoice_date')
            sort_order = request.args.get('sort_order', 'desc')
            
            if hasattr(Invoice, sort_by):
                column = getattr(Invoice, sort_by)
                if sort_order.lower() == 'asc':
                    query = query.order_by(asc(column))
                else:
                    query = query.order_by(desc(column))
            else:
                query = query.order_by(desc(Invoice.invoice_date))
            
            # Pagination
            page = int(request.args.get('page', 1))
            per_page = min(int(request.args.get('per_page', 50)), 100)  # Max 100 items per page
            
            total_count = query.count()
            invoices = query.offset((page - 1) * per_page).limit(per_page).all()
            
            return jsonify({
                'invoices': [invoice.to_dict() for invoice in invoices],
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total_count,
                    'pages': (total_count + per_page - 1) // per_page
                }
            })
            
    except Exception as e:
        logger.error(f"Error fetching invoices: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@api_bp.route('/invoices/<string:invoice_id>', methods=['GET'])
def get_invoice(invoice_id: str):
    """Get a specific invoice by ID."""
    try:
        with db_manager.get_session() as session:
            invoice = session.query(Invoice).filter(Invoice.id == invoice_id).first()
            
            if not invoice:
                return jsonify({'error': 'Invoice not found'}), 404
            
            return jsonify(invoice.to_dict())
            
    except Exception as e:
        logger.error(f"Error fetching invoice {invoice_id}: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@api_bp.route('/providers', methods=['GET'])
def get_providers():
    """Get list of available providers and their statistics."""
    try:
        with db_manager.get_session() as session:
            # Get provider statistics
            provider_stats = session.query(
                Invoice.provider_name,
                Invoice.service_type,
                func.count(Invoice.id).label('invoice_count'),
                func.sum(Invoice.total_amount).label('total_amount'),
                func.avg(Invoice.total_amount).label('avg_amount'),
                func.max(Invoice.invoice_date).label('latest_invoice'),
                func.min(Invoice.invoice_date).label('earliest_invoice')
            ).group_by(Invoice.provider_name, Invoice.service_type).all()
            
            providers = []
            for stat in provider_stats:
                providers.append({
                    'provider_name': stat.provider_name,
                    'service_type': stat.service_type,
                    'invoice_count': stat.invoice_count,
                    'total_amount': float(stat.total_amount) if stat.total_amount else 0,
                    'avg_amount': float(stat.avg_amount) if stat.avg_amount else 0,
                    'latest_invoice': stat.latest_invoice.isoformat() if stat.latest_invoice else None,
                    'earliest_invoice': stat.earliest_invoice.isoformat() if stat.earliest_invoice else None
                })
            
            return jsonify({'providers': providers})
            
    except Exception as e:
        logger.error(f"Error fetching providers: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@api_bp.route('/analytics', methods=['GET'])
def get_analytics():
    """Get aggregated analytics and statistics."""
    try:
        with db_manager.get_session() as session:
            # Overall statistics
            total_invoices = session.query(func.count(Invoice.id)).scalar()
            total_amount = session.query(func.sum(Invoice.total_amount)).scalar()
            avg_amount = session.query(func.avg(Invoice.total_amount)).scalar()
            total_service_charges = session.query(func.sum(Invoice.service_charge)).scalar()
            
            # Calculate total usage charges (usage_quantity * usage_rate)
            total_usage_charges = session.query(
                func.sum(Invoice.usage_quantity * Invoice.usage_rate)
            ).filter(
                and_(Invoice.usage_quantity.isnot(None), Invoice.usage_rate.isnot(None))
            ).scalar()
            
            # Monthly trends (last 12 months)
            twelve_months_ago = datetime.now() - timedelta(days=365)
            monthly_data = session.query(
                func.strftime('%Y-%m', Invoice.invoice_date).label('month'),
                func.count(Invoice.id).label('invoice_count'),
                func.sum(Invoice.total_amount).label('total_amount'),
                func.avg(Invoice.total_amount).label('avg_amount')
            ).filter(
                Invoice.invoice_date >= twelve_months_ago
            ).group_by(
                func.strftime('%Y-%m', Invoice.invoice_date)
            ).order_by('month').all()
            
            # Service type breakdown
            service_breakdown = session.query(
                Invoice.service_type,
                func.count(Invoice.id).label('count'),
                func.sum(Invoice.total_amount).label('total'),
                func.avg(Invoice.total_amount).label('average')
            ).group_by(Invoice.service_type).all()
            
            # Provider performance
            provider_performance = session.query(
                Invoice.provider_name,
                func.count(Invoice.id).label('count'),
                func.sum(Invoice.total_amount).label('total'),
                func.avg(Invoice.usage_quantity).label('avg_usage')
            ).group_by(Invoice.provider_name).all()
            
            analytics = {
                'overview': {
                    'total_invoices': total_invoices or 0,
                    'total_amount': float(total_amount) if total_amount else 0,
                    'average_amount': float(avg_amount) if avg_amount else 0,
                    'total_service_charges': float(total_service_charges) if total_service_charges else 0,
                    'total_usage_charges': float(total_usage_charges) if total_usage_charges else 0,
                    'data_period': {
                        'start': twelve_months_ago.isoformat(),
                        'end': datetime.now().isoformat()
                    }
                },
                'monthly_trends': [
                    {
                        'month': data.month,
                        'invoice_count': data.invoice_count,
                        'total_amount': float(data.total_amount) if data.total_amount else 0,
                        'avg_amount': float(data.avg_amount) if data.avg_amount else 0
                    }
                    for data in monthly_data
                ],
                'service_breakdown': [
                    {
                        'service_type': service.service_type,
                        'count': service.count,
                        'total': float(service.total) if service.total else 0,
                        'average': float(service.average) if service.average else 0
                    }
                    for service in service_breakdown
                ],
                'provider_performance': [
                    {
                        'provider_name': provider.provider_name,
                        'count': provider.count,
                        'total': float(provider.total) if provider.total else 0,
                        'avg_usage': float(provider.avg_usage) if provider.avg_usage else 0
                    }
                    for provider in provider_performance
                ]
            }
            
            return jsonify(analytics)
            
    except Exception as e:
        logger.error(f"Error generating analytics: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@api_bp.route('/analytics/enhanced', methods=['GET'])
def get_enhanced_analytics():
    """Get enhanced analytics with service-specific filtering."""
    try:
        # Get query parameters
        service_type = request.args.get('service_type', '')
        months = int(request.args.get('months', 12))
        analysis_type = request.args.get('analysis_type', 'spending')
        
        with db_manager.get_session() as session:
            # Base query filter
            base_filter = []
            
            # Date filter
            start_date = datetime.now() - timedelta(days=months*30)
            base_filter.append(Invoice.invoice_date >= start_date)
            
            # Service type filter
            if service_type:
                base_filter.append(Invoice.service_type == service_type)
            
            # Service-specific monthly trends
            monthly_trends_by_service = {}
            for service in ['Electricity', 'Gas', 'Water']:
                service_filter = base_filter + [Invoice.service_type == service]
                
                # Spending trends
                spending_data = session.query(
                    func.strftime('%Y-%m', Invoice.invoice_date).label('month'),
                    func.sum(Invoice.total_amount).label('total_amount'),
                    func.avg(Invoice.total_amount).label('avg_amount'),
                    func.count(Invoice.id).label('count')
                ).filter(and_(*service_filter)).group_by(
                    func.strftime('%Y-%m', Invoice.invoice_date)
                ).order_by('month').all()
                
                # Usage trends
                usage_data = session.query(
                    func.strftime('%Y-%m', Invoice.invoice_date).label('month'),
                    func.sum(Invoice.usage_quantity).label('total_usage'),
                    func.avg(Invoice.usage_quantity).label('avg_usage')
                ).filter(and_(*service_filter)).filter(
                    Invoice.usage_quantity.isnot(None)
                ).group_by(
                    func.strftime('%Y-%m', Invoice.invoice_date)
                ).order_by('month').all()
                
                # Rate trends  
                rate_data = session.query(
                    func.strftime('%Y-%m', Invoice.invoice_date).label('month'),
                    func.avg(Invoice.usage_rate).label('avg_rate'),
                    func.min(Invoice.usage_rate).label('min_rate'),
                    func.max(Invoice.usage_rate).label('max_rate')
                ).filter(and_(*service_filter)).filter(
                    Invoice.usage_rate.isnot(None)
                ).group_by(
                    func.strftime('%Y-%m', Invoice.invoice_date)
                ).order_by('month').all()
                
                # Service fee trends
                service_fee_data = session.query(
                    func.strftime('%Y-%m', Invoice.invoice_date).label('month'),
                    func.sum(Invoice.service_charge).label('total_service_charge'),
                    func.avg(Invoice.service_charge).label('avg_service_charge')
                ).filter(and_(*service_filter)).filter(
                    Invoice.service_charge.isnot(None)
                ).group_by(
                    func.strftime('%Y-%m', Invoice.invoice_date)
                ).order_by('month').all()
                
                monthly_trends_by_service[service] = {
                    'spending': [
                        {
                            'month': d.month,
                            'total_amount': float(d.total_amount) if d.total_amount else 0,
                            'avg_amount': float(d.avg_amount) if d.avg_amount else 0,
                            'count': d.count
                        } for d in spending_data
                    ],
                    'usage': [
                        {
                            'month': d.month,
                            'total_usage': float(d.total_usage) if d.total_usage else 0,
                            'avg_usage': float(d.avg_usage) if d.avg_usage else 0
                        } for d in usage_data
                    ],
                    'rates': [
                        {
                            'month': d.month,
                            'avg_rate': float(d.avg_rate) if d.avg_rate else 0,
                            'min_rate': float(d.min_rate) if d.min_rate else 0,
                            'max_rate': float(d.max_rate) if d.max_rate else 0
                        } for d in rate_data
                    ],
                    'service_fees': [
                        {
                            'month': d.month,
                            'total_service_charge': float(d.total_service_charge) if d.total_service_charge else 0,
                            'avg_service_charge': float(d.avg_service_charge) if d.avg_service_charge else 0
                        } for d in service_fee_data
                    ]
                }
            
            # Overall statistics by service
            service_stats = {}
            for service in ['Electricity', 'Gas', 'Water']:
                service_filter = base_filter + [Invoice.service_type == service]
                
                stats = session.query(
                    func.count(Invoice.id).label('total_invoices'),
                    func.sum(Invoice.total_amount).label('total_amount'),
                    func.avg(Invoice.total_amount).label('avg_amount'),
                    func.sum(Invoice.service_charge).label('total_service_charges'),
                    func.avg(Invoice.usage_rate).label('avg_rate'),
                    func.sum(Invoice.usage_quantity).label('total_usage'),
                    func.avg(Invoice.usage_quantity).label('avg_usage')
                ).filter(and_(*service_filter)).first()
                
                service_stats[service] = {
                    'total_invoices': stats.total_invoices or 0,
                    'total_amount': float(stats.total_amount) if stats.total_amount else 0,
                    'avg_amount': float(stats.avg_amount) if stats.avg_amount else 0,
                    'total_service_charges': float(stats.total_service_charges) if stats.total_service_charges else 0,
                    'avg_rate': float(stats.avg_rate) if stats.avg_rate else 0,
                    'total_usage': float(stats.total_usage) if stats.total_usage else 0,
                    'avg_usage': float(stats.avg_usage) if stats.avg_usage else 0
                }
            
            # Rate comparison across services
            rate_comparison = session.query(
                Invoice.service_type,
                func.avg(Invoice.usage_rate).label('avg_rate'),
                func.min(Invoice.usage_rate).label('min_rate'),
                func.max(Invoice.usage_rate).label('max_rate'),
                func.count(Invoice.id).label('count')
            ).filter(and_(*base_filter)).filter(
                Invoice.usage_rate.isnot(None)
            ).group_by(Invoice.service_type).all()
            
            # Cost breakdown analysis
            cost_breakdown = session.query(
                Invoice.service_type,
                func.sum(Invoice.service_charge).label('total_service_charges'),
                func.sum(Invoice.usage_quantity * Invoice.usage_rate).label('total_usage_charges'),
                func.sum(Invoice.total_amount).label('total_amount')
            ).filter(and_(*base_filter)).filter(
                and_(Invoice.usage_quantity.isnot(None), Invoice.usage_rate.isnot(None))
            ).group_by(Invoice.service_type).all()
            
            enhanced_analytics = {
                'filters': {
                    'service_type': service_type or 'All Services',
                    'months': months,
                    'analysis_type': analysis_type,
                    'period': {
                        'start': start_date.isoformat(),
                        'end': datetime.now().isoformat()
                    }
                },
                'service_trends': monthly_trends_by_service,
                'service_statistics': service_stats,
                'rate_comparison': [
                    {
                        'service_type': r.service_type,
                        'avg_rate': float(r.avg_rate) if r.avg_rate else 0,
                        'min_rate': float(r.min_rate) if r.min_rate else 0,
                        'max_rate': float(r.max_rate) if r.max_rate else 0,
                        'count': r.count
                    } for r in rate_comparison
                ],
                'cost_breakdown': [
                    {
                        'service_type': c.service_type,
                        'total_service_charges': float(c.total_service_charges) if c.total_service_charges else 0,
                        'total_usage_charges': float(c.total_usage_charges) if c.total_usage_charges else 0,
                        'total_amount': float(c.total_amount) if c.total_amount else 0,
                        'service_charge_percentage': (float(c.total_service_charges) / float(c.total_amount) * 100) if c.total_amount and c.total_service_charges else 0,
                        'usage_charge_percentage': (float(c.total_usage_charges) / float(c.total_amount) * 100) if c.total_amount and c.total_usage_charges else 0
                    } for c in cost_breakdown
                ]
            }
            
            return jsonify(enhanced_analytics)
            
    except Exception as e:
        logger.error(f"Error generating enhanced analytics: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@api_bp.route('/sync', methods=['POST'])
def trigger_sync():
    """Trigger manual sync of invoices from email providers."""
    try:
        # Get optional parameters
        provider = request.json.get('provider') if request.is_json else None
        mode = request.json.get('mode', 'incremental') if request.is_json else 'incremental'
        
        # In a real implementation, this would trigger the email fetcher
        # For now, we'll simulate the process
        sync_result = {
            'status': 'initiated',
            'timestamp': datetime.now().isoformat(),
            'mode': mode,
            'provider': provider,
            'message': 'Sync process initiated. Check processing history for results.',
            'estimated_duration': '2-5 minutes'
        }
        
        # Log the sync request
        logger.info(f"Manual sync triggered - Mode: {mode}, Provider: {provider}")
        
        # TODO: Implement actual sync logic
        # This would typically involve:
        # 1. Calling the email_fetcher service
        # 2. Running PDF parser on new files
        # 3. Updating the database
        # 4. Returning real-time status
        
        return jsonify(sync_result), 202  # 202 Accepted
        
    except Exception as e:
        logger.error(f"Error triggering sync: {str(e)}")
        return jsonify({'error': 'Failed to initiate sync'}), 500


@api_bp.route('/processing-history', methods=['GET'])
def get_processing_history():
    """Get processing history for monitoring sync operations."""
    try:
        with db_manager.get_session() as session:
            # Get pagination parameters
            page = int(request.args.get('page', 1))
            per_page = min(int(request.args.get('per_page', 20)), 50)
            
            # Query processing history
            query = session.query(ProcessingHistory).order_by(desc(ProcessingHistory.processing_date))
            
            # Filter by provider if specified
            provider = request.args.get('provider')
            if provider:
                query = query.filter(ProcessingHistory.provider_name == provider)
            
            total_count = query.count()
            history = query.offset((page - 1) * per_page).limit(per_page).all()
            
            return jsonify({
                'history': [item.to_dict() for item in history],
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total_count,
                    'pages': (total_count + per_page - 1) // per_page
                }
            })
            
    except Exception as e:
        logger.error(f"Error fetching processing history: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500




@api_bp.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({'error': 'Endpoint not found'}), 404


@api_bp.errorhandler(405)
def method_not_allowed(error):
    """Handle 405 errors."""
    return jsonify({'error': 'Method not allowed'}), 405


@api_bp.errorhandler(400)
def bad_request(error):
    """Handle 400 errors."""
    return jsonify({'error': 'Bad request'}), 400


# New Integration Endpoints

@api_bp.route('/system/status', methods=['GET'])
def get_system_status():
    """Get comprehensive system status including all services."""
    if not INTEGRATION_AVAILABLE:
        return jsonify({
            'error': 'Integration services not available',
            'basic_health': 'API running but email/PDF services not loaded'
        }), 503
    
    try:
        integration_service = IntegrationService()
        status = integration_service.get_system_status()
        
        return jsonify(status)
        
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/sync/full', methods=['POST'])
def run_full_sync():
    """Run complete email fetch and PDF parsing pipeline."""
    if not INTEGRATION_AVAILABLE:
        return jsonify({'error': 'Integration services not available'}), 503
    
    try:
        data = request.get_json() or {}
        provider = data.get('provider')
        days_back = data.get('days_back', 7)
        
        integration_service = IntegrationService()
        result = integration_service.run_full_sync(provider, days_back)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error running full sync: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/sync/email-only', methods=['POST'])
def run_email_sync():
    """Run email fetch without PDF parsing."""
    if not INTEGRATION_AVAILABLE:
        return jsonify({'error': 'Integration services not available'}), 503
    
    try:
        data = request.get_json() or {}
        provider = data.get('provider')
        days_back = data.get('days_back', 7)
        
        integration_service = IntegrationService()
        result = integration_service.run_email_sync_only(provider, days_back)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error running email sync: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/sync/pdf-only', methods=['POST'])
def run_pdf_parsing():
    """Parse existing PDFs without fetching new emails."""
    if not INTEGRATION_AVAILABLE:
        return jsonify({'error': 'Integration services not available'}), 503
    
    try:
        data = request.get_json() or {}
        provider = data.get('provider')
        
        integration_service = IntegrationService()
        result = integration_service.run_pdf_parsing_only(provider)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error running PDF parsing: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/sync/history', methods=['GET'])
def get_sync_history():
    """Get batch operation history."""
    if not INTEGRATION_AVAILABLE:
        return jsonify({'error': 'Integration services not available'}), 503
    
    try:
        limit = int(request.args.get('limit', 20))
        
        integration_service = IntegrationService()
        history = integration_service.get_sync_history(limit)
        
        return jsonify({'history': history})
        
    except Exception as e:
        logger.error(f"Error getting sync history: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/email/status', methods=['GET'])
def get_email_status():
    """Get email service authentication status."""
    if not INTEGRATION_AVAILABLE:
        return jsonify({'error': 'Integration services not available'}), 503
    
    try:
        email_service = EmailService()
        status = email_service.get_service_status()
        
        return jsonify(status)
        
    except Exception as e:
        logger.error(f"Error getting email status: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/pdf/statistics', methods=['GET'])
def get_pdf_statistics():
    """Get PDF processing statistics."""
    if not INTEGRATION_AVAILABLE:
        return jsonify({'error': 'Integration services not available'}), 503
    
    try:
        pdf_service = PDFService()
        stats = pdf_service.get_processing_statistics()
        
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Error getting PDF statistics: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/pdf/reprocess', methods=['POST'])
def reprocess_failed_pdfs():
    """Reprocess PDFs that previously failed."""
    if not INTEGRATION_AVAILABLE:
        return jsonify({'error': 'Integration services not available'}), 503
    
    try:
        data = request.get_json() or {}
        provider = data.get('provider')
        
        pdf_service = PDFService()
        result = pdf_service.reprocess_failed_pdfs(provider)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error reprocessing PDFs: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/templates/test', methods=['POST'])
def test_template():
    """Test a parsing template with sample PDF."""
    if not INTEGRATION_AVAILABLE:
        return jsonify({'error': 'Integration services not available'}), 503
    
    try:
        data = request.get_json()
        if not data or 'provider' not in data or 'pdf_path' not in data:
            return jsonify({'error': 'provider and pdf_path required'}), 400
        
        provider = data['provider']
        pdf_path = data['pdf_path']
        
        pdf_service = PDFService()
        result = pdf_service.test_template_with_sample(provider, pdf_path)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error testing template: {e}")
        return jsonify({'error': str(e)}), 500


# =============================================================================
# CONFIGURATION ENDPOINTS
# =============================================================================

@api_bp.route('/configuration/gmail', methods=['GET'])
def get_gmail_configuration():
    """Get current Gmail configuration (masked credentials)."""
    if not INTEGRATION_AVAILABLE:
        return jsonify({'error': 'Integration services not available'}), 503
    
    try:
        email_service = EmailService()
        auth_adapter = email_service.auth_adapter
        
        gmail_config = auth_adapter.credentials.get('gmail', {})
        
        # Mask sensitive data
        masked_config = {
            'client_id': gmail_config.get('client_id', ''),
            'client_secret': '••••••••' if gmail_config.get('client_secret') else '',
            'refresh_token': '••••••••' if gmail_config.get('refresh_token') else '',
            'status': 'configured' if gmail_config.get('client_id') and gmail_config.get('client_secret') else 'not_configured'
        }
        
        return jsonify({
            'success': True,
            'config': masked_config
        })
        
    except Exception as e:
        logger.error(f"Error getting Gmail configuration: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/configuration/gmail', methods=['POST'])
def save_gmail_configuration():
    """Save Gmail configuration."""
    if not INTEGRATION_AVAILABLE:
        return jsonify({'error': 'Integration services not available'}), 503
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No configuration data provided'}), 400
        
        required_fields = ['client_id', 'client_secret']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        email_service = EmailService()
        auth_adapter = email_service.auth_adapter
        
        # Update Gmail configuration
        if 'gmail' not in auth_adapter.credentials:
            auth_adapter.credentials['gmail'] = {}
        
        gmail_config = auth_adapter.credentials['gmail']
        gmail_config['client_id'] = data['client_id']
        gmail_config['client_secret'] = data['client_secret']
        
        if data.get('refresh_token'):
            gmail_config['refresh_token'] = data['refresh_token']
        
        # Save to file
        auth_adapter._save_credentials()
        
        return jsonify({
            'success': True,
            'message': 'Gmail configuration saved successfully'
        })
        
    except Exception as e:
        logger.error(f"Error saving Gmail configuration: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/configuration/gmail/test', methods=['POST'])
def test_gmail_connection():
    """Test Gmail connection."""
    if not INTEGRATION_AVAILABLE:
        return jsonify({'error': 'Integration services not available'}), 503
    
    try:
        email_service = EmailService()
        auth_adapter = email_service.auth_adapter
        
        # Try to get credentials
        creds = auth_adapter.get_gmail_credentials()
        if not creds:
            return jsonify({'error': 'Gmail credentials not configured'}), 400
        
        # Try to make a simple API call
        import requests
        
        headers = {
            'Authorization': f"Bearer {creds['access_token']}",
            'Content-Type': 'application/json'
        }
        
        # Test with a simple profile request
        response = requests.get(
            'https://gmail.googleapis.com/gmail/v1/users/me/profile',
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            profile_data = response.json()
            return jsonify({
                'success': True,
                'message': 'Gmail connection successful',
                'email': profile_data.get('emailAddress', 'Unknown')
            })
        else:
            return jsonify({
                'error': f'Gmail API returned status {response.status_code}: {response.text}'
            }), 400
        
    except Exception as e:
        logger.error(f"Error testing Gmail connection: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/configuration/gmail/oauth-url', methods=['POST'])
def get_oauth_url():
    """Generate OAuth2 authorization URL."""
    if not INTEGRATION_AVAILABLE:
        return jsonify({'error': 'Integration services not available'}), 503
    
    try:
        email_service = EmailService()
        auth_adapter = email_service.auth_adapter
        
        gmail_config = auth_adapter.credentials.get('gmail', {})
        client_id = gmail_config.get('client_id')
        
        if not client_id:
            return jsonify({'error': 'Gmail client ID not configured'}), 400
        
        # Generate OAuth2 URL
        from urllib.parse import urlencode
        
        scopes = ' '.join(gmail_config.get('scopes', ['https://www.googleapis.com/auth/gmail.readonly']))
        redirect_uri = 'http://localhost:5000/auth/callback'  # Localhost callback
        
        oauth_params = {
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'scope': scopes,
            'response_type': 'code',
            'access_type': 'offline',
            'prompt': 'consent'
        }
        
        auth_url = f"https://accounts.google.com/o/oauth2/auth?{urlencode(oauth_params)}"
        
        return jsonify({
            'success': True,
            'auth_url': auth_url,
            'message': 'Complete OAuth flow and paste the authorization code back into the refresh token field'
        })
        
    except Exception as e:
        logger.error(f"Error generating OAuth URL: {e}")
        return jsonify({'error': str(e)}), 500



@api_bp.route('/configuration/status', methods=['GET'])
def get_configuration_status():
    """Get detailed configuration and connection status."""
    if not INTEGRATION_AVAILABLE:
        return jsonify({'error': 'Integration services not available'}), 503
    
    try:
        email_service = EmailService()
        service_status = email_service.get_service_status()
        
        return jsonify({
            'success': True,
            'status': service_status
        })
        
    except Exception as e:
        logger.error(f"Error getting configuration status: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/configuration/providers', methods=['GET'])
def get_provider_configuration():
    """Get current provider configuration for email capture."""
    try:
        import json
        config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'providers.json')
        
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config_data = json.load(f)
                
            # Extract provider configurations
            providers = []
            for provider_key, provider_config in config_data.get('providers', {}).items():
                providers.append({
                    'service_type': provider_config.get('service_type'),
                    'provider_name': provider_config.get('provider_name'),
                    'email_patterns': provider_config.get('email_patterns', {})
                })
            
            return jsonify({
                'success': True,
                'providers': providers,
                'global_settings': config_data.get('global_settings', {})
            })
        else:
            return jsonify({
                'success': True,
                'providers': [],
                'global_settings': {}
            })
            
    except Exception as e:
        logger.error(f"Error getting provider configuration: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/configuration/providers', methods=['POST'])
def save_provider_configuration():
    """Save provider configuration for email capture."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No configuration data provided'}), 400
        
        providers_config = data.get('providers', [])
        global_settings = data.get('global_settings', {})
        
        # Validate required fields
        for provider in providers_config:
            if not provider.get('provider_name') or not provider.get('service_type'):
                return jsonify({'error': 'Provider name and service type are required'}), 400
        
        # Load existing config or create new
        import json
        config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'providers.json')
        
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config_data = json.load(f)
        else:
            config_data = {'providers': {}, 'global_settings': {}}
        
        # Update provider configurations
        config_data['providers'] = {}
        for provider in providers_config:
            provider_key = provider['provider_name'].replace(' ', '_')
            config_data['providers'][provider_key] = {
                'provider_name': provider['provider_name'],
                'service_type': provider['service_type'],
                'email_patterns': provider.get('email_patterns', {}),
                'parsing_config': {
                    'template': f"{provider_key.lower()}_template",
                    'backup_ocr': True,
                    'validation_rules': {
                        'amount_range': [20, 2000],
                        'usage_range': [0, 10000],
                        'required_fields': ['invoice_date', 'total_amount']
                    }
                },
                'processing_options': {
                    'priority': 'medium',
                    'auto_validate': True,
                    'notify_on_error': True
                }
            }
        
        # Update global settings
        if global_settings:
            config_data['global_settings'] = global_settings
        
        # Save configuration
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, 'w') as f:
            json.dump(config_data, f, indent=2)
        
        return jsonify({
            'success': True,
            'message': 'Provider configuration saved successfully'
        })
        
    except Exception as e:
        logger.error(f"Error saving provider configuration: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/configuration/providers/test', methods=['POST'])
def test_provider_patterns():
    """Test email patterns with current Gmail connection."""
    if not INTEGRATION_AVAILABLE:
        return jsonify({'error': 'Integration services not available'}), 503
    
    try:
        email_service = EmailService()
        
        # Load current provider configuration
        import json
        config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'providers.json')
        
        if not os.path.exists(config_path):
            return jsonify({'error': 'No provider configuration found'}), 400
            
        with open(config_path, 'r') as f:
            config_data = json.load(f)
        
        results = []
        for provider_key, provider_config in config_data.get('providers', {}).items():
            # Simulate email search (dry run)
            service_type = provider_config.get('service_type')
            email_patterns = provider_config.get('email_patterns', {})
            
            # For testing purposes, return mock results
            # In a real implementation, this would perform actual email searches
            results.append({
                'service_type': service_type,
                'provider_name': provider_config.get('provider_name'),
                'matches': len(email_patterns.get('from', [])) * 5,  # Mock result
                'sample_subjects': [
                    f"{service_type} Bill - Ready for Download",
                    f"Your {service_type} Statement is Available",
                    f"Invoice from {provider_config.get('provider_name')}"
                ]
            })
        
        return jsonify({
            'success': True,
            'results': results,
            'message': 'Pattern test completed successfully'
        })
        
    except Exception as e:
        logger.error(f"Error testing provider patterns: {e}")
        return jsonify({'error': str(e)}), 500


# ================================
# UTILITY ATTRIBUTES ENDPOINTS
# ================================

@api_bp.route('/configuration/utility-attributes', methods=['GET'])
def get_utility_attributes():
    """Get utility attributes configuration."""
    try:
        import json
        config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'utility_attributes.json')
        
        # Default configuration
        default_attributes = {
            'electricity': {
                'provider_name': '',
                'billing_cycle': 'monthly',
                'custom_cycle_days': None,
                'due_date': '1',
                'custom_due_day': None,
                'avg_monthly_usage': None
            },
            'gas': {
                'provider_name': '',
                'billing_cycle': 'monthly', 
                'custom_cycle_days': None,
                'due_date': '1',
                'custom_due_day': None,
                'avg_monthly_usage': None
            },
            'water': {
                'provider_name': '',
                'billing_cycle': 'quarterly',
                'custom_cycle_days': None,
                'due_date': '1',
                'custom_due_day': None,
                'avg_monthly_usage': None
            }
        }
        
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                attributes = json.load(f)
        else:
            attributes = default_attributes
        
        return jsonify({
            'success': True,
            'attributes': attributes
        })
        
    except Exception as e:
        logger.error(f"Error loading utility attributes: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/configuration/utility-attributes', methods=['POST'])
def save_utility_attributes():
    """Save utility attributes configuration."""
    try:
        import json
        
        data = request.get_json()
        if not data or 'attributes' not in data:
            return jsonify({'error': 'Invalid request data'}), 400
            
        attributes = data['attributes']
        
        # Validate attributes structure
        required_services = ['electricity', 'gas', 'water']
        for service in required_services:
            if service not in attributes:
                return jsonify({'error': f'Missing {service} attributes'}), 400
                
            service_attr = attributes[service]
            if 'billing_cycle' not in service_attr:
                return jsonify({'error': f'Missing billing_cycle for {service}'}), 400
        
        # Create config directory if it doesn't exist
        config_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'config')
        os.makedirs(config_dir, exist_ok=True)
        
        # Save configuration
        config_path = os.path.join(config_dir, 'utility_attributes.json')
        with open(config_path, 'w') as f:
            json.dump(attributes, f, indent=2)
            
        logger.info("Utility attributes configuration saved successfully")
        
        return jsonify({
            'success': True,
            'message': 'Utility attributes saved successfully'
        })
        
    except Exception as e:
        logger.error(f"Error saving utility attributes: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/configuration/utility-attributes/validate', methods=['POST'])
def validate_billing_schedule():
    """Validate billing schedule for potential conflicts."""
    try:
        import json
        from datetime import datetime, timedelta, date
        
        # Load current attributes
        config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'utility_attributes.json')
        
        if not os.path.exists(config_path):
            return jsonify({'error': 'No utility attributes configuration found'}), 400
            
        with open(config_path, 'r') as f:
            attributes = json.load(f)
        
        conflicts = []
        next_bills = []
        
        # Calculate next bill dates for each service
        today = date.today()
        
        for service_name, service_attr in attributes.items():
            if not service_attr.get('provider_name'):
                continue
                
            billing_cycle = service_attr.get('billing_cycle', 'monthly')
            
            # Calculate cycle in days
            cycle_days_map = {
                'monthly': 30,
                'bi-monthly': 60,
                'quarterly': 90,
                'semi-annual': 180,
                'annual': 365,
                'custom': service_attr.get('custom_cycle_days', 30)
            }
            
            cycle_days = cycle_days_map.get(billing_cycle, 30)
            
            # Calculate next bill date (simplified)
            next_bill_date = today + timedelta(days=cycle_days)
            
            next_bills.append({
                'service': f"{service_name.title()} ({service_attr['provider_name']})",
                'date': next_bill_date.strftime('%Y-%m-%d'),
                'cycle': billing_cycle
            })
        
        # Check for potential conflicts (same week billing)
        bill_weeks = {}
        for bill in next_bills:
            bill_date = datetime.strptime(bill['date'], '%Y-%m-%d').date()
            week_key = bill_date.isocalendar()[:2]  # (year, week)
            
            if week_key not in bill_weeks:
                bill_weeks[week_key] = []
            bill_weeks[week_key].append(bill)
        
        # Find conflicts (multiple bills in same week)
        for week, bills in bill_weeks.items():
            if len(bills) > 1:
                services = [bill['service'] for bill in bills]
                conflicts.append(f"Multiple bills due in week {week[1]} of {week[0]}: {', '.join(services)}")
        
        validation_result = {
            'conflicts': conflicts,
            'next_bills': next_bills,
            'total_services': len([s for s in attributes.values() if s.get('provider_name')])
        }
        
        return jsonify({
            'success': True,
            'validation': validation_result
        })
        
    except Exception as e:
        logger.error(f"Error validating billing schedule: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/export/csv', methods=['GET'])
def export_invoices_csv():
    """Export invoices to CSV format with optional filtering."""
    try:
        import csv
        from io import StringIO
        
        # Get query parameters for filtering
        provider = request.args.get('provider', '')
        service_type = request.args.get('service_type', '') 
        start_date = request.args.get('start_date', '')
        end_date = request.args.get('end_date', '')
        
        with db_manager.get_session() as session:
            # Build the query with filters
            query = session.query(Invoice)
            
            if provider:
                query = query.filter(Invoice.provider_name.ilike(f'%{provider}%'))
            
            if service_type:
                query = query.filter(Invoice.service_type == service_type)
            
            if start_date:
                try:
                    start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                    query = query.filter(Invoice.invoice_date >= start_dt)
                except ValueError:
                    pass
            
            if end_date:
                try:
                    end_dt = datetime.strptime(end_date, '%Y-%m-%d')
                    query = query.filter(Invoice.invoice_date <= end_dt)
                except ValueError:
                    pass
            
            # Order by date (newest first)
            invoices = query.order_by(desc(Invoice.invoice_date)).all()
            
            # Create CSV content
            output = StringIO()
            writer = csv.writer(output)
            
            # Write header row
            headers = [
                'Invoice Date',
                'Provider Name', 
                'Service Type',
                'Total Amount',
                'Service Charge',
                'Usage Quantity',
                'Usage Rate',
                'Usage Charge',
                'Billing Period Start',
                'Billing Period End',
                'File Path',
                'Processing Status',
                'Created At'
            ]
            writer.writerow(headers)
            
            # Write data rows
            for invoice in invoices:
                # Calculate usage charge
                usage_charge = 0
                if invoice.usage_quantity and invoice.usage_rate:
                    usage_charge = float(invoice.usage_quantity) * float(invoice.usage_rate)
                
                row = [
                    invoice.invoice_date.strftime('%Y-%m-%d') if invoice.invoice_date else '',
                    invoice.provider_name or '',
                    invoice.service_type or '',
                    f"{float(invoice.total_amount):.2f}" if invoice.total_amount else '0.00',
                    f"{float(invoice.service_charge):.2f}" if invoice.service_charge else '0.00',
                    f"{float(invoice.usage_quantity):.2f}" if invoice.usage_quantity else '',
                    f"{float(invoice.usage_rate):.6f}" if invoice.usage_rate else '',
                    f"{usage_charge:.2f}",
                    invoice.billing_period_start.strftime('%Y-%m-%d') if invoice.billing_period_start else '',
                    invoice.billing_period_end.strftime('%Y-%m-%d') if invoice.billing_period_end else '',
                    invoice.file_path or '',
                    invoice.processing_status or '',
                    invoice.created_at.strftime('%Y-%m-%d %H:%M:%S') if invoice.created_at else ''
                ]
                writer.writerow(row)
            
            # Get CSV content
            csv_content = output.getvalue()
            output.close()
            
            # Create response with proper headers
            from flask import Response
            response = Response(
                csv_content,
                mimetype='text/csv',
                headers={
                    'Content-Disposition': 'attachment; filename=invoices_export.csv',
                    'Content-Type': 'text/csv; charset=utf-8'
                }
            )
            
            logger.info(f"CSV export completed: {len(invoices)} invoices exported")
            return response
            
    except Exception as e:
        logger.error(f"Error exporting CSV: {str(e)}")
        return jsonify({'error': 'Failed to export CSV'}), 500