@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_EXE=d:\Users\zhuqi\anaconda3\envs\rs_clean\python.exe"

"%PYTHON_EXE%" -c "import pygame" >nul 2>nul
if errorlevel 1 (
    echo pygame is not installed in rs_clean.
    echo Run this once:
    echo "%PYTHON_EXE%" -m pip install pygame
    pause
    exit /b 1
)

"%PYTHON_EXE%" "%~dp0main.py"
if errorlevel 1 pause
