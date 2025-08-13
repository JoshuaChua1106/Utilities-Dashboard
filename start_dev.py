#!/usr/bin/env python3
"""
Development Server Starter

Starts both backend API server (Flask) and frontend server for local development.
"""

import os
import sys
import time
import subprocess
import signal
from pathlib import Path

def start_servers():
    """Start both backend and frontend servers."""
    print("🚀 Starting Utilities Tracker Development Servers")
    print("=" * 50)
    
    # Change to project root
    project_root = Path(__file__).parent
    os.chdir(project_root)
    
    # Start backend server
    print("🔧 Starting backend API server...")
    backend_cmd = [
        sys.executable, 
        "web_app/backend/app.py", 
        "--host=localhost", 
        "--port=5000"
    ]
    
    # Activate virtual environment if it exists
    if Path("venv/bin/python3").exists():
        backend_cmd[0] = "venv/bin/python3"
    elif Path("venv/Scripts/python.exe").exists():
        backend_cmd[0] = "venv/Scripts/python.exe"
    
    backend_process = subprocess.Popen(
        backend_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        preexec_fn=os.setsid if hasattr(os, 'setsid') else None
    )
    
    # Wait a moment for backend to start
    time.sleep(2)
    
    # Start frontend server
    print("🌐 Starting frontend server...")
    frontend_cmd = [sys.executable, "web_app/serve_frontend.py"]
    
    if Path("venv/bin/python3").exists():
        frontend_cmd[0] = "venv/bin/python3"
    elif Path("venv/Scripts/python.exe").exists():
        frontend_cmd[0] = "venv/Scripts/python.exe"
    
    frontend_process = subprocess.Popen(
        frontend_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        preexec_fn=os.setsid if hasattr(os, 'setsid') else None
    )
    
    print("\n✅ Development servers started!")
    print("🔗 Backend API: http://localhost:5000")
    print("🌐 Frontend UI: http://localhost:3000")
    print("📊 Database: SQLite (./data/invoices.db)")
    print("\nPress Ctrl+C to stop all servers\n")
    
    # Monitor processes
    try:
        while True:
            # Check if processes are still running
            if backend_process.poll() is not None:
                print("❌ Backend server stopped unexpectedly")
                break
            if frontend_process.poll() is not None:
                print("❌ Frontend server stopped unexpectedly")
                break
            
            time.sleep(1)
    
    except KeyboardInterrupt:
        print("\n🛑 Stopping development servers...")
        
        # Terminate processes
        try:
            if hasattr(os, 'killpg'):
                os.killpg(os.getpgid(backend_process.pid), signal.SIGTERM)
                os.killpg(os.getpgid(frontend_process.pid), signal.SIGTERM)
            else:
                backend_process.terminate()
                frontend_process.terminate()
        except:
            pass
        
        # Wait for processes to terminate
        try:
            backend_process.wait(timeout=5)
            frontend_process.wait(timeout=5)
        except:
            # Force kill if needed
            try:
                backend_process.kill()
                frontend_process.kill()
            except:
                pass
        
        print("✅ Development servers stopped")

def main():
    """Main entry point."""
    try:
        start_servers()
    except Exception as e:
        print(f"❌ Error starting development servers: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()