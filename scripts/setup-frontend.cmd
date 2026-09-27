@echo off
REM Frontend setup: install dependencies.
setlocal
cd /d "%~dp0..\frontend"
call npm install
if errorlevel 1 exit /b 1
echo.
echo Frontend dependencies installed.
echo Copy .env.example to .env.local and fill in the values.
