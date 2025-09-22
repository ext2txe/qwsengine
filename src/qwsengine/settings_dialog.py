from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QCheckBox,
    QPushButton, QMessageBox
)

class SettingsDialog(QDialog):
    def __init__(self, parent=None, settings_manager=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("QWSEngine Settings")
        self.setModal(True)
        self.resize(500, 400)

        layout = QVBoxLayout(self)

        # Start URL
        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel("Start URL:"))
        self.url_input = QLineEdit()
        self.url_input.setText(self.settings_manager.get("start_url", "https://flanq.com"))
        self.url_input.setPlaceholderText("Enter default URL for new tabs")
        url_layout.addWidget(self.url_input)
        layout.addLayout(url_layout)

        # Window size
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

        # Logging
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

        # Browser data
        browser_layout = QVBoxLayout()
        browser_layout.addWidget(QLabel("Browser Data Options:"))
        self.persist_cookies = QCheckBox("Persist Cookies (remember logins)")
        self.persist_cookies.setChecked(self.settings_manager.get("persist_cookies", True))
        browser_layout.addWidget(self.persist_cookies)
        self.persist_cache = QCheckBox("Persist Cache (faster page loading)")
        self.persist_cache.setChecked(self.settings_manager.get("persist_cache", True))
        browser_layout.addWidget(self.persist_cache)

        clear_data_button = QPushButton("Clear All Browser Data")
        clear_data_button.setToolTip("Clear cookies, cache, and all stored browser data")
        clear_data_button.clicked.connect(self.clear_browser_data)
        browser_layout.addWidget(clear_data_button)
        layout.addLayout(browser_layout)

        # Log file info
        if self.settings_manager.get_log_file_path():
            log_info = QLabel(f"Log file: {self.settings_manager.get_log_file_path()}")
            log_info.setStyleSheet("color: gray; font-size: 9px;")
            log_info.setWordWrap(True)
            layout.addWidget(log_info)

        info_label = QLabel("Settings are automatically saved. Browser data changes require restart.")
        info_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(info_label)

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
        try:
            url = self.url_input.text().strip()
            if not url:
                QMessageBox.warning(self, "Invalid URL", "Please enter a valid start URL.")
                return
            if not url.startswith(("http://", "https://")):
                url = "https://" + url

            try:
                width = int(self.width_input.text())
                height = int(self.height_input.text())
                if width < 400 or height < 300:
                    QMessageBox.warning(self, "Invalid Size", "Window size must be at least 400x300.")
                    return
            except ValueError:
                QMessageBox.warning(self, "Invalid Size", "Please enter valid numbers for width and height.")
                return

            self.settings_manager.set("start_url", url)
            self.settings_manager.set("window_width", width)
            self.settings_manager.set("window_height", height)
            self.settings_manager.set("logging_enabled", self.logging_enabled.isChecked())
            self.settings_manager.set("log_navigation", self.log_navigation.isChecked())
            self.settings_manager.set("log_tab_actions", self.log_tab_actions.isChecked())
            self.settings_manager.set("log_errors", self.log_errors.isChecked())
            self.settings_manager.set("persist_cookies", self.persist_cookies.isChecked())
            self.settings_manager.set("persist_cache", self.persist_cache.isChecked())

            if self.settings_manager.save_settings():
                QMessageBox.information(self, "Settings Saved", "Settings have been saved successfully!")
                self.accept()
            else:
                QMessageBox.critical(self, "Save Error", "Failed to save settings to file.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")
