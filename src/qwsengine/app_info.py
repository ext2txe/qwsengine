# src/qwsengine/app_info.py
# A dependency-free module that owns app metadata + standard paths.

from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import QStandardPaths

# ---- App identity ---------------------------------------------------------
APP_ORG  = "codaland.com"
APP_NAME = "QWSEngine"
APP_ID   = f"{APP_ORG}.{APP_NAME}"

# Qt resource prefix (use like f"{RESOURCE_PREFIX}/icons/logo.png")
RESOURCE_PREFIX = ":/qws"

# Version (single source of truth is package __init__.py if available)
try:
    from . import __version__ as APP_VERSION  # defined in qwsengine/__init__.py
except Exception:
    APP_VERSION = "0.4.6-dev"

# ---- Standard locations (cross-platform) ----------------------------------
def app_dir(kind: QStandardPaths.StandardLocation) -> Path:
    """
    Returns a writable per-user directory for the app, e.g.
    - Windows: %APPDATA%/QWSEngine/codaland.com
    - macOS:   ~/Library/Application Support/QWSEngine/codaland.com
    - Linux:   ~/.local/share/QWSEngine/codaland.com (or ~/.config for AppConfigLocation)
    """
    base = Path(QStandardPaths.writableLocation(kind))
    # Swapped order: APP_NAME / APP_ORG instead of APP_ORG / APP_NAME
    path = base / APP_NAME / APP_ORG
    path.mkdir(parents=True, exist_ok=True)
    return path

# Commonly used paths
APP_BASE_PATH = app_dir(QStandardPaths. AppLocalDataLocation)
SETTINGS_PATH = app_dir(QStandardPaths.AppLocalDataLocation) / "settings.json"
CACHE_DIR     = app_dir(QStandardPaths.CacheLocation)
DATA_DIR      = app_dir(QStandardPaths.AppDataLocation)
LOG_DIR       = app_dir(QStandardPaths.AppConfigLocation) / "log"
