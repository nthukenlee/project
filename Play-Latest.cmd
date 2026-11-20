@echo off
setlocal
cd /d "%~dp0"
"%LOCALAPPDATA%\Programs\Python\Python314\python.exe" -B "%~dp0main.py"
if errorlevel 1 pause
