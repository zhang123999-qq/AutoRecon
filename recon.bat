@echo off
chcp 65001 >nul 2>&1
title 信息收集工具 v2.0

echo ====================================================
echo    信息收集自动化工具 v2.0
echo    模块化重构版 - 作者: 小欣
echo ====================================================
echo.

:: 检查Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到Python，请先安装Python 3.x
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: 获取目标
set "TARGET=%~1"
if "%TARGET%"=="" (
    set /p "TARGET=请输入目标域名: "
)

if "%TARGET%"=="" (
    echo [错误] 未输入目标域名
    pause
    exit /b 1
)

echo.
echo 正在扫描: %TARGET%
echo.

:: 切换目录并运行
cd /d "%~dp0"
python -u recon.py %TARGET%

if errorlevel 1 (
    echo.
    echo [错误] 程序执行出错
)

echo.
pause
