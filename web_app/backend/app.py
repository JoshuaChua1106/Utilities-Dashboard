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

from flask import Flask, jsonify, send_from_directory, request
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
    CORS(app, origins=["http://localhost:3000", "http://localhost:8000", "http://localhost:8080"])
    
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
    
    @app.route('/auth/callback')
    def oauth_callback():
        """Handle OAuth2 callback from Google."""
        try:
            import requests
            import json
            from pathlib import Path
            
            # Get authorization code from query parameters
            auth_code = request.args.get('code')
            error = request.args.get('error')
            
            if error:
                return f"""
                <html>
                    <body>
                        <h2>OAuth Error</h2>
                        <p>Error: {error}</p>
                        <p>Please close this window and try again.</p>
                    </body>
                </html>
                """, 400
            
            if not auth_code:
                return """
                <html>
                    <body>
                        <h2>OAuth Error</h2>
                        <p>No authorization code received.</p>
                        <p>Please close this window and try again.</p>
                    </body>
                </html>
                """, 400
            
            # Load Gmail configuration from environment variables or file
            import os
            
            # First try environment variables
            client_id = os.getenv('GMAIL_CLIENT_ID')
            client_secret = os.getenv('GMAIL_CLIENT_SECRET')
            
            # If not in environment, try credentials file
            if not client_id or not client_secret:
                config_dir = Path(__file__).parent.parent.parent / "config"
                config_file = config_dir / "credentials.json"
                
                if not config_file.exists():
                    return """
                    <html>
                        <body>
                            <h2>Configuration Error</h2>
                            <p>Gmail configuration not found in environment variables or file.</p>
                            <p>Please configure GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET environment variables.</p>
                        </body>
                    </html>
                    """, 400
                    
                with open(config_file, 'r') as f:
                    credentials = json.load(f)
                
                gmail_config = credentials.get('gmail', {})
                client_id = gmail_config.get('client_id')
                client_secret = gmail_config.get('client_secret')
            
            if not client_id or not client_secret:
                return """
                <html>
                    <body>
                        <h2>Configuration Error</h2>
                        <p>Client ID or Secret missing. Please configure Gmail API credentials first.</p>
                        <p>Please close this window and save your credentials.</p>
                    </body>
                </html>
                """, 400
            
            # Exchange authorization code for tokens
            token_url = "https://oauth2.googleapis.com/token"
            token_data = {
                'client_id': client_id,
                'client_secret': client_secret,
                'code': auth_code,
                'grant_type': 'authorization_code',
                'redirect_uri': 'http://localhost:5000/auth/callback'
            }
            
            token_response = requests.post(token_url, data=token_data)
            token_json = token_response.json()
            
            if token_response.status_code != 200 or 'error' in token_json:
                error_msg = token_json.get('error_description', 'Unknown error')
                return f"""
                <html>
                    <body>
                        <h2>Token Exchange Error</h2>
                        <p>Error: {error_msg}</p>
                        <p>Please close this window and try again.</p>
                    </body>
                </html>
                """, 400
            
            # Save tokens based on configuration source
            refresh_token = token_json.get('refresh_token')
            access_token = token_json.get('access_token')
            token_expiry = datetime.now().isoformat()
            
            # If using environment variables, suggest updating .env file
            if os.getenv('GMAIL_CLIENT_ID'):
                logger.info("Tokens received - update .env file with new refresh token if needed")
                # We don't automatically update .env to avoid overwriting it
                # The user should manually update GMAIL_REFRESH_TOKEN if needed
            else:
                # Save to credentials file if using file-based config
                gmail_config['access_token'] = access_token
                gmail_config['refresh_token'] = refresh_token
                gmail_config['token_expiry'] = token_expiry
                
                # Update the credentials structure
                credentials['gmail'] = gmail_config
                
                with open(config_file, 'w') as f:
                    json.dump(credentials, f, indent=2)
            
            logger.info("OAuth2 flow completed successfully")
            
            return """
            <html>
                <head>
                    <title>OAuth Success</title>
                    <style>
                        body { font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }
                        .success { color: #28a745; }
                        .code { background: #f8f9fa; padding: 10px; border-radius: 5px; font-family: monospace; }
                    </style>
                </head>
                <body>
                    <h2 class="success">✅ OAuth2 Authorization Successful!</h2>
                    <p>Your Gmail account has been successfully connected to the Utilities Tracker.</p>
                    <h3>Next Steps:</h3>
                    <ol>
                        <li><strong>Close this window</strong></li>
                        <li><strong>Go back to the Configuration tab</strong></li>
                        <li><strong>Click "Test Connection"</strong> to verify the setup</li>
                        <li><strong>Configure Email Capture patterns</strong> for your utility providers</li>
                    </ol>
                    <p>You can now use the application to automatically fetch utility invoices from your Gmail account.</p>
                    <script>
                        // Auto-close after 10 seconds
                        setTimeout(() => {
                            window.close();
                        }, 10000);
                    </script>
                </body>
            </html>
            """
            
        except Exception as e:
            logger.error(f"Error in OAuth callback: {e}")
            return f"""
            <html>
                <body>
                    <h2>Internal Error</h2>
                    <p>Error: {str(e)}</p>
                    <p>Please close this window and try again.</p>
                </body>
            </html>
            """, 500
    
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