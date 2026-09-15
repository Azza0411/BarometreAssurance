@echo off
REM Compile la plateforme en un seul executable portable (voir
REM docs/packaging_portable.md). A executer UNE FOIS (par le developpeur,
REM pas l'utilisateur final) apres tout changement de code, avant de
REM distribuer le dossier dist\FSMarketIntelligence\ genere.
setlocal

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

if exist "%SCRIPT_DIR%.venv\Scripts\python.exe" (
    set PYTHON=%SCRIPT_DIR%.venv\Scripts\python.exe
) else (
    set PYTHON=python
)

echo Etape 1/2 : build du frontend (npm run build)...
pushd frontend
call npm run build
popd
if errorlevel 1 (
    echo [ERREUR] Build frontend echoue.
    pause
    exit /b 1
)

echo Etape 2/2 : compilation PyInstaller (dist\FSMarketIntelligence\)...
"%PYTHON%" -m PyInstaller --noconfirm launcher\FSMarketIntelligence.spec
if errorlevel 1 (
    echo [ERREUR] Compilation echouee - voir la sortie ci-dessus.
    pause
    exit /b 1
)

echo.
echo Termine. Distribuer le dossier dist\FSMarketIntelligence\ (l'utilisateur
echo final double-clique FSMarketIntelligence.exe a l'interieur).
pause
