import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from qwsengine.app_info import APP_ID
from qwsengine.main_window import BrowserWindow

def main():
    app = QApplication(sys.argv)
    
    # Configure app identity from single source of truth
    
    # Optional: Windows taskbar grouping
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:
        pass
    
    # Set icon
    app.setWindowIcon(QIcon(r"C:\Users\joe\source\repos\qwsengine\resources\icons\logo.ico"))
    
    window = BrowserWindow()
    window.show()
    window.settings_manager.log_system_event("App", "Application fully loaded and visible")
    
    try:
        sys.exit(app.exec())
    except Exception as e:
        if hasattr(window, 'settings_manager'):
            window.settings_manager.log_error("App", f"Application crashed: {str(e)}")
        raise

if __name__ == "__main__":
    main()


