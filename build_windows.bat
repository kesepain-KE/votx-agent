@echo off
setlocal

cd /d "%~dp0"

if exist "build_env\Scripts\activate.bat" (
    echo [ENV] Activating isolated build environment...
    call "build_env\Scripts\activate.bat"
)

echo ============================================================
echo   votx-agent Windows Build Script
echo ============================================================
echo.

pip show pyinstaller >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [INSTALL] Installing PyInstaller...
    pip install pyinstaller
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] PyInstaller install failed.
        pause
        exit /b 1
    )
)

echo [BUILD] Building votx-agent.exe...
echo.

echo [CLEANUP] Cleaning __pycache__...
for /d /r %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d" 2>nul
del /s /q *.pyc 2>nul

rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul

pyinstaller votx-agent.spec

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Build failed
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   [SUCCESS] Build successful!
echo ============================================================

mkdir dist\votx-agent\users 2>nul
echo users/ > dist\votx-agent\users\.gitkeep

mkdir dist\votx-agent\tmp 2>nul
echo tmp/ > dist\votx-agent\tmp\.gitkeep

echo [COPY] Copying project architecture folders outside...
xcopy /E /I /Y agents dist\votx-agent\agents\ >nul
xcopy /E /I /Y config dist\votx-agent\config\ >nul
xcopy /E /I /Y corn dist\votx-agent\corn\ >nul
xcopy /E /I /Y provider dist\votx-agent\provider\ >nul
xcopy /E /I /Y run dist\votx-agent\run\ >nul
xcopy /E /I /Y skills dist\votx-agent\skills\ >nul
xcopy /E /I /Y tools dist\votx-agent\tools\ >nul
xcopy /E /I /Y web dist\votx-agent\web\ >nul
copy /Y paths.py dist\votx-agent\ >nul
copy /Y AGENTS.md dist\votx-agent\ >nul
copy /Y set_user.py dist\votx-agent\ >nul
copy /Y setup.py dist\votx-agent\ >nul
if exist ".env.example" copy /Y .env.example dist\votx-agent\ >nul

echo.
echo Wait 2 seconds to release handles...
timeout /t 2 /nobreak >nul

echo [PACKAGE] Zipping into dist\votx-agent-windows.zip...
powershell -Command "Compress-Archive -Path dist\votx-agent -DestinationPath dist\votx-agent-windows.zip -Force"

echo [CLEANUP] Removing unzipped output folder...
rmdir /s /q dist\votx-agent 2>nul

echo [SUCCESS] Package created at dist\votx-agent-windows.zip
echo.
pause
