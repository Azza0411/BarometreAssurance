@echo off
REM Double-cliquer ce fichier pour ouvrir la plateforme — aucune commande
REM a taper. Voir launcher/start_platform.py et docs/packaging_portable.md.
setlocal

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

if exist "%SCRIPT_DIR%.venv\Scripts\python.exe" (
    set PYTHON=%SCRIPT_DIR%.venv\Scripts\python.exe
) else (
    set PYTHON=python
)

"%PYTHON%" launcher\start_platform.py
if errorlevel 1 (
    echo.
    echo Un probleme est survenu au demarrage - voir logs\app.log
    pause
)
