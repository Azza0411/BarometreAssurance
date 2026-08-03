#!/usr/bin/env bash
# Lance le pipeline complet (collecte + extraction + qualite) et journalise
# le resultat. Prevu pour cron, ex. tous les dimanches a 2h :
#   0 2 * * 0 /path/to/run_pipeline.sh >> /path/to/logs/cron.log 2>&1
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python"
if [ -x "$VENV_PYTHON" ]; then
    PYTHON="$VENV_PYTHON"
else
    PYTHON="python3"
fi

"$PYTHON" pipelines/run_pipeline.py
exit $?
