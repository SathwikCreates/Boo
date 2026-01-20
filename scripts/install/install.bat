@echo off
setlocal enabledelayedexpansion

REM Boo Journal Installation Script - Windows
REM This script runs the universal Python installer

echo.
echo ===============================================
echo  Boo Journal Installation Script - Windows
echo ===============================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.9+ from https://python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation
    echo.
    pause
    exit /b 1
)

echo Python detected. Starting installation...
echo.

REM Get the directory of this script and navigate to project root
set SCRIPT_DIR=%~dp0
set PROJECT_ROOT=%SCRIPT_DIR%..\..

REM Run the Python installation script
python "%SCRIPT_DIR%install.py"
set INSTALL_RESULT=%ERRORLEVEL%

echo.
if %INSTALL_RESULT% equ 0 (
    echo ===============================================
    echo  Installation completed successfully!
    echo ===============================================
    echo.
    echo You can now run Boo Journal using:
    echo   - Double-click: scripts\run\launch.bat
    echo   - Command line: python scripts\run\launch.py
    echo.
) else (
    echo ===============================================
    echo  Installation failed!
    echo ===============================================
    echo.
    echo Please check the error messages above and try again.
    echo If you need help, see Documentation\INSTALLATION_GUIDE.md
    echo.
)

echo Press any key to exit...
pause >nul
exit /b %INSTALL_RESULT%