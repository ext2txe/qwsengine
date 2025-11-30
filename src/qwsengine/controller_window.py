# qwsengine/controller_window.py
from __future__ import annotations

# Qt
from PySide6.QtCore import QTimer, Qt, QSettings, QByteArray, QCoreApplication, QEvent
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QGroupBox, QTabWidget,
    QSpinBox, QCheckBox, QStatusBar, QTextEdit, QComboBox
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
        try:
            # Try direct import
            from ..qwsengine.main_window import BrowserWindow
        except (ImportError, ValueError):
            try:
                # Try absolute import
                from qwsengine.main_window import BrowserWindow
            except ImportError:
                # Last resort: dynamic import
                mod = import_module("qwsengine.main_window")
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
            if not self.browser_window:
                return
                    
            # Get current tab's browser view
            tab = self.browser_window.tab_manager.get_current_tab()
            if not tab or not hasattr(tab, "view") or not tab.view:
                self.update_status("No active tab available", level="WARNING")
                return
                
            # Try different methods to open DevTools
            view = tab.view
            page = view.page()
            
            # # Method 1: Using triggerAction (most common)
            # if hasattr(page, "triggerAction"):
            #     from PySide6.QtWebEngineCore import QWebEnginePage
            #     # Try with WebInspector action first (newer versions)
            #     try:
            #         page.triggerAction(QWebEnginePage.WebInspector)
            #         self.log_command("Open DevTools (WebInspector)")
            #         self.update_status("Developer tools opened")
            #         return
            #     except Exception:
            #         # Fall back to InspectElement
            #         try:
            #             page.triggerAction(QWebEnginePage.InspectElement)
            #             self.log_command("Open DevTools (InspectElement)")
            #             self.update_status("Developer tools opened")
            #             return
            #         except Exception:
            #             pass
            
            # Method 2: Using settings to enable devtools and F12 key simulation
            try:
                # Enable inspector
                settings = page.settings()
                settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
                settings.setAttribute(QWebEngineSettings.WebAttribute.DeveloperExtrasEnabled, True)
                
                # Try to simulate F12 key
                from PySide6.QtCore import Qt
                from PySide6.QtGui import QKeyEvent
                key_press = QKeyEvent(QEvent.KeyPress, Qt.Key_F12, Qt.NoModifier)
                key_release = QKeyEvent(QEvent.KeyRelease, Qt.Key_F12, Qt.NoModifier)
                
                # Send key events
                QApplication.sendEvent(view, key_press)
                QApplication.sendEvent(view, key_release)
                
                self.log_command("Open DevTools (F12)")
                self.update_status("Developer tools opened (F12)")
                return
            except Exception:
                pass
            
            # Method 3: JavaScript method (last resort)
            try:
                # Try to open DevTools using JavaScript
                script = """
                if (window.open) {
                    // This only works if DevTools is not already open
                    window.open('about:blank', '_blank', 'nodeIntegration=1,contextIsolation=0');
                    console.log('Attempting to open dev tools via JavaScript');
                }
                """
                page.runJavaScript(script)
                self.log_command("Open DevTools (JavaScript)")
                self.update_status("Attempted to open developer tools via JavaScript")
                return
            except Exception:
                pass
            
            self.update_status("Failed to open developer tools. Try using F12 or right-click -> Inspect", level="WARNING")
        except Exception as e:
            self.update_status(f"Developer tools error: {e}", "ERROR")
            
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
                self.update_status(f"Failed to open settings dialog: {e}")            # qwsengine/controller_window.py
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