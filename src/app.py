import sys
import os
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from PySide6.QtCore import QTimer
from qwsengine.app_info import APP_ID

# Import the QResource system to ensure resources are available
from qwsengine import resources_rc

from qwsengine.main_window import BrowserWindow
from qwsengine.controller_window import BrowserControllerWindow
from qwsengine.settings import SettingsManager


def main():
    app = QApplication(sys.argv)
    
    # Configure app identity from single source of truth
    
    # Optional: Windows taskbar grouping
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:
        pass
    
    # Set icon - using resource prefix from app_info
    try:
        app.setWindowIcon(QIcon(f"{RESOURCE_PREFIX}/icons/logo.ico"))
    except:
        pass  # Icon optional
    
    ## Create main browser window
    #browser_window = BrowserWindow()
    #browser_window.show()
    #browser_window.settings_manager.log_system_event("App", "Application fully loaded and visible")
    
    # Create controller window and ensure it connects properly
    controller_window = BrowserControllerWindow()
    
    # Delay showing controller slightly to ensure browser is fully initialized
    def show_controller():
        controller_window.show()
        controller_window.raise_()
        controller_window.activateWindow()
        # Force update status after connection
        controller_window.update_status("Connected to browser - Ready")
        browser_window.settings_manager.log_system_event("App", "Controller window launched")
    
    # Show controller after a brief delay
    QTimer.singleShot(100, show_controller)
    # Set icon
  # The resource prefix is ":/qws" based on your app_info.py
    app.setWindowIcon(QIcon(":/qws/icons/logo.ico"))
    
    # Create settings manager first
    settings_manager = SettingsManager()
    
    # Create and show controller window first
    controller_window = BrowserControllerWindow(parent=None, settings_manager=settings_manager)
    controller_window.show()
    controller_window.update_status("Controller ready")
    
    # Check if browser should auto-launch
    should_auto_launch_browser = settings_manager.get("auto_launch_browser", True)
    
    # If auto-launch is enabled, create and show the browser window
    browser_window = None
    if should_auto_launch_browser:
        browser_window = BrowserWindow(settings_manager=settings_manager)
        browser_window.show()
        settings_manager.log_system_event("App", "Application fully loaded and visible")
        
        # Connect controller to browser
        controller_window.browser_window = browser_window
        controller_window.update_status("Connected to browser - Ready")
    
    try:
        sys.exit(app.exec())
    except Exception as e:
        if hasattr(browser_window, 'settings_manager'):
            browser_window.settings_manager.log_error("App", f"Application crashed: {str(e)}")
        raise


if __name__ == "__main__":
    main()