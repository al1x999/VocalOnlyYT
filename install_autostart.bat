@echo off
echo ========================================================
echo   Installing Vocal Remover Background Auto-Start...
echo ========================================================
copy /Y "%~dp0start_server_silent.vbs" "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\"
if %errorlevel% equ 0 (
    echo [SUCCESS] Added to Windows Startup!
    echo The backend will now run automatically in the background with zero popups.
) else (
    echo [ERROR] Failed to add to Startup.
)
pause
