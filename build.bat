@echo off
echo ==========================================
echo   Translation Bridge - EXE Builder
echo ==========================================
echo.

:: Make sure all runtime dependencies are present in THIS Python, otherwise
:: PyInstaller silently builds an exe that crashes with "No module named ...".
echo Installing/verifying dependencies...
python -m pip install -r requirements.txt

echo.
echo Building Translation Bridge.exe ...
echo.

:: Clean previous builds to avoid conflicts
if exist "build" rmdir /s /q build

:: The tracked spec is the single source of packaging configuration.
:: It generates a temporary icon from assets/logo.png, so a clean clone works.
python -m PyInstaller --noconfirm "Translation Bridge.spec"

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
