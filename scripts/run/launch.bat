@echo off
echo Starting Boo Journal Application...
echo.

REM Get the current directory and resolve full paths
set ROOT_DIR=%~dp0..\..
for %%i in ("%ROOT_DIR%") do set "FULL_ROOT=%%~fi"

echo Project root: %FULL_ROOT%
echo.

REM Create temporary batch files for each server
echo @echo off > "%TEMP%\start_frontend.bat"
echo cd /d "%FULL_ROOT%\frontend" >> "%TEMP%\start_frontend.bat"
echo npm run dev >> "%TEMP%\start_frontend.bat"
echo pause >> "%TEMP%\start_frontend.bat"

echo @echo off > "%TEMP%\start_backend.bat"
echo cd /d "%FULL_ROOT%\backend" >> "%TEMP%\start_backend.bat"
echo call venv\Scripts\activate >> "%TEMP%\start_backend.bat"
echo python run.py >> "%TEMP%\start_backend.bat"
echo pause >> "%TEMP%\start_backend.bat"

REM Start frontend in a new window
echo Starting Frontend (React)...
start "Boo Frontend" cmd /k "%TEMP%\start_frontend.bat"

REM Wait a moment for frontend to start
timeout /t 3 /nobreak >nul

REM Start backend in a new window
echo Starting Backend (Python FastAPI)...
start "Boo Backend" cmd /k "%TEMP%\start_backend.bat"

REM Wait for servers to initialize
echo Waiting for servers to initialize...
timeout /t 5 /nobreak >nul

REM Open browser automatically
echo Opening Boo Journal in your default browser...
start "" "http://localhost:3000"

echo.
echo Boo Journal is starting up!
echo Frontend: http://localhost:3000
echo Backend:  http://localhost:8000
echo.
echo Launcher exiting automatically...

REM Clean up temporary files
del "%TEMP%\start_frontend.bat" 2>nul
del "%TEMP%\start_backend.bat" 2>nul