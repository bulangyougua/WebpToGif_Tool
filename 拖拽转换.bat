@echo off

if "%~1"=="" (
    echo Drag folders onto this script
    echo WebP files will be converted to GIF in a newgif subfolder
    pause
    exit /b
)

echo [ARGS] %*
echo [DIR] %~dp0

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] python not found. Install Python and add it to PATH.
    pause
    exit /b
)

echo [PYTHON]
python -c "import sys; print(sys.executable)"
echo.

python "%~dp0webp_to_gif.py" %*
if errorlevel 1 (
    echo [ERROR] Python script failed
) else (
    echo [OK] Python script finished
)
pause