# qwsengine/controller_window.py
from __future__ import annotations

# Qt
from PySide6.QtCore import QTimer, Qt, QSettings, QByteArray, QCoreApplication, QEvent
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QGroupBox, QTabWidget,
    QSpinBox, QCheckBox, QStatusBar, QTextEdit
)

# Project
try:
    from .app_info import APP_VERSION, APP_NAME
except Exception:
    APP_VERSION = "dev"
    APP_NAME = "QWSEngine"

from .settings_dialog import SettingsDialog
from .settings import SettingsManager
from .browser_operations import BrowserOperations  # NEW IMPORT

class BrowserControllerWindow(QMainWindow):
    def __init__(self, browser_window=None, parent=None):
        super().__init__(parent)
        self.browser_window = browser_window
        self.settings_manager = browser_window.settings_manager if browser_window else None

        # NEW: Initialize browser operations utility
        self.browser_ops = BrowserOperations(
            settings_manager=self.settings_manager,
            status_callback=self.update_status
        )

        self.auto_reload_timer = QTimer()
        self.auto_reload_timer.timeout.connect(self.on_auto_reload_timeout)
        self.auto_reload_enabled = False

        self.setWindowTitle(f"Qt Browser (controller) v{APP_VERSION}")
        self.resize(450, 900)

        # Initialize scripting engine...
        # ... (unchanged) ...

        # Ensure we actually get destroyed when the user closes the window
        self.setAttribute(Qt.WA_DeleteOnClose, True)

        # Some window flags cause a Hide instead of Close – watch both
        self.installEventFilter(self)

        # Fallback: if we're destroyed via other means, still close main
        self.destroyed.connect(lambda *_: self._safe_close_main())

        self.init_ui()

        # ⟵ restore controller window geometry/state
        self._restore_window_state()

        # ... existing debug / settings checks ...
        if self.settings_manager:
            self.load_settings()
            self.update_status("Ready")
        else:
            self.update_status("Warning: No settings manager")

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

    def eventFilter(self, obj, ev):
        if obj is self:
            et = ev.type()
            if et == QEvent.Close:
                # Normal close path
                try:
                    self._persist_window_state()
                except Exception:
                    pass
                self._safe_close_main()
            elif et == QEvent.Hide and not self.isVisible():
                # Tool-style windows often emit Hide instead of Close
                try:
                    self._persist_window_state()
                except Exception:
                    pass
                self._safe_close_main()
        return super().eventFilter(obj, ev)

    def _safe_close_main(self):
        """Best-effort: close the main BrowserWindow if it exists."""
        try:
            bw = getattr(self, "browser_window", None)
            if not bw:
                # Fallback: find it among top-level widgets
                from PySide6.QtWidgets import QApplication
                for w in QApplication.topLevelWidgets():
                    if w.__class__.__name__ == "BrowserWindow":
                        bw = w
                        break
            if bw and bw.isVisible():
                # Close on next tick to avoid re-entrancy
                QTimer.singleShot(0, bw.close)
        except Exception:
            pass

    def closeEvent(self, event):
        """Persist controller state and close the main browser window too."""
        try:
            if hasattr(self, "_persist_window_state"):
                self._persist_window_state()
        except Exception:
            pass

        # Stop timers safely
        try:
            if hasattr(self, "auto_reload_timer") and self.auto_reload_timer.isActive():
                self.auto_reload_timer.stop()
        except Exception:
            pass

        # Best-effort: close the BrowserWindow
        try:
            bw = self._resolve_main_window()
            if bw:
                # Avoid re-entrancy issues: close on next tick
                QTimer.singleShot(0, bw.close)
        except Exception:
            pass

        # Log and then finish closing the controller
        try:
            if self.settings_manager:
                self.settings_manager.log_system_event("controller", "Controller window closed")
        except Exception:
            pass

        super().closeEvent(event)

    def _resolve_main_window(self):
        """Return the live BrowserWindow instance, even if self.browser_window wasn't set."""
        # Prefer the direct reference if provided
        bw = getattr(self, "browser_window", None)
        if bw:
            return bw
        # Fallback: scan top-level widgets
        try:
            for w in QApplication.topLevelWidgets():
                # match by type name to avoid importing main_window here
                if w.__class__.__name__ == "BrowserWindow":
                    return w
        except Exception:
            pass
        return None

    # -----------------------------------------------------------------
    def init_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        # Title + status
        title = QLabel("<h1>Browser Controller</h1>")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        self.status_label = QLabel("Ready")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet(
            "QLabel { background:#1976d2; color:white; padding:10px; "
            "border:2px solid #1565c0; border-radius:5px; font-weight:bold; font-size:11pt; }"
        )
        layout.addWidget(self.status_label)

        # Tabs
        self.tab_widget = QTabWidget(self)
        layout.addWidget(self.tab_widget)

        # --- Tab 1: Controls ---
        controls_tab = QWidget(self)
        controls_layout = QVBoxLayout(controls_tab)
        controls_layout.setSpacing(10)

        controls_layout.addWidget(self.create_navigation_section())
        controls_layout.addWidget(self.create_quick_actions_section())
        controls_layout.addWidget(self.create_auto_reload_section())
        controls_layout.addWidget(self.create_screenshot_section())
        controls_layout.addWidget(self.create_log_section())
        controls_layout.addStretch(1)
        self.tab_widget.addTab(controls_tab, "Controls")

        # --- Tab 2: Scripting ---
        script_tab = QWidget(self)
        script_layout = QVBoxLayout(script_tab)
        script_layout.setSpacing(10)

        script_layout.addWidget(self.create_scripting_section())
        script_layout.addStretch(1)
        self.tab_widget.addTab(script_tab, "Scripting")

        # --- Tab 3: Settings ---
        settings_tab = QWidget(self)
        settings_layout = QVBoxLayout(settings_tab)
        settings_layout.setSpacing(10)

        settings_layout.addWidget(self.create_user_agent_section())
        settings_layout.addWidget(self.create_proxy_section())

        # new: path + "Edit settings…" button
        settings_layout.addWidget(self.create_app_settings_section())

        settings_layout.addStretch(1)
        self.tab_widget.addTab(settings_tab, "Settings")

        if not hasattr(self, "status_label"):
            self.status_label = QLabel("")
            self.status_label.setStyleSheet("color: gray;")
            layout.addWidget(self.status_label)

        if not self.statusBar():
            self.setStatusBar(QStatusBar(self))

    def create_navigation_section(self):
        """Create navigation controls"""
        group = QGroupBox("Navigation")
        layout = QVBoxLayout()
        
        # URL input
        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel("URL:"))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://example.com")
        self.url_input.returnPressed.connect(self.on_navigate)
        url_layout.addWidget(self.url_input)
        layout.addLayout(url_layout)
        
        # Navigate button
        nav_btn = QPushButton("Navigate")
        nav_btn.clicked.connect(self.on_navigate)
        nav_btn.setStyleSheet("""
            QPushButton { 
                background-color: #2196f3; 
                color: white; 
                padding: 10px; 
                font-weight: bold;
                font-size: 11pt;
            }
            QPushButton:hover {
                background-color: #1976d2;
            }
        """)
        layout.addWidget(nav_btn)
        
        group.setLayout(layout)
        return group
        
    def create_quick_actions_section(self):
        """Create quick action buttons"""
        group = QGroupBox("Quick Actions")
        layout = QVBoxLayout()
        
        # Row 1
        row1 = QHBoxLayout()
        
        reload_btn = QPushButton("🔄 Reload")
        reload_btn.clicked.connect(self.on_reload)
        reload_btn.setStyleSheet("QPushButton { background-color: #4caf50; color: white; padding: 10px; font-weight: bold; }")
        row1.addWidget(reload_btn)
        
        back_btn = QPushButton("⬅ Back")
        back_btn.clicked.connect(self.on_back)
        back_btn.setStyleSheet("QPushButton { background-color: #607d8b; color: white; padding: 10px; font-weight: bold; }")
        row1.addWidget(back_btn)
        
        layout.addLayout(row1)
        
        # Row 2
        row2 = QHBoxLayout()
        
        forward_btn = QPushButton("➡ Forward")
        forward_btn.clicked.connect(self.on_forward)
        forward_btn.setStyleSheet("QPushButton { background-color: #607d8b; color: white; padding: 10px; font-weight: bold; }")
        row2.addWidget(forward_btn)
        
        stop_btn = QPushButton("⏹ Stop")
        stop_btn.clicked.connect(self.on_stop)
        stop_btn.setStyleSheet("QPushButton { background-color: #f44336; color: white; padding: 10px; font-weight: bold; }")
        row2.addWidget(stop_btn)
        
        layout.addLayout(row2)
        
        # Row 3 - Screenshot and HTML
        row3 = QHBoxLayout()
        
        screenshot_btn = QPushButton("📷 Screenshot")
        screenshot_btn.clicked.connect(self.on_screenshot)
        screenshot_btn.setStyleSheet("QPushButton { background-color: #9c27b0; color: white; padding: 10px; font-weight: bold; }")
        row3.addWidget(screenshot_btn)
        
        html_btn = QPushButton("💾 Save HTML")
        html_btn.clicked.connect(self.on_save_html)
        html_btn.setStyleSheet("QPushButton { background-color: #ff9800; color: white; padding: 10px; font-weight: bold; }")
        row3.addWidget(html_btn)
        
        layout.addLayout(row3)
        
        # Row 4 - Full page screenshot
        full_screenshot_btn = QPushButton("📸 Full Page Screenshot")
        full_screenshot_btn.clicked.connect(self.on_full_screenshot)
        full_screenshot_btn.setStyleSheet("QPushButton { background-color: #673ab7; color: white; padding: 10px; font-weight: bold; }")
        layout.addWidget(full_screenshot_btn)
        
        group.setLayout(layout)
        return group

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

    def create_auto_reload_section(self):
        """Create auto-reload controls"""
        group = QGroupBox("Auto-Reload Timer")
        layout = QVBoxLayout()
        
        # Interval input
        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("Interval (seconds):"))
        self.interval_spin = QSpinBox()
        self.interval_spin.setMinimum(5)
        self.interval_spin.setMaximum(3600)
        self.interval_spin.setValue(30)
        interval_layout.addWidget(self.interval_spin)
        layout.addLayout(interval_layout)
        
        # Toggle button
        self.auto_reload_btn = QPushButton("▶ Start Auto-Reload")
        self.auto_reload_btn.clicked.connect(self.on_toggle_auto_reload)
        self.auto_reload_btn.setStyleSheet("QPushButton { background-color: #2196f3; color: white; padding: 10px; font-weight: bold; }")
        layout.addWidget(self.auto_reload_btn)
        
        # Screenshot on reload checkbox
        self.auto_reload_screenshot_cb = QCheckBox("Take screenshot after each reload")
        self.auto_reload_screenshot_cb.stateChanged.connect(self.on_auto_reload_screenshot_changed)
        layout.addWidget(self.auto_reload_screenshot_cb)
        
        group.setLayout(layout)
        return group       
        
    def create_scripting_section(self):
        """Create scripting controls"""
        group = QGroupBox("Script Automation")
        layout = QVBoxLayout()
        
        # Script editor
        self.script_editor = QTextEdit()
        self.script_editor.setPlaceholderText(
            "Enter commands (one per line):\n\n"
            "navigate https://example.com\n"
            "wait 2000\n"
            "reload\n"
            "wait 1000\n"
            "screenshot\n"
            "status Starting navigation tests\n"
            "back\n"
            "forward\n"
            "stop\n"
            "save_html\n"
            "screenshot_full\n"
            "set_user_agent Mozilla/5.0...\n"
            "enable_proxy\n"
            "disable_proxy\n"
            "auto_reload start 30\n"
            "auto_reload stop\n"
            "auto_reload_screenshot on\n"
            "auto_reload_screenshot off\n"
            "\n# Use # for comments\n"
            "# wait times are in milliseconds"
        )
        self.script_editor.setMaximumHeight(200)
        layout.addWidget(self.script_editor)
        
        # Progress bar
        progress_layout = QHBoxLayout()
        progress_layout.addWidget(QLabel("Progress:"))
        self.script_progress_label = QLabel("0 / 0")
        progress_layout.addWidget(self.script_progress_label)
        progress_layout.addStretch()
        layout.addLayout(progress_layout)
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        validate_btn = QPushButton("Validate Script")
        validate_btn.clicked.connect(self.on_validate_script)
        validate_btn.setStyleSheet("QPushButton { background-color: #607d8b; color: white; padding: 8px; }")
        button_layout.addWidget(validate_btn)
        
        self.script_start_btn = QPushButton("▶ Start Script")
        self.script_start_btn.clicked.connect(self.on_start_script)
        self.script_start_btn.setStyleSheet("QPushButton { background-color: #4caf50; color: white; padding: 8px; font-weight: bold; }")
        button_layout.addWidget(self.script_start_btn)
        
        self.script_pause_btn = QPushButton("⏸ Pause")
        self.script_pause_btn.clicked.connect(self.on_pause_script)
        self.script_pause_btn.setStyleSheet("QPushButton { background-color: #ff9800; color: white; padding: 8px; }")
        self.script_pause_btn.setEnabled(False)
        button_layout.addWidget(self.script_pause_btn)
        
        self.script_stop_btn = QPushButton("⏹ Stop")
        self.script_stop_btn.clicked.connect(self.on_stop_script)
        self.script_stop_btn.setStyleSheet("QPushButton { background-color: #f44336; color: white; padding: 8px; }")
        self.script_stop_btn.setEnabled(False)
        button_layout.addWidget(self.script_stop_btn)
        
        layout.addLayout(button_layout)
        
        # Save/Load buttons
        file_layout = QHBoxLayout()
        
        save_script_btn = QPushButton("💾 Save Script")
        save_script_btn.clicked.connect(self.on_save_script)
        file_layout.addWidget(save_script_btn)
        
        load_script_btn = QPushButton("📂 Load Script")
        load_script_btn.clicked.connect(self.on_load_script)
        file_layout.addWidget(load_script_btn)
        
        layout.addLayout(file_layout)
        
        group.setLayout(layout)
        return group
        
    def create_screenshot_section(self):
        """Create screenshot preview"""
        group = QGroupBox("Screenshot Preview")
        layout = QVBoxLayout()
        
        self.screenshot_label = QLabel("No screenshot captured")
        self.screenshot_label.setMinimumHeight(150)
        self.screenshot_label.setStyleSheet("QLabel { background-color: #f5f5f5; border: 1px solid #ddd; }")
        self.screenshot_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.screenshot_label)
        
        clear_btn = QPushButton("Clear Preview")
        clear_btn.clicked.connect(self.clear_screenshot)
        layout.addWidget(clear_btn)
        
        group.setLayout(layout)
        return group
        
    def create_log_section(self):
        """Create command log"""
        group = QGroupBox("Command Log")
        layout = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        layout.addWidget(self.log_text)
        
        clear_log_btn = QPushButton("Clear Log")
        clear_log_btn.clicked.connect(self.log_text.clear)
        layout.addWidget(clear_log_btn)
        
        group.setLayout(layout)
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
        
    def log_command(self, command):
        """Log a command with timestamp"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {command}")
        if self.settings_manager:
            self.settings_manager.log_system_event("controller", "Command", command)
        
    def update_status(self, text: str, *, timeout_ms: int = 4000, level: str = "INFO"):
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
        
    def check_browser_window(self):
        """Check if browser window is connected"""
        if not self.browser_window:
            self.update_status("ERROR: No browser window connected!")
            self.log_command("ERROR: Browser window not connected")
            return False
        return True
        
    def on_navigate(self):
        """Handle navigate button click"""
        url = self.url_input.text().strip()
        
        if not self.check_browser_window():
            return
            
        if not url:
            self.update_status("ERROR: No URL entered")
            return
        
        # Add http:// if no protocol specified
        if not url.startswith(('http://', 'https://', 'about:', 'file:')):
            url = 'https://' + url
            
        self.log_command(f"Navigate to: {url}")
        self.update_status(f"Navigating to: {url}")
        
        try:
            # Get the current tab directly
            current_tab = self.browser_window.tabs.currentWidget()
            if not current_tab:
                self.update_status("ERROR: No active tab found")
                self.log_command("ERROR: No active tab in browser")
                return
            
            # Get the webview from the tab
            if hasattr(current_tab, 'view'):
                view = current_tab.view
            elif hasattr(current_tab, 'browser'):
                view = current_tab.browser
            else:
                self.update_status("ERROR: Could not find browser view in tab")
                self.log_command("ERROR: Tab has no view or browser attribute")
                return
            
            # Navigate using QUrl
            from PySide6.QtCore import QUrl
            qurl = QUrl(url)
            if not qurl.isValid():
                self.update_status(f"ERROR: Invalid URL: {url}")
                self.log_command(f"ERROR: Invalid URL: {url}")
                return
            
            view.setUrl(qurl)
            self.update_status(f"Navigating to: {url}")
            self.log_command(f"Successfully sent navigation request to: {url}")
            
        except Exception as e:
            error_msg = f"Navigation failed: {e}"
            self.update_status(error_msg)
            self.log_command(error_msg)
            import traceback
            traceback.print_exc()
        
    def on_reload(self):
        """Handle reload button click"""
        if not self.check_browser_window():
            return
        self.log_command("Page reload")
        self.update_status("Reloading page...")
        
        try:
            current_tab = self.browser_window.tabs.currentWidget()
            if current_tab:
                view = getattr(current_tab, 'view', None) or getattr(current_tab, 'browser', None)
                if view:
                    view.reload()
                    self.log_command("Reload command sent successfully")
                else:
                    self.update_status("ERROR: No view found")
        except Exception as e:
            self.update_status(f"Reload failed: {e}")
        
    def on_back(self):
        """Handle back button click"""
        if not self.check_browser_window():
            return
        self.log_command("Navigate back")
        
        try:
            current_tab = self.browser_window.tabs.currentWidget()
            if current_tab:
                view = getattr(current_tab, 'view', None) or getattr(current_tab, 'browser', None)
                if view:
                    view.back()
                    self.log_command("Back command sent successfully")
        except Exception as e:
            self.update_status(f"Back failed: {e}")
        
    def on_forward(self):
        """Handle forward button click"""
        if not self.check_browser_window():
            return
        self.log_command("Navigate forward")
        
        try:
            current_tab = self.browser_window.tabs.currentWidget()
            if current_tab:
                view = getattr(current_tab, 'view', None) or getattr(current_tab, 'browser', None)
                if view:
                    view.forward()
                    self.log_command("Forward command sent successfully")
        except Exception as e:
            self.update_status(f"Forward failed: {e}")
        
    def on_stop(self):
        """Handle stop button click"""
        if not self.check_browser_window():
            return
        self.log_command("Stop loading")
        
        try:
            current_tab = self.browser_window.tabs.currentWidget()
            if current_tab:
                view = getattr(current_tab, 'view', None) or getattr(current_tab, 'browser', None)
                if view:
                    view.stop()
                    self.log_command("Stop command sent successfully")
        except Exception as e:
            self.update_status(f"Stop failed: {e}")
        
    def on_apply_user_agent(self):
        """Handle user agent application"""
        if not self.settings_manager:
            return
            
        ua = self.ua_input.text().strip()
        if ua:
            self.settings_manager.set("user_agent", ua)
            self.settings_manager.save()
            self.log_command(f"User agent set: {ua[:50]}...")
            self.update_status("User agent applied (restart may be required)")
        else:
            self.settings_manager.set("user_agent", "")
            self.settings_manager.save()
            self.log_command("User agent cleared (using default)")
            self.update_status("User agent cleared")
            
    def on_toggle_auto_reload(self):
        """Handle auto-reload toggle"""
        if not self.check_browser_window():
            return
            
        self.auto_reload_enabled = not self.auto_reload_enabled
        
        if self.auto_reload_enabled:
            interval = self.interval_spin.value()
            self.auto_reload_timer.start(interval * 1000)
            self.auto_reload_btn.setText("⏹ Stop Auto-Reload")
            self.auto_reload_btn.setStyleSheet("QPushButton { background-color: #f44336; color: white; padding: 10px; font-weight: bold; }")
            self.log_command(f"Auto-reload started (interval: {interval}s)")
            self.update_status(f"Auto-reload active ({interval}s)")
            self.interval_spin.setEnabled(False)
        else:
            self.auto_reload_timer.stop()
            self.auto_reload_btn.setText("▶ Start Auto-Reload")
            self.auto_reload_btn.setStyleSheet("QPushButton { background-color: #2196f3; color: white; padding: 10px; font-weight: bold; }")
            self.log_command("Auto-reload stopped")
            self.update_status("Auto-reload stopped")
            self.interval_spin.setEnabled(True)
            
    def on_auto_reload_timeout(self):
        """Handle auto-reload timer timeout"""
        self.log_command("Auto-reload triggered")
        self.on_reload()
        
        # Check if screenshot should be taken
        if self.auto_reload_screenshot_cb.isChecked():
            # Wait a bit for page to load before screenshot
            QTimer.singleShot(2000, self.on_screenshot)
    
    def on_auto_reload_screenshot_changed(self, state):
        """Handle auto-reload screenshot checkbox"""
        enabled = state == 2  # Qt.Checked
        if self.settings_manager:
            self.settings_manager.set("auto_reload_screenshot", enabled)
        self.log_command(f"Auto-reload screenshot: {'enabled' if enabled else 'disabled'}")

    # =========================================================================
    # REFACTORED: Screenshot and HTML methods now use browser_ops
    # =========================================================================
    
    def on_screenshot(self):
        """Handle screenshot button click"""
        if not self.check_browser_window():
            return
        
        self.log_command("Screenshot requested")
        self.update_status("Capturing screenshot...")
        
        current_tab = self.browser_window.tabs.currentWidget()
        if not current_tab:
            self.update_status("No active tab found")
            return
        
        # Use browser_ops for the actual screenshot
        self.browser_ops.save_screenshot(tab=current_tab)
        
        # Capture preview for the controller's preview widget
        try:
            view = getattr(current_tab, 'view', None) or getattr(current_tab, 'browser', None)
            if view:
                pixmap = view.grab()
                if not pixmap.isNull():
                    scaled_pixmap = pixmap.scaled(
                        self.screenshot_label.width() - 10,
                        self.screenshot_label.height() - 10,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation
                    )
                    self.screenshot_label.setPixmap(scaled_pixmap)
                    self.update_status("Screenshot captured")
        except Exception as e:
            self.log_command(f"Preview error: {e}")
    
    def on_full_screenshot(self):
        """Handle full page screenshot button click"""
        if not self.check_browser_window():
            return
        
        self.log_command("Full page screenshot requested")
        self.update_status("Capturing full page...")
        
        current_tab = self.browser_window.tabs.currentWidget()
        if not current_tab:
            self.update_status("No active tab found")
            return
        
        # Use browser_ops
        self.browser_ops.save_full_page_screenshot(tab=current_tab)
    
    def on_save_html(self):
        """Handle save HTML button click"""
        if not self.check_browser_window():
            return
        
        self.log_command("Save HTML requested")
        self.update_status("Saving HTML...")
        
        current_tab = self.browser_window.tabs.currentWidget()
        if not current_tab:
            self.update_status("No active tab found")
            return
        
        # Use browser_ops
        self.browser_ops.save_html(tab=current_tab)
    
    def clear_screenshot(self):
        """Clear screenshot preview"""
        self.screenshot_label.clear()
        self.screenshot_label.setText("No screenshot captured")
        self.log_command("Screenshot preview cleared")

    # =========================================================================
    # Script handling methods (unchanged - keeping for reference)
    # =========================================================================
    
    def on_validate_script(self):
        """Validate script syntax"""
        script_text = self.script_editor.toPlainText()
        if not script_text.strip():
            self.update_status("No script to validate")
            return
        
        # Note: ScriptValidator needs to be imported if this functionality is used
        # is_valid, errors = ScriptValidator.validate(script_text)
        # For now, just show a placeholder
        self.update_status("Script validation not yet implemented")
        self.log_command("Script validation requested")
            
    def on_start_script(self):
        """Start script execution"""
        script_text = self.script_editor.toPlainText()
        if not script_text.strip():
            self.update_status("No script to execute")
            return
        
        # Placeholder - implement with your script engine
        self.update_status("Script execution not yet implemented")
        self.log_command("Script execution requested")
        
    def on_pause_script(self):
        """Pause/resume script execution"""
        # Placeholder - implement with your script engine
        self.update_status("Script pause/resume not yet implemented")
        self.log_command("Script pause requested")
            
    def on_stop_script(self):
        """Stop script execution"""
        # Placeholder - implement with your script engine
        self.update_status("Script stop not yet implemented")
        self.log_command("Script stop requested")
        
    def on_script_started(self):
        """Handle script started"""
        self.script_editor.setEnabled(False)
        self.script_start_btn.setEnabled(False)
        self.script_pause_btn.setEnabled(True)
        self.script_stop_btn.setEnabled(True)
        self.update_status("Script running...")
        
    def on_script_finished(self):
        """Handle script finished"""
        self.script_editor.setEnabled(True)
        self.script_start_btn.setEnabled(True)
        self.script_pause_btn.setEnabled(False)
        self.script_stop_btn.setEnabled(False)
        self.script_pause_btn.setText("⏸ Pause")
        self.update_status("Script finished")
        self.script_progress_label.setText("Complete")
        
    def on_script_command_executed(self, command):
        """Handle script command executed"""
        # Already logged by script engine
        pass
        
    def on_script_error(self, error):
        """Handle script error"""
        self.update_status(f"Script error: {error}")
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.warning(self, "Script Error", error)
        
    def on_script_progress(self, current, total):
        """Update script progress"""
        self.script_progress_label.setText(f"{current} / {total}")
        # Update pause button text based on state if script engine available
        # if self.script_engine.is_paused:
        #     self.script_pause_btn.setText("▶ Resume")
        # else:
        #     self.script_pause_btn.setText("⏸ Pause")
            
    def on_save_script(self):
        """Save script to file"""
        from PySide6.QtWidgets import QFileDialog
        
        if not self.settings_manager:
            return
            
        scripts_dir = self.settings_manager.config_dir / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save Script",
            str(scripts_dir / "script.txt"),
            "Script Files (*.txt);;All Files (*.*)"
        )
        
        if filename:
            try:
                script_text = self.script_editor.toPlainText()
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(script_text)
                self.update_status(f"Script saved: {filename}")
                self.log_command(f"Script saved to: {filename}")
            except Exception as e:
                self.update_status(f"Failed to save script: {e}")
                
    def on_load_script(self):
        """Load script from file"""
        from PySide6.QtWidgets import QFileDialog
        
        if not self.settings_manager:
            return
            
        scripts_dir = self.settings_manager.config_dir / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Load Script",
            str(scripts_dir),
            "Script Files (*.txt);;All Files (*.*)"
        )
        
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    script_text = f.read()
                self.script_editor.setPlainText(script_text)
                self.update_status(f"Script loaded: {filename}")
                self.log_command(f"Script loaded from: {filename}")
            except Exception as e:
                self.update_status(f"Failed to load script: {e}")

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
        v = QVBoxLayout(group)

        # full path to settings.json
        self.settings_path_label = QLabel()
        self.settings_path_label.setWordWrap(True)
        self.settings_path_label.setStyleSheet("color: gray; font-size: 10px;")
        v.addWidget(self.settings_path_label)

        row = QHBoxLayout()
        edit_btn = QPushButton("Edit settings…")
        edit_btn.clicked.connect(self.on_edit_settings)
        row.addWidget(edit_btn)
        row.addStretch(1)
        v.addLayout(row)

        # fill path
        try:
            p = self.settings_manager.settings_path
            self.settings_path_label.setText(f"settings.json: {str(p.resolve())}")
        except Exception:
            self.settings_path_label.setText("settings.json: (unknown)")

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
        """Open the Settings dialog; refresh UI and path label on save."""
        try:
            if not getattr(self, "settings_manager", None):
                # Fallback so the dialog can still open even if launched standalone
                from .settings import SettingsManager
                self.settings_manager = SettingsManager()

            dlg = SettingsDialog(self, self.settings_manager)
            if dlg.exec():
                # Settings saved – refresh fields and the displayed path
                if hasattr(self, "load_settings"):
                    self.load_settings()
                self._refresh_settings_path_label()
                if hasattr(self, "update_status"):
                    self.update_status("Settings saved.")
            else:
                if hasattr(self, "update_status"):
                    self.update_status("Settings unchanged.")
        except Exception as e:
            if hasattr(self, "update_status"):
                self.update_status(f"Failed to open settings dialog: {e}")