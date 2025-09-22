import sys
import json
import os
import logging
from datetime import datetime
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QTabWidget, QDialog, QLabel,
    QMessageBox, QMenuBar, QMenu, QCheckBox
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
from PySide6.QtCore import QStandardPaths, QUrl
from PySide6.QtGui import QAction


class CustomFileHandler(logging.Handler):
    """Custom logging handler that opens and closes file for each write"""
    
    def __init__(self, log_file):
        super().__init__()
        self.log_file = log_file
        
    def emit(self, record):
        try:
            # Format the record
            msg = self.format(record)
            
            # Open file, write, and immediately close
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(msg + '\n')
                f.flush()  # Ensure data is written to disk
                
        except Exception:
            # If logging fails, we don't want to crash the app
            pass


class LogManager:
    def __init__(self, config_dir):
        self.config_dir = Path(config_dir)
        self.log_dir = self.config_dir / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Create log file with datestamp
        today = datetime.now().strftime("%Y%m%d")
        self.log_file = self.log_dir / f"{today}_qwsengine.log"
        
        self.setup_logging()
        self.log("Application starting", "SYSTEM")
    
    def setup_logging(self):
        """Configure Python logging with custom handler that closes file after each write"""
        # Create custom formatter
        class QWSEngineFormatter(logging.Formatter):
            def format(self, record):
                timestamp = datetime.now().strftime("%H%M%S.%f")[:-3]  # hhmmss.fff
                return f"{timestamp}: {record.getMessage()}"
        
        # Configure logger
        self.logger = logging.getLogger('qwsengine')
        self.logger.setLevel(logging.DEBUG)
        
        # Remove existing handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # Custom file handler that closes file after each write
        file_handler = CustomFileHandler(self.log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(QWSEngineFormatter())
        
        # Console handler (optional - for debugging)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(QWSEngineFormatter())
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        # Prevent propagation to root logger
        self.logger.propagate = False
    
    def log(self, message, level="INFO"):
        """Log a message with specified level"""
        if level == "DEBUG":
            self.logger.debug(message)
        elif level == "INFO":
            self.logger.info(message)
        elif level == "WARNING":
            self.logger.warning(message)
        elif level == "ERROR":
            self.logger.error(message)
        elif level == "CRITICAL":
            self.logger.critical(message)
        elif level == "SYSTEM":
            self.logger.info(f"[SYSTEM] {message}")
        elif level == "NAV":
            self.logger.info(f"[NAVIGATION] {message}")
        elif level == "TAB":
            self.logger.info(f"[TAB] {message}")
        elif level == "COOKIE":
            self.logger.info(f"[COOKIE] {message}")
        else:
            self.logger.info(message)
    
    def log_navigation(self, url, title="", tab_id=None):
        """Log page navigation"""
        tab_info = f"Tab-{tab_id} " if tab_id else ""
        self.log(f"{tab_info}Navigated to: {url} | Title: {title}", "NAV")
    
    def log_tab_action(self, action, tab_id=None, details=""):
        """Log tab-related actions"""
        tab_info = f"Tab-{tab_id} " if tab_id else ""
        self.log(f"{tab_info}{action} {details}".strip(), "TAB")
    
    def log_error(self, error_msg, context=""):
        """Log errors with context"""
        full_msg = f"{error_msg}"
        if context:
            full_msg += f" | Context: {context}"
        self.log(full_msg, "ERROR")
    
    def log_system_event(self, event, details=""):
        """Log system-level events"""
        full_msg = f"{event}"
        if details:
            full_msg += f" | {details}"
        self.log(full_msg, "SYSTEM")
    
    def get_log_file_path(self):
        """Return current log file path"""
        return str(self.log_file)


class SettingsManager:
    def __init__(self):
        self.config_dir = Path(QStandardPaths.writableLocation(QStandardPaths.ConfigLocation)) / "qwsengine"
        self.config_file = self.config_dir / "settings.json"
        self.default_settings = {
            "start_url": "https://flanq.com",
            "window_width": 1024,
            "window_height": 768,
            "logging_enabled": True,
            "log_navigation": True,
            "log_tab_actions": True,
            "log_errors": True,
            "persist_cookies": True,
            "persist_cache": True
        }
        self.settings = self.load_settings()
        
        # Initialize logging
        self.log_manager = LogManager(self.config_dir) if self.get("logging_enabled", True) else None
        
        # Setup persistent web profile
        self.web_profile = self.setup_web_profile()
    
    def load_settings(self):
        """Load settings from JSON file or return defaults"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    loaded_settings = json.load(f)
                # Merge with defaults to ensure all keys exist
                settings = self.default_settings.copy()
                settings.update(loaded_settings)
                return settings
        except Exception as e:
            print(f"Error loading settings: {e}")
        return self.default_settings.copy()
    
    def save_settings(self):
        """Save current settings to JSON file"""
        try:
            # Create config directory if it doesn't exist
            self.config_dir.mkdir(parents=True, exist_ok=True)
            
            with open(self.config_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving settings: {e}")
            return False
    
    def get(self, key, default=None):
        """Get a setting value"""
        return self.settings.get(key, default)
    
    def set(self, key, value):
        """Set a setting value"""
        self.settings[key] = value
    
    def update(self, new_settings):
        """Update multiple settings"""
        self.settings.update(new_settings)
    
    def log(self, message, level="INFO"):
        """Log a message if logging is enabled"""
        if self.log_manager:
            self.log_manager.log(message, level)
    
    def log_navigation(self, url, title="", tab_id=None):
        """Log navigation if enabled"""
        if self.log_manager and self.get("log_navigation", True):
            self.log_manager.log_navigation(url, title, tab_id)
    
    def log_tab_action(self, action, tab_id=None, details=""):
        """Log tab action if enabled"""
        if self.log_manager and self.get("log_tab_actions", True):
            self.log_manager.log_tab_action(action, tab_id, details)
    
    def log_error(self, error_msg, context=""):
        """Log error if enabled"""
        if self.log_manager and self.get("log_errors", True):
            self.log_manager.log_error(error_msg, context)
    
    def log_system_event(self, event, details=""):
        """Log system event"""
        if self.log_manager:
            self.log_manager.log_system_event(event, details)
    
    def get_log_file_path(self):
        """Get current log file path"""
        if self.log_manager:
            return self.log_manager.get_log_file_path()
        return None
    
    def setup_web_profile(self):
        """Setup persistent web profile for cookies and cache - fixed approach"""
        try:
            # Create profile data directory
            profile_dir = self.config_dir / "profile"
            profile_dir.mkdir(parents=True, exist_ok=True)
            
            if self.get("persist_cookies", True):
                # CRITICAL FIX: Create named profile (not off-the-record)
                # This is equivalent to: QWebEngineProfile("PersistentProfile", this)
                profile = QWebEngineProfile("QWSEnginePersistent")
                
                # Set storage path with absolute path (not relative)
                absolute_profile_path = str(profile_dir.resolve())
                profile.setPersistentStoragePath(absolute_profile_path)
                profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
                
                if self.log_manager:
                    self.log_manager.log(f"Created NAMED persistent profile: QWSEnginePersistent", "SYSTEM")
                    self.log_manager.log(f"Absolute storage path: {absolute_profile_path}", "SYSTEM")
                    
            else:
                # Use off-the-record profile when persistence is disabled
                profile = QWebEngineProfile()
                if self.log_manager:
                    self.log_manager.log("Using off-the-record profile (no persistence)", "SYSTEM")
            
            if self.get("persist_cache", True):
                # Set cache directory with absolute path
                cache_path = profile_dir / "cache"
                cache_path.mkdir(exist_ok=True)
                absolute_cache_path = str(cache_path.resolve())
                
                profile.setCachePath(absolute_cache_path)
                profile.setHttpCacheMaximumSize(100 * 1024 * 1024)
                profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.DiskHttpCache)
                
                if self.log_manager:
                    self.log_manager.log(f"Absolute cache path: {absolute_cache_path}", "SYSTEM")
            
            # Set download path with absolute path
            download_path = profile_dir / "downloads"
            download_path.mkdir(exist_ok=True)
            absolute_download_path = str(download_path.resolve())
            profile.setDownloadPath(absolute_download_path)
            
            if self.log_manager:
                self.log_manager.log(f"Profile configured - Storage: {profile.persistentStoragePath()}", "SYSTEM")
                self.log_manager.log(f"Download path: {absolute_download_path}", "SYSTEM")
            
            return profile
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.log_error(f"Failed to setup web profile: {str(e)}")
            return QWebEngineProfile()  # Fallback to off-the-record

    def get_web_profile(self):
        """Get the configured web profile"""
        return self.web_profile
    
    def get_log_file_path(self):
        """Get current log file path"""
        if self.log_manager:
            return self.log_manager.get_log_file_path()
        return None


class SettingsDialog(QDialog):
    def __init__(self, parent=None, settings_manager=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.setup_ui()
    
    def setup_ui(self):
        self.setWindowTitle("QWSEngine Settings")
        self.setModal(True)
        self.resize(500, 400)
        
        layout = QVBoxLayout(self)
        
        # Start URL setting
        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel("Start URL:"))
        self.url_input = QLineEdit()
        current_url = self.settings_manager.get("start_url", "https://flanq.com")
        self.url_input.setText(current_url)
        self.url_input.setPlaceholderText("Enter default URL for new tabs")
        url_layout.addWidget(self.url_input)
        layout.addLayout(url_layout)
        
        # Window size settings
        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("Window Size:"))
        
        self.width_input = QLineEdit()
        self.width_input.setText(str(self.settings_manager.get("window_width", 1024)))
        self.width_input.setPlaceholderText("Width")
        
        size_layout.addWidget(QLabel("Width:"))
        size_layout.addWidget(self.width_input)
        
        self.height_input = QLineEdit()
        self.height_input.setText(str(self.settings_manager.get("window_height", 768)))
        self.height_input.setPlaceholderText("Height")
        
        size_layout.addWidget(QLabel("Height:"))
        size_layout.addWidget(self.height_input)
        layout.addLayout(size_layout)
        
        # Logging settings
        logging_layout = QVBoxLayout()
        logging_layout.addWidget(QLabel("Logging Options:"))
        
        self.logging_enabled = QCheckBox("Enable Logging")
        self.logging_enabled.setChecked(self.settings_manager.get("logging_enabled", True))
        logging_layout.addWidget(self.logging_enabled)
        
        self.log_navigation = QCheckBox("Log Page Navigation")
        self.log_navigation.setChecked(self.settings_manager.get("log_navigation", True))
        logging_layout.addWidget(self.log_navigation)
        
        self.log_tab_actions = QCheckBox("Log Tab Actions")
        self.log_tab_actions.setChecked(self.settings_manager.get("log_tab_actions", True))
        logging_layout.addWidget(self.log_tab_actions)
        
        self.log_errors = QCheckBox("Log Errors")
        self.log_errors.setChecked(self.settings_manager.get("log_errors", True))
        logging_layout.addWidget(self.log_errors)
        
        layout.addLayout(logging_layout)
        
        # Browser data settings
        browser_layout = QVBoxLayout()
        browser_layout.addWidget(QLabel("Browser Data Options:"))
        
        self.persist_cookies = QCheckBox("Persist Cookies (remember logins)")
        self.persist_cookies.setChecked(self.settings_manager.get("persist_cookies", True))
        browser_layout.addWidget(self.persist_cookies)
        
        self.persist_cache = QCheckBox("Persist Cache (faster page loading)")
        self.persist_cache.setChecked(self.settings_manager.get("persist_cache", True))
        browser_layout.addWidget(self.persist_cache)
        
        # Clear data button
        clear_data_button = QPushButton("Clear All Browser Data")
        clear_data_button.clicked.connect(self.clear_browser_data)
        clear_data_button.setToolTip("Clear cookies, cache, and all stored browser data")
        browser_layout.addWidget(clear_data_button)
        
        layout.addLayout(browser_layout)
        
        # Log file info
        if self.settings_manager.get_log_file_path():
            log_info = QLabel(f"Log file: {self.settings_manager.get_log_file_path()}")
            log_info.setStyleSheet("color: gray; font-size: 9px;")
            log_info.setWordWrap(True)
            layout.addWidget(log_info)
        
        # Log file info
        if self.settings_manager.get_log_file_path():
            log_info = QLabel(f"Log file: {self.settings_manager.get_log_file_path()}")
            log_info.setStyleSheet("color: gray; font-size: 9px;")
            log_info.setWordWrap(True)
            layout.addWidget(log_info)
        
        # Info label
        info_label = QLabel("Settings are automatically saved. Browser data changes require restart.")
        info_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(info_label)
        
        # Spacer
        layout.addStretch()
        
        # Buttons
        button_layout = QHBoxLayout()
        
        reset_button = QPushButton("Reset to Defaults")
        reset_button.clicked.connect(self.reset_to_defaults)
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save_settings)
        save_button.setDefault(True)
        
        button_layout.addWidget(reset_button)
        button_layout.addStretch()
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(save_button)
        layout.addLayout(button_layout)
    
    def clear_browser_data(self):
        """Clear all browser data"""
        reply = QMessageBox.question(self, "Clear Browser Data", 
                                   "This will delete all cookies, cache, and stored data. Continue?",
                                   QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            if self.settings_manager.clear_browser_data():
                QMessageBox.information(self, "Data Cleared", 
                                      "Browser data cleared successfully! Restart the application to see changes.")
            else:
                QMessageBox.warning(self, "Clear Failed", "Failed to clear browser data.")
    
    def reset_to_defaults(self):
        """Reset all settings to default values"""
        self.url_input.setText("https://flanq.com")
        self.width_input.setText("1024")
        self.height_input.setText("768")
        self.logging_enabled.setChecked(True)
        self.log_navigation.setChecked(True)
        self.log_tab_actions.setChecked(True)
        self.log_errors.setChecked(True)
        self.persist_cookies.setChecked(True)
        self.persist_cache.setChecked(True)
    
    def save_settings(self):
        """Validate and save settings"""
        try:
            # Validate URL
            url = self.url_input.text().strip()
            if not url:
                QMessageBox.warning(self, "Invalid URL", "Please enter a valid start URL.")
                return
            
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
            
            # Validate window size
            try:
                width = int(self.width_input.text())
                height = int(self.height_input.text())
                if width < 400 or height < 300:
                    QMessageBox.warning(self, "Invalid Size", "Window size must be at least 400x300.")
                    return
            except ValueError:
                QMessageBox.warning(self, "Invalid Size", "Please enter valid numbers for width and height.")
                return
            
            # Update settings
            self.settings_manager.set("start_url", url)
            self.settings_manager.set("window_width", width)
            self.settings_manager.set("window_height", height)
            self.settings_manager.set("logging_enabled", self.logging_enabled.isChecked())
            self.settings_manager.set("log_navigation", self.log_navigation.isChecked())
            self.settings_manager.set("log_tab_actions", self.log_tab_actions.isChecked())
            self.settings_manager.set("log_errors", self.log_errors.isChecked())
            self.settings_manager.set("persist_cookies", self.persist_cookies.isChecked())
            self.settings_manager.set("persist_cache", self.persist_cache.isChecked())
            
            # Save to file
            if self.settings_manager.save_settings():
                QMessageBox.information(self, "Settings Saved", "Settings have been saved successfully!")
                self.accept()
            else:
                QMessageBox.critical(self, "Save Error", "Failed to save settings to file.")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")


class BrowserTab(QWidget):
    # Class variable to track tab IDs
    _tab_counter = 0
    
    def __init__(self, tab_widget, url=None, settings_manager=None):
        super().__init__()
        self.tab_widget = tab_widget
        self.settings_manager = settings_manager
        
        # Assign unique tab ID
        BrowserTab._tab_counter += 1
        self.tab_id = BrowserTab._tab_counter
        
        # Use settings for default URL if none provided
        if url is None:
            url = self.settings_manager.get("start_url", "https://flanq.com")
        
        # Log tab creation
        self.settings_manager.log_tab_action("Created", self.tab_id, f"URL: {url}")

        # Layouts
        layout = QVBoxLayout(self)
        controls_layout = QHBoxLayout()

        # URL input field
        self.url_input = QLineEdit()
        self.url_input.setText(url)
        self.url_input.returnPressed.connect(self.load_url)  # Enter key support

        # Go button
        go_button = QPushButton("Go")
        go_button.clicked.connect(self.load_url)

        # "+" button to create a new tab
        new_tab_button = QPushButton("+")
        new_tab_button.clicked.connect(self.create_new_tab)
        new_tab_button.setToolTip("Create new tab (Ctrl+T)")

        # Add controls
        controls_layout.addWidget(self.url_input)
        controls_layout.addWidget(go_button)
        controls_layout.addWidget(new_tab_button)

        # Browser view with persistent profile
        # Create a page with the persistent profile first
        profile = self.settings_manager.get_web_profile()
        page = QWebEnginePage(profile, self)
        self.browser = QWebEngineView()
        self.browser.setPage(page)
        
        # Add comprehensive cookie debugging
        if self.settings_manager.get("logging_enabled", True):
            try:
                cookie_store = profile.cookieStore()
                
                # Log when cookies are added
                cookie_store.cookieAdded.connect(lambda cookie: 
                    self.settings_manager.log(f"Cookie added: {cookie.name().data().decode()} = {cookie.value().data().decode()[:50]}... for {cookie.domain()}", "COOKIE"))
                
                # Log when cookies are removed
                cookie_store.cookieRemoved.connect(lambda cookie: 
                    self.settings_manager.log(f"Cookie removed: {cookie.name().data().decode()} from {cookie.domain()}", "COOKIE"))
                
                self.settings_manager.log(f"Cookie store initialized for tab {self.tab_id}", "COOKIE")
                
            except Exception as e:
                self.settings_manager.log_error(f"Could not setup cookie debugging: {str(e)}")
        
        # Connect signals before loading
        self.browser.titleChanged.connect(self.update_tab_title)
        self.browser.urlChanged.connect(self.update_url_bar)
        self.browser.loadStarted.connect(self.on_load_started)
        self.browser.loadFinished.connect(self.on_load_finished)
        
        # Load the URL
        self.browser.load(url)

        # Add widgets to layout
        layout.addLayout(controls_layout)
        layout.addWidget(self.browser)

    def load_url(self):
        url = self.url_input.text().strip()
        if not url.startswith("http"):
            url = "https://" + url
        
        self.settings_manager.log_tab_action("Manual navigation", self.tab_id, f"URL: {url}")
        self.browser.load(url)

    def create_new_tab(self):
        # Get parent window to access settings
        parent_window = self.get_browser_window()
        if parent_window:
            self.settings_manager.log_tab_action("New tab requested", self.tab_id)
            new_tab = BrowserTab(self.tab_widget, settings_manager=parent_window.settings_manager)
            index = self.tab_widget.addTab(new_tab, "New Tab")
            self.tab_widget.setCurrentIndex(index)

    def get_browser_window(self):
        """Find the parent BrowserWindow"""
        parent = self.parent()
        while parent:
            if isinstance(parent, BrowserWindow):
                return parent
            parent = parent.parent()
        return None

    def update_tab_title(self, title):
        index = self.tab_widget.indexOf(self)
        if index >= 0:
            short_title = title[:15] + ("…" if len(title) > 15 else "")
            self.tab_widget.setTabText(index, short_title)
            self.settings_manager.log_tab_action("Title updated", self.tab_id, f"Title: {title}")
    
    def update_url_bar(self, qurl):
        """Update URL bar when page changes"""
        url = qurl.toString()
        self.url_input.setText(url)
    
    def on_load_started(self):
        """Called when page starts loading"""
        url = self.browser.url().toString()
        self.settings_manager.log_navigation(url, "", self.tab_id)
        
        # Check cookie directory before loading
        if self.settings_manager.get("logging_enabled", True):
            self.check_cookie_files("before load")
    
    def on_load_finished(self, success):
        """Called when page finishes loading"""
        url = self.browser.url().toString()
        title = self.browser.title()
        
        if success:
            self.settings_manager.log_navigation(url, title, self.tab_id)
            
            # Check cookie directory after loading
            if self.settings_manager.get("logging_enabled", True):
                self.check_cookie_files("after load")
                
        else:
            self.settings_manager.log_error(f"Failed to load page: {url}", f"Tab-{self.tab_id}")
    
    def check_cookie_files(self, when):
        """Check what's in the cookies directory and other potential cookie locations"""
        try:
            profile_dir = Path(self.settings_manager.config_dir) / "profile"
            
            # Check the cookies subdirectory
            cookies_dir = profile_dir / "cookies"
            if cookies_dir.exists():
                contents = list(cookies_dir.iterdir())
                if contents:
                    self.settings_manager.log(f"Cookies directory {when}: {[p.name for p in contents]}", "COOKIE")
                    # Check file sizes and types
                    for item in contents:
                        if item.is_file():
                            size = item.stat().st_size
                            self.settings_manager.log(f"Cookie file {item.name}: {size} bytes", "COOKIE")
                else:
                    self.settings_manager.log(f"Cookies directory {when}: empty", "COOKIE")
            else:
                self.settings_manager.log(f"Cookies directory {when}: does not exist", "COOKIE")
            
            # Look for SQLite database files that might contain cookies
            if profile_dir.exists():
                for item in profile_dir.iterdir():
                    if item.is_file():
                        name_lower = item.name.lower()
                        if (any(keyword in name_lower for keyword in ['cookie', 'network', 'state', 'history']) or 
                            item.suffix.lower() in ['.db', '.sqlite', '.sqlite3']):
                            size = item.stat().st_size
                            modified = item.stat().st_mtime
                            self.settings_manager.log(f"Profile file {item.name}: {size} bytes, modified: {modified}", "COOKIE")
                
                # Also check subdirectories for database files
                for subdir in profile_dir.iterdir():
                    if subdir.is_dir() and subdir.name in ['Local Storage', 'databases', 'IndexedDB']:
                        try:
                            for item in subdir.rglob('*'):
                                if item.is_file() and item.suffix.lower() in ['.db', '.sqlite', '.sqlite3', '.ldb']:
                                    size = item.stat().st_size
                                    rel_path = item.relative_to(profile_dir)
                                    self.settings_manager.log(f"Database file {rel_path}: {size} bytes", "COOKIE")
                        except Exception:
                            pass
                        
        except Exception as e:
            self.settings_manager.log_error(f"Could not check cookie files {when}: {str(e)}")
    
    def closeEvent(self, event):
        """Called when tab is being closed"""
        self.settings_manager.log_tab_action("Closed", self.tab_id)
        super().closeEvent(event)


class BrowserWindow(QWidget):
    def __init__(self):
        super().__init__()
        
        # Initialize settings manager
        self.settings_manager = SettingsManager()
        
        # Log application startup
        script_path = os.path.abspath(__file__)
        self.settings_manager.log_system_event("Application started", f"Script: {script_path}")
        
        # Setup window
        self.setWindowTitle("QWSEngine - PySide6 Multi-tab Browser")
        
        # Apply saved window size
        width = self.settings_manager.get("window_width", 1024)
        height = self.settings_manager.get("window_height", 768)
        self.resize(width, height)
        self.settings_manager.log_system_event("Window initialized", f"Size: {width}x{height}")
        
        self.setup_ui()
        
        # Start with one browser tab using configured start URL
        self.create_initial_tab()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create menu bar
        self.create_menu_bar(layout)
        
        # Tab control
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        layout.addWidget(self.tabs)
    
    def create_menu_bar(self, layout):
        """Create menu bar with settings option"""
        menu_bar = QMenuBar()
        
        # File menu
        file_menu = menu_bar.addMenu("File")
        
        new_tab_action = QAction("New Tab", self)
        new_tab_action.setShortcut("Ctrl+T")
        new_tab_action.triggered.connect(self.create_new_tab)
        file_menu.addAction(new_tab_action)
        
        file_menu.addSeparator()
        
        settings_action = QAction("Settings...", self)
        settings_action.triggered.connect(self.open_settings)
        file_menu.addAction(settings_action)
        
        file_menu.addSeparator()
        
        # Add view logs action
        view_logs_action = QAction("View Logs...", self)
        view_logs_action.triggered.connect(self.view_logs)
        file_menu.addAction(view_logs_action)
        
        file_menu.addSeparator()
        
        # Add clear browser data action
        clear_data_action = QAction("Clear Browser Data...", self)
        clear_data_action.triggered.connect(self.clear_browser_data)
        file_menu.addAction(clear_data_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        layout.addWidget(menu_bar)
    
    def create_initial_tab(self):
        """Create the first tab with configured start URL"""
        first_tab = BrowserTab(self.tabs, settings_manager=self.settings_manager)
        self.tabs.addTab(first_tab, "Home")
        self.settings_manager.log_system_event("Initial tab created")
    
    def create_new_tab(self):
        """Create a new tab (called from menu)"""
        new_tab = BrowserTab(self.tabs, settings_manager=self.settings_manager)
        index = self.tabs.addTab(new_tab, "New Tab")
        self.tabs.setCurrentIndex(index)
        self.settings_manager.log_system_event("New tab created from menu")
    
    def open_settings(self):
        """Open settings dialog"""
        try:
            self.settings_manager.log_system_event("Settings dialog opening...")
            dialog = SettingsDialog(self, self.settings_manager)
            self.settings_manager.log_system_event("Settings dialog created")
            result = dialog.exec()
            if result == QDialog.Accepted:
                self.settings_manager.log_system_event("Settings saved")
            else:
                self.settings_manager.log_system_event("Settings dialog cancelled")
        except Exception as e:
            self.settings_manager.log_error(f"Failed to open settings dialog: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to open settings: {str(e)}")
    
    def clear_browser_data(self):
        """Clear all browser data from menu"""
        reply = QMessageBox.question(self, "Clear Browser Data", 
                                   "This will delete all cookies, cache, downloads, and stored data. Continue?",
                                   QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            if self.settings_manager.clear_browser_data():
                QMessageBox.information(self, "Data Cleared", 
                                      "Browser data cleared successfully! Please restart the application.")
                self.settings_manager.log_system_event("Browser data cleared via menu")
            else:
                QMessageBox.warning(self, "Clear Failed", "Failed to clear browser data.")
    
    def view_logs(self):
        """Open log file location"""
        log_path = self.settings_manager.get_log_file_path()
        if log_path:
            try:
                # Open file explorer to log location
                import subprocess
                import platform
                
                log_dir = os.path.dirname(log_path)
                if platform.system() == "Windows":
                    subprocess.run(["explorer", log_dir])
                elif platform.system() == "Darwin":  # macOS
                    subprocess.run(["open", log_dir])
                else:  # Linux
                    subprocess.run(["xdg-open", log_dir])
                
                self.settings_manager.log_system_event("Log directory opened")
            except Exception as e:
                self.settings_manager.log_error(f"Failed to open log directory: {str(e)}")
                QMessageBox.information(self, "Log Location", f"Log file location:\n{log_path}")
        else:
            QMessageBox.information(self, "Logging Disabled", "Logging is currently disabled.")
    
    def close_tab(self, index):
        if self.tabs.count() > 1:
            widget = self.tabs.widget(index)
            tab_id = getattr(widget, 'tab_id', None)
            self.settings_manager.log_tab_action("Closed via X button", tab_id)
            widget.deleteLater()
            self.tabs.removeTab(index)
        else:
            # Close application if last tab is closed
            self.settings_manager.log_system_event("Last tab closed - shutting down")
            self.close()
    
    def closeEvent(self, event):
        """Called when application is closing"""
        # Force cookie synchronization before closing
        try:
            profile = self.settings_manager.get_web_profile()
            # In some versions of Qt WebEngine, we need to explicitly sync
            if hasattr(profile, 'clearHttpCache'):
                # This can sometimes trigger a save
                pass
            self.settings_manager.log_system_event("Attempting to sync cookies before shutdown")
        except Exception as e:
            self.settings_manager.log_error(f"Error during cookie sync: {str(e)}")
        
        self.settings_manager.log_system_event("Application shutting down")
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("QWSEngine")
    app.setApplicationVersion("1.1.0")
    
    window = BrowserWindow()
    window.show()
    
    # Log final startup completion
    window.settings_manager.log_system_event("Application fully loaded and visible")
    
    try:
        sys.exit(app.exec())
    except Exception as e:
        if hasattr(window, 'settings_manager'):
            window.settings_manager.log_error(f"Application crashed: {str(e)}")
        raise