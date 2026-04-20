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

echo.
echo Building Translation Bridge.exe ...
echo.

:: Clean previous builds to avoid conflicts
if exist "build" rmdir /s /q build
if exist "Translation Bridge.spec" del /q "Translation Bridge.spec"

:: Build the exe (optimized)
pyinstaller --noconfirm ^
    --onefile ^
    --windowed ^
    --name "Translation Bridge" ^
    --icon "assets\icon.ico" ^
    --add-data "assets\logo.png;assets" ^
    --hidden-import customtkinter ^
    --hidden-import PIL ^
    --hidden-import pystray ^
    --hidden-import chat_bridge ^
    --hidden-import chat_bridge.app ^
    --hidden-import chat_bridge.translator ^
    --hidden-import chat_bridge.config ^
    --hidden-import chat_bridge.hotkey ^
    --hidden-import chat_bridge.tray ^
    --hidden-import chat_bridge.constants ^
    --hidden-import chat_bridge.ui ^
    --hidden-import chat_bridge.ui.theme ^
    --hidden-import chat_bridge.ui.setup_screen ^
    --hidden-import chat_bridge.ui.main_screen ^
    --hidden-import chat_bridge.ui.settings ^
    --hidden-import chat_bridge.ui.toast ^
    --hidden-import chat_bridge.ui.history ^
    --exclude-module keyboard ^
    --exclude-module numpy ^
    --exclude-module pandas ^
    --exclude-module matplotlib ^
    --exclude-module scipy ^
    --exclude-module IPython ^
    --exclude-module notebook ^
    --exclude-module pytest ^
    --exclude-module unittest ^
    --exclude-module doctest ^
    --exclude-module pdb ^
    --exclude-module tkinter.test ^
    --exclude-module lib2to3 ^
    --exclude-module xmlrpc ^
    --exclude-module pydoc ^
    --optimize 2 ^
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
