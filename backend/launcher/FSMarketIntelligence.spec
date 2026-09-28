# -*- mode: python ; coding: utf-8 -*-
# Spec PyInstaller pour le lanceur "un clic" — voir docs/packaging_portable.md.
# Build : depuis la racine du projet, `pyinstaller launcher\FSMarketIntelligence.spec`
# (ou `build_exe.bat`, qui fait exactement ça). Résultat dans dist\FSMarketIntelligence\
# (dossier ignoré par git — voir .gitignore) : FSMarketIntelligence.exe est le
# fichier à double-cliquer.
import os

# SPECPATH (fourni par PyInstaller) = dossier de ce fichier (launcher/) —
# chemin RELATIF plutôt qu'absolu codé en dur, pour que ce spec fonctionne
# quel que soit l'endroit où le dépôt est cloné.
# SPECPATH = backend/launcher/ ; PROJECT_ROOT = SCRAPING/ (racine du dépôt)
# BACKEND_ROOT = SCRAPING/backend/ (code Python, database, extraction)
PROJECT_ROOT = os.path.dirname(os.path.dirname(SPECPATH))
BACKEND_ROOT = os.path.dirname(SPECPATH)

_data_dir = os.path.join(BACKEND_ROOT, "data")
_data_files = [
    (os.path.join(_data_dir, f), "data")
    for f in os.listdir(_data_dir)
    if f.lower().endswith(".xlsx")
] if os.path.isdir(_data_dir) else []

a = Analysis(
    [os.path.join(SPECPATH, "main.py")],
    pathex=[PROJECT_ROOT],
    binaries=[],
    datas=[
        (os.path.join(PROJECT_ROOT, "frontend", "dist"), "frontend/dist"),
        (os.path.join(BACKEND_ROOT, "database", "schema.sql"), "database"),
        (os.path.join(BACKEND_ROOT, "extraction", "tessdata_ara"), "extraction/tessdata_ara"),
        (os.path.join(BACKEND_ROOT, "chatbot_portable", "rag_corpus_extra.json"), "chatbot_portable"),
        (os.path.join(BACKEND_ROOT, "chatbot_portable", "MarketInsurance.db"), "chatbot_portable"),
        *_data_files,
    ],
    hiddenimports=["pymysql", "chatbot_portable.app"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # torch/paddle/cv2 : dépendances optionnelles lourdes détectées par
    # erreur (jamais utilisées par ce projet) qui, une fois exclues,
    # réduisent le temps de build de ~5 minutes à ~2 minutes.
    # jedi/IPython/notebook : tirent un chemin de fichier vendored si long
    # (jedi/third_party/django-stubs/...) qu'il dépasse la limite Windows
    # MAX_PATH une fois combiné à un chemin de build profondément imbriqué
    # (FileNotFoundError constaté) — jamais utilisés par ce projet non plus.
    excludes=["torch", "paddle", "cv2", "jedi", "IPython", "notebook"],
    noarchive=False,
    optimize=0,
)

# ucrtbase.dll/vcruntime140*.dll : déjà présentes sur tout Windows 10/11,
# inutile de les embarquer — et un filtre système (EDR/antivirus) bloque
# systématiquement l'écriture d'un fichier portant le nom exact
# "ucrtbase.dll" lors de la copie finale (PermissionError constaté sur
# DEUX emplacements disque différents, donc pas un problème de chemin).
# On les retire de la liste plutôt que de contourner cette protection.
_SYSTEM_DLL_NAMES = {"ucrtbase.dll", "vcruntime140.dll", "vcruntime140_1.dll"}
a.binaries = [b for b in a.binaries if os.path.basename(b[0]).lower() not in _SYSTEM_DLL_NAMES]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FSMarketIntelligence",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="FSMarketIntelligence",
)
