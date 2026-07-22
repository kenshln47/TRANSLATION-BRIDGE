@echo off
setlocal
cd /d "%~dp0"
echo ==========================================
echo   Translation Bridge - EXE Builder
echo ==========================================
echo.

set "BUILD_PY=%CD%\.venv\Scripts\python.exe"
if not exist "%BUILD_PY%" (
    echo Creating an isolated Python environment...
    where py >nul 2>&1
    if not errorlevel 1 (
        py -3.11 -m venv ".venv" >nul 2>&1
    )
    if not exist "%BUILD_PY%" (
        where python >nul 2>&1
        if errorlevel 1 (
            echo ERROR: Python 3.11 or 3.12 x64 was not found.
            goto :fail
        )
        python -m venv ".venv"
        if errorlevel 1 goto :fail
    )
)

"%BUILD_PY%" -c "import struct,sys; assert sys.version_info[:2] in ((3,11),(3,12)) and struct.calcsize('P') == 8"
if errorlevel 1 (
    echo ERROR: The build requires 64-bit Python 3.11 or 3.12.
    goto :fail
)

:: Make sure all runtime dependencies are present in this Python.
echo Installing/verifying dependencies...
"%BUILD_PY%" -m pip install --upgrade "pip==26.1.2"
if errorlevel 1 goto :fail
"%BUILD_PY%" -m pip install --requirement requirements.txt
if errorlevel 1 goto :fail

echo Preparing bundled OCR models...
if not exist "scripts\prepare_ocr_models.py" goto :fail
"%BUILD_PY%" "scripts\prepare_ocr_models.py"
if errorlevel 1 goto :fail

echo.
echo Building Translation Bridge.exe ...
echo.

:: Remove old artifacts first so a failed build can never look successful.
if exist "build" rmdir /s /q build
if errorlevel 1 goto :fail
if exist "dist\Translation Bridge.exe" del /f /q "dist\Translation Bridge.exe"
if errorlevel 1 goto :fail
if exist "dist\Translation Bridge" rmdir /s /q "dist\Translation Bridge"
if errorlevel 1 goto :fail
if exist "dist\Translation Bridge Portable.zip" del /f /q "dist\Translation Bridge Portable.zip"
if errorlevel 1 goto :fail

:: Build the convenient one-file variant first. It is slower to launch because
:: PyInstaller must unpack the bundled OCR runtime on every start.
"%BUILD_PY%" -m PyInstaller --noconfirm --clean "Translation Bridge.spec"
if errorlevel 1 goto :fail

if not exist "dist\Translation Bridge.exe" goto :fail
for %%I in ("dist\Translation Bridge.exe") do if %%~zI LEQ 0 goto :fail

echo Verifying packaged imports...
start "" /wait "dist\Translation Bridge.exe" --smoke-test
if errorlevel 1 goto :fail

:: The portable folder is the recommended release. It is extracted once by
:: the user and avoids unpacking 150+ MB into %%TEMP%% on every launch.
echo Building fast portable folder...
set "TB_BUILD_ONEDIR=1"
"%BUILD_PY%" -m PyInstaller --noconfirm "Translation Bridge.spec"
if errorlevel 1 (
    set "TB_BUILD_ONEDIR="
    goto :fail
)
set "TB_BUILD_ONEDIR="

if not exist "dist\Translation Bridge\Translation Bridge.exe" goto :fail
echo Verifying fast portable build...
start "" /wait "dist\Translation Bridge\Translation Bridge.exe" --smoke-test
if errorlevel 1 goto :fail

echo Creating release ZIP...
powershell -NoProfile -Command "Compress-Archive -LiteralPath 'dist\Translation Bridge' -DestinationPath 'dist\Translation Bridge Portable.zip' -CompressionLevel Optimal -Force"
if errorlevel 1 goto :fail

echo.
echo ==========================================
echo   SUCCESS! Release files are in: dist\
echo   Recommended: dist\Translation Bridge Portable.zip
echo   Single file: dist\Translation Bridge.exe
for %%I in ("dist\Translation Bridge.exe") do echo   Size: %%~zI bytes
echo   Single-file SHA-256:
set BUILD_HASH=
for /f "usebackq delims=" %%H in (`powershell -NoProfile -Command "(Get-FileHash -LiteralPath 'dist\Translation Bridge.exe' -Algorithm SHA256).Hash"`) do set BUILD_HASH=%%H
if not defined BUILD_HASH goto :fail
echo   %BUILD_HASH%
echo   Portable ZIP SHA-256:
set PORTABLE_HASH=
for /f "usebackq delims=" %%H in (`powershell -NoProfile -Command "(Get-FileHash -LiteralPath 'dist\Translation Bridge Portable.zip' -Algorithm SHA256).Hash"`) do set PORTABLE_HASH=%%H
if not defined PORTABLE_HASH goto :fail
echo   %PORTABLE_HASH%
echo ==========================================
pause
exit /b 0

:fail
echo.
echo ==========================================
echo   BUILD FAILED. No release artifact was produced.
echo ==========================================
if exist "dist\Translation Bridge.exe" del /f /q "dist\Translation Bridge.exe"
if exist "dist\Translation Bridge Portable.zip" del /f /q "dist\Translation Bridge Portable.zip"
if exist "dist\Translation Bridge" rmdir /s /q "dist\Translation Bridge"
pause
exit /b 1
