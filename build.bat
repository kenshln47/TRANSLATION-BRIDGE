@echo off
echo ==========================================
echo   Translation Bridge - EXE Builder
echo ==========================================
echo.

:: Check if pyinstaller is installed
pip show pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

:: Check if keyboard is installed
pip show keyboard >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing keyboard library...
    pip install keyboard
)

echo.
echo Building Translation Bridge.exe ...
echo.

:: Clean previous builds to avoid conflicts
if exist "build" rmdir /s /q build
if exist "Translation Bridge.spec" del /q "Translation Bridge.spec"

:: Build the exe
pyinstaller --noconfirm ^
    --onefile ^
    --windowed ^
    --name "Translation Bridge" ^
    --icon "assets\icon.ico" ^
    --add-data "assets\logo.png;assets" ^
    --add-data ".api_key;." ^
    --hidden-import customtkinter ^
    --hidden-import PIL ^
    --hidden-import keyboard ^
    --hidden-import pystray ^
    --exclude-module numpy ^
    --exclude-module pandas ^
    --exclude-module matplotlib ^
    chat_bridge.py

echo.
echo ==========================================
if exist "dist\Translation Bridge.exe" (
    echo   SUCCESS! Your .exe is in: dist\
    echo   File: dist\Translation Bridge.exe
) else (
    echo   Build failed. Check errors above.
)
echo ==========================================
pause
