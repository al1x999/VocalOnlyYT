@echo off
title YouTube Vocal Remover Server
echo ========================================================
echo         YouTube Vocal Remover - AI Server
echo ========================================================

REM Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not found on your system PATH!
    echo Please install Python 3.9 or higher and add to PATH.
    pause
    exit /b 1
)

REM Check for NVIDIA GPU
where nvidia-smi >nul 2>&1
if %errorlevel% equ 0 (
    echo [GPU DETECTED] NVIDIA CUDA GPU detected! Checking PyTorch GPU support...
    python -c "import torch; exit(0 if torch.cuda.is_available() else 1)" >nul 2>&1
    if %errorlevel% neq 0 (
        echo [GPU SETUP] Installing PyTorch CUDA 12.1...
        pip install torch --index-url https://download.pytorch.org/whl/cu121
    )
)

echo [SERVER] Installing dependencies from server\requirements.txt...
pip install -r server\requirements.txt

echo ========================================================
echo Launching Server on http://127.0.0.1:8000
echo Default Shortcut: Ctrl + Shift + R
echo Keep this window open while using the Chrome extension!
echo ========================================================

REM Automatically free port 8000 if occupied by old process
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do taskkill /F /PID %%a >nul 2>&1

python server/app.py

pause
