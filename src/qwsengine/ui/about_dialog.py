# src/qwsengine/about_dialog.py
from __future__ import annotations
from pathlib import Path
import platform
import sys

from PySide6 import __version__ as PYSIDE_VERSION
from PySide6.QtCore import Qt, qVersion, QDateTime
from PySide6.QtGui import QIcon, QTextOption
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QHBoxLayout, QVBoxLayout, QPlainTextEdit, QWidget
from PySide6.QtWebEngineCore import QWebEngineProfile

# NEW: import shared app info (single source of truth)
from qwsengine.app_info import APP_NAME, APP_VERSION, SETTINGS_PATH, RESOURCE_PREFIX

try:
    from qwsengine.core.settings import SettingsManager  # only to read current settings cleanly
    def load_settings(): return SettingsManager().settings
except Exception:
    def load_settings(): return {}

class AboutDialog(QDialog):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(f"About {APP_NAME}")
        self.setWindowModality(Qt.ApplicationModal)
        self.setMinimumWidth(520)

        # Use shared resource prefix for icon
        icon_label = QLabel(self)
        icon = QIcon(f"{RESOURCE_PREFIX}/icons/logo.png")
        icon_label.setPixmap(icon.pixmap(64, 64))

        title = QLabel(f"<b>{APP_NAME}</b><br>Version {APP_VERSION}", self)
        title.setTextFormat(Qt.RichText)

        header = QHBoxLayout()
        header.addWidget(icon_label, 0, Qt.AlignTop)
        header.addSpacing(8)
        header.addWidget(title, 1, Qt.AlignVCenter)

        details = QPlainTextEdit(self)
        details.setReadOnly(True)
        details.setPlainText(self._system_info_text())
        details.setWordWrapMode(QTextOption.WordWrap)

        buttons = QDialogButtonBox(QDialogButtonBox.Close, parent=self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)

        root = QVBoxLayout(self)
        root.addLayout(header)
        root.addWidget(details, 1)
        root.addWidget(buttons)

    def _system_info_text(self) -> str:
        py_ver    = sys.version.split()[0]
        os_name   = platform.system()
        os_rel    = platform.release()
        os_ver    = platform.version()
        machine   = platform.machine()
        qt_ver    = qVersion()
        pyside_ver= PYSIDE_VERSION
        now       = QDateTime.currentDateTime().toString(Qt.ISODate)

        prof = QWebEngineProfile.defaultProfile()
        ua   = prof.httpUserAgent()
        cache_path   = Path(prof.cachePath() or "")
        storage_path = Path(prof.persistentStoragePath() or "")
        cookies_policy = prof.persistentCookiesPolicy()

        settings = load_settings()
        features = settings.get("features", {})

        webengine_hint = self._parse_webengine_versions(ua)

        lines = [
            f"{APP_NAME} {APP_VERSION}",
            f"Built on:        {now}",
            "",
            "Runtime",
            f"- Python:         {py_ver}",
            f"- PySide6:        {pyside_ver}",
            f"- Qt:             {qt_ver}",
            f"- OS:             {os_name} {os_rel} ({os_ver})",
            f"- Arch:           {machine}",
            "",
            "Qt WebEngine",
            f"- User-Agent:     {ua}",
            f"- {webengine_hint}" if webengine_hint else "- (WebEngine versions parsed from UA when available)",
            f"- Cookies:        {'Persistent' if cookies_policy else 'Session'}",
            f"- Cache path:     {cache_path}",
            f"- Storage path:   {storage_path}",
            "",
            "Configuration",
            f"- Settings file:  {SETTINGS_PATH}",
        ]
        if features:
            lines.append("- Features:")
            for k, v in sorted(features.items()):
                lines.append(f"  • {k}: {'ENABLED' if bool(v) else 'disabled'}")
        else:
            lines.append("- Features: (none)")
        return "\n".join(lines)

    def _parse_webengine_versions(self, ua: str) -> str | None:
        chrom = qtwe = None
        for p in ua.split():
            if p.startswith("Chrome/"):
                chrom = p.split("/", 1)[-1]
            if p.startswith("QtWebEngine/"): 
                qtwe  = p.split("/", 1)[-1]
        bits = []
        if chrom: 
            bits.append(f"Chromium: {chrom}")
        if qtwe:  
            bits.append(f"QtWebEngine: {qtwe}")
        return ", ".join(bits) if bits else None
