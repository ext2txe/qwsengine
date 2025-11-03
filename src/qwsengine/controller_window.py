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
                # Avoid re-entrancy issues: close on next tick
                QTimer.singleShot(0, bw.close)
        except Exception:
            pass

        # Log closure
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

        # Add browser launch settings (NEW)
        settings_layout.addWidget(self.create_browser_launch_settings())

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

    # NEW METHOD: Launch browser functionality
    def launch_browser(self):
        """Launch a browser window if not already connected."""
        if self.browser_window and hasattr(self.browser_window, 'isVisible') and self.browser_window.isVisible():
            # Already have a browser window, just activate it
            self.browser_window.activateWindow()
            self.update_status("Browser window activated")
            return
        
        try:
            from .main_window import BrowserWindow
            
            # Create browser window
            self.browser_window = BrowserWindow(settings_manager=self.settings_manager)
            
            # Show the window
            self.browser_window.show()
            
            # Update status
            self.update_status("Browser launched and connected")
        except Exception as e:
            self.update_status(f"Failed to launch browser: {e}", "ERROR")

    # NEW METHOD: Browser launch settings
    def create_browser_launch_settings(self):
        """Create settings for browser auto-launch."""
        group = QGroupBox("Browser Launch Settings")
        layout = QVBoxLayout(group)
        
        # Auto-launch checkbox
        self.auto_launch_cb = QCheckBox("Launch browser automatically on startup")
        
        # Set initial state based on setting
        if self.settings_manager:
            auto_launch = self.settings_manager.get("auto_launch_browser", True)
            self.auto_launch_cb.setChecked(auto_launch)
        
        # Connect to save settings when changed
        self.auto_launch_cb.stateChanged.connect(self._on_auto_launch_changed)
        
        layout.addWidget(self.auto_launch_cb)
        
        # Startup URL
        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel("Startup URL:"))
        
        self.start_url_input = QLineEdit()
        
        # Set initial URL from settings
        if self.settings_manager:
            start_url = self.settings_manager.get("start_url", "")
            self.start_url_input.setText(start_url)
        
        # Connect to save settings when changed
        self.start_url_input.editingFinished.connect(self._on_start_url_changed)
        
        url_layout.addWidget(self.start_url_input)
        layout.addLayout(url_layout)
        
        # Launch browser now button
        launch_btn = QPushButton("Launch Browser")
        launch_btn.clicked.connect(self.launch_browser)
        layout.addWidget(launch_btn)
        
        return group

    # NEW METHOD: Handler for auto-launch setting
    def _on_auto_launch_changed(self, state):
        """Save auto-launch setting when changed."""
        if not self.settings_manager:
            return
        
        auto_launch = (state == Qt.Checked)
        self.settings_manager.set("auto_launch_browser", auto_launch)
        
        # Save settings if possible
        if hasattr(self.settings_manager, "save"):
            self.settings_manager.save()
        
        self.update_status(f"Browser auto-launch {'enabled' if auto_launch else 'disabled'}")

    # NEW METHOD: Handler for start URL setting
    def _on_start_url_changed(self):
        """Save startup URL when changed."""
        if not self.settings_manager:
            return
        
        start_url = self.start_url_input.text().strip()
        self.settings_manager.set("start_url", start_url)
        
        # Save settings if possible
        if hasattr(self.settings_manager, "save"):
            self.settings_manager.save()
        
        self.update_status("Startup URL saved")

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
        toggle_element_btn = QPushButton("Toggle Element Visibility")
        toggle_element_btn.clicked.connect(self.on_toggle_element)
        layout.addWidget(toggle_element_btn)

        group.setLayout(layout)
        return group

    def create_auto_reload_section(self):
        """Create auto-reload controls"""
        group = QGroupBox("Auto-Reload")
        layout = QVBoxLayout()
        
        # Enable checkbox
        self.auto_reload_cb = QCheckBox("Enable auto-reload")
        self.auto_reload_cb.stateChanged.connect(self.on_auto_reload_changed)
        layout.addWidget(self.auto_reload_cb)
        
        # Interval slider
        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("Interval:"))
        
        self.reload_interval = QSpinBox()
        self.reload_interval.setRange(1, 3600)
        self.reload_interval.setValue(15)
        self.reload_interval.setSuffix(" seconds")
        self.reload_interval.valueChanged.connect(self.on_interval_changed)
        
        interval_layout.addWidget(self.reload_interval)
        layout.addLayout(interval_layout)
        
        # Start/stop button
        self.reload_btn = QPushButton("Start Auto-Reload")
        self.reload_btn.clicked.connect(self.on_toggle_auto_reload)
        layout.addWidget(self.reload_btn)
        
        group.setLayout(layout)
        return group

    def create_screenshot_section(self):
        """Create screenshot controls"""
        group = QGroupBox("Screenshots")
        layout = QVBoxLayout()
        
        # Regular screenshot
        screenshot_btn = QPushButton("Take Screenshot")
        screenshot_btn.clicked.connect(self.on_take_screenshot)
        layout.addWidget(screenshot_btn)
        
        # Full page screenshot
        full_page_btn = QPushButton("Full Page Screenshot")
        full_page_btn.clicked.connect(self.on_take_full_page_screenshot)
        layout.addWidget(full_page_btn)
        
        group.setLayout(layout)
        return group

    def create_log_section(self):
        """Create log output area"""
        group = QGroupBox("Command Log")
        layout = QVBoxLayout()
        
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumHeight(100)
        layout.addWidget(self.log_output)
        
        group.setLayout(layout)
        return group

    def create_scripting_section(self):
        """Create scripting UI"""
        group = QGroupBox("JavaScript Execution")
        layout = QVBoxLayout()
        
        # JavaScript editor
        layout.addWidget(QLabel("Enter JavaScript code:"))
        self.script_editor = QTextEdit()
        self.script_editor.setPlaceholderText("console.log('Hello world!');")
        layout.addWidget(self.script_editor)
        
        # Execute button
        button_layout = QHBoxLayout()
        
        run_btn = QPushButton("Run Script")
        run_btn.clicked.connect(self.on_run_script)
        button_layout.addWidget(run_btn)
        
        save_btn = QPushButton("Save Script")
        save_btn.clicked.connect(self.on_save_script)
        button_layout.addWidget(save_btn)
        
        load_btn = QPushButton("Load Script")
        load_btn.clicked.connect(self.on_load_script)
        button_layout.addWidget(load_btn)
        
        layout.addLayout(button_layout)
        
        group.setLayout(layout)
        return group

    def create_user_agent_section(self):
        """Create user agent controls"""
        group = QGroupBox("User Agent")
        layout = QVBoxLayout()
        
        # User agent input
        layout.addWidget(QLabel("Custom User Agent:"))
        self.user_agent_input = QLineEdit()
        self.user_agent_input.setPlaceholderText("Mozilla/5.0 (Windows NT 10.0; Win64; x64)...")
        layout.addWidget(self.user_agent_input)
        
        # Apply button
        apply_btn = QPushButton("Apply User Agent")
        apply_btn.clicked.connect(self.on_apply_user_agent)
        layout.addWidget(apply_btn)
        
        # Common presets
        layout.addWidget(QLabel("Presets:"))
        presets_layout = QHBoxLayout()
        
        chrome_btn = QPushButton("Chrome")
        chrome_btn.clicked.connect(lambda: self.on_preset_user_agent("chrome"))
        presets_layout.addWidget(chrome_btn)
        
        firefox_btn = QPushButton("Firefox")
        firefox_btn.clicked.connect(lambda: self.on_preset_user_agent("firefox"))
        presets_layout.addWidget(firefox_btn)
        
        mobile_btn = QPushButton("Mobile")
        mobile_btn.clicked.connect(lambda: self.on_preset_user_agent("mobile"))
        presets_layout.addWidget(mobile_btn)
        
        layout.addLayout(presets_layout)
        
        group.setLayout(layout)
        return group

    def create_proxy_section(self):
        """Create proxy settings"""
        group = QGroupBox("Proxy Settings")
        layout = QVBoxLayout(group)
        
        # Enabled checkbox
        self.proxy_enabled_cb = QCheckBox("Use Proxy")
        self.proxy_enabled_cb.stateChanged.connect(self.on_proxy_enabled_changed)
        layout.addWidget(self.proxy_enabled_cb)
        
        # Proxy details
        details_layout = QHBoxLayout()
        
        self.proxy_type_input = QLineEdit("http")
        details_layout.addWidget(self.proxy_type_input)
        details_layout.addWidget(QLabel("://"))
        
        self.proxy_host_input = QLineEdit()
        self.proxy_host_input.setPlaceholderText("proxy.example.com")
        details_layout.addWidget(self.proxy_host_input, 1)  # Stretch
        
        details_layout.addWidget(QLabel(":"))
        
        self.proxy_port_input = QSpinBox()
        self.proxy_port_input.setRange(1, 65535)
        self.proxy_port_input.setValue(8080)
        details_layout.addWidget(self.proxy_port_input)
        
        layout.addLayout(details_layout)
        
        # Apply button
        apply_btn = QPushButton("Apply Proxy Settings")
        apply_btn.clicked.connect(self.on_apply_proxy)
        layout.addWidget(apply_btn)
        
        # Status label
        self.proxy_status = QLabel("Status: Not configured")
        layout.addWidget(self.proxy_status)
        
        return group

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

    # --- Navigation actions --------------------------------------------------------
    
    def on_navigate(self):
        """Navigate to URL in current tab."""
        try:
            if not self.browser_window:
                self.update_status("No browser window connected", "WARNING")
                return
                
            url = self.url_input.text().strip()
            if not url:
                return
                
            self.browser_window.tab_manager.navigate_current(url)
            self.log_command(f"Navigating to: {url}")
            
        except Exception as e:
            self.update_status(f"Navigation failed: {e}", "ERROR")

    def on_back(self):
        try:
            if not self.browser_window:
                return
                
            # Get current tab's browser view
            tab = self.browser_window.tab_manager.get_current_tab()
            if tab and tab.view:
                tab.view.back()
                self.log_command("Back")
                
        except Exception as e:
            self.update_status(f"Back failed: {e}", "ERROR")

    def on_forward(self):
        try:
            if not self.browser_window:
                return
                
            # Get current tab's browser view
            tab = self.browser_window.tab_manager.get_current_tab()
            if tab and tab.view:
                tab.view.forward()
                self.log_command("Forward")
                
        except Exception as e:
            self.update_status(f"Forward failed: {e}", "ERROR")

    def on_reload(self):
        try:
            if not self.browser_window:
                return
                
            # Get current tab's browser view
            tab = self.browser_window.tab_manager.get_current_tab()
            if tab and tab.view:
                tab.view.reload()
                self.log_command("Reload")
                
        except Exception as e:
            self.update_status(f"Reload failed: {e}", "ERROR")
    
    # --- Quick actions -------------------------------------------------------------
    
    def on_new_tab(self):
        try:
            if not self.browser_window:
                return
                
            # Create new tab
            self.browser_window.tab_manager.new_tab()
            self.log_command("New Tab")
                
        except Exception as e:
            self.update_status(f"New tab failed: {e}", "ERROR")

    def on_open_dev_tools(self):
        try:
            if not self.browser_window:
                return
                
            # Get current tab's browser view
            tab = self.browser_window.tab_manager.get_current_tab()
            if tab and tab.view and hasattr(tab.view.page(), "triggerAction"):
                from PySide6.QtWebEngineCore import QWebEnginePage
                tab.view.page().triggerAction(QWebEnginePage.InspectElement)
                self.update_status("Developer tools opened")
            else:
                self.update_status("Cannot open developer tools - no active tab", level="WARNING")
        except Exception as e:
            self.update_status(f"Failed to open dev tools: {e}", level="ERROR")

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
            tab.view.page().triggerAction(QWebEnginePage.WebAction.InspectElement)
            self.log_command("Open Developer Tools")
        except Exception as e:
            self.update_status(f"Developer tools failed: {e}", "ERROR")

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
                    return "Toggled element visibility";
                } else {
                    return "No elements found to toggle";
                }
            })();
            """
            
            # Execute on current tab
            tab = self.browser_window.tab_manager.get_current_tab()
            if tab and tab.view and tab.view.page():
                tab.view.page().runJavaScript(script, 0, self._handle_script_result)
                self.log_command("Toggle Element")
                
        except Exception as e:
            self.update_status(f"Toggle failed: {e}", "ERROR")
    
    # --- Auto-reload ---------------------------------------------------------------
    
    def on_auto_reload_changed(self, state):
        """Handle auto-reload checkbox change."""
        self.auto_reload_enabled = (state == Qt.Checked)
        
        if not self.auto_reload_enabled and self.auto_reload_timer.isActive():
            self.auto_reload_timer.stop()
            self.reload_btn.setText("Start Auto-Reload")
            
    def on_interval_changed(self, value):
        """Handle interval change."""
        if self.auto_reload_timer.isActive():
            self.auto_reload_timer.setInterval(value * 1000)
            
    def on_toggle_auto_reload(self):
        """Start/stop auto-reload."""
        if self.auto_reload_timer.isActive():
            self.auto_reload_timer.stop()
            self.reload_btn.setText("Start Auto-Reload")
            self.log_command("Auto-reload stopped")
        else:
            if not self.auto_reload_enabled:
                self.auto_reload_cb.setChecked(True)
                
            interval = self.reload_interval.value() * 1000  # convert to ms
            self.auto_reload_timer.setInterval(interval)
            self.auto_reload_timer.start()
            self.reload_btn.setText("Stop Auto-Reload")
            self.log_command(f"Auto-reload started ({self.reload_interval.value()} seconds)")
            
    def on_auto_reload_timeout(self):
        """Handle auto-reload timer timeout."""
        try:
            if not self.browser_window:
                return
                
            # Get current tab's browser view
            tab = self.browser_window.tab_manager.get_current_tab()
            if tab and tab.view:
                tab.view.reload()
                self.log_command("Auto-reload triggered")
                
        except Exception as e:
            self.update_status(f"Auto-reload failed: {e}", "ERROR")
    
    # --- Screenshots ---------------------------------------------------------------
    
    def on_take_screenshot(self):
        """Take a screenshot of the current tab."""
        try:
            if not self.browser_window:
                return
                
            current = self.browser_window.tab_manager.get_current_tab()
            if not current:
                self.update_status("No active tab", "WARNING")
                return
                
            # Use the browser_ops helper if available
            if hasattr(self, 'browser_ops') and hasattr(self.browser_ops, 'save_screenshot'):
                self.browser_ops.save_screenshot(tab=current)
                self.log_command("Screenshot captured")
            else:
                # Fallback to browser window method
                if hasattr(self.browser_window, 'save_current_tab_screenshot'):
                    self.browser_window.save_current_tab_screenshot()
                    self.log_command("Screenshot captured")
                
        except Exception as e:
            self.update_status(f"Screenshot failed: {e}", "ERROR")

    def on_take_full_page_screenshot(self):
        """Take a full-page screenshot."""
        try:
            if not self.browser_window:
                return
                
            current = self.browser_window.tab_manager.get_current_tab()
            if not current:
                self.update_status("No active tab", "WARNING")
                return
                
            # Use the browser_ops helper if available
            if hasattr(self, 'browser_ops') and hasattr(self.browser_ops, 'save_full_page_screenshot'):
                self.browser_ops.save_full_page_screenshot(tab=current)
                self.log_command("Full-page screenshot started")
            else:
                # Fallback to browser window method
                if hasattr(self.browser_window, 'save_full_page_screenshot'):
                    self.browser_window.save_full_page_screenshot()
                    self.log_command("Full-page screenshot started")
                
        except Exception as e:
            self.update_status(f"Full-page screenshot failed: {e}", "ERROR")
    
    # --- Scripting -----------------------------------------------------------------
    
    def on_run_script(self):
        """Execute JavaScript in the current tab."""
        try:
            if not self.browser_window:
                self.update_status("No browser window connected", "WARNING")
                return
                
            # Get script content
            script = self.script_editor.toPlainText().strip()
            if not script:
                self.update_status("No script to run", "WARNING")
                return
                
            # Get current tab
            tab = self.browser_window.tab_manager.get_current_tab()
            if not tab or not tab.view or not tab.view.page():
                self.update_status("No active tab", "WARNING")
                return
                
            # Execute script
            tab.view.page().runJavaScript(script, 0, self._handle_script_result)
            self.log_command("Script executed")
                
        except Exception as e:
            self.update_status(f"Script execution failed: {e}", "ERROR")
            
    def _handle_script_result(self, result):
        """Handle JavaScript execution result."""
        if result is not None:
            self.update_status(f"Script result: {str(result)}")
            
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
    
    # --- User Agent ----------------------------------------------------------------
    
    def on_preset_user_agent(self, preset):
        """Set a preset user agent."""
        if preset == "chrome":
            ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        elif preset == "firefox":
            ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0"
        elif preset == "mobile":
            ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1"
        else:
            return
            
        self.user_agent_input.setText(ua)
        self.on_apply_user_agent()
    
    def on_apply_user_agent(self):
        """Apply the custom user agent."""
        try:
            if not self.settings_manager:
                self.update_status("No settings manager available", "WARNING")
                return
                
            user_agent = self.user_agent_input.text().strip()
            
            # Save to settings
            self.settings_manager.set("user_agent", user_agent)
            
            # Apply to browser
            if hasattr(self.settings_manager, "web_profile"):
                self.settings_manager.web_profile.setHttpUserAgent(user_agent)
                
            self.update_status(f"User agent {'updated' if user_agent else 'reset to default'}")
            self.log_command(f"User agent {'updated' if user_agent else 'reset to default'}")
                
        except Exception as e:
            self.update_status(f"Failed to apply user agent: {e}", "ERROR")
    
    # --- Proxy Settings ------------------------------------------------------------
    
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
                self.update_status(f"Failed to open settings dialog: {e}")
