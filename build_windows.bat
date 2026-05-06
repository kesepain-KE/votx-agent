@echo off
setlocal

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
pause
