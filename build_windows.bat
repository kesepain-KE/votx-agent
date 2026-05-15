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
set "HAS_NODE=0"
where node >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    for /f %%v in ('node --version 2^>^&1') do set "NODE_VER=%%v"
    set "HAS_NODE=1"
    echo   Node.js %NODE_VER%         [OK]
) else (
    echo   [ERROR] Node.js not found!
    echo.
    echo   React frontend build requires Node.js ^>= 18.
    echo   Download: https://nodejs.org/
    echo.
    pause
    exit /b 1
)

where npm >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo   [ERROR] npm not found!
    echo   Download: https://nodejs.org/
    pause
    exit /b 1
)

echo   All prerequisites met.
echo.

REM ---- 激活构建环境 ----
if exist "build_env\Scripts\activate.bat" (
    echo [ENV] Activating isolated build environment...
    call "build_env\Scripts\activate.bat"
)

REM ---- 安装 PyInstaller ----
echo [INSTALL] Installing Python dependencies...
pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python dependencies install failed.
    pause
    exit /b 1
)

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

REM ---- 构建 .exe ----
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
echo   [SUCCESS] votx-agent.exe built!
echo ============================================================
echo.

mkdir dist\votx-agent\users 2>nul
echo users/ > dist\votx-agent\users\.gitkeep

mkdir dist\votx-agent\tmp 2>nul
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
mkdir dist\votx-agent\message-runtime 2>nul
copy /Y message\config.example.json dist\votx-agent\message-runtime\config.example.json >nul
xcopy /E /I /Y provider dist\votx-agent\provider\ >nul
xcopy /E /I /Y run dist\votx-agent\run\ >nul
xcopy /E /I /Y skills dist\votx-agent\skills\ >nul
xcopy /E /I /Y tools dist\votx-agent\tools\ >nul
copy /Y paths.py dist\votx-agent\ >nul
copy /Y AGENTS.md dist\votx-agent\ >nul
copy /Y set_user.py dist\votx-agent\ >nul
copy /Y setup.py dist\votx-agent\ >nul
if exist ".env.example" copy /Y .env.example dist\votx-agent\ >nul

REM ---- 复制 web/（含 src 和 dist）----
echo [COPY] Copying web/...
xcopy /E /I /Y web dist\votx-agent\web\ >nul

REM ---- 构建前端 ----
echo.
echo [FRONTEND] Building React frontend...
pushd dist\votx-agent\web
call npm install
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] npm install failed
    popd
    rmdir /s /q dist\votx-agent 2>nul
    pause
    exit /b 1
)
call npm run build
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] npm run build failed
    popd
    rmdir /s /q dist\votx-agent 2>nul
    pause
    exit /b 1
)
popd
echo   React frontend built successfully

REM ---- 清理 web/ 中构建不需要的文件（只保留 dist/）----
echo [CLEANUP] Stripping web source and node_modules from package...
rmdir /s /q dist\votx-agent\web\node_modules 2>nul
rmdir /s /q dist\votx-agent\web\src 2>nul
rmdir /s /q dist\votx-agent\web\routes 2>nul
rmdir /s /q dist\votx-agent\web\__pycache__ 2>nul
del /q dist\votx-agent\web\package.json 2>nul
del /q dist\votx-agent\web\package-lock.json 2>nul
del /q dist\votx-agent\web\tsconfig.json 2>nul
del /q dist\votx-agent\web\vite.config.ts 2>nul
del /q dist\votx-agent\web\index.html 2>nul
del /q dist\votx-agent\web\__init__.py 2>nul
del /q dist\votx-agent\web\commands.py 2>nul
del /q dist\votx-agent\web\session.py 2>nul
del /q dist\votx-agent\web\server.py 2>nul

REM ---- 打包 ----
echo.
echo Wait 2 seconds to release handles...
timeout /t 2 /nobreak >nul

echo [PACKAGE] Zipping into dist\votx-agent-windows.zip...
powershell -Command "Compress-Archive -Path dist\votx-agent -DestinationPath dist\votx-agent-windows.zip -Force"

echo [CLEANUP] Removing unzipped output folder...
rmdir /s /q dist\votx-agent 2>nul

echo.
echo ============================================================
echo   [DONE] dist\votx-agent-windows.zip
echo ============================================================
echo.
pause
