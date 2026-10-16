@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PY=python"
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if exist "%USERPROFILE%\.workbuddy\binaries\python\versions\3.13.12\python.exe" set "PY=%USERPROFILE%\.workbuddy\binaries\python\versions\3.13.12\python.exe"

echo ============================================
echo   立即更换一张壁纸（今天已换过会自动跳过）
echo ============================================
"%PY%" wallpaper_daily.py --force
echo.
pause
