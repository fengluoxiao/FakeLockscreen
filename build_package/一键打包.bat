@echo off
title ���������� - һ�����

echo ===============================================
echo           ���������� - һ�����
echo ===============================================
echo.

cd /d "%~dp0"

REM ���Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ? ����δ�ҵ�Python�����Ȱ�װPython 3.7+
    pause
    exit /b 1
)

echo ? Python�������ͨ��
echo.

echo ��ѡ����ģʽ��
echo.
echo [1] ��׼ģʽ����Сexe����ҪĿ�������Python������
echo [2] ��������ģʽ���ϴ�exe����ȫ�������У�
echo.
set /p choice=������ѡ�� (1 �� 2)��Ĭ��Ϊ1: 

if "%choice%"=="" set choice=1
if "%choice%"=="2" goto COLLECT_ALL
if "%choice%"=="1" goto STANDARD
echo ��Чѡ��ʹ��Ĭ�ϱ�׼ģʽ
goto STANDARD

:STANDARD
echo.
echo ? ��ʼִ�б�׼ģʽ���...
echo.
python build_exe.py
goto END

:COLLECT_ALL
echo.
echo ? ��ʼִ����������ģʽ���...
echo.
python build_exe.py --collect-all
goto END

:END
echo.
echo ===============================================
echo               ����������
echo ===============================================

pause 