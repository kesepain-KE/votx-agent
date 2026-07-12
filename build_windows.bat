@echo off
setlocal

cd /d "%~dp0"

echo ============================================================
echo   votx-agent Windows Build Script
echo ============================================================
echo.

REM ---- 前置检查 ----
echo [CHECK] Checking prerequisites...

REM 检查 Python
set "PYTHON="
where python >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    for /f "tokens=2" %%v in ('python --version 2^>^&1') do set "PY_VER=%%v"
    echo   Python %PY_VER%             [OK]
) else (
    echo   [ERROR] Python not found!
    echo   Please install Python ^>= 3.10 from https://www.python.org/downloads/
    pause
    exit /b 1
)

REM 检查 Node.js
where node >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    for /f %%v in ('node --version 2^>^&1') do set "NODE_VER=%%v"
    echo   Node.js %NODE_VER%         [OK]
) else (
    echo   [ERROR] Node.js not found!
    echo   Please install Node.js ^>= 18 from https://nodejs.org/
    pause
    exit /b 1
)

where npm >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo   [ERROR] npm not found!
    pause
    exit /b 1
)

echo   All prerequisites met.
echo.

REM ---- 构建环境 ----
echo [ENV] Setting up build environment...

set "VENV_DIR=%~dp0build_env"

REM 创建 venv（不存在时）
if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo   Creating virtual environment...
    python -m venv "%VENV_DIR%"
    if %ERRORLEVEL% NEQ 0 (
        echo   [ERROR] Failed to create virtual environment
        pause
        exit /b 1
    )
)

REM 激活 venv
set "PYTHON=%VENV_DIR%\Scripts\python.exe"
set "PIP=%VENV_DIR%\Scripts\pip.exe"

echo   Virtual environment: %VENV_DIR%   [OK]

REM 升级 pip
"%PYTHON%" -m pip install --upgrade pip
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] pip upgrade failed.
    pause
    exit /b 1
)

REM 安装依赖
echo [INSTALL] Installing Python dependencies...
"%PIP%" install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python dependencies install failed.
    pause
    exit /b 1
)

REM 检查 PyInstaller
"%PYTHON%" -m pip show pyinstaller >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [INSTALL] Installing PyInstaller...
    "%PIP%" install pyinstaller
)

"%PYTHON%" -m pip show pyinstaller >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] PyInstaller install failed.
    pause
    exit /b 1
)

REM ---- 清理 ----
echo [CLEANUP] Cleaning __pycache__...
for /d /r %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d" 2>nul
del /s /q *.pyc 2>nul

rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul

REM ---- 构建 .exe ----
echo [BUILD] Building votx-agent.exe...
"%PYTHON%" -m PyInstaller votx-agent.spec
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Build failed
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   [SUCCESS] votx-agent-web.exe and votx-agent-cli.exe built!
echo ============================================================
echo.

mkdir dist\votx-agent\users 2>nul
mkdir dist\votx-agent\tmp 2>nul
echo users/ > dist\votx-agent\users\.gitkeep
echo tmp/ > dist\votx-agent\tmp\.gitkeep

REM ---- 复制项目文件 ----
echo [COPY] Copying project files...
xcopy /E /I /Y agents dist\votx-agent\agents\ >nul
xcopy /E /I /Y config dist\votx-agent\config\ >nul
xcopy /E /I /Y cron dist\votx-agent\cron\ >nul
xcopy /E /I /Y message dist\votx-agent\message\ >nul
del /q dist\votx-agent\message\config.json 2>nul
del /q dist\votx-agent\message\config.local.json 2>nul
rmdir /s /q dist\votx-agent\message\push_queue 2>nul
del /q dist\votx-agent\message\identity\identity_map.json 2>nul
xcopy /E /I /Y plugins dist\votx-agent\plugins\ >nul
xcopy /E /I /Y provider dist\votx-agent\provider\ >nul
xcopy /E /I /Y run dist\votx-agent\run\ >nul
xcopy /E /I /Y skills dist\votx-agent\skills\ >nul
xcopy /E /I /Y knowledge dist\votx-agent\knowledge\ >nul
copy /Y paths.py dist\votx-agent\ >nul
del /s /q dist\votx-agent\*.bak 2>nul
copy /Y AGENTS.md dist\votx-agent\ >nul
copy /Y set_user.py dist\votx-agent\ >nul
copy /Y start.py dist\votx-agent\ >nul
copy /Y start_web.py dist\votx-agent\ >nul
copy /Y main.py dist\votx-agent\ >nul
copy /Y update.py dist\votx-agent\ >nul
copy /Y setup.py dist\votx-agent\ >nul
copy /Y requirements.txt dist\votx-agent\ >nul
copy /Y version.json dist\votx-agent\ >nul
if exist ".env.example" copy /Y .env.example dist\votx-agent\ >nul

REM ---- 复制 web/ ----
echo [COPY] Copying web/...
robocopy web dist\votx-agent\web /E /XD node_modules __pycache__ /XF *.pyc *.pyo >nul
if %ERRORLEVEL% GEQ 8 (
    echo [ERROR] Copy web/ failed
    pause
    exit /b 1
)

REM ---- 构建前端 ----
echo [FRONTEND] Building React frontend...
pushd dist\votx-agent\web
call npm ci
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] npm ci failed
    popd
    pause
    exit /b 1
)
call npm run build
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] npm run build failed
    popd
    pause
    exit /b 1
)
popd

echo [CLEANUP] Removing web node_modules from package...
rmdir /s /q dist\votx-agent\web\node_modules 2>nul

REM ---- 打包 ----
echo [PACKAGE] Zipping into dist\votx-agent-windows.zip...
timeout /t 2 /nobreak >nul
powershell -NoProfile -Command "Compress-Archive -Path dist\votx-agent -DestinationPath dist\votx-agent-windows.zip -Force"
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] ZIP package creation failed. Keeping dist\votx-agent for inspection.
    pause
    exit /b 1
)
if not exist "dist\votx-agent-windows.zip" (
    echo [ERROR] ZIP package was not created. Keeping dist\votx-agent for inspection.
    pause
    exit /b 1
)
for %%Z in ("dist\votx-agent-windows.zip") do if %%~zZ LEQ 0 (
    echo [ERROR] ZIP package is empty. Keeping dist\votx-agent for inspection.
    pause
    exit /b 1
)

echo [CLEANUP] Removing unzipped output folder...
rmdir /s /q dist\votx-agent 2>nul

echo.
echo ============================================================
echo   [DONE] dist\votx-agent-windows.zip
echo ============================================================
echo.
pause
