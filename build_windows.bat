@echo off
chcp 65001 >nul
setlocal

:: 切换到脚本所在目录，无论您在哪里双击或调用，都能确保在正确的目录工作
cd /d "%~dp0"

:: 自动激活独立的构建环境（如果存在）
if exist "build_env\Scripts\activate.bat" (
    echo [ENV] 正在激活独立的构建环境 (build_env)...
    call "build_env\Scripts\activate.bat"
)

echo ============================================================
echo   votx-agent Windows 构建脚本
echo ============================================================
echo.

:: 检查 PyInstaller
pip show pyinstaller >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [INSTALL] 正在安装 PyInstaller...
    pip install pyinstaller
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] PyInstaller 安装失败，请手动安装: pip install pyinstaller
        pause
        exit /b 1
    )
)

echo [BUILD] 正在构建 votx-agent.exe...
echo.

:: 清理 Python 运行缓存
echo [CLEANUP] 正在清理 __pycache__ 缓存文件...
for /d /r %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d" 2>nul
del /s /q *.pyc 2>nul

:: 清理旧构建
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul

:: 构建
pyinstaller votx-agent.spec

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] 构建失败
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   [SUCCESS] 构建完成！
echo   输出: dist\votx-agent\votx-agent.exe
echo ============================================================

:: 创建 users 目录（运行必需）
mkdir dist\votx-agent\users 2>nul
echo users/ > dist\votx-agent\users\.gitkeep

:: 创建 tmp 目录
mkdir dist\votx-agent\tmp 2>nul
echo tmp/ > dist\votx-agent\tmp\.gitkeep

echo.
echo 使用方法:
echo   双击运行 dist\votx-agent\votx-agent.exe
echo   或命令行: dist\votx-agent\votx-agent.exe --port=1478
echo.

:: 等待一秒确保文件句柄释放
timeout /t 2 /nobreak >nul

echo [PACKAGE] 正在打包为 zip 文件...
powershell -Command "Compress-Archive -Path dist\votx-agent -DestinationPath dist\votx-agent-windows.zip -Force"

echo [CLEANUP] 正在清理打包前的临时文件...
rmdir /s /q dist\votx-agent 2>nul

echo [SUCCESS] 打包完成！路径: dist\votx-agent-windows.zip
echo.
pause
