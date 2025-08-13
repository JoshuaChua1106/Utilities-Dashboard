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


@api_bp.route('/export/csv', methods=['GET'])
def export_csv():
    """Export invoice data as CSV for Power BI or other tools."""
    try:
        with db_manager.get_session() as session:
            # Get all invoices for export
            invoices = session.query(Invoice).order_by(desc(Invoice.invoice_date)).all()
            
            # Generate CSV content
            csv_lines = ['Provider,ServiceType,InvoiceDate,TotalAmount,UsageQuantity,UsageRate,ServiceCharge,BillingStart,BillingEnd']
            
            for invoice in invoices:
                line = ','.join([
                    str(invoice.provider_name or ''),
                    str(invoice.service_type or ''),
                    invoice.invoice_date.strftime('%Y-%m-%d') if invoice.invoice_date else '',
                    str(float(invoice.total_amount)) if invoice.total_amount else '',
                    str(float(invoice.usage_quantity)) if invoice.usage_quantity else '',
                    str(float(invoice.usage_rate)) if invoice.usage_rate else '',
                    str(float(invoice.service_charge)) if invoice.service_charge else '',
                    invoice.billing_period_start.strftime('%Y-%m-%d') if invoice.billing_period_start else '',
                    invoice.billing_period_end.strftime('%Y-%m-%d') if invoice.billing_period_end else ''
                ])
                csv_lines.append(line)
            
            csv_content = '\n'.join(csv_lines)
            
            # In a real implementation, this might save to a file or S3
            # For now, return the CSV content
            return jsonify({
                'csv_data': csv_content,
                'record_count': len(invoices),
                'generated_at': datetime.now().isoformat(),
                'message': 'CSV data generated successfully'
            })
            
    except Exception as e:
        logger.error(f"Error exporting CSV: {str(e)}")
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