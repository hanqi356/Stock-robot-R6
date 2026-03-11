@echo off
chcp 65001 >nul
title 量化交易系统 R6 - 缠论双引擎增强版

echo ========================================
echo   量化交易系统 R6 - 缠论双引擎增强版
echo ========================================
echo.

cd /d "%~dp0"

:: 检查 Python
set PYTHON_CMD=
py --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=py
)

if "%PYTHON_CMD%"=="" (
    python --version >nul 2>&1
    if not errorlevel 1 (
        set PYTHON_CMD=python
    )
)

if "%PYTHON_CMD%"=="" (
    echo.
    echo [错误] 未检测到 Python 环境
    echo 请先安装 Python 3.10 或更高版本
    echo 下载地址：https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [OK] 检测到 Python: %PYTHON_CMD%
echo.

:: 检查虚拟环境
if exist ".venv\Scripts\activate.bat" (
    echo [提示] 检测到虚拟环境，正在激活...
    call .venv\Scripts\activate.bat
    echo [OK] 虚拟环境已激活
    echo.
)

:: 加载缠论模块
echo [1/2] 正在加载缠论双引擎模块...
%PYTHON_CMD% -c "from chan_auto_patch import auto_integrate; auto_integrate()" 2>nul
if errorlevel 1 (
    echo [提示] 缠论模块加载失败，将以标准模式启动
) else (
    echo [OK] 缠论模块加载成功
)
echo.

:: 启动 GUI
echo [2/2] 正在启动 GUI 程序...
echo.
%PYTHON_CMD% stock_pro_gui.py --chan-mode

if errorlevel 1 (
    echo.
    echo [错误] 启动失败，请检查错误信息
    echo.
    pause
)
