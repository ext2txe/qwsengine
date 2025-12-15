# qwsengine/ui/browser_controller_window.py
from __future__ import annotations

# Qt
from PySide6.QtCore import QTimer, Qt, QSettings, QByteArray, QCoreApplication, QEvent
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QGroupBox, QTabWidget,
    QSpinBox, QCheckBox, QStatusBar, QTextEdit, QComboBox, QFileDialog
)

# WebEngine
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings

# Project
try:
    from qwsengine.app_info import APP_VERSION, APP_NAME
except Exception:
    APP_VERSION = "dev"
    APP_NAME = "QWSEngine"

from .settings_dialog import SettingsDialog
from qwsengine.core.settings import SettingsManager
from .browser_operations import BrowserOperations  # NEW IMPORT

class BrowserControllerWindow(QMainWindow):
    def __init__(self, browser_window=None, parent=None, settings_manager=None):
        super().__init__(parent)
        self.browser_window = browser_window
        
        # Allow passing settings_manager directly
        if settings_manager:
            self.settings_manager = settings_manager
        elif browser_window and hasattr(browser_window, 'settings_manager'):
            self.settings_manager = browser_window.settings_manager
        else:
            self.settings_manager = None

        # NEW: Initialize browser operations utility
        self.browser_ops = BrowserOperations(
            settings_manager=self.settings_manager,
            status_callback=self.update_status,
            command_callback=self.log_command
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
                url1 = bw.settings_manager.get('start_url')
                url2 = self.settings_manager.get('start_url')
                if url1 != url2:
                    bw.settings_manager.set('start_url',url2 )
                # Avoid re-entrancy issues: close on next tick
                QTimer.singleShot(0, bw.close)
                QApplication.processEvents()
                url2 = self.settings_manager.get('start_url')

        except Exception:
            pass

        # Log closure
        try:
            if self.settings_manager:
                _save_settings()
                self.settings_manager.log_system_event("controller", "Controller window closed")
            else:
                pass
        except Exception:
            pass

        super().closeEvent(event)

    def _save_settings(self):

        urlInSettings = self.settings_manager['start_url']
        urlInForm = self.start_url_input.text
        if (urlInForm != urlInSettings):
            # we need to fix something
            pass
        pass

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
        
    def _get_current_tab(self):
        """Get the currently active tab from the main window"""
        main_window = self._resolve_main_window()
        if main_window and hasattr(main_window, 'tab_manager'):
            return main_window.tab_manager.get_current_tab()
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

        # Tab control
        self.tab_widget = QTabWidget(self)
        layout.addWidget(self.tab_widget)

        # --- Tab 1: Controls ---
        controls_tab = QWidget(self)
        controls_layout = QVBoxLayout(controls_tab)
        controls_layout.setSpacing(10)

        controls_layout.addWidget(self.create_browser_launch_settings())
        controls_layout.addWidget(self.create_navigation_section())
        controls_layout.addWidget(self.create_quick_actions_section())
        controls_layout.addWidget(self.create_auto_reload_section())
        controls_layout.addWidget(self.create_screenshot_section())
        controls_layout.addWidget(self.create_save_page_images_section())
        controls_layout.addWidget(self.create_open_devtools_section())
        controls_layout.addWidget(self.create_log_section())
        controls_layout.addStretch(1)
        self.tab_widget.addTab(controls_tab, "Controls")

        # --- Tab 2: Scripting ---
        script_tab = QWidget(self)
        script_layout = QVBoxLayout(script_tab)
        script_layout.setSpacing(10)

        script_layout.addWidget(self.create_script_file_section())
        script_layout.addWidget(self.create_scripting_section())
        script_layout.addStretch(1)
        self.tab_widget.addTab(script_tab, "Scripting")

        # --- Tab 3: Settings ---
        settings_tab = QWidget(self)
        settings_layout = QVBoxLayout(settings_tab)
        settings_layout.setSpacing(10)

        settings_layout.addWidget(self.create_user_agent_section())
        settings_layout.addWidget(self.create_proxy_section())
        settings_layout.addWidget(self.create_app_settings_section())
        settings_layout.addStretch(1)
        self.tab_widget.addTab(settings_tab, "Settings")

        # Status bar
        self.statusBar().showMessage("Ready")

    def launch_browser(self):
        """Launch a new browser window."""
        if getattr(self, "browser_window", None):
            if self.browser_window.isVisible():
                self.update_status("Browser window already open")
                self.browser_window.activateWindow()  # Bring to front
                return
            # Otherwise it exists but is hidden; show it again
            self.browser_window.show()
            self.update_status("Browser window restored")
            return

        # Get full module path to ensure proper imports
        from importlib import import_module

        BrowserWindow = None
        try:
            # Preferred: new UI location
            from qwsengine.ui.main_window import BrowserWindow
        except ImportError:
            try:
                # Backwards-compat: legacy location, if it still exists
                from qwsengine.main_window import BrowserWindow
            except ImportError:
                # Last resort: dynamic import from UI module
                mod = import_module("qwsengine.ui.main_window")
                BrowserWindow = getattr(mod, "BrowserWindow")

        try:
            # Create new browser window with our settings
            self.browser_window = BrowserWindow(settings_manager=self.settings_manager)
            self.browser_window.show()
            self.update_status("Browser window launched")

            # Start auto-reload timer if enabled
            self._update_auto_reload_state()

        except Exception as e:
            self.update_status(f"Failed to launch browser: {e}", level="ERROR")
            self.log_command(f"Launch browser error: {e}")


    def create_browser_launch_settings(self):
        """Create browser launch settings"""
        group = QGroupBox("Browser")
        layout = QVBoxLayout()
        
        # Launch button
        launch_btn = QPushButton("Launch Browser")
        launch_btn.clicked.connect(self.launch_browser)
        launch_btn.setStyleSheet("""
            QPushButton { 
                background-color: #4caf50; 
                color: white; 
                padding: 10px; 
                font-weight: bold;
                font-size: 12pt;
            }
            QPushButton:hover {
                background-color: #388e3c;
            }
        """)
        layout.addWidget(launch_btn)
        
        # Auto-launch setting
        auto_layout = QHBoxLayout()
        self.auto_launch_cb = QCheckBox("Auto-launch browser")
        self.auto_launch_cb.setChecked(True)  # Default to true
        self.auto_launch_cb.stateChanged.connect(self._on_auto_launch_changed)
        auto_layout.addWidget(self.auto_launch_cb)
        layout.addLayout(auto_layout)
        
        # Start URL
        start_url_layout = QHBoxLayout()
        start_url_layout.addWidget(QLabel("Start URL:"))
        self.start_url_input = QLineEdit()
        if self.settings_manager:
            self.start_url_input.setText(self.settings_manager.get("starturl", "https://www.google.com"))
        else:
            self.start_url_input.setText("https://www.google.com")
        self.start_url_input.returnPressed.connect(self._on_start_url_changed)
        start_url_layout.addWidget(self.start_url_input)
        layout.addLayout(start_url_layout)
        
        group.setLayout(layout)
        return group
    
    def _on_auto_launch_changed(self, state):
        if not self.settings_manager:
            return
            
        enabled = (state == Qt.Checked)
        self.settings_manager.set("auto_launch_browser", enabled)
        self.settings_manager.save()
        self.update_status(f"Auto-launch browser {'enabled' if enabled else 'disabled'}")
    
    def _on_start_url_changed(self):
        if not self.settings_manager:
            return
            
        url = self.start_url_input.text().strip()
        self.settings_manager.set("start_url", url)
        # Fixed: Add save_settings call here
        self.settings_manager.save_settings()
        self.update_status(f"Start URL set to: {url}")
        # Add logging
        self.log_command(f"Start URL changed to: {url}")

    def on_open_dev_tools(self):
        """Open developer tools for current tab."""
        try:
            if not self.browser_window:
                return
                
            # Get current tab's browser view
            tab = self._get_current_tab()
            if tab and hasattr(tab, "view") and tab.view and hasattr(tab.view.page(), "triggerAction"):
                from PySide6.QtWebEngineCore import QWebEnginePage
                tab.view.page().triggerAction(QWebEnginePage.InspectElement)
                self.log_command("Open Developer Tools")
                
                self.update_status("Developer tools opened")
            else:
                self.update_status("Cannot open developer tools - no active tab", level="WARNING")
        except Exception as e:
            self.update_status(f"Developer tools failed: {e}", "ERROR")

    def on_extract_images(self):
        """Extract all images from the current page."""
        if self._resolve_main_window(): 
            current_tab = self._get_current_tab()
            if current_tab:
                self.browser_ops.extract_images(tab=current_tab)
                self.log_command("Extract images action executed")
            else:
                self.update_status("No active tab", level="WARNING")
        else:
            self.update_status("Browser window not available", level="ERROR")

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
        
        # Navigation buttons
        button_layout = QHBoxLayout()
        
        back_btn = QPushButton("◀ Back")
        back_btn.clicked.connect(self.on_back)
        button_layout.addWidget(back_btn)
        
        reload_btn = QPushButton("↻ Reload")
        reload_btn.clicked.connect(self.on_reload)
        button_layout.addWidget(reload_btn)
        
        forward_btn = QPushButton("▶ Forward")
        forward_btn.clicked.connect(self.on_forward)
        button_layout.addWidget(forward_btn)
        
        layout.addLayout(button_layout)
        
        group.setLayout(layout)
        return group

    def create_quick_actions_section(self):
        """Create quick actions"""
        group = QGroupBox("Quick Actions")
        layout = QVBoxLayout()
        
        # New Tab
        new_tab_btn = QPushButton("New Tab")
        new_tab_btn.clicked.connect(self.on_new_tab)
        layout.addWidget(new_tab_btn)
        
        # Save HTML button
        save_html_btn = QPushButton("Save HTML")
        save_html_btn.setToolTip("Save the current page's HTML content")
        save_html_btn.clicked.connect(self.on_save_html)
        layout.addWidget(save_html_btn)
        
        # Open Dev Tools
        dev_tools_btn = QPushButton("Open Developer Tools")
        dev_tools_btn.clicked.connect(self.on_open_dev_tools)
        layout.addWidget(dev_tools_btn)
        
        # Show/hide elements
        toggle_btn = QPushButton("Toggle Element")
        toggle_btn.clicked.connect(self.on_toggle_element)
        layout.addWidget(toggle_btn)
        
        group.setLayout(layout)
        return group

    def create_auto_reload_section(self):
        """Create auto reload section"""
        group = QGroupBox("Auto Reload")
        layout = QVBoxLayout()
        
        # Enable/disable
        enable_layout = QHBoxLayout()
        self.auto_reload_cb = QCheckBox("Enable Auto Reload")
        self.auto_reload_cb.stateChanged.connect(self.on_auto_reload_toggle)
        enable_layout.addWidget(self.auto_reload_cb)
        layout.addLayout(enable_layout)
        
        # Interval
        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("Interval (seconds):"))
        self.reload_interval = QSpinBox()
        self.reload_interval.setMinimum(1)
        self.reload_interval.setMaximum(3600)  # 1 hour max
        self.reload_interval.setValue(10)  # Default: 10 seconds
        self.reload_interval.valueChanged.connect(self.on_interval_changed)
        interval_layout.addWidget(self.reload_interval)
        layout.addLayout(interval_layout)
        
        # Status
        self.reload_status = QLabel("Auto reload: Disabled")
        layout.addWidget(self.reload_status)
        
        group.setLayout(layout)
        return group

    def create_screenshot_section(self):
        """Create screenshot controls"""
        group = QGroupBox("Screenshot")
        layout = QVBoxLayout()
        
        # Capture visible part
        visible_btn = QPushButton("Capture Visible Part")
        visible_btn.clicked.connect(self.on_capture_visible)
        layout.addWidget(visible_btn)
        
        # Capture full page
        full_page_btn = QPushButton("Capture Full Page")
        full_page_btn.clicked.connect(self.on_capture_full_page)
        layout.addWidget(full_page_btn)
        
        group.setLayout(layout)
        return group
    
    def create_save_page_images_section(self):
        """Create Extract Page Images"""
        group = QGroupBox("Extract Page Images")
        layout = QVBoxLayout()

        # create button
        saveimages_btn = QPushButton("Extract Images")
        saveimages_btn.clicked.connect(self.on_extract_images)
        layout.addWidget(saveimages_btn)

        group.setLayout(layout)
        return group   

    def create_open_devtools_section(self):
        """Create DevTools button"""
        group = QGroupBox("DevTools")
        layout = QVBoxLayout()

        # create button
        devtools_btn = QPushButton("Open DevTools window")
        devtools_btn.clicked.connect(self.on_open_dev_tools)
        layout.addWidget(devtools_btn)

        group.setLayout(layout)
        return group    

    def create_log_section(self):
        """Create log output section"""
        group = QGroupBox("Command Log")
        layout = QVBoxLayout()
        
        # Log output text area
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumHeight(120)
        layout.addWidget(self.log_output)
        
        group.setLayout(layout)
        return group
    
    def create_script_file_section(self):
        """Create script file management controls"""
        group = QGroupBox("Scripting")
        layout = QVBoxLayout()
        
        # Script file path selection
        file_label = QLabel("Script File:")
        layout.addWidget(file_label)
        
        file_layout = QHBoxLayout()
        self.script_file_path_label = QLabel("(No file selected)")
        self.script_file_path_label.setStyleSheet("color: gray; font-style: italic;")
        file_layout.addWidget(self.script_file_path_label)
        
        select_btn = QPushButton("Select")
        select_btn.setMaximumWidth(80)
        select_btn.clicked.connect(self.on_select_script_file)
        file_layout.addWidget(select_btn)
        layout.addLayout(file_layout)
        
        # Script content display/edit
        content_label = QLabel("Script Content:")
        layout.addWidget(content_label)
        
        self.script_file_content = QTextEdit()
        self.script_file_content.setPlaceholderText("Select a script file to view or edit its content")
        self.script_file_content.setMinimumHeight(180)
        layout.addWidget(self.script_file_content)
        
        # Save button
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.on_save_script_content)
        layout.addWidget(save_btn)
        
        group.setLayout(layout)
        return group
    
    def create_scripting_section(self):
        """Create scripting controls"""
        group = QGroupBox("JavaScript Execution")
        layout = QVBoxLayout()
        
        # Script input
        script_label = QLabel("JavaScript:")
        layout.addWidget(script_label)
        
        self.script_input = QTextEdit()
        self.script_input.setPlaceholderText("Enter JavaScript to execute in the current tab")
        self.script_input.setMinimumHeight(200)
        layout.addWidget(self.script_input)
        
        # Execute button
        exec_layout = QHBoxLayout()
        exec_btn = QPushButton("Execute Script")
        exec_btn.clicked.connect(self.on_execute_script)
        exec_layout.addWidget(exec_btn)
        layout.addLayout(exec_layout)
        
        # Result display
        result_label = QLabel("Result:")
        layout.addWidget(result_label)
        
        self.script_result = QTextEdit()
        self.script_result.setReadOnly(True)
        self.script_result.setMinimumHeight(100)
        layout.addWidget(self.script_result)
        
        group.setLayout(layout)
        return group
    
    def create_user_agent_section(self):
        """Create user agent controls"""
        group = QGroupBox("User Agent")
        layout = QVBoxLayout()
        
        # User agent input
        ua_layout = QVBoxLayout()
        ua_label = QLabel("Custom User Agent:")
        ua_layout.addWidget(ua_label)
        
        self.user_agent_input = QLineEdit()
        self.user_agent_input.setPlaceholderText("Enter custom User-Agent string")
        ua_layout.addWidget(self.user_agent_input)
        layout.addLayout(ua_layout)
        
        # Apply button
        apply_btn = QPushButton("Apply User Agent")
        apply_btn.clicked.connect(self.on_apply_user_agent)
        layout.addWidget(apply_btn)
        
        # Reset button
        reset_btn = QPushButton("Reset to Default")
        reset_btn.clicked.connect(self.on_reset_user_agent)
        layout.addWidget(reset_btn)
        
        # Preset dropdown
        preset_label = QLabel("Presets:")
        layout.addWidget(preset_label)
        
        self.ua_presets = QComboBox()
        self.ua_presets.addItem("Chrome Windows", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
        self.ua_presets.addItem("Firefox Windows", "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0")
        self.ua_presets.addItem("Safari macOS", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15")
        self.ua_presets.addItem("Edge Windows", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 Edg/91.0.864.59")
        self.ua_presets.addItem("Chrome Android", "Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36")
        self.ua_presets.addItem("iPhone", "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1")
        
        self.ua_presets.currentIndexChanged.connect(self.on_ua_preset_selected)
        layout.addWidget(self.ua_presets)
        
        self.ua_status = QLabel("Status: Using default")
        layout.addWidget(self.ua_status)
        
        group.setLayout(layout)
        return group
    
    def create_proxy_section(self):
        """Create proxy settings controls"""
        group = QGroupBox("Proxy Settings")
        layout = QVBoxLayout()
        
        # Enable proxy
        self.proxy_enabled_cb = QCheckBox("Enable Proxy")
        self.proxy_enabled_cb.stateChanged.connect(self.on_proxy_enabled_changed)
        layout.addWidget(self.proxy_enabled_cb)
        
        # Proxy type (http, socks, etc.)
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Type:"))
        self.proxy_type_input = QLineEdit()
        self.proxy_type_input.setText("http")
        self.proxy_type_input.setToolTip("Proxy type (http, socks5, etc.)")
        type_layout.addWidget(self.proxy_type_input)
        layout.addLayout(type_layout)
        
        # Host
        host_layout = QHBoxLayout()
        host_layout.addWidget(QLabel("Host:"))
        self.proxy_host_input = QLineEdit()
        self.proxy_host_input.setPlaceholderText("proxy.example.com")
        host_layout.addWidget(self.proxy_host_input)
        layout.addLayout(host_layout)
        
        # Port
        port_layout = QHBoxLayout()
        port_layout.addWidget(QLabel("Port:"))
        self.proxy_port_input = QSpinBox()
        self.proxy_port_input.setMinimum(1)
        self.proxy_port_input.setMaximum(65535)
        self.proxy_port_input.setValue(8080)
        port_layout.addWidget(self.proxy_port_input)
        layout.addLayout(port_layout)
        
        # Apply button
        apply_btn = QPushButton("Apply Proxy Settings")
        apply_btn.clicked.connect(self.on_apply_proxy)
        layout.addWidget(apply_btn)
        
        # Status
        self.proxy_status = QLabel("Status: Disabled")
        layout.addWidget(self.proxy_status)
        
        # Initially disable proxy inputs
        self._set_proxy_inputs_enabled(False)
        
        group.setLayout(layout)
        return group
    
    def create_app_settings_section(self):
        """Create app settings controls"""
        group = QGroupBox("App Settings")
        layout = QVBoxLayout()
        
        # Settings path
        self.settings_path_label = QLabel("settings.json: (unknown)")
        layout.addWidget(self.settings_path_label)
        
        # Edit settings button
        edit_settings_btn = QPushButton("Edit App Settings")
        edit_settings_btn.clicked.connect(self.on_edit_settings)
        layout.addWidget(edit_settings_btn)
        
        # Update path label
        self._refresh_settings_path_label()
        
        group.setLayout(layout)
        return group
    
    # --- Navigation actions --------------------------------------------------
    def on_navigate(self):
        """Navigate to URL in current tab."""
        if not self.browser_window:
            self.update_status("Browser window not available", level="WARNING")
            return
            
        url = self.url_input.text().strip()
        if not url:
            self.update_status("Please enter a URL", level="WARNING")
            return
            
        # Add http:// if no scheme
        if not url.startswith(("http://", "https://", "file://", "about:")):
            url = "https://" + url
        
        # Find current tab
        tab_manager = getattr(self.browser_window, "tab_manager", None)
        if not tab_manager:
            self.update_status("Tab manager not available", level="ERROR")
            return
            
        tab_manager.navigate_current(url)
        self.log_command(f"Navigate to: {url}")
    
    def on_back(self):
        """Navigate back in current tab."""
        if not self.browser_window:
            self.update_status("Browser window not available", level="WARNING")
            return
            
        self.browser_window.back()
        self.log_command("Back")
    
    def on_forward(self):
        """Navigate forward in current tab."""
        if not self.browser_window:
            self.update_status("Browser window not available", level="WARNING")
            return
            
        self.browser_window.forward()
        self.log_command("Forward")
    
    def on_reload(self):
        """Reload current tab."""
        if not self.browser_window:
            self.update_status("Browser window not available", level="WARNING")
            return
            
        self.browser_window.reload()
        self.log_command("Reload")
    
    def on_new_tab(self):
        """Create a new tab."""
        if not self.browser_window:
            self.update_status("Browser window not available", level="WARNING")
            return
            
        tab_manager = getattr(self.browser_window, "tab_manager", None)
        if not tab_manager:
            self.update_status("Tab manager not available", level="ERROR")
            return
            
        tab_manager.new_tab(switch=True)
        self.log_command("New tab")
        
    def on_extract_images(self):
        """Extract all images from the current page."""
        if self._resolve_main_window() and hasattr(self.browser_ops, 'extract_images'):
            current_tab = self._get_current_tab()
            if current_tab:
                self.browser_ops.extract_images(tab=current_tab)
                self.log_command("Extract images action executed")
            else:
                self.update_status("No active tab", level="WARNING")
        else:
            self.update_status("Image extraction unavailable", level="ERROR")

    def on_open_dev_tools(self):
        """Open developer tools for current tab."""
        try:
            if not self._resolve_main_window():
                self.update_status("Browser window not available", level="WARNING")
                return

            tab = self._get_current_tab()
            if not tab:
                self.update_status("No active tab available", level="WARNING")
                return

            view = getattr(tab, "view", None) or getattr(tab, "browser", None)
            if view is None:
                self.update_status("No browser view found on current tab", level="ERROR")
                return

            page = view.page()

            # Ensure devtools are enabled for the inspected page
            try:
                page.settings().setAttribute(QWebEngineSettings.WebAttribute.DeveloperExtrasEnabled, True)
            except Exception:
                pass

            # Create / reuse a dedicated DevTools window
            if not hasattr(self, "_devtools_window") or self._devtools_window is None:
                self._devtools_window = QMainWindow(self)
                self._devtools_window.setWindowTitle("DevTools")
                self._devtools_window.resize(1100, 700)

                self._devtools_view = QWebEngineView(self._devtools_window)
                self._devtools_window.setCentralWidget(self._devtools_view)

            # Match the inspected page profile (cookies/cache/etc.)
            try:
                profile = page.profile()
            except Exception:
                profile = QWebEngineProfile.defaultProfile()

            devtools_page = QWebEnginePage(profile, self._devtools_view)
            self._devtools_view.setPage(devtools_page)

            # Wire devtools page to the inspected page
            page.setDevToolsPage(self.devtools_page)

            self._devtools_window.show()
            self._devtools_window.raise_()
            self._devtools_window.activateWindow()

            self.log_command("DevTools opened")
            self.update_status("Developer tools opened", level="INFO")
        except Exception as e:
            self.update_status(f"Developer tools error: {e}", level="ERROR")
            
    def on_save_html(self):
        """Save the HTML of the current page"""
        if self._resolve_main_window() and hasattr(self.browser_ops, 'save_html'):
            current_tab = self._get_current_tab()
            if current_tab:
                self.browser_ops.save_html(tab=current_tab)
                self.update_status("Saving HTML content...")
            else:
                self.update_status("No active tab found", level="WARNING")
        else:
            self.update_status("Browser window not available", level="WARNING")
    
    def on_toggle_element(self):
        try:
            if not self.browser_window:
                return
                
            # Simple element toggle script
            script = """
            (function() {
                // Simple example - toggle visibility of first <div>
                var elements = document.getElementsByTagName('div');
                if (elements.length > 0) {
                    var el = elements[0];
                    if (el.style.display === 'none') {
                        el.style.display = '';
                    } else {
                        el.style.display = 'none';
                    }
                    return "Toggled element visibility: " + (el.style.display || "visible");
                } else {
                    return "No div elements found";
                }
            })();
            """
            
            # Get current tab's browser view
            tab = self.browser_window.tab_manager.get_current_tab()
            if tab and tab.view:
                tab.view.page().runJavaScript(script, self._handle_script_result)
                self.log_command("Toggle element visibility")
                self.update_status("Toggling element...")
            else:
                self.update_status("No active tab", level="WARNING")
                
        except Exception as e:
            self.update_status(f"Toggle element failed: {e}", level="ERROR")
    
    # --- Auto reload handling ------------------------------------------------
    def on_auto_reload_toggle(self, state):
        self.auto_reload_enabled = (state == Qt.Checked)
        self._update_auto_reload_state()
    
    def on_interval_changed(self, value):
        if self.auto_reload_enabled:
            # Update timer with new interval
            self._update_auto_reload_state()
    
    def _update_auto_reload_state(self):
        # Stop any existing timer
        if self.auto_reload_timer.isActive():
            self.auto_reload_timer.stop()
        
        if self.auto_reload_enabled:
            interval_ms = self.reload_interval.value() * 1000
            self.auto_reload_timer.start(interval_ms)
            self.reload_status.setText(f"Auto reload: Every {self.reload_interval.value()} seconds")
        else:
            self.reload_status.setText("Auto reload: Disabled")
    
    def on_auto_reload_timeout(self):
        """Handle auto-reload timer timeout."""
        if self.browser_window:
            # Only reload if window is available
            self.browser_window.reload()
            self.log_command(f"Auto reload (interval: {self.reload_interval.value()}s)")
    
    # --- Screenshot functions ------------------------------------------------
    def on_capture_visible(self):
        """Capture visible portion of page."""
        if not self.browser_window:
            self.update_status("Browser window not available", level="WARNING")
            return

        # Use browser_ops to handle screenshot
        current_tab = self._get_current_tab()
        if current_tab:
            self.browser_ops.save_screenshot(tab=current_tab)
            self.update_status("Capturing visible area...")
            self.log_command("Capture visible screenshot")
        else:
            self.update_status("No active tab", level="WARNING")
    
    def on_capture_full_page(self):
        """Capture full scrollable page."""
        if not self.browser_window:
            self.update_status("Browser window not available", level="WARNING")
            return
            
        # Use browser_ops to handle full page screenshot
        current_tab = self._get_current_tab()
        if current_tab:
            self.browser_ops.save_full_page_screenshot(tab=current_tab)
            self.update_status("Capturing full page (may take a moment)...")
            self.log_command("Capture full page screenshot")
        else:
            self.update_status("No active tab", level="WARNING")
    
    # --- Scripting functions -------------------------------------------------
    def on_execute_script(self):
        """Execute JavaScript in current tab."""
        if not self.browser_window:
            self.update_status("Browser window not available", level="WARNING")
            return
            
        script = self.script_input.toPlainText().strip()
        if not script:
            self.update_status("Please enter a JavaScript script", level="WARNING")
            return
            
        # Get current tab's browser view
        tab = self.browser_window.tab_manager.get_current_tab()
        if tab and tab.view:
            # Execute the script
            tab.view.page().runJavaScript(script, self._handle_script_result)
            self.log_command("Execute script")
            self.update_status("Executing script...")
        else:
            self.update_status("No active tab", level="WARNING")
    
    def _handle_script_result(self, result):
        """Handle JavaScript execution result."""
        # Convert result to string
        if result is None:
            result_text = "undefined (or no return value)"
        elif isinstance(result, (dict, list)):
            import json
            try:
                result_text = json.dumps(result, indent=2)
            except Exception:
                result_text = str(result)
        else:
            result_text = str(result)
            
        # Update result display
        self.script_result.setPlainText(result_text)
        self.update_status("Script executed")
        
    def on_select_script_file(self):
        """Open file dialog to select script file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Script File",
            "",
            "JavaScript Files (*.js);;Text Files (*.txt);;All Files (*)"
        )
        
        if file_path:
            try:
                # Save the file path to settings
                if self.settings_manager:
                    self.settings_manager.set("script_file_path", file_path, persist=True)
                    self.update_status(f"Script file selected: {file_path}")
                else:
                    self.update_status("Settings manager not available", level="WARNING")
                    return
                
                # Load and display the file content
                self._load_script_file_content(file_path)
                
            except Exception as e:
                self.update_status(f"Error selecting script file: {e}", level="ERROR")
    
    def _load_script_file_content(self, file_path):
        """Load script file content into the editor."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Update UI
            self.script_file_content.setPlainText(content)
            self.script_file_path_label.setText(file_path)
            self.script_file_path_label.setStyleSheet("color: white; font-style: normal;")
            self.update_status(f"Loaded: {file_path}")
            
        except FileNotFoundError:
            self.update_status(f"Script file not found: {file_path}", level="ERROR")
            self.script_file_path_label.setText(f"(File not found: {file_path})")
            self.script_file_path_label.setStyleSheet("color: red; font-style: italic;")
        except Exception as e:
            self.update_status(f"Failed to read script file: {e}", level="ERROR")
    
    def on_save_script_content(self):
        """Save script content to file, backing up the original with timestamp."""
        file_path = None
        
        # Get file path from label
        label_text = self.script_file_path_label.text()
        if label_text and not label_text.startswith("("):
            file_path = label_text
        
        if not file_path:
            self.update_status("No script file selected. Use 'Select' to choose a file.", level="WARNING")
            return
        
        try:
            # Check if file exists - if so, back it up with timestamp
            from pathlib import Path
            import shutil
            from datetime import datetime
            
            file_path_obj = Path(file_path)
            
            if file_path_obj.exists():
                # Create backup with timestamp
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = file_path_obj.with_stem(f"{file_path_obj.stem}_backup_{timestamp}")
                shutil.copy2(file_path, backup_path)
                self.update_status(f"Backed up original to: {backup_path}")
            
            # Write new content
            content = self.script_file_content.toPlainText()
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            self.update_status(f"Script saved: {file_path}")
            self.log_command(f"Saved script to {file_path}")
            
        except Exception as e:
            self.update_status(f"Failed to save script file: {e}", level="ERROR")
        
    # --- User Agent functions ------------------------------------------------
    def on_apply_user_agent(self):
        """Apply custom user agent."""
        if not self.settings_manager:
            self.update_status("Settings manager not available", level="WARNING")
            return
            
        ua = self.user_agent_input.text().strip()
        if not ua:
            self.update_status("Please enter a User-Agent string", level="WARNING")
            return
            
        # Save to settings
        self.settings_manager.set("user_agent", ua)
        self.settings_manager.save()
        
        # Apply to WebEngine (usually requires restart)
        self.update_status("User Agent set (restart browser to apply)")
        self.ua_status.setText("Status: Custom UA set (restart needed)")
        self.log_command(f"Set User-Agent: {ua}")
    
    def on_reset_user_agent(self):
        """Reset user agent to default."""
        if not self.settings_manager:
            self.update_status("Settings manager not available", level="WARNING")
            return
            
        # Remove from settings
        self.settings_manager.set("user_agent", "")
        self.settings_manager.save()
        
        # Clear input
        self.user_agent_input.clear()
        
        self.update_status("User Agent reset to default (restart browser to apply)")
        self.ua_status.setText("Status: Using default")
        self.log_command("Reset User-Agent to default")
    
    def on_ua_preset_selected(self, index):
        """Handle User-Agent preset selection."""
        if index < 0:
            return
            
        ua = self.ua_presets.currentData()
        if ua:
            self.user_agent_input.setText(ua)
    
    # --- Proxy functions -----------------------------------------------------
    def _set_proxy_inputs_enabled(self, enabled: bool):
        """Enable/disable proxy input fields."""
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

    # --- Helpers ------------------------------------------------------------------
    
    def load_settings(self):
        """Load settings and update UI."""
        try:
            # Load proxy settings
            if self.settings_manager:
                mode = self.settings_manager.get("proxy_mode", "none")
                self.proxy_enabled_cb.setChecked(mode == "manual")
                
                self.proxy_type_input.setText(self.settings_manager.get("proxy_type", "http"))
                self.proxy_host_input.setText(self.settings_manager.get("proxy_host", ""))
                self.proxy_port_input.setValue(self.settings_manager.get("proxy_port", 8080))
                
                # Update UI state
                self._set_proxy_inputs_enabled(mode == "manual")
                if mode == "manual":
                    host = self.settings_manager.get("proxy_host", "")
                    port = self.settings_manager.get("proxy_port", 0)
                    ptype = self.settings_manager.get("proxy_type", "http")
                    if host and port:
                        self.proxy_status.setText(f"Status: Active ({ptype}://{host}:{port})")
                    else:
                        self.proxy_status.setText("Status: Incomplete configuration")
                else:
                    self.proxy_status.setText(f"Status: {mode.capitalize()}")
                
                # Load user agent
                ua = self.settings_manager.get("user_agent", "")
                self.user_agent_input.setText(ua)

            # Load start URL
            if self.settings_manager:
                start_url = self.settings_manager.get("start_url", "https://www.google.com")
                self.start_url_input.setText(start_url)
            
            # Load script file path and content
            if self.settings_manager:
                script_file_path = self.settings_manager.get("script_file_path", "")
                if script_file_path:
                    self._load_script_file_content(script_file_path)
                
        except Exception as e:
            self.update_status(f"Failed to load settings: {e}", "WARNING")

    def update_status(self, message, level="INFO", timeout_ms=5000):
        """Update status label and log."""
        # Update status label
        if level == "ERROR":
            self.status_label.setStyleSheet(
                "QLabel { background:#d32f2f; color:white; padding:10px; "
                "border:2px solid #b71c1c; border-radius:5px; font-weight:bold; font-size:11pt; }"
            )
        elif level == "WARNING":
            self.status_label.setStyleSheet(
                "QLabel { background:#ff9800; color:white; padding:10px; "
                "border:2px solid #f57c00; border-radius:5px; font-weight:bold; font-size:11pt; }"
            )
        else:  # INFO
            self.status_label.setStyleSheet(
                "QLabel { background:#1976d2; color:white; padding:10px; "
                "border:2px solid #1565c0; border-radius:5px; font-weight:bold; font-size:11pt; }"
            )
            
        self.status_label.setText(message)
        
        # Update status bar if exists
        if self.statusBar():
            self.statusBar().showMessage(message, timeout_ms)
            
        # Log to console for debugging
        prefix = f"[{level}]"
        print(f"{prefix} {message}")
    
    def log_command(self, message):
        """Add entry to command log."""
        if hasattr(self, "log_output") and self.log_output:
            # Add timestamp
            from datetime import datetime
            timestamp = datetime.now().strftime("%H:%M:%S")
            
            # Add to log
            self.log_output.append(f"[{timestamp}] {message}")

    def _refresh_settings_path_label(self):
        try:
            if self.settings_manager and getattr(self.settings_manager, "settings_path", None):
                p = self.settings_manager.settings_path  # Path
            else:
                # Fallback to show where it would be
                from qwsengine.core.settings import SettingsManager
                p = SettingsManager().settings_path
            self.settings_path_label.setText(f"settings.json: {str(p.resolve())}")
        except Exception:
            self.settings_path_label.setText("settings.json: (unknown)")

    def on_edit_settings(self):

        """Open the Settings dialog; refresh UI and path label on save."""
        try:
            if not getattr(self, "settings_manager", None):
                # Fallback so the dialog can still open even if launched standalone
                from qwsengine.core.settings import SettingsManager
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
                self.update_status(f"Failed to open settings dialog: {e}")            # qwsengine/browser_controller_window.py
