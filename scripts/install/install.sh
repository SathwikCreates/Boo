#!/bin/bash

# Boo Journal Installation Script - macOS/Linux
# This script runs the universal Python installer

set -e  # Exit on any error

echo ""
echo "==============================================="
echo " Boo Journal Installation Script - Unix"
echo "==============================================="
echo ""

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    if ! command -v python &> /dev/null; then
        echo "ERROR: Python is not installed or not in PATH"
        echo "Please install Python 3.9+ using your system package manager:"
        echo ""
        echo "macOS:   brew install python@3.11"
        echo "Ubuntu:  sudo apt install python3.11 python3.11-venv python3-pip"
        echo "CentOS:  sudo yum install python3.11 python3-pip"
        echo "Fedora:  sudo dnf install python3.11 python3-pip"
        echo ""
        exit 1
    else
        PYTHON_CMD="python"
    fi
else
    PYTHON_CMD="python3"
fi

# Check Python version
PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | cut -d' ' -f2)
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d'.' -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d'.' -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 9 ]); then
    echo "ERROR: Python 3.9+ required. Current version: $PYTHON_VERSION"
    echo "Please upgrade Python and try again."
    exit 1
fi

echo "Python $PYTHON_VERSION detected. Starting installation..."
echo ""

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

# Make the Python script executable if it isn't already
chmod +x "$SCRIPT_DIR/install.py"

# Run the Python installation script
if $PYTHON_CMD "$SCRIPT_DIR/install.py"; then
    echo ""
    echo "==============================================="
    echo " Installation completed successfully!"
    echo "==============================================="
    echo ""
    echo "You can now run Boo Journal using:"
    echo "  - Command line: bash scripts/run/launch.sh"
    echo "  - Universal: python scripts/run/launch.py"
    echo ""
    echo "Make sure to install Ollama and pull the recommended models:"
    echo "  ollama pull mistral:7b"
    echo "  ollama pull qwen3:8b"
    echo ""
else
    echo ""
    echo "==============================================="
    echo " Installation failed!"
    echo "==============================================="
    echo ""
    echo "Please check the error messages above and try again."
    echo "If you need help, see Documentation/INSTALLATION_GUIDE.md"
    echo ""
    exit 1
fi