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

:: Build the exe (optimized)
pyinstaller --noconfirm ^
    --onefile ^
    --windowed ^
    --name "Translation Bridge" ^
    --icon "assets\icon.ico" ^
    --add-data "assets\logo.png;assets" ^
    --hidden-import customtkinter ^
    --hidden-import PIL ^
    --hidden-import keyboard ^
    --hidden-import pystray ^
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
