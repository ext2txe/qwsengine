import sys
import json
import os
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QTabWidget, QDialog, QLabel,
    QMessageBox, QMenuBar, QMenu
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QStandardPaths
from PySide6.QtGui import QAction


class SettingsManager:
    def __init__(self):
        self.config_dir = Path(QStandardPaths.writableLocation(QStandardPaths.ConfigLocation)) / "qwsengine"
        self.config_file = self.config_dir / "settings.json"
        self.default_settings = {
            "start_url": "https://flanq.com",
            "window_width": 1024,
            "window_height": 768
        }
        self.settings = self.load_settings()
    
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


class SettingsDialog(QDialog):
    def __init__(self, parent=None, settings_manager=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.setup_ui()
    
    def setup_ui(self):
        self.setWindowTitle("QWSEngine Settings")
        self.setModal(True)
        self.resize(500, 300)
        
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
        
        # Info label
        info_label = QLabel("Settings are automatically saved and will take effect on restart.")
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
    
    def reset_to_defaults(self):
        """Reset all settings to default values"""
        self.url_input.setText("https://flanq.com")
        self.width_input.setText("1024")
        self.height_input.setText("768")
    
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
            
            # Save to file
            if self.settings_manager.save_settings():
                QMessageBox.information(self, "Settings Saved", "Settings have been saved successfully!")
                self.accept()
            else:
                QMessageBox.critical(self, "Save Error", "Failed to save settings to file.")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")


class BrowserTab(QWidget):
    def __init__(self, tab_widget, url=None, settings_manager=None):
        super().__init__()
        self.tab_widget = tab_widget
        self.settings_manager = settings_manager
        
        # Use settings for default URL if none provided
        if url is None:
            url = self.settings_manager.get("start_url", "https://flanq.com")

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

        # Browser view
        self.browser = QWebEngineView()
        self.browser.load(url)

        # Update tab title when page title changes
        self.browser.titleChanged.connect(self.update_tab_title)
        
        # Update URL bar when page changes
        self.browser.urlChanged.connect(self.update_url_bar)

        # Add widgets to layout
        layout.addLayout(controls_layout)
        layout.addWidget(self.browser)

    def load_url(self):
        url = self.url_input.text().strip()
        if not url.startswith("http"):
            url = "https://" + url
        self.browser.load(url)

    def create_new_tab(self):
        # Get parent window to access settings
        parent_window = self.get_browser_window()
        if parent_window:
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
            self.tab_widget.setTabText(index, title[:15] + ("…" if len(title) > 15 else ""))
    
    def update_url_bar(self, qurl):
        """Update URL bar when page changes"""
        self.url_input.setText(qurl.toString())


class BrowserWindow(QWidget):
    def __init__(self):
        super().__init__()
        
        # Initialize settings manager
        self.settings_manager = SettingsManager()
        
        # Setup window
        self.setWindowTitle("QWSEngine - PySide6 Multi-tab Browser")
        
        # Apply saved window size
        width = self.settings_manager.get("window_width", 1024)
        height = self.settings_manager.get("window_height", 768)
        self.resize(width, height)
        
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
        
        exit_action = QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        layout.addWidget(menu_bar)
    
    def create_initial_tab(self):
        """Create the first tab with configured start URL"""
        first_tab = BrowserTab(self.tabs, settings_manager=self.settings_manager)
        self.tabs.addTab(first_tab, "Home")
    
    def create_new_tab(self):
        """Create a new tab (called from menu)"""
        new_tab = BrowserTab(self.tabs, settings_manager=self.settings_manager)
        index = self.tabs.addTab(new_tab, "New Tab")
        self.tabs.setCurrentIndex(index)
    
    def open_settings(self):
        """Open settings dialog"""
        dialog = SettingsDialog(self, self.settings_manager)
        dialog.exec()
    
    def close_tab(self, index):
        if self.tabs.count() > 1:
            widget = self.tabs.widget(index)
            widget.deleteLater()
            self.tabs.removeTab(index)
        else:
            # Close application if last tab is closed
            self.close()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("QWSEngine")
    app.setApplicationVersion("1.0.0")
    
    window = BrowserWindow()
    window.show()
    sys.exit(app.exec())