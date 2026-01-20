#!/usr/bin/env python3
"""
Boo Journal Installation Script
Automatically sets up the Boo Journal application with all dependencies.
"""

import os
import sys
import platform
import subprocess
import shutil
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

def print_step(step_num, total_steps, description):
    """Print a step with formatting"""
    print_colored(f"\n[{step_num}/{total_steps}] {description}", Colors.OKBLUE + Colors.BOLD)

def print_success(text):
    """Print success message"""
    print_colored(f"✓ {text}", Colors.OKGREEN)

def print_warning(text):
    """Print warning message"""
    print_colored(f"⚠ {text}", Colors.WARNING)

def print_error(text):
    """Print error message"""
    print_colored(f"✗ {text}", Colors.FAIL)

def run_command(command, shell=True, cwd=None, check=True, stream_output=False):
    """Run a command and return the result"""
    try:
        if isinstance(command, str):
            print_colored(f"  Running: {command}", Colors.OKCYAN)
        else:
            print_colored(f"  Running: {' '.join(command)}", Colors.OKCYAN)
        
        if stream_output:
            # Stream output in real-time for long-running commands
            process = subprocess.Popen(
                command,
                shell=shell,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                universal_newlines=True
            )
            
            output_lines = []
            for line in iter(process.stdout.readline, ''):
                line = line.rstrip()
                if line:
                    print(f"    {line}")
                    output_lines.append(line)
            
            process.wait()
            
            if check and process.returncode != 0:
                raise subprocess.CalledProcessError(process.returncode, command)
            
            # Create a result-like object for compatibility
            class StreamResult:
                def __init__(self, returncode, stdout):
                    self.returncode = returncode
                    self.stdout = stdout
                    self.stderr = ""
            
            return StreamResult(process.returncode, '\n'.join(output_lines))
        else:
            # Original behavior for quick commands
            result = subprocess.run(
                command, 
                shell=shell, 
                capture_output=True, 
                text=True, 
                cwd=cwd,
                check=check
            )
            
            if result.stdout.strip():
                print(f"  Output: {result.stdout.strip()}")
            
            return result
            
    except subprocess.CalledProcessError as e:
        print_error(f"Command failed: {e}")
        if hasattr(e, 'stderr') and e.stderr:
            print_error(f"Error: {e.stderr.strip()}")
        return None

def check_python_version():
    """Check if Python version is adequate"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 9):
        print_error(f"Python 3.9+ required. Current version: {version.major}.{version.minor}.{version.micro}")
        return False
    print_success(f"Python {version.major}.{version.minor}.{version.micro} detected")
    return True

def check_node_version():
    """Check if Node.js version is adequate"""
    try:
        result = run_command("node --version", check=False)
        if result and result.returncode == 0:
            version_str = result.stdout.strip().lstrip('v')
            major_version = int(version_str.split('.')[0])
            if major_version >= 18:
                print_success(f"Node.js {version_str} detected")
                return True
            else:
                print_error(f"Node.js 18+ required. Current version: {version_str}")
                return False
        else:
            print_error("Node.js not found")
            return False
    except Exception as e:
        print_error(f"Error checking Node.js: {e}")
        return False

def check_npm_version():
    """Check if npm is available"""
    try:
        result = run_command("npm --version", check=False)
        if result and result.returncode == 0:
            version_str = result.stdout.strip()
            print_success(f"npm {version_str} detected")
            return True
        else:
            print_error("npm not found")
            return False
    except Exception as e:
        print_error(f"Error checking npm: {e}")
        return False

def check_git_version():
    """Check if Git is available"""
    try:
        result = run_command("git --version", check=False)
        if result and result.returncode == 0:
            version_str = result.stdout.strip()
            print_success(f"{version_str} detected")
            return True
        else:
            print_error("Git not found")
            return False
    except Exception as e:
        print_error(f"Error checking Git: {e}")
        return False

def get_project_root():
    """Get the project root directory (two levels up from this script)"""
    script_path = Path(__file__).resolve()
    return script_path.parent.parent.parent

def setup_python_venv(project_root):
    """Set up Python virtual environment"""
    backend_dir = project_root / "backend"
    venv_dir = backend_dir / "venv"
    
    if venv_dir.exists():
        print_success("Virtual environment already exists")
        return True
    
    print_colored("Creating Python virtual environment...", Colors.OKCYAN)
    
    # Create virtual environment
    result = run_command([sys.executable, "-m", "venv", str(venv_dir)], cwd=str(backend_dir))
    if not result:
        return False
    
    print_success("Virtual environment created")
    return True

def install_python_dependencies(project_root):
    """Install Python dependencies"""
    backend_dir = project_root / "backend"
    venv_dir = backend_dir / "venv"
    requirements_file = backend_dir / "requirements.txt"
    
    if not requirements_file.exists():
        print_error(f"Requirements file not found: {requirements_file}")
        return False
    
    # Determine pip executable path
    system = platform.system().lower()
    if system == "windows":
        pip_executable = venv_dir / "Scripts" / "pip.exe"
    else:
        pip_executable = venv_dir / "bin" / "pip"
    
    if not pip_executable.exists():
        print_error(f"pip not found in virtual environment: {pip_executable}")
        return False
    
    print_colored("Installing Python dependencies...", Colors.OKCYAN)
    
    # Upgrade pip first using python -m pip to avoid path issues
    python_executable = venv_dir / ("Scripts" if os.name == 'nt' else "bin") / ("python.exe" if os.name == 'nt' else "python")
    result = run_command([str(python_executable), "-m", "pip", "install", "--upgrade", "pip"], shell=False, cwd=str(backend_dir), stream_output=True)
    if not result:
        return False
    
    # Install requirements using python -m pip with real-time output
    result = run_command([str(python_executable), "-m", "pip", "install", "-r", "requirements.txt"], shell=False, cwd=str(backend_dir), stream_output=True)
    if not result:
        return False
    
    print_success("Python dependencies installed")
    return True

def install_node_dependencies(project_root):
    """Install Node.js dependencies"""
    frontend_dir = project_root / "frontend"
    package_json = frontend_dir / "package.json"
    
    if not package_json.exists():
        print_error(f"package.json not found: {package_json}")
        return False
    
    print_colored("Installing Node.js dependencies...", Colors.OKCYAN)
    
    # For Windows, we need to use shell=True or find npm.cmd explicitly
    if os.name == 'nt':
        # On Windows, npm is actually npm.cmd, so we need shell=True
        result = run_command("npm install", shell=True, cwd=str(frontend_dir), stream_output=True)
    else:
        # On Unix-like systems, use list format with shell=False
        result = run_command(["npm", "install"], shell=False, cwd=str(frontend_dir), stream_output=True)
    
    if not result:
        return False
    
    print_success("Node.js dependencies installed")
    return True

def create_directories(project_root):
    """Create necessary directories"""
    directories = [
        project_root / "backend" / "TTS",
        project_root / "backend" / "data",
        project_root / "backend" / "audio_recordings",
        project_root / "backend" / "embeddings_cache"
    ]
    
    print_colored("Creating necessary directories...", Colors.OKCYAN)
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        print_success(f"Directory ready: {directory.name}/")
    
    return True

def test_backend_setup(project_root):
    """Test if backend setup is working"""
    backend_dir = project_root / "backend"
    venv_dir = backend_dir / "venv"
    
    # Determine python executable path
    system = platform.system().lower()
    if system == "windows":
        python_executable = venv_dir / "Scripts" / "python.exe"
    else:
        python_executable = venv_dir / "bin" / "python"
    
    if not python_executable.exists():
        print_error(f"Python not found in virtual environment: {python_executable}")
        return False
    
    print_colored("Testing backend setup...", Colors.OKCYAN)
    
    # Test import of key dependencies
    test_imports = [
        "import fastapi",
        "import uvicorn", 
        "import whisper",
        "import sentence_transformers"
    ]
    
    for test_import in test_imports:
        result = run_command([str(python_executable), "-c", test_import], cwd=str(backend_dir), check=False)
        if not result or result.returncode != 0:
            print_error(f"Failed to import: {test_import.split()[-1]}")
            return False
    
    print_success("Backend setup test passed")
    return True

def test_frontend_setup(project_root):
    """Test if frontend setup is working"""
    frontend_dir = project_root / "frontend"
    
    print_colored("Testing frontend setup...", Colors.OKCYAN)
    
    # Check if node_modules exists and has content
    node_modules = frontend_dir / "node_modules"
    if not node_modules.exists() or not any(node_modules.iterdir()):
        print_error("node_modules directory is empty or missing")
        return False
    
    print_success("Frontend setup test passed")
    return True

def main():
    """Main installation function"""
    print_header("Boo Journal Installation Script")
    print_colored("This script will automatically set up Boo Journal with all dependencies.", Colors.OKBLUE)
    
    # Step 1: Check prerequisites
    print_step(1, 8, "Checking Prerequisites")
    
    all_prereqs = True
    all_prereqs &= check_python_version()
    all_prereqs &= check_node_version()
    all_prereqs &= check_npm_version()
    all_prereqs &= check_git_version()
    
    if not all_prereqs:
        print_error("\nPrerequisites check failed!")
        print_colored("Please install missing prerequisites and run this script again.", Colors.WARNING)
        print_colored("See Documentation/INSTALLATION_GUIDE.md for installation instructions.", Colors.WARNING)
        sys.exit(1)
    
    print_success("All prerequisites satisfied!")
    
    # Get project root
    project_root = get_project_root()
    print_colored(f"Project root: {project_root}", Colors.OKCYAN)
    
    # Step 2: Create directories
    print_step(2, 8, "Creating Project Directories")
    if not create_directories(project_root):
        print_error("Failed to create directories")
        sys.exit(1)
    
    # Step 3: Set up Python virtual environment
    print_step(3, 8, "Setting Up Python Virtual Environment")
    if not setup_python_venv(project_root):
        print_error("Failed to set up Python virtual environment")
        sys.exit(1)
    
    # Step 4: Install Python dependencies
    print_step(4, 8, "Installing Python Dependencies")
    if not install_python_dependencies(project_root):
        print_error("Failed to install Python dependencies")
        sys.exit(1)
    
    # Step 5: Install Node.js dependencies
    print_step(5, 8, "Installing Node.js Dependencies")
    if not install_node_dependencies(project_root):
        print_error("Failed to install Node.js dependencies")
        sys.exit(1)
    
    # Step 6: Test backend setup
    print_step(6, 8, "Testing Backend Setup")
    if not test_backend_setup(project_root):
        print_error("Backend setup test failed")
        sys.exit(1)
    
    # Step 7: Test frontend setup
    print_step(7, 8, "Testing Frontend Setup")
    if not test_frontend_setup(project_root):
        print_error("Frontend setup test failed")
        sys.exit(1)
    
    # Step 8: Installation complete
    print_step(8, 8, "Installation Complete!")
    
    print_header("🎉 Boo Journal Installation Successful!")
    
    print_colored("\nNext steps:", Colors.OKBLUE + Colors.BOLD)
    print_colored("1. Install and configure Ollama:", Colors.OKBLUE)
    print_colored("   - Download from: https://ollama.ai/", Colors.OKCYAN)
    print_colored("   - Pull recommended models:", Colors.OKCYAN)
    print_colored("     ollama pull mistral:7b", Colors.OKCYAN)
    print_colored("     ollama pull qwen3:8b", Colors.OKCYAN)
    
    print_colored("\n2. (Optional) Download TTS voices:", Colors.OKBLUE)
    print_colored("   - Download from: https://huggingface.co/rhasspy/piper-voices/tree/main/en", Colors.OKCYAN)
    print_colored("   - Place .onnx and .onnx.json files in backend/TTS/", Colors.OKCYAN)
    
    print_colored("\n3. Launch Boo Journal:", Colors.OKBLUE)
    print_colored("   - Windows: Run scripts/run/launch.bat", Colors.OKCYAN)
    print_colored("   - macOS/Linux: Run scripts/run/launch.sh", Colors.OKCYAN)
    print_colored("   - Universal: python scripts/run/launch.py", Colors.OKCYAN)
    
    print_colored(f"\n✓ Installation completed successfully!", Colors.OKGREEN + Colors.BOLD)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_colored("\n\nInstallation cancelled by user.", Colors.WARNING)
        sys.exit(1)
    except Exception as e:
        print_error(f"\nUnexpected error: {e}")
        sys.exit(1)