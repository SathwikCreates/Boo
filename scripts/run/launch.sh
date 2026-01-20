#!/bin/bash

# Boo Journal Launch Script - macOS/Linux
# This script runs the universal Python launcher

set -e  # Exit on any error

echo ""
echo "============================================"
echo " Boo Journal Launch Script - Unix"
echo "============================================"
echo ""

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    if ! command -v python &> /dev/null; then
        echo "ERROR: Python is not installed or not in PATH"
        echo "Please install Python 3.9+ first"
        exit 1
    else
        PYTHON_CMD="python"
    fi
else
    PYTHON_CMD="python3"
fi

echo "Starting Boo Journal..."
echo ""

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

echo "Project root: $PROJECT_ROOT"

# Check if virtual environment exists
if [ ! -f "$PROJECT_ROOT/backend/venv/bin/python" ]; then
    echo "ERROR: Python virtual environment not found!"
    echo "Please run the installation script first:"
    echo "  scripts/install/install.sh"
    echo ""
    exit 1
fi

# Check if node_modules exists
if [ ! -d "$PROJECT_ROOT/frontend/node_modules" ]; then
    echo "ERROR: Frontend dependencies not installed!"
    echo "Please run the installation script first:"
    echo "  scripts/install/install.sh"
    echo ""
    exit 1
fi

# Make the Python script executable if it isn't already
chmod +x "$SCRIPT_DIR/launch.py"

echo ""
echo "============================================"
echo " Starting Boo Journal servers..."
echo "============================================"
echo ""

# Function to open URL in browser
open_browser() {
    local url="$1"
    if command -v xdg-open > /dev/null; then
        # Linux
        xdg-open "$url"
    elif command -v open > /dev/null; then
        # macOS
        open "$url"
    elif command -v start > /dev/null; then
        # Windows (in case this runs in WSL)
        start "$url"
    else
        echo "Could not detect how to open browser. Please manually open: $url"
        return 1
    fi
}

# Check if we should run the universal Python launcher (better) or simple approach
if [ "$1" = "--simple" ]; then
    echo "Starting servers in simple mode..."
    echo ""
    
    # Start backend
    echo "Starting backend server..."
    cd "$PROJECT_ROOT/backend"
    source venv/bin/activate
    python run.py &
    BACKEND_PID=$!
    
    # Wait for backend
    sleep 3
    
    # Start frontend
    echo "Starting frontend server..."
    cd "$PROJECT_ROOT/frontend"
    npm run dev &
    FRONTEND_PID=$!
    
    # Wait for frontend to start
    sleep 5
    
    echo ""
    echo "============================================"
    echo " Boo Journal is running!"
    echo "============================================"
    echo "Frontend: http://localhost:3000"
    echo "Backend:  http://localhost:8000"
    echo ""
    
    # Open browser
    echo "Opening browser..."
    if open_browser "http://localhost:3000"; then
        echo "Browser opened successfully"
    fi
    
    echo ""
    echo "Press Ctrl+C to stop both servers"
    
    # Wait for interrupt
    trap "echo ''; echo 'Stopping servers...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT
    wait
else
    # Run the Python launcher script (recommended)
    exec $PYTHON_CMD "$SCRIPT_DIR/launch.py"
fi