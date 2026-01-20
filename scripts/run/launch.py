#!/usr/bin/env python3
"""
Boo Journal Launch Script
Automatically starts both backend and frontend servers.
"""

import os
import sys
import platform
import subprocess
import time
import signal
import webbrowser
from pathlib import Path

class Colors:
    """ANSI color codes for terminal output"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_colored(text, color=Colors.ENDC):
    """Print colored text to terminal"""
    print(f"{color}{text}{Colors.ENDC}")

def print_header(text):
    """Print a header with formatting"""
    print_colored(f"\n{'='*60}", Colors.HEADER)
    print_colored(f" {text}", Colors.HEADER + Colors.BOLD)
    print_colored(f"{'='*60}", Colors.HEADER)

def print_success(text):
    """Print success message"""
    print_colored(f"✓ {text}", Colors.OKGREEN)

def print_warning(text):
    """Print warning message"""
    print_colored(f"⚠ {text}", Colors.WARNING)

def print_error(text):
    """Print error message"""
    print_colored(f"✗ {text}", Colors.FAIL)

def get_project_root():
    """Get the project root directory (two levels up from this script)"""
    script_path = Path(__file__).resolve()
    return script_path.parent.parent.parent

def check_prerequisites():
    """Check if installation was completed properly"""
    project_root = get_project_root()
    
    # Check backend virtual environment
    backend_dir = project_root / "backend"
    venv_dir = backend_dir / "venv"
    
    system = platform.system().lower()
    if system == "windows":
        python_executable = venv_dir / "Scripts" / "python.exe"
    else:
        python_executable = venv_dir / "bin" / "python"
    
    if not python_executable.exists():
        print_error("Python virtual environment not found!")
        print_colored("Please run the installation script first:", Colors.WARNING)
        print_colored("  Windows: scripts/install/install.bat", Colors.OKCYAN)
        print_colored("  macOS/Linux: scripts/install/install.sh", Colors.OKCYAN)
        return False
    
    # Check frontend node_modules
    frontend_dir = project_root / "frontend"
    node_modules = frontend_dir / "node_modules"
    
    if not node_modules.exists() or not any(node_modules.iterdir()):
        print_error("Frontend dependencies not installed!")
        print_colored("Please run the installation script first:", Colors.WARNING)
        print_colored("  Windows: scripts/install/install.bat", Colors.OKCYAN)
        print_colored("  macOS/Linux: scripts/install/install.sh", Colors.OKCYAN)
        return False
    
    print_success("Prerequisites check passed")
    return True

def start_backend(project_root):
    """Start the backend server"""
    backend_dir = project_root / "backend"
    venv_dir = backend_dir / "venv"
    
    system = platform.system().lower()
    if system == "windows":
        python_executable = venv_dir / "Scripts" / "python.exe"
    else:
        python_executable = venv_dir / "bin" / "python"
    
    print_colored("Starting backend server...", Colors.OKBLUE)
    
    try:
        # Start backend process
        backend_process = subprocess.Popen(
            [str(python_executable), "run.py"],
            cwd=str(backend_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Give backend time to start
        time.sleep(3)
        
        # Check if process is still running
        if backend_process.poll() is None:
            print_success("Backend server started successfully")
            print_colored("  Backend API: http://localhost:8000", Colors.OKCYAN)
            return backend_process
        else:
            stdout, stderr = backend_process.communicate()
            print_error("Backend server failed to start")
            if stderr:
                print_error(f"Error: {stderr}")
            return None
            
    except Exception as e:
        print_error(f"Failed to start backend: {e}")
        return None

def start_frontend(project_root):
    """Start the frontend server"""
    frontend_dir = project_root / "frontend"
    
    print_colored("Starting frontend server...", Colors.OKBLUE)
    
    try:
        # Start frontend process
        frontend_process = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=str(frontend_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Give frontend time to start
        time.sleep(5)
        
        # Check if process is still running
        if frontend_process.poll() is None:
            print_success("Frontend server started successfully")
            print_colored("  Frontend App: http://localhost:3000", Colors.OKCYAN)
            return frontend_process
        else:
            stdout, stderr = frontend_process.communicate()
            print_error("Frontend server failed to start")
            if stderr:
                print_error(f"Error: {stderr}")
            return None
            
    except Exception as e:
        print_error(f"Failed to start frontend: {e}")
        return None

def cleanup_processes(backend_process, frontend_process):
    """Clean up running processes"""
    print_colored("\nShutting down servers...", Colors.WARNING)
    
    if backend_process and backend_process.poll() is None:
        print_colored("Stopping backend server...", Colors.OKCYAN)
        backend_process.terminate()
        try:
            backend_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            backend_process.kill()
    
    if frontend_process and frontend_process.poll() is None:
        print_colored("Stopping frontend server...", Colors.OKCYAN)
        frontend_process.terminate()
        try:
            frontend_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            frontend_process.kill()
    
    print_success("Servers stopped")

def main():
    """Main launcher function"""
    print_header("Boo Journal Launcher")
    
    # Check prerequisites
    if not check_prerequisites():
        sys.exit(1)
    
    project_root = get_project_root()
    print_colored(f"Project root: {project_root}", Colors.OKCYAN)
    
    backend_process = None
    frontend_process = None
    
    try:
        # Start backend
        backend_process = start_backend(project_root)
        if not backend_process:
            print_error("Failed to start backend. Exiting.")
            sys.exit(1)
        
        # Start frontend
        frontend_process = start_frontend(project_root)
        if not frontend_process:
            print_error("Failed to start frontend. Cleaning up.")
            cleanup_processes(backend_process, None)
            sys.exit(1)
        
        # Both servers started successfully
        print_header("🚀 Boo Journal is running!")
        print_colored("Frontend: http://localhost:3000", Colors.OKGREEN + Colors.BOLD)
        print_colored("Backend:  http://localhost:8000", Colors.OKGREEN + Colors.BOLD)
        
        # Wait a moment for servers to fully initialize
        print_colored("\nWaiting for servers to fully initialize...", Colors.OKCYAN)
        time.sleep(3)
        
        # Open browser automatically
        try:
            print_colored("Opening Boo Journal in your default browser...", Colors.OKCYAN)
            webbrowser.open("http://localhost:3000")
            print_success("Browser opened successfully")
        except Exception as e:
            print_warning(f"Could not open browser automatically: {e}")
            print_colored("Please manually open: http://localhost:3000", Colors.OKCYAN)
        
        print_colored("\nPress Ctrl+C to stop both servers", Colors.WARNING)
        
        # Wait for user interruption
        try:
            while True:
                # Check if processes are still running
                if backend_process.poll() is not None:
                    print_error("Backend server stopped unexpectedly")
                    break
                if frontend_process.poll() is not None:
                    print_error("Frontend server stopped unexpectedly")
                    break
                
                time.sleep(1)
        
        except KeyboardInterrupt:
            print_colored("\nReceived shutdown signal", Colors.WARNING)
    
    except Exception as e:
        print_error(f"Unexpected error: {e}")
    
    finally:
        cleanup_processes(backend_process, frontend_process)
        print_colored("\nBoo Journal stopped", Colors.OKBLUE)

if __name__ == "__main__":
    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        print_colored("\nShutdown requested", Colors.WARNING)
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        main()
    except Exception as e:
        print_error(f"Fatal error: {e}")
        sys.exit(1)