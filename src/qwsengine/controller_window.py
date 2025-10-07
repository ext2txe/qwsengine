# qwsengine/controller_window.py
from __future__ import annotations

# Qt
from PySide6.QtCore import QTimer, Qt, QSettings, QByteArray, QCoreApplication
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QGroupBox, QTabWidget,
    QSpinBox, QCheckBox, QStatusBar   # ← add QStatusBar
)

# Project
try:
    from .app_info import APP_VERSION, APP_NAME
except Exception:
    APP_VERSION = "dev"
    APP_NAME = "QWSEngine"

from .settings_dialog import SettingsDialog
from .settings import SettingsManager

class BrowserControllerWindow(QMainWindow):
    def __init__(self, browser_window=None, parent=None):
        super().__init__(parent)
        self.browser_window = browser_window
        self.settings_manager = browser_window.settings_manager if browser_window else None

        self.auto_reload_timer = QTimer()
        self.auto_reload_timer.timeout.connect(self.on_auto_reload_timeout)
        self.auto_reload_enabled = False

        self.setWindowTitle(f"Qt Browser (controller) v{APP_VERSION}")
        self.resize(450, 900)

        # Initialize scripting engine...
        # ... (unchanged) ...

        self.init_ui()

        # ⟵ restore controller window geometry/state
        self._restore_window_state()

        # ... existing debug / settings checks ...
        if self.settings_manager:
            self.load_settings()
            self.update_status("Ready")
        else:
            self.update_status("Warning: No settings manager")

    # ---------- NEW: save/restore controller window geometry ----------
    def _restore_window_state(self):
        try:
            qs = QSettings("qwsengine", "QtBrowserController")
            g = qs.value("controller/geometry", None)
            s = qs.value("controller/state", None)
            if isinstance(g, QByteArray):
                self.restoreGeometry(g)
            if isinstance(s, QByteArray):
                self.restoreState(s)
        except Exception:
            pass

    def _persist_window_state(self):
        try:
            qs = QSettings("qwsengine", "QtBrowserController")
            qs.setValue("controller/geometry", self.saveGeometry())
            qs.setValue("controller/state", self.saveState())
        except Exception:
            pass

    def closeEvent(self, event):
        # persist controller geometry/state
        try:
            from PySide6.QtCore import QSettings
            qs = QSettings("qwsengine", "QtBrowserController")
            qs.setValue("controller/geometry", self.saveGeometry())
            qs.setValue("controller/state", self.saveState())
        except Exception:
            pass

        # also close the main browser window
        try:
            if getattr(self, "browser_window", None):
                self.browser_window.close()
        except Exception:
            pass

        super().closeEvent(event)

    # -----------------------------------------------------------------
    def init_ui(self):
        # Central widget + root layout
        central = QWidget(self)
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        # Tabs
        self.tab_widget = QTabWidget(self)
        root.addWidget(self.tab_widget)

        # ----- Settings tab -----
        settings_tab = QWidget(self)
        settings_layout = QVBoxLayout(settings_tab)
        settings_layout.setContentsMargins(8, 8, 8, 8)
        settings_layout.setSpacing(8)

        # Sections (these methods were provided earlier)
        settings_layout.addWidget(self.create_user_agent_section())
        settings_layout.addWidget(self.create_proxy_section())
        settings_layout.addWidget(self.create_app_settings_section())
        settings_layout.addStretch(1)

        self.tab_widget.addTab(settings_tab, "Settings")

        # Optional: a simple status label at the bottom (if you don't already have one)
        if not hasattr(self, "status_label"):
            self.status_label = QLabel("")
            self.status_label.setStyleSheet("color: gray;")
            root.addWidget(self.status_label)

        if not self.statusBar():
            self.setStatusBar(QStatusBar(self))

    def create_user_agent_section(self):
        group = QGroupBox("User Agent")
        layout = QVBoxLayout()

        self.ua_input = QLineEdit()
        self.ua_input.setPlaceholderText("Custom User Agent (leave empty for default)")
        layout.addWidget(self.ua_input)

        ua_btn = QPushButton("Apply User Agent")
        ua_btn.clicked.connect(self.on_apply_user_agent)
        ua_btn.setStyleSheet("QPushButton { background-color: #3f51b5; color: white; padding: 8px; }")
        layout.addWidget(ua_btn)

        group.setLayout(layout)
        return group

    # --- Proxy UI section ---------------------------------------------------------
    def create_proxy_section(self):
        group = QGroupBox("Proxy")
        v = QVBoxLayout(group)

        # Row: enable
        row0 = QHBoxLayout()
        self.proxy_enabled_cb = QCheckBox("Enable Proxy")
        self.proxy_enabled_cb.stateChanged.connect(self.on_proxy_enabled_changed)
        row0.addWidget(self.proxy_enabled_cb)
        row0.addStretch(1)
        v.addLayout(row0)

        # Row: host
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Host:"))
        self.proxy_host_input = QLineEdit()
        self.proxy_host_input.setPlaceholderText("proxy.example.com")
        row1.addWidget(self.proxy_host_input, 1)
        v.addLayout(row1)

        # Row: port
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Port:"))
        self.proxy_port_input = QSpinBox()
        self.proxy_port_input.setRange(0, 65535)
        self.proxy_port_input.setValue(0)
        row2.addWidget(self.proxy_port_input)
        v.addLayout(row2)

        # Row: type
        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Type:"))
        self.proxy_type_input = QLineEdit()
        self.proxy_type_input.setPlaceholderText("http | socks5")
        row3.addWidget(self.proxy_type_input)
        v.addLayout(row3)

        # Row: actions/status
        row4 = QHBoxLayout()
        apply_btn = QPushButton("Apply Proxy")
        apply_btn.clicked.connect(self.on_apply_proxy)
        row4.addWidget(apply_btn)
        self.proxy_status = QLabel("Status: —")
        self.proxy_status.setStyleSheet("color: gray;")
        row4.addWidget(self.proxy_status, 1)
        v.addLayout(row4)

        return group

    # --- Load settings into the UI -----------------------------------------------
    def load_settings(self):
        if not self.settings_manager:
            return
        # Mode -> checkbox
        mode = (self.settings_manager.get("proxy_mode", "system") or "system").lower()
        is_manual = (mode == "manual")
        self.proxy_enabled_cb.setChecked(is_manual)

        # Host
        self.proxy_host_input.setText(self.settings_manager.get("proxy_host", ""))

        # Port (robust to string/int/None)
        raw_port = self.settings_manager.get("proxy_port", 0)
        try:
            port = int(raw_port) if raw_port else 0
        except Exception:
            port = 0
        if 0 <= port <= 65535:
            self.proxy_port_input.setValue(port)

        # Type
        self.proxy_type_input.setText(self.settings_manager.get("proxy_type", "http"))

        # Enable/disable inputs
        self._set_proxy_inputs_enabled(is_manual)

        # Optional status text
        if is_manual and self.proxy_host_input.text().strip():
            self.proxy_status.setText(
                f"Status: Enabled ({self.proxy_type_input.text().strip() or 'http'}://"
                f"{self.proxy_host_input.text().strip()}:{self.proxy_port_input.value()})"
            )
        else:
            self.proxy_status.setText("Status: Disabled" if not is_manual else "Status: Enabled")

    # --- Helpers ------------------------------------------------------------------
    def _set_proxy_inputs_enabled(self, enabled: bool):
        self.proxy_host_input.setEnabled(enabled)
        self.proxy_port_input.setEnabled(enabled)
        self.proxy_type_input.setEnabled(enabled)

    def _apply_proxy_via_manager(self, *, mode: str, proxy_type: str, host: str | None, port: int | None, persist: bool = True) -> bool:
        """Apply proxy using SettingsManager API if available; otherwise write keys directly."""
        sm = self.settings_manager
        ok = True
        try:
            if hasattr(sm, "set_proxy_settings"):
                ok = bool(sm.set_proxy_settings(
                    mode=mode,
                    proxy_type=proxy_type,
                    host=host or None,
                    port=port or None,
                    persist=persist,
                    apply_now=True,
                ))
            else:
                # Fallback: write keys and apply
                sm.set("proxy_mode", mode, persist=False)
                sm.set("proxy_type", proxy_type, persist=False)
                sm.set("proxy_host", host or "", persist=False)
                sm.set("proxy_port", int(port or 0), persist=False)
                if hasattr(sm, "save_settings"):
                    sm.save_settings()
                if hasattr(sm, "apply_proxy_settings"):
                    sm.apply_proxy_settings()
        except Exception:
            ok = False
        return ok

    # --- Signals ------------------------------------------------------------------
    def on_proxy_enabled_changed(self, state):
        if not self.settings_manager:
            return
        enabled = (state == Qt.Checked)
        self._set_proxy_inputs_enabled(enabled)
        mode = "manual" if enabled else "none"   # swap 'none'->'system' if you prefer system proxies when disabled
        ok = self._apply_proxy_via_manager(
            mode=mode,
            proxy_type=(self.proxy_type_input.text().strip() or "http"),
            host=self.proxy_host_input.text().strip() or None,
            port=int(self.proxy_port_input.value()) or None,
            persist=True,
        )
        if ok:
            self.proxy_status.setText(f"Status: {'Enabled' if enabled else 'Disabled'}")
            if hasattr(self, "update_status"):
                self.update_status(f"Proxy {'enabled' if enabled else 'disabled'}")
        else:
            if hasattr(self, "update_status"):
                self.update_status("Failed to toggle proxy")

    def on_apply_proxy(self):
        if not self.settings_manager:
            return
        enabled = self.proxy_enabled_cb.isChecked()
        host = self.proxy_host_input.text().strip()
        port = int(self.proxy_port_input.value())
        ptype = (self.proxy_type_input.text().strip() or "http").lower()

        if enabled and (not host or port <= 0):
            if hasattr(self, "update_status"):
                self.update_status("ERROR: Proxy host/port required")
            return

        mode = "manual" if enabled else "none"
        ok = self._apply_proxy_via_manager(
            mode=mode,
            proxy_type=ptype,
            host=host or None,
            port=port or None,
            persist=True,
        )

        if ok and enabled:
            self.proxy_status.setText(f"Status: Active ({ptype}://{host}:{port})")
            if hasattr(self, "update_status"):
                self.update_status("Proxy settings applied (WebEngine may require restart)")
        elif ok:
            self.proxy_status.setText("Status: Disabled")
            if hasattr(self, "update_status"):
                self.update_status("Proxy disabled")
        else:
            if hasattr(self, "update_status"):
                self.update_status("Failed to save/apply proxy settings")


    def create_app_settings_section(self):
        group = QGroupBox("App Settings")
        v = QVBoxLayout()

        # path label
        self.settings_path_label = QLabel()
        self.settings_path_label.setWordWrap(True)
        self.settings_path_label.setStyleSheet("color: gray; font-size: 10px;")
        v.addWidget(self.settings_path_label)

        # buttons row
        row = QHBoxLayout()
        edit_btn = QPushButton("Edit settings…")
        edit_btn.clicked.connect(self.on_edit_settings)
        row.addWidget(edit_btn)

        v.addLayout(row)
        group.setLayout(v)

        # initial fill
        self._refresh_settings_path_label()
        return group

    def _refresh_settings_path_label(self):
        try:
            if self.settings_manager and getattr(self.settings_manager, "settings_path", None):
                p = self.settings_manager.settings_path  # Path
            else:
                # Fallback to show where it would be
                from .settings import SettingsManager
                p = SettingsManager().settings_path
            self.settings_path_label.setText(f"settings.json: {str(p.resolve())}")
        except Exception:
            self.settings_path_label.setText("settings.json: (unknown)")

    def on_edit_settings(self):
        try:
            if not self.settings_manager:
                # If launched without a browser, allow editing anyway (writes same file)
                from .settings import SettingsManager
                self.settings_manager = SettingsManager()

            dlg = SettingsDialog(self, self.settings_manager)
            if dlg.exec():
                # reload visible fields and refresh the hint
                self.load_settings()
                self._refresh_settings_path_label()
                self.update_status("Settings saved.")
            else:
                self.update_status("Settings unchanged.")
        except Exception as e:
            self.update_status(f"Failed to open settings dialog: {e}")

    # ---------- minor fix: apply UA without calling non-existent .save() ----------
    def on_apply_user_agent(self):
        if not self.settings_manager:
            return
        ua = self.ua_input.text().strip()
        # Persist + apply immediately via SettingsManager helper
        from .settings import SettingsManager  # type: ignore  # for types
        try:
            # Prefer dedicated helper that also reapplies to live profile
            self.settings_manager.apply_user_agent(ua or None)
            self.log_command(f"User agent {'set' if ua else 'cleared'}")
            self.update_status("User agent applied.")
        except Exception:
            # Safe fallback
            self.settings_manager.set("user_agent", ua)
            self.settings_manager.save_settings()
            self.update_status("User agent saved (restart may be required).")

    def on_auto_reload_timeout(self):
        """Auto-reload the active page if we have a browser window."""
        try:
            bw = getattr(self, "browser_window", None)
            if not bw:
                return

            # Try a few common hooks without assuming exact class names
            if hasattr(bw, "reload_current"):
                bw.reload_current()
                return
            if hasattr(bw, "_reload_current"):
                bw._reload_current()
                return
            if hasattr(bw, "current_webview"):
                v = bw.current_webview()
                if v:
                    v.reload()
                return
            if hasattr(bw, "current_tab"):
                tab = bw.current_tab()
                view = getattr(tab, "view", None) or getattr(tab, "browser", None)
                if view:
                    view.reload()
        except Exception:
            # Don't let timer exceptions crash the controller
            pass

    def update_status(self, text: str, *, timeout_ms: int = 4000):
        """Show a transient message and also log it if possible."""
        try:
            sb = self.statusBar()
            if sb:
                sb.showMessage(text, timeout_ms)
        except Exception:
            pass
        # Optional: also log via SettingsManager (best-effort)
        try:
            if self.settings_manager and hasattr(self.settings_manager, "log_system_event"):
                self.settings_manager.log_system_event("controller", text)
        except Exception:
            pass

    def log_command(self, message: str):
        """Best-effort debug logging hook used elsewhere."""
        try:
            if self.settings_manager and hasattr(self.settings_manager, "log_system_event"):
                self.settings_manager.log_system_event("controller", message)
        except Exception:
            pass
