@echo off
REM Create the backend virtual environment on Python 3.13 and install deps.
setlocal
cd /d "%~dp0..\backend"
py -3.13 -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
