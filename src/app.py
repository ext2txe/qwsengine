import sys

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon

from qwsengine.app_info import APP_ID
from qwsengine.ui import resources_rc  # noqa: F401  - ensure Qt resources are registered

from qwsengine.core import AppContext          # <-- comes from the new minimal core/__init__.py
from qwsengine.core.settings import SettingsManager
from qwsengine.ui.browser_window import BrowserWindow
from qwsengine.ui.browser_controller_window import BrowserControllerWindow


def main() -> None:
    """Application entry point."""
    app = QApplication(sys.argv)

    # Optional: Windows taskbar grouping + app identity
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:
        # Non-Windows or failure – just ignore
        pass

    # Set main application icon from Qt resources (":/qws" prefix comes from resources_rc)
    try:
        app.setWindowIcon(QIcon(":/qws/icons/logo.ico"))
    except Exception:
        # Icon is nice to have but not critical
        pass

    # --- new context wiring ---
    ctx = AppContext.create(qt_app=app)
    settings_manager = ctx.settings_manager

    controller_window = BrowserControllerWindow(
        parent=None,
        settings_manager=settings_manager,
    )
    controller_window.show()

    controller_window.update_status("Controller ready")

    # Optionally auto-launch the browser window based on settings
    should_auto_launch_browser = settings_manager.get("auto_launch_browser", True)

    browser_window = None
    if should_auto_launch_browser:
        # browser window – NOTE: ctx is passed in now
        browser_window = BrowserWindow(
            ctx=ctx,
            settings_manager=settings_manager,
        )
        browser_window.show()
        # Wire controller to browser
        controller_window.browser_window = browser_window
        controller_window.update_status("Connected to browser - Ready")

    # --- Event loop + crash logging -----------------------------------------
    try:
        sys.exit(app.exec())
    except Exception as e:
        # Best-effort logging – don’t crash if logging fails
        try:
            if browser_window is not None and hasattr(browser_window, "settings_manager"):
                browser_window.settings_manager.log_error("App", f"Application crashed: {e}")
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
