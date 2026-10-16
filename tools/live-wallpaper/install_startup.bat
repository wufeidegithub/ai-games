@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PY=python"
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if exist "%USERPROFILE%\.workbuddy\binaries\python\versions\3.13.12\python.exe" set "PY=%USERPROFILE%\.workbuddy\binaries\python\versions\3.13.12\python.exe"

echo ============================================
echo   安装开机自启（推荐，不需要管理员权限）
echo ============================================
"%PY%" wallpaper_daily.py --install-startup
echo.
pause
