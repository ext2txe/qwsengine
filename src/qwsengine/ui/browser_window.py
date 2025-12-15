# qwsengine/browser_window.py
from __future__ import annotations
import os
from pathlib import Path
import platform
import subprocess

from datetime import datetime
from typing import Optional, Union

from PySide6.QtCore import QUrl, QRect, QByteArray, QSettings, QTimer
from PySide6.QtGui import QAction, QPainter, QImage, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QTabWidget,
    QToolBar,
    QMenuBar,
    QStatusBar,    
    QComboBox,
    QDialog,
    QLineEdit,
    QVBoxLayout,
    QApplication,
    QMessageBox,
    QToolButton
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineProfile
from qwsengine.app_info import APP_VERSION, LOG_DIR
from .menu_builder import MenuBuilder
from .toolbar_builder import ToolbarBuilder
from .tab_manager import TabManager


# Import your tab widget (your traceback shows browser_tab.py)
from .browser_tab import BrowserTab
from qwsengine.core.settings import SettingsManager
from .settings_dialog import SettingsDialog
from qwsengine.ui.about_dialog import AboutDialog
from .browser_operations import BrowserOperations  # NEW IMPORT
from qwsengine.core.log_manager import LogManager

class BrowserWindow(QMainWindow):
    """
    Main application window with tabbed browsing.

    Design:
      - Single source of truth for tab creation: _new_tab()
      - _blank/window.open() handled by WebView.createWindow via:
            tab.browser.set_create_window_handler(self._create_new_tab_and_return_view)
      - Optional legacy newTabRequested(QUrl) routed to open_url_in_new_tab()
    """

    def __init__(
        self,
        ctx: AppContext | None = None,
        settings_manager: SettingsManager | None = None,
        parent=None,
    ):
        super().__init__(parent)

        self.ctx = ctx

        # decide which settings_manager to use
        if settings_manager is not None:
            self.settings_manager = settings_manager
        elif ctx is not None and getattr(ctx, "settings_manager", None) is not None:
            self.settings_manager = ctx.settings_manager
        else:
            # last-resort fallback so the window can still be created
            self.settings_manager = SettingsManager()
            
        #from .ui.menu_builder import MenuBuilder
        self.menu_builder = MenuBuilder(self)
        self.toolbar_builder = ToolbarBuilder(self)
        self.tab_manager = TabManager(self)

        # NEW: Initialize browser operations utility
        self.browser_ops = BrowserOperations(
            settings_manager=self.settings_manager,
            status_callback=self.show_status
        )

        from PySide6.QtWebEngineCore import QWebEngineProfile

        pcp = QWebEngineProfile.PersistentCookiesPolicy
        policy = getattr(pcp, "ForcePersistentCookies", pcp.AllowPersistentCookies)
        QWebEngineProfile.defaultProfile().setPersistentCookiesPolicy(policy)

        self.log_info(f"QWSEngine browser v{APP_VERSION} starts")

        self.setWindowTitle(f"Qt Browser v{APP_VERSION}")
        self.resize(1200, 800)

        self._setup_ui()

        # ⬇⬇ restore window geometry/state BEFORE first show
        self.settings_manager.restore_window_state(self)

        # Scripts folder under app config
        self.scripts_dir = self.settings_manager.config_dir / "scripts"
        self.scripts_dir.mkdir(parents=True, exist_ok=True)

        # Populate the combo at startup
        self._load_script_list()

        #

        return
     
    def configure_profile(profile: QWebEngineProfile):
        cache = app_dir(QStandardPaths.CacheLocation) / "web"
        storage = app_dir(QStandardPaths.AppDataLocation) / "web"
        profile.setCachePath(str(cache))
        profile.setPersistentStoragePath(str(storage))
        profile.setPersistentCookiesPolicy(QWebEngineProfile.ForcePersistentCookies)

    def show_about_dialog(self):
        dlg = AboutDialog(self)
        dlg.exec()

    def _setup_ui(self):

        self.menu_builder.build_menu_bar()


        # --- Central layout with tabs --------------------------------------------
        central = QWidget(self)
        self.setCentralWidget(central)

        vbox = QVBoxLayout(central)
        vbox.setContentsMargins(0, 0, 0, 0)

        # ---Menu  ---------------------------------------------------

        # --- Create Tool bar ---------------------------------------------------
        toolbar = self.toolbar_builder.create_navigation_toolbar()
        vbox.addWidget(toolbar)

        # --- Create Tabs ---------------------------------------------------        
        self.tabs = self.tab_manager.get_tab_widget()
        vbox.addWidget(self.tabs)

        # --- Create Status bar ---------------------------------------------------
        self.status_bar = QStatusBar(self)
        vbox.addWidget(self.status_bar)

        self._restore_window_state()

        #install handlers
        #self.tab_manager.install_handlers()

        # Initial tab
        self.tab_manager.create_initial_tab()

        initial_tab = self.tab_manager.get_current_tab()
        if initial_tab and initial_tab.view:
            initial_url = initial_tab.view.url()
            if self.toolbar_builder.urlbar:
                self.toolbar_builder.urlbar.setText(initial_url.toString())

        self.status_bar.showMessage("Loading…", 2000)  # auto-clear after 2s
        
    def _nav_go(self):
        tab = self.tabs.currentWidget()
        if not tab:
            return
        view = self._view_of(tab)

        text = self.url_edit.text().strip()
        if not text:
            return

        q = QUrl.fromUserInput(text)
        if q.isValid():
            view.setUrl(q)   # or view.load(q)

    def clear_browser_data(self):
        reply = QMessageBox.question(self, "Clear Browser Data",
                                   "This will delete all cookies, cache, downloads, and stored data. Continue?",
                                   QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            if self.settings_manager.clear_browser_data():
                QMessageBox.information(self, "Data Cleared",
                                      "Browser data cleared successfully! Please restart the application.")
                self.settings_manager.log_system_event("browser_window", "browser_window","Browser data cleared via menu")
            else:
                QMessageBox.warning(self, "Clear Failed", "Failed to clear browser data.")

    def log_info(self, message):
        self.settings_manager.log_info("browser_window", f"{message}")

    # REFACTORED: Now uses browser_ops
    def save_current_tab_html(self):
        """Save HTML of current tab"""
        current = self.tabs.currentWidget()
        self.browser_ops.save_html(tab=current)

    # REFACTORED: Now uses browser_ops
    def save_current_tab_screenshot(self):
        """Save screenshot of current tab"""
        current = self.tabs.currentWidget()
        self.browser_ops.save_screenshot(tab=current)

    # REFACTORED: Now uses browser_ops
    def save_full_page_screenshot(self):
        """Capture entire scrollable page"""
        current = self.tabs.currentWidget()
        self.browser_ops.save_full_page_screenshot(tab=current)

    # DELETED: All _fps_* methods now in BrowserOperations class
    # _fps_start, _fps_next_tile, _fps_grab_tile, _fps_finish, _fps_fail, _fps_reset

    def _view_of(self, tab: QWidget) -> QWebEngineView:
        """
        Return the QWebEngineView for a given tab. This must never return None.
        """
        # Preferred: direct attribute set by our BrowserTab
        view = getattr(tab, "view", None)
        if isinstance(view, QWebEngineView):
            return view

        # Defensive fallback: search the tab for any QWebEngineView child
        found = tab.findChild(QWebEngineView)
        if found is not None:
            return found

        # If we get here, our tab is malformed
        raise RuntimeError("Could not find QWebEngineView in BrowserTab")

    def view_settings_json(self):
        """Open the settings.json file in the system's default editor."""
        try:
            settings_path = self.settings_manager.settings_path  # / "settings.json"
            
            # Ensure the file exists
            if not settings_path.exists():
                QMessageBox.information(
                    self, 
                    "Settings File Not Found",
                    f"The settings.json file does not exist yet at:\n{settings_path}\n\n"
                    "It will be created when you save settings."
                )
                self.settings_manager.log_system_event("browser_window", "Settings file not found", str(settings_path))
                return
            
            import subprocess
            import platform
            
            system = platform.system()
            settings_file = str(settings_path.resolve())
            
            if system == "Windows":
                # Use notepad as default editor on Windows
                subprocess.run(["notepad.exe", settings_file])
            elif system == "Darwin":  # macOS
                # Use open command which respects default app associations
                subprocess.run(["open", "-t", settings_file])  # -t forces text editor
            else:  # Linux / BSD
                # Try common editors, fallback to xdg-open
                editors = ["gedit", "kate", "nano", "vim", "xdg-open"]
                for editor in editors:
                    try:
                        subprocess.run([editor, settings_file])
                        break
                    except FileNotFoundError:
                        continue
            
            self.show_status(f"Opened settings.json → {settings_file}", level="INFO")
            self.settings_manager.log_system_event("browser_window", "Settings file opened", settings_file)
            
        except Exception as e:
            QMessageBox.warning(
                self,
                "Error Opening Settings",
                f"Failed to open settings.json:\n{str(e)}\n\n"
                f"File location:\n{settings_path}"
            )
            self.show_status(f"Failed to open settings.json: {e}", level="ERROR")
            self.settings_manager.log_error("browser_window", f"Open settings.json failed: {e}")

    def show_status(self, message: str, timeout_ms: int = 5000, level: str = "INFO"):
        """
        Show a transient message in the status bar and log it.
        level: "INFO" | "WARNING" | "ERROR"
        """
        if hasattr(self, "status_bar"):
            self.status_bar.showMessage(message, timeout_ms)

        # Log alongside showing it
        if level == "ERROR":
            self.settings_manager.log_error("browser_window", message)
        elif level == "WARNING":
            self.settings_manager.log_system_event("browser_window", "Warning", message)
        else:
            self.settings_manager.log_system_event("browser_window", "Status", message)

    def view_logs(self):
        """Open the logs directory in the file explorer."""
        try:
            # Get the log directory directly from settings manager
            log_dir = LOG_DIR   # self.settings_manager.get_log_dir()
            
            if not log_dir.exists():
                log_dir.mkdir(parents=True, exist_ok=True)
            
            import subprocess
            import platform
            
            log_dir_str = str(log_dir.resolve())
            
            system = platform.system()
            if system == "Windows":
                subprocess.run(["explorer", log_dir_str])
            elif system == "Darwin":
                subprocess.run(["open", log_dir_str])
            else:
                subprocess.run(["xdg-open", log_dir_str])
            
            self.settings_manager.log_system_event("browser_window", "Log directory opened", log_dir_str)
            
        except Exception as e:
            self.settings_manager.log_error("browser_window", f"Failed to open log directory: {str(e)}")
            # Fallback: show the path in a message box
            try:
                log_dir = self.settings_manager.get_log_dir()
                QMessageBox.information(self, "Log Location", f"Log directory:\n{log_dir}")
            except Exception:
                QMessageBox.warning(self, "Error", f"Failed to open logs: {str(e)}")

    def _get_settings_manager(self):
        """
        Return a usable settings manager. Handles older attribute names and fallbacks.
        """
        sm = getattr(self, "settings_manager", None) or getattr(self, "settings", None)
        if sm is not None:
            return sm
        # Last-resort: try importing your SettingsManager (adjust import if needed)
        try:
            from .settings import SettingsManager
            sm = SettingsManager()
            # cache so we don't do this again
            self.settings_manager = sm
            return sm
        except Exception as e:
            raise RuntimeError(f"Could not obtain settings manager: {e}")


    # =========================================================================
    # Public actions
    # =========================================================================

    def _initial_url(self) -> QUrl:
        """
        Pull a start URL from settings (try a few common keys),
        fall back to about:blank if none provided.
        """
        get = getattr(self.settings_manager, "get", None)
        val = None

        if callable(get):
            for key in ("start_url", "homepage", "home_url", "StartUrl", "HomePage"):
                try:
                    val = get(key)
                except Exception:
                    pass
                if val:
                    break

        if not val:
            # optional hardcoded fallback, change to whatever you want
            val = "https://example.com"

        q = QUrl.fromUserInput(val)
        return q if q.isValid() else QUrl("about:blank")

    def _get_tab_widget(self) -> QTabWidget:
        tw = getattr(self, "tab_widget", None)
        if isinstance(tw, QTabWidget):
            return tw
        # common legacy names
        for name in ("tabs", "tabWidget", "tabview"):
            tw = getattr(self, name, None)
            if isinstance(tw, QTabWidget):
                self.tab_widget = tw
                return tw
        # search children as fallback
        tw = self.findChild(QTabWidget)
        if isinstance(tw, QTabWidget):
            self.tab_widget = tw
            return tw
        # last resort: create one and set as central
        tw = QTabWidget(self)
        self.setCentralWidget(tw)
        self.tab_widget = tw
        tw.currentChanged.connect(lambda _: self._sync_urlbar_with_current_tab())
        return tw

    # def _get_current_tab(self):
    #     tw = self._get_tab_widget()
    #     container = tw.currentWidget()
    #     if not container:
    #         return None
    #     # BrowserTab is the direct child we added to the container
    #     return container.findChild(BrowserTab)

    def _sync_urlbar_with_current_tab(self):
        tab = self._get_current_tab()
        if tab and hasattr(self, "urlbar"):
            try:
                self.urlbar.setText(self._view_of(tab).url().toString())
            except Exception:
                pass

    def back(self, checked: bool = False):
        w = self._get_current_webview()
        if w: 
            w.back()

    def forward(self, checked: bool = False):
        w = self._get_current_webview()
        if w: 
            w.forward()

    def reload(self, checked: bool = False):
        w = self._get_current_webview()
        if w: 
            w.reload()

    def stop(self, checked: bool = False):
        w = self._get_current_webview()
        if w: 
            w.stop()

    def home(self):
        self.navigate_current(self.settings_manager.get("home_url", "about:blank"))

    # --- Public API for menu / shortcuts ----------------------------------------
    def create_new_tab(self, arg=None, *, switch: bool = True):
        """Create a new tab."""
        return self.tab_manager.new_tab(switch=switch)

    def _new_tab(self, url=None, switch=True, profile=None, background=False):
        """Internal tab creation."""
        return self.tab_manager._new_tab(url=url, switch=switch, profile=profile, background=background)

    def _get_current_tab(self):
        """Get current tab."""
        return self.tab_manager.get_current_tab()

    def _get_current_webview(self):
        """Get current webview."""
        return self.tab_manager.get_current_view()

    def open_url_in_new_tab(self, url, switch=True):
        """Open URL in new tab."""
        return self.tab_manager.open_url_in_new_tab(url, switch)

    def navigate_current(self, url):
        """Navigate current tab."""
        self.tab_manager.navigate_current(url)

    def create_tab_for_popup(self):
        """Create tab for popup."""
        return self.tab_manager.create_tab_for_popup()

    def _create_new_tab_and_return_view(self):
        """Create tab and return view (for window.open)."""
        return self.tab_manager._handle_new_window_request()


    def _update_tab_title(self, tab, title: str):
        i = self.tabs.indexOf(tab)
        if i != -1:
            self.tabs.setTabText(i, title if title else "New Tab")

    def _on_tab_title_changed(self, container, title: str):
        tw = self._get_tab_widget()
        i = tw.indexOf(container)
        if i != -1:
            tw.setTabText(i, title or "New Tab")
            tw.setTabToolTip(i, title or "")

    def _on_tab_url_changed(self, container, qurl: QUrl):
        # Update address bar ONLY if this is the CURRENT tab
        tw = self._get_tab_widget()
        if tw.currentWidget() is container and hasattr(self, "urlbar"):
            self.urlbar.setText(qurl.toString())

    def _on_urlbar_return_pressed(self):
        urlbar = self.toolbar_builder.urlbar
        if urlbar:
            text = urlbar.text().strip()
            if text:
                self.navigate_current(text)


    # Optional hooks; safe no-ops if you don't override them elsewhere
    def on_tab_load_started(self):  # pragma: no cover
        pass

    def on_tab_load_finished(self):  # pragma: no cover
        """Handle tab load completion, updating URL and title"""
        # Get current tab
        tab = self.tab_manager.get_current_tab()
        if not tab:
            return
            
        # Update URL bar with current URL
        current_url = tab.view.url()
        if hasattr(self.toolbar_builder, "urlbar") and self.toolbar_builder.urlbar:
            self.toolbar_builder.urlbar.setText(current_url.toString())
            
        # Update tab title if available
        current_title = tab.view.title()
        if current_title:
            index = self.tabs.currentIndex()
            if index >= 0:
                # Truncate long titles
                short_title = current_title[:20] + "..." if len(current_title) > 20 else current_title
                self.tabs.setTabText(index, short_title)

    def _on_url_changed(self, qurl: QUrl, tab: QWidget):
        # keep it quiet if you don't need anything here yet
        pass

    def closeEvent(self, event):
        # Persist geometry/state before closing
        self.save_window_geometry()
        super().closeEvent(event)


    # Logging helper
    def _log(self, msg: str, extra: str = ""):
        try:
            self.settings_manager.log_system_event("browser_window", msg, extra)
        except Exception:
            pass

    def _restore_window_state(self):
        """
        Restore window geometry/state from settings_manager, else from QSettings.
        """
        # 1) Try project settings_manager
        geom = self.settings_manager.get("window/geometry")
        state = self.settings_manager.get("window/state")

        restored = False
        if isinstance(geom, (bytes, bytearray, QByteArray)):
            try:
                self.restoreGeometry(QByteArray(geom))
                restored = True
            except Exception:
                pass
        elif isinstance(geom, str):
            # stored as hex/base64-like string; Qt can handle QByteArray.fromHex for pure hex,
            # but many managers just keep raw bytes repr. Safer: try latin-1 decode fallback.
            try:
                self.restoreGeometry(QByteArray(geom.encode("latin-1", "ignore")))
                restored = True
            except Exception:
                pass

        if isinstance(state, (bytes, bytearray, QByteArray)):
            try:
                self.restoreState(QByteArray(state))
            except Exception:
                pass
        elif isinstance(state, str):
            try:
                self.restoreState(QByteArray(state.encode("latin-1", "ignore")))
            except Exception:
                pass

        if restored:
            return  # done

        # 2) Fallback to QSettings (org/app names can be anything stable)
        try:
            qs = QSettings("qwsengine", "QtBrowser")
            g = qs.value("window/geometry", None)
            s = qs.value("window/state", None)
            if isinstance(g, QByteArray):
                self.restoreGeometry(g)
            if isinstance(s, QByteArray):
                self.restoreState(s)
        except Exception:
            pass

    def _persist_window_state(self):
        """
        Save window geometry/state to settings_manager (and QSettings as a safe fallback).
        """
        try:
            g = self.saveGeometry()  # QByteArray
            s = self.saveState()     # QByteArray
        except Exception:
            return

        # 1) Project settings manager
        try:
            self.settings_manager.set("window/geometry", bytes(g))  # store as bytes
            self.settings_manager.set("window/state", bytes(s))
        except Exception:
            pass

        # 2) QSettings fallback
        try:
            qs = QSettings("qwsengine", "QtBrowser")
            qs.setValue("window/geometry", g)
            qs.setValue("window/state", s)
        except Exception:
            pass

    def open_settings(self):
        try:
            self.settings_manager.log_system_event("browser_window", "Settings dialog opening...")
            dialog = SettingsDialog(self, self.settings_manager)
            self.settings_manager.log_system_event("browser_window", "Settings dialog created")
            result = dialog.exec()
            if result == QDialog.Accepted:
                self.settings_manager.log_system_event("browser_window", "Settings saved")
            else:
                self.settings_manager.log_system_event("browser_window", "Settings dialog cancelled")
        except Exception as e:
            self.settings_manager.log_error("browser_window", f"Failed to open settings dialog: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to open settings: {str(e)}")


# --- Script methods -----------------------------------
    def _load_script_list(self):
        """Populate the scripts combo with all *.js files under the scripts folder."""
        try:
            if not hasattr(self, "scripts_combo"):
                return  # toolbar not built yet

            self.scripts_dir.mkdir(parents=True, exist_ok=True)
            js_files = sorted([p for p in self.scripts_dir.glob("*.js") if p.is_file()], key=lambda p: p.name.lower())

            self.scripts_combo.blockSignals(True)
            self.scripts_combo.clear()
            for p in js_files:
                # store full path as userData, display only filename
                self.scripts_combo.addItem(p.name, userData=str(p))
            self.scripts_combo.blockSignals(False)

            self.show_status(f"Scripts loaded: {len(js_files)} file(s)", level="INFO")
            self.settings_manager.log_system_event("browser_window", "Scripts list refreshed", f"{self.scripts_dir}")
        except Exception as e:
            self.show_status(f"Failed to load scripts: {e}", level="ERROR")
            self.settings_manager.log_error("browser_window", f"Load scripts failed: {e}")

    def refresh_scripts_list(self):
        """Refresh button handler."""
        self._load_script_list()

    def execute_selected_script(self):
        """Load the selected .js file into the page, then call its default function (filename without .js)."""
        try:
            current = self.tabs.currentWidget()
            if not current:
                self.show_status("No active tab to execute against.", level="WARNING")
                return
            _isLoadedAttr = hasattr(current, "is_loaded")
            _isLoaded = current.is_loaded()
            if hasattr(current, "is_loaded") and not current.is_loaded():
                self.show_status("Page still loading… try again when it finishes.", level="WARNING")
                return

            idx = self.scripts_combo.currentIndex() if hasattr(self, "scripts_combo") else -1
            if idx < 0:
                self.show_status("No script selected.", level="WARNING")
                return

            path_str = self.scripts_combo.currentData()
            if not path_str:
                self.show_status("Invalid script selection.", level="ERROR")
                return

            path = Path(path_str)
            if not path.exists():
                self.show_status(f"Script not found: {path.name}", level="ERROR")
                return

            # Read JS source
            try:
                js_source = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                js_source = path.read_text(encoding="utf-8-sig")

            # Derive default function name from file name
            func_name = self._derive_function_name_from_file(path.name)

            self.show_status(f"Executing: {path.name} → {func_name}()", level="INFO")
            page = current.browser.page()

            # Step 1: inject/execute the script source so its function is defined in page context
            def after_inject(_result):
                # Step 2: call the derived function if present
                call_code = f"""
                    (function() {{
                        try {{
                            var fn = window["{func_name}"];
                            if (typeof fn === "function") {{
                                return fn();
                            }}
                            return "__NOFUNC__:{func_name}";
                        }} catch (e) {{
                            return "__ERR__:" + (e && e.message ? e.message : String(e));
                        }}
                    }})();
                """
                page.runJavaScript(call_code, self._on_script_executed(path.name, func_name))

            page.runJavaScript(js_source, after_inject)

        except Exception as e:
            self.show_status(f"Execute failed: {e}", level="ERROR")
            self.settings_manager.log_error("browser_window", f"Execute script failed: {e}")

    def _derive_function_name_from_file(self, filename: str) -> str:
        """
        Convert a file name like 'hello-world 01.js' -> 'hello_world_01'
        so we can call window[funcName]().
        """
        stem = filename
        if stem.lower().endswith(".js"):
            stem = stem[:-3]
        # Replace invalid JS identifier chars with underscores
        import re
        func = re.sub(r"[^A-Za-z0-9_]", "_", stem)
        # Identifiers can't start with a digit; prefix underscore if needed
        if func and func[0].isdigit():
            func = "_" + func
        # Avoid empty name
        return func or "script"

    def _on_script_executed(self, script_name: str, func_name: str):
        """Create a callback capturing the script & function name for post-execution status/log."""
        def cb(result):
            try:
                if isinstance(result, str) and result.startswith("__NOFUNC__:"):
                    missing = result.split(":", 1)[1] if ":" in result else func_name
                    self.show_status(f"No function named {missing}() found after loading {script_name}.", level="ERROR")
                    self.settings_manager.log_error("browser_window", f"Script function missing: {missing} in {script_name}")
                    return
                if isinstance(result, str) and result.startswith("__ERR__:"):
                    msg = result.split(":", 1)[1] if ":" in result else "Unknown error"
                    self.show_status(f"{func_name}() threw: {msg}", level="ERROR")
                    self.settings_manager.log_error("browser_window", f"Script error {script_name}/{func_name}: {msg}")
                    return

                # Success (result may be None if the function returns nothing)
                preview = ""
                if result is not None:
                    text = str(result)
                    if len(text) > 120:
                        text = text[:117] + "..."
                    preview = f" (result: {text})"
                self.show_status(f"Executed {func_name}() from {script_name}{preview}", level="INFO")
                self.settings_manager.log_system_event("browser_window", "Script executed", f"{script_name} -> {func_name}()")
            except Exception as e:
                self.show_status(f"Execution callback error: {e}", level="ERROR")
                self.settings_manager.log_error("browser_window", f"Script callback error: {e}", script_name)
        return cb

    def open_scripts_folder(self):
        """Open the scripts directory in the OS file manager."""
        try:
            # Ensure folder exists
            self.scripts_dir.mkdir(parents=True, exist_ok=True)
            folder = str(self.scripts_dir.resolve())

            system = platform.system()
            if system == "Windows":
                subprocess.run(["explorer", folder])
            elif system == "Darwin":  # macOS
                subprocess.run(["open", folder])
            else:  # Linux / BSD
                subprocess.run(["xdg-open", folder])

            self.show_status(f"Opened scripts folder → {folder}", level="INFO")
            self.settings_manager.log_system_event("browser_window", "Scripts folder opened", folder)
        except Exception as e:
            self.show_status(f"Failed to open scripts folder: {e}", level="ERROR")
            self.settings_manager.log_error("browser_window", f"Open scripts folder failed: {e}")

    def _user_agent_from_settings(self) -> str | None:
        get = getattr(self.settings_manager, "get", None)
        if not callable(get):
            return None
        for key in ("user_agent", "UserAgent", "userAgent", "ua"):
            try:
                val = get(key)
            except Exception:
                val = None
            if val:
                s = str(val).strip()
                if s:
                    return s
        return None

    def _apply_user_agent_to_profile(self, profile):
        ua = self._user_agent_from_settings()
        if ua and profile.httpUserAgent() != ua:
            profile.setHttpUserAgent(ua)

    # --- Geometry/state (safe JSON via base64) ---------------------------------
    def _qba_to_b64(self, qba: QByteArray) -> str:
        # QByteArray -> base64 ascii string
        return bytes(qba.toBase64()).decode("ascii")

    def _b64_to_qba(self, s: str) -> QByteArray:
        # base64 ascii string -> QByteArray
        return QByteArray.fromBase64(s.encode("ascii"))

    def save_window_geometry(self):
        try:
            geom_b64 = self._qba_to_b64(self.saveGeometry())
            state_b64 = self._qba_to_b64(self.saveState())
            self.settings_manager.set("window_geometry_b64", geom_b64)
            self.settings_manager.set("window_state_b64", state_b64)
            url = self.settings_manager.settings['start_url']
            #self.settings_manager.save()
            self.settings_manager.log("[SYSTEM] Window geometry/state saved cleanly", "SYSTEM")
        except Exception as e:
            self.settings_manager.log_error("browser_window", f"Failed to save geometry/state: {e}")

    def restore_window_geometry(self):
        try:
            # Prefer new base64 keys
            g_b64 = self.settings_manager.get("window_geometry_b64", "")
            s_b64 = self.settings_manager.get("window_state_b64", "")

            # Back-compat: if old raw-bytes keys exist, try to use them without touching settings.json
            if not g_b64:
                old_g = self.settings_manager.get("window_geometry")
                if isinstance(old_g, (bytes, bytearray)):
                    self.restoreGeometry(QByteArray(old_g))
            if not s_b64:
                old_s = self.settings_manager.get("window_state")
                if isinstance(old_s, (bytes, bytearray)):
                    self.restoreState(QByteArray(old_s))

            if isinstance(g_b64, str) and g_b64:
                self.restoreGeometry(self._b64_to_qba(g_b64))
            if isinstance(s_b64, str) and s_b64:
                self.restoreState(self._b64_to_qba(s_b64))
        except Exception as e:
            self.settings_manager.log_error("browser_window", f"Failed to restore geometry/state: {e}")

# --- Optional manual run for smoke testing -----------------------------------
if __name__ == "__main__":  # pragma: no cover
    import sys

    app = QApplication(sys.argv)
    #win = BrowserWindow()
    win.show()
    sys.exit(app.exec())