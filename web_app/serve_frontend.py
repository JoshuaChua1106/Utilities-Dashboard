#!/usr/bin/env python3
"""
Simple HTTP server for frontend development.

Serves the frontend static files on localhost:3000 for development.
"""

import http.server
import socketserver
import os
import sys
from pathlib import Path

def main():
    # Change to frontend directory
    frontend_dir = Path(__file__).parent / 'frontend'
    os.chdir(frontend_dir)
    
    PORT = 3000
    
    class MyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
        def end_headers(self):
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
            super().end_headers()
    
    try:
        with socketserver.TCPServer(("", PORT), MyHTTPRequestHandler) as httpd:
            print(f"🌐 Frontend server starting at http://localhost:{PORT}")
            print(f"📁 Serving files from: {frontend_dir}")
            print(f"🔗 Backend API expected at: http://localhost:5000")
            print("\nPress Ctrl+C to stop the server")
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n✅ Frontend server stopped")
    except OSError as e:
        if e.errno == 48:  # Address already in use
            print(f"❌ Port {PORT} is already in use")
            print("   Try stopping any existing servers or use a different port")
        else:
            print(f"❌ Error starting server: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()