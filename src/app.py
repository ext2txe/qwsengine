import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from qwsengine.main_window import BrowserWindow

def main():
    app = QApplication(sys.argv)

    # Optional but recommended on Windows: make sure taskbar uses *your* icon/group
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("qwsengine.app")
    except Exception:
        pass
    app.setWindowIcon(QIcon(r"C:\Users\joe\source\repos\qwsengine\resources\icons\logo.ico"))

    app.setApplicationName("QWSEngine")
    app.setApplicationVersion("1.1.0")
    window = BrowserWindow()
    window.show()
    window.settings_manager.log_system_event("Application fully loaded and visible")
    try:
        sys.exit(app.exec())
    except Exception as e:
        if hasattr(window, 'settings_manager'):
            window.settings_manager.log_error(f"Application crashed: {str(e)}")
        raise

if __name__ == "__main__":
    main()
