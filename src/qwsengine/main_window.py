import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QMenuBar, QMessageBox
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QDialog

from .settings import SettingsManager
from .settings_dialog import SettingsDialog
from .browser_tab import BrowserTab

class BrowserWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.settings_manager = SettingsManager()

        script_path = os.path.abspath(__file__)
        self.settings_manager.log_system_event("Application started", f"Script: {script_path}")

        self.setWindowTitle("QWSEngine - PySide6 Multi-tab Browser")

        width = self.settings_manager.get("window_width", 1024)
        height = self.settings_manager.get("window_height", 768)
        self.resize(width, height)
        self.settings_manager.log_system_event("Window initialized", f"Size: {width}x{height}")

        self._setup_ui()
        self._create_initial_tab()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        menu_bar = self._create_menu_bar()
        layout.addWidget(menu_bar)

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        layout.addWidget(self.tabs)

    def _create_menu_bar(self):
        menu_bar = QMenuBar()

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

        view_logs_action = QAction("View Logs...", self)
        view_logs_action.triggered.connect(self.view_logs)
        file_menu.addAction(view_logs_action)

        file_menu.addSeparator()

        clear_data_action = QAction("Clear Browser Data...", self)
        clear_data_action.triggered.connect(self.clear_browser_data)
        file_menu.addAction(clear_data_action)

        file_menu.addSeparator()

        exit_action = QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        return menu_bar

    def _create_initial_tab(self):
        first_tab = BrowserTab(self.tabs, settings_manager=self.settings_manager)
        self.tabs.addTab(first_tab, "Home")
        self.settings_manager.log_system_event("Initial tab created")

    def create_new_tab(self):
        new_tab = BrowserTab(self.tabs, settings_manager=self.settings_manager)
        index = self.tabs.addTab(new_tab, "New Tab")
        self.tabs.setCurrentIndex(index)
        self.settings_manager.log_system_event("New tab created from menu")

    def open_settings(self):
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
        log_path = self.settings_manager.get_log_file_path()
        if log_path:
            try:
                import subprocess
                import platform
                log_dir = os.path.dirname(log_path)
                if platform.system() == "Windows":
                    subprocess.run(["explorer", log_dir])
                elif platform.system() == "Darwin":
                    subprocess.run(["open", log_dir])
                else:
                    subprocess.run(["xdg-open", log_dir])
                self.settings_manager.log_system_event("Log directory opened")
            except Exception as e:
                self.settings_manager.log_error(f"Failed to open log directory: {str(e)}")
                QMessageBox.information(self, "Log Location", f"Log file location:\n{log_path}")
        else:
            QMessageBox.information(self, "Logging Disabled", "Logging is currently disabled.")

    def close_tab(self, index: int):
        if self.tabs.count() > 1:
            widget = self.tabs.widget(index)
            tab_id = getattr(widget, 'tab_id', None)
            self.settings_manager.log_tab_action("Closed via X button", tab_id)
            widget.deleteLater()
            self.tabs.removeTab(index)
        else:
            self.settings_manager.log_system_event("Last tab closed - shutting down")
            self.close()

    def closeEvent(self, event):
        try:
            profile = self.settings_manager.get_web_profile()
            if hasattr(profile, 'clearHttpCache'):
                pass
            self.settings_manager.log_system_event("Attempting to sync cookies before shutdown")
        except Exception as e:
            self.settings_manager.log_error(f"Error during cookie sync: {str(e)}")

        self.settings_manager.log_system_event("Application shutting down")
        super().closeEvent(event)
