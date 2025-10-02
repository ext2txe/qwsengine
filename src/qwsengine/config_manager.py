# src/qwsengine/config_manager.py
from pathlib import Path
from PySide6.QtCore import QStandardPaths
import json

APP_ORG = "YourOrg"
APP_NAME = "QWSEngine"
SCHEMA_VERSION = 3

def app_dir(kind: QStandardPaths.StandardLocation) -> Path:
    base = Path(QStandardPaths.writableLocation(kind))
    path = base / APP_ORG / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path

SETTINGS_PATH = app_dir(QStandardPaths.AppConfigLocation) / "settings.json"

DEFAULTS = {
    "_schemaVersion": SCHEMA_VERSION,
    "proxy": {"enabled": False, "host": "", "port": 0, "user": "", "password": ""},
    "features": {"experimental_fullpage_capture": False},
}

def migrate_settings(data: dict) -> dict:
    ver = int(data.get("_schemaVersion", 1))
    if ver < 2:
        data.setdefault("proxy", {}).setdefault("enabled", False)
        ver = 2
    if ver < 3:
        data.setdefault("features", {})["experimental_fullpage_capture"] = False
        ver = 3
    data["_schemaVersion"] = ver
    return data

def load_settings() -> dict:
    if SETTINGS_PATH.exists():
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    else:
        data = DEFAULTS.copy()
    return migrate_settings(data)

def save_settings(data: dict):
    SETTINGS_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")

def is_enabled(name: str) -> bool:
    s = load_settings()
    return s.get("features", {}).get(name, DEFAULTS["features"].get(name, False))
