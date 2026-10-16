@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PY=python"
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if exist "%USERPROFILE%\.workbuddy\binaries\python\versions\3.13.12\python.exe" set "PY=%USERPROFILE%\.workbuddy\binaries\python\versions\3.13.12\python.exe"

echo ============================================
echo   注册计划任务：每天 09:00 自动换壁纸
echo   （时间可在 config.json 里改 task_time）
echo ============================================
"%PY%" wallpaper_daily.py --install-task
echo.
pause
