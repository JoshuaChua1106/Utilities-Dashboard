#!/usr/bin/env python3
"""
Utilities Tracker Web Application

Flask backend providing REST API for the utilities tracking system.
Supports both local SQLite and AWS RDS PostgreSQL through adapter pattern.
"""

import os
import sys
import logging
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from web_app.backend.models import db_manager
from web_app.backend.api import api_bp

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_app(config=None):
    """Create and configure Flask application."""
    app = Flask(__name__)
    
    # Basic configuration
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['JSON_SORT_KEYS'] = False
    app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True
    
    # CORS configuration
    CORS(app, origins=["http://localhost:3000", "http://localhost:8000"])
    
    # Register blueprints
    app.register_blueprint(api_bp)
    
    @app.route('/')
    def index():
        """Root endpoint providing API information."""
        return jsonify({
            'name': 'Utilities Tracker API',
            'version': '1.0.0',
            'environment': 'aws' if os.getenv('AWS_MODE') == 'true' else 'local',
            'status': 'running',
            'timestamp': datetime.now().isoformat(),
            'endpoints': {
                'health': '/api/health',
                'invoices': '/api/invoices',
                'providers': '/api/providers',
                'analytics': '/api/analytics',
                'sync': '/api/sync',
                'processing_history': '/api/processing-history',
                'export': '/api/export/csv'
            },
            'documentation': {
                'api_docs': 'https://github.com/your-org/utilities-tracker/blob/main/docs/api-documentation.md',
                'usage_guide': 'See USAGE.md for detailed instructions',
                'setup_guide': 'See README.md for setup instructions'
            }
        })
    
    @app.route('/favicon.ico')
    def favicon():
        """Serve favicon."""
        return '', 204
    
    @app.errorhandler(404)
    def not_found(error):
        """Global 404 handler."""
        return jsonify({
            'error': 'Not Found',
            'message': 'The requested resource was not found',
            'status': 404
        }), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        """Global 500 handler."""
        logger.error(f"Internal server error: {str(error)}")
        return jsonify({
            'error': 'Internal Server Error',
            'message': 'An internal error occurred',
            'status': 500
        }), 500
    
    # Initialize database tables
    try:
        db_manager.create_tables()
        logger.info("Database tables initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database tables: {str(e)}")
    
    return app


def main():
    """Main entry point for running the application."""
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Utilities Tracker Web Application')
    parser.add_argument('--host', default=os.getenv('API_HOST', '0.0.0.0'),
                       help='Host to bind to (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=int(os.getenv('API_PORT', 5000)),
                       help='Port to bind to (default: 5000)')
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug mode')
    parser.add_argument('--reload', action='store_true',
                       help='Enable auto-reload on file changes')
    
    args = parser.parse_args()
    
    # Create application
    app = create_app()
    
    # Environment info
    environment = 'AWS' if os.getenv('AWS_MODE') == 'true' else 'Local'
    logger.info(f"Starting Utilities Tracker API in {environment} mode")
    logger.info(f"Server will be available at: http://{args.host}:{args.port}")
    
    # Health check
    try:
        health = db_manager.health_check()
        if health['status'] == 'healthy':
            logger.info(f"Database connection successful: {health['database_type']}")
            logger.info(f"Invoice count: {health.get('invoice_count', 0)}")
        else:
            logger.warning(f"Database health check failed: {health.get('error')}")
    except Exception as e:
        logger.error(f"Database health check error: {str(e)}")
    
    # Start development server
    try:
        app.run(
            host=args.host,
            port=args.port,
            debug=args.debug or os.getenv('FLASK_DEBUG') == '1',
            use_reloader=args.reload
        )
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()