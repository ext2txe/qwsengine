# qwsengine/controller_window.py
from PySide6.QtCore import QTimer, Qt, QUrl, QSettings, QByteArray  # ⟵ add QSettings, QByteArray

# ...existing imports...

from .settings_dialog import SettingsDialog  # ⟵ ensure available

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
        # Persist size/pos on close
        self._persist_window_state()
        return super().closeEvent(event)

    # -----------------------------------------------------------------
    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        # ... title, status, tabs (unchanged) ...

        # Tab 3: Settings
        settings_tab = QWidget()
        settings_layout = QVBoxLayout(settings_tab)
        settings_layout.setSpacing(10)

        ua_group = self.create_user_agent_section()
        settings_layout.addWidget(ua_group)

        proxy_group = self.create_proxy_section()
        settings_layout.addWidget(proxy_group)

        # ⟵ NEW: app settings section with path + "Edit settings…" button
        app_group = self.create_app_settings_section()
        settings_layout.addWidget(app_group)

        settings_layout.addStretch()
        self.tab_widget.addTab(settings_tab, "Settings")

    # ... existing sections ...

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

    # ⟵ NEW: shows settings.json path + opens SettingsDialog
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
