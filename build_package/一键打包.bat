@echo off
title 假锁屏工具 - 一键打包

echo ===============================================
echo           假锁屏工具 - 一键打包
echo ===============================================
echo.

cd /d "%~dp0"

REM 检查Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ? 错误：未找到Python，请先安装Python 3.7+
    pause
    exit /b 1
)

echo ? Python环境检查通过
echo.

echo 请选择打包模式：
echo.
echo [1] 标准模式（较小exe，需要目标机器有Python环境）
echo [2] 依赖内置模式（较大exe，完全独立运行）
echo.
set /p choice=请输入选择 (1 或 2)，默认为1: 

if "%choice%"=="" set choice=1
if "%choice%"=="2" goto COLLECT_ALL
if "%choice%"=="1" goto STANDARD
echo 无效选择，使用默认标准模式
goto STANDARD

:STANDARD
echo.
echo ? 开始执行标准模式打包...
echo.
python build_exe.py
goto END

:COLLECT_ALL
echo.
echo ? 开始执行依赖内置模式打包...
echo.
python build_exe.py --collect-all
goto END

:END
echo.
echo ===============================================
echo               打包任务完成
echo ===============================================

pause 