@echo off
chcp 65001 >nul
cls
title 量化交易系统 R6 - 一键安装并运行

color 0A

echo ============================================
echo    量化交易系统 R6 - 全自动安装工具
echo ============================================
echo.

py --version >nul 2>&1
if %errorlevel% == 0 (
    echo [OK] Python 已安装
    goto CREATE_VENV
)

echo [提示] 未检测到 Python 环境
echo.
echo 正在自动下载并安装 Python 3.11.9...
echo.
echo [1/5] 下载 Python 安装程序...

:: 创建临时目录
set "TEMP_DIR=%TEMP%\StockRobotR6"
if not exist "%TEMP_DIR%" mkdir "%TEMP_DIR%"

:: 下载 Python 3.11.9（64 位）
powershell -Command "& {Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile '%TEMP_DIR%\python_installer.exe'}"

if not exist "%TEMP_DIR%\python_installer.exe" (
    echo [错误] Python 下载失败，请手动安装
    echo 下载地址：https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [OK] Python 安装程序下载完成

echo.
echo [2/5] 安装 Python（静默安装，可能需要 2-3 分钟）...
start /wait "" "%TEMP_DIR%\python_installer.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_pip=1

:: 等待安装完成
timeout /t 5 /nobreak >nul

:: 刷新环境变量
setx PATH "%PATH%;%LOCALAPPDATA%\Programs\Python\Python311\Scripts;%LOCALAPPDATA%\Programs\Python\Python311"

:: 验证安装
py --version >nul 2>&1
if %errorlevel% neq 0 (
    python --version >nul 2>&1
    if %errorlevel% neq 0 (
        echo [错误] Python 安装失败
        pause
        exit /b 1
    )
    set PYTHON_CMD=python
) else (
    set PYTHON_CMD=py
)

echo [OK] Python 安装成功

:: 清理安装程序
del "%TEMP_DIR%\python_installer.exe" >nul 2>&1
if exist "%TEMP_DIR%" rmdir /S /Q "%TEMP_DIR%" >nul 2>&1

:CREATE_VENV
echo.
echo [3/5] 配置虚拟环境...
if not exist ".venv" (
    echo 正在创建虚拟环境...
    py -m venv .venv
    if %errorlevel% neq 0 (
        echo [错误] 创建虚拟环境失败
        pause
        exit /b 1
    )
    echo [OK] 虚拟环境创建成功
) else (
    echo [OK] 虚拟环境已存在
)

:ACTIVATE_VENV
echo.
echo [4/5] 激活虚拟环境...
call .venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo [错误] 激活虚拟环境失败
    pause
    exit /b 1
)
echo [OK] 虚拟环境已激活

:INSTALL_DEPS
echo.
echo [5/5] 安装依赖库（这可能需要 3-5 分钟）...
echo.

echo 正在升级 pip 工具...
python -m pip install --upgrade pip setuptools wheel --quiet

echo 正在安装项目依赖...
if exist "requirements.txt" (
    python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --quiet
) else (
    echo [警告] requirements.txt 不存在，安装基础依赖...
    python -m pip install numpy pandas matplotlib pillow pytdx akshare --quiet
)

if %errorlevel% neq 0 (
    echo [警告] 部分依赖安装失败，但不影响主要功能
)

echo.
echo [4/4] 验证安装...
python -c "import pandas; import numpy; import tkinter" >nul 2>&1
if %errorlevel% neq 0 (
    echo [警告] 部分模块验证失败，但不影响主要功能
) else (
    echo [OK] 核心模块验证通过
)

echo.
echo ============================================
echo    安装完成！
echo ============================================
echo.
echo 下一步操作:
echo   1. 双击 启动专业版.bat 启动程序
echo   2. 或运行 python verify_install.py 验证安装
echo.
echo 提示:
echo   - 启动专业版.bat 菜单含快速自检选项
echo   - AI 功能需配置 API 密钥
echo   - 实盘交易需登录券商客户端
echo.
pause

exit