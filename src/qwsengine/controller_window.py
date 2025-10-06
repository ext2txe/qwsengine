# qwsengine/controller_window.py
"""
Standalone controller window for QWSEngine browser.
Can be launched separately to control an existing browser instance.
"""

from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QSpinBox, QGroupBox, QTextEdit, QCheckBox
)
from PySide6.QtCore import QTimer, Qt, QUrl
from PySide6.QtGui import QPixmap

from .app_info import APP_VERSION
from .controller_script import ControllerScript, ScriptValidator


class BrowserControllerWindow(QMainWindow):
    """
    Standalone controller window for browser commands.
    Communicates with BrowserWindow instance to control browser tabs.
    """
    
    def __init__(self, browser_window=None, parent=None):
        super().__init__(parent)
        self.browser_window = browser_window
        self.settings_manager = browser_window.settings_manager if browser_window else None
        
        self.auto_reload_timer = QTimer()
        self.auto_reload_timer.timeout.connect(self.on_auto_reload_timeout)
        self.auto_reload_enabled = False
        
        self.setWindowTitle(f"Qt Browser (controller) v{APP_VERSION}")
        self.resize(450, 900)
        
        # Initialize scripting engine
        self.script_engine = ControllerScript(self)
        self.script_engine.command_executed.connect(self.on_script_command_executed)
        self.script_engine.script_error.connect(self.on_script_error)
        self.script_engine.script_started.connect(self.on_script_started)
        self.script_engine.script_finished.connect(self.on_script_finished)
        self.script_engine.progress_update.connect(self.on_script_progress)
        
        self.init_ui()
        
        # Debug: Log connection status
        if self.browser_window:
            print(f"DEBUG: Controller connected to browser window: {self.browser_window}")
            print(f"DEBUG: Settings manager: {self.settings_manager}")
        else:
            print("DEBUG: Controller created WITHOUT browser window")
            
        if self.settings_manager:
            self.load_settings()
            self.update_status("Ready")
        else:
            self.update_status("Warning: No settings manager")
        
    def set_browser_window(self, browser_window):
        """Connect to a browser window instance"""
        self.browser_window = browser_window
        self.settings_manager = browser_window.settings_manager
        self.load_settings()
        self.log_command("Connected to browser window")
        
    def init_ui(self):
        """Initialize the user interface"""
        central = QWidget()
        self.setCentralWidget(central)
        
        layout = QVBoxLayout(central)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Title
        title = QLabel("<h1>Browser Controller</h1>")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Status display
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("""
            QLabel {
                background-color: #1976d2;
                color: white;
                padding: 10px;
                border: 2px solid #1565c0;
                border-radius: 5px;
                font-weight: bold;
                font-size: 11pt;
            }
        """)
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)
        
        # Create tab widget
        from PySide6.QtWidgets import QTabWidget
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # Tab 1: Controls
        controls_tab = QWidget()
        controls_layout = QVBoxLayout(controls_tab)
        controls_layout.setSpacing(10)
        
        nav_group = self.create_navigation_section()
        controls_layout.addWidget(nav_group)
        
        actions_group = self.create_quick_actions_section()
        controls_layout.addWidget(actions_group)
        
        reload_group = self.create_auto_reload_section()
        controls_layout.addWidget(reload_group)
        
        screenshot_group = self.create_screenshot_section()
        controls_layout.addWidget(screenshot_group)
        
        log_group = self.create_log_section()
        controls_layout.addWidget(log_group)
        
        controls_layout.addStretch()
        self.tab_widget.addTab(controls_tab, "Controls")
        
        # Tab 2: Scripting
        script_tab = QWidget()
        script_layout = QVBoxLayout(script_tab)
        script_layout.setSpacing(10)
        
        script_group = self.create_scripting_section()
        script_layout.addWidget(script_group)
        
        script_layout.addStretch()
        self.tab_widget.addTab(script_tab, "Scripting")
        
        # Tab 3: Settings
        settings_tab = QWidget()
        settings_layout = QVBoxLayout(settings_tab)
        settings_layout.setSpacing(10)
        
        ua_group = self.create_user_agent_section()
        settings_layout.addWidget(ua_group)
        
        proxy_group = self.create_proxy_section()
        settings_layout.addWidget(proxy_group)
        
        settings_layout.addStretch()
        self.tab_widget.addTab(settings_tab, "Settings")
        
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
        """Create user agent controls"""
        group = QGroupBox("User Agent")
        layout = QVBoxLayout()
        
        # User agent input
        self.ua_input = QLineEdit()
        self.ua_input.setPlaceholderText("Custom User Agent (leave empty for default)")
        layout.addWidget(self.ua_input)
        
        # Apply button
        ua_btn = QPushButton("Apply User Agent")
        ua_btn.clicked.connect(self.on_apply_user_agent)
        ua_btn.setStyleSheet("QPushButton { background-color: #3f51b5; color: white; padding: 8px; }")
        layout.addWidget(ua_btn)
        
        group.setLayout(layout)
        return group
        
    def create_proxy_section(self):
        """Create proxy controls"""
        group = QGroupBox("Proxy Settings")
        layout = QVBoxLayout()
        
        # Proxy enabled checkbox
        self.proxy_enabled_cb = QCheckBox("Enable Proxy")
        self.proxy_enabled_cb.stateChanged.connect(self.on_proxy_enabled_changed)
        layout.addWidget(self.proxy_enabled_cb)
        
        # Proxy host
        host_layout = QHBoxLayout()
        host_layout.addWidget(QLabel("Host:"))
        self.proxy_host_input = QLineEdit()
        self.proxy_host_input.setPlaceholderText("proxy.example.com")
        host_layout.addWidget(self.proxy_host_input)
        layout.addLayout(host_layout)
        
        # Proxy port
        port_layout = QHBoxLayout()
        port_layout.addWidget(QLabel("Port:"))
        self.proxy_port_input = QSpinBox()
        self.proxy_port_input.setRange(1, 65535)
        self.proxy_port_input.setValue(8080)
        port_layout.addWidget(self.proxy_port_input)
        layout.addLayout(port_layout)
        
        # Proxy type
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Type:"))
        self.proxy_type_input = QLineEdit()
        self.proxy_type_input.setPlaceholderText("http, https, socks5")
        self.proxy_type_input.setText("http")
        type_layout.addWidget(self.proxy_type_input)
        layout.addLayout(type_layout)
        
        # Apply button
        apply_proxy_btn = QPushButton("Apply Proxy Settings")
        apply_proxy_btn.clicked.connect(self.on_apply_proxy)
        apply_proxy_btn.setStyleSheet("QPushButton { background-color: #ff5722; color: white; padding: 8px; font-weight: bold; }")
        layout.addWidget(apply_proxy_btn)
        
        # Status
        self.proxy_status = QLabel("Status: Not configured")
        self.proxy_status.setStyleSheet("QLabel { padding: 5px; font-style: italic; }")
        layout.addWidget(self.proxy_status)
        
        group.setLayout(layout)
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
        
    def load_settings(self):
        """Load settings from settings manager"""
        if not self.settings_manager:
            return
            
        try:
            # Load proxy settings
            proxy_enabled = self.settings_manager.get("proxy_enabled", False)
            self.proxy_enabled_cb.setChecked(proxy_enabled)
            
            proxy_host = self.settings_manager.get("proxy_host", "")
            self.proxy_host_input.setText(proxy_host)
            
            proxy_port = self.settings_manager.get("proxy_port", 8080)
            self.proxy_port_input.setValue(proxy_port)
            
            proxy_type = self.settings_manager.get("proxy_type", "http")
            self.proxy_type_input.setText(proxy_type)
            
            # Load user agent
            user_agent = self.settings_manager.get("user_agent", "")
            self.ua_input.setText(user_agent)
            
            self.log_command("Settings loaded from configuration")
        except Exception as e:
            self.log_command(f"Error loading settings: {e}")
        
    def log_command(self, command):
        """Log a command with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {command}")
        if self.settings_manager:
            self.settings_manager.log_system_event("controller", "Command", command)
        
    def update_status(self, message):
        """Update status label"""
        self.status_label.setText(message)
        
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
        
    def on_proxy_enabled_changed(self, state):
        """Handle proxy enabled checkbox"""
        if not self.settings_manager:
            return
        enabled = state == 2  # Qt.Checked
        self.settings_manager.set("proxy_enabled", enabled)
        self.proxy_status.setText(f"Status: {'Enabled' if enabled else 'Disabled'}")
        
    def on_apply_proxy(self):
        """Handle proxy settings application"""
        if not self.settings_manager:
            return
            
        enabled = self.proxy_enabled_cb.isChecked()
        host = self.proxy_host_input.text().strip()
        port = self.proxy_port_input.value()
        proxy_type = self.proxy_type_input.text().strip()
        
        if enabled and not host:
            self.update_status("ERROR: Proxy host required")
            return
            
        # Save to settings
        self.settings_manager.set("proxy_enabled", enabled)
        self.settings_manager.set("proxy_host", host)
        self.settings_manager.set("proxy_port", port)
        self.settings_manager.set("proxy_type", proxy_type)
        self.settings_manager.save()
        
        if enabled:
            self.log_command(f"Proxy configured: {proxy_type}://{host}:{port}")
            self.proxy_status.setText(f"Status: Active ({proxy_type}://{host}:{port})")
            self.update_status("Proxy settings applied (restart may be required)")
        else:
            self.log_command("Proxy disabled")
            self.proxy_status.setText("Status: Disabled")
            self.update_status("Proxy disabled")
            
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
    # Script handling methods
    # =========================================================================
    
    def on_validate_script(self):
        """Validate script syntax"""
        script_text = self.script_editor.toPlainText()
        if not script_text.strip():
            self.update_status("No script to validate")
            return
            
        is_valid, errors = ScriptValidator.validate(script_text)
        
        if is_valid:
            line_count = self.script_engine.load_script(script_text)
            self.update_status(f"✓ Script valid ({line_count} commands)")
            self.log_command(f"Script validated: {line_count} commands")
        else:
            error_msg = "Script validation errors:\n" + "\n".join(errors)
            self.update_status("✗ Script has errors")
            self.log_command("Script validation failed")
            
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Script Validation", error_msg)
            
    def on_start_script(self):
        """Start script execution"""
        script_text = self.script_editor.toPlainText()
        if not script_text.strip():
            self.update_status("No script to execute")
            return
            
        # Validate first
        is_valid, errors = ScriptValidator.validate(script_text)
        if not is_valid:
            error_msg = "Script has errors:\n" + "\n".join(errors[:5])
            if len(errors) > 5:
                error_msg += f"\n... and {len(errors) - 5} more errors"
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Script Errors", error_msg)
            return
            
        # Load and start
        line_count = self.script_engine.load_script(script_text)
        self.update_status(f"Starting script ({line_count} commands)...")
        self.script_engine.start()
        
    def on_pause_script(self):
        """Pause/resume script execution"""
        if self.script_engine.is_paused:
            self.script_engine.resume()
        else:
            self.script_engine.pause()
            
    def on_stop_script(self):
        """Stop script execution"""
        self.script_engine.stop()
        
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
        if self.script_engine.is_paused:
            self.script_pause_btn.setText("▶ Resume")
        else:
            self.script_pause_btn.setText("⏸ Pause")
            
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
        
    def on_screenshot(self):
        """Handle screenshot button click"""
        if not self.check_browser_window():
            return
            
        self.log_command("Screenshot requested")
        self.update_status("Capturing screenshot...")
        self.browser_window.save_current_tab_screenshot()
        
        # Capture preview
        try:
            current = self.browser_window.tabs.currentWidget()
            if current and hasattr(current, 'view'):
                pixmap = current.view.grab()
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
        self.browser_window.save_full_page_screenshot()
        
    def on_save_html(self):
        """Handle save HTML button click"""
        if not self.check_browser_window():
            return
            
        self.log_command("Save HTML requested")
        self.update_status("Saving HTML...")
        self.browser_window.save_current_tab_html()
        
    def clear_screenshot(self):
        """Clear screenshot preview"""
        self.screenshot_label.clear()
        self.screenshot_label.setText("No screenshot captured")
        self.log_command("Screenshot preview cleared")
        
    def closeEvent(self, event):
        """Handle window close"""
        if self.auto_reload_timer.isActive():
            self.auto_reload_timer.stop()
        if self.settings_manager:
            self.settings_manager.log_system_event("controller", "Controller window closed")
        super().closeEvent(event)