@echo off
REM Lance le pipeline complet (collecte + extraction + qualite) et journalise
REM le resultat. Prevu pour le Planificateur de taches Windows.
REM
REM Enregistrement (une fois, depuis une invite avec droits admin) :
REM   schtasks /create /tn "FSMarketIntelligence_Pipeline" ^
REM     /tr "\"%~dp0run_pipeline.bat\"" /sc weekly /d SUN /st 02:00
setlocal

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

if exist "%SCRIPT_DIR%.venv\Scripts\python.exe" (
    set PYTHON=%SCRIPT_DIR%.venv\Scripts\python.exe
) else (
    set PYTHON=python
)

"%PYTHON%" pipelines\run_pipeline.py
exit /b %ERRORLEVEL%
