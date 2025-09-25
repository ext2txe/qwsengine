# qwsengine/main_window.py
from __future__ import annotations
import os
from pathlib import Path

from datetime import datetime
from typing import Optional, Union

from PySide6.QtCore import QUrl, Qt, QSize, QRect, QByteArray, QSettings, QTimer
from PySide6.QtGui import QAction, QPainter, QImage, QIcon, QKeySequence
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
)

# Import your tab widget (your traceback shows browser_tab.py)
from .browser_tab import BrowserTab
from .safe_settings import _SafeSettings
from .settings import SettingsManager
from .settings_dialog import SettingsDialog


# WebView is referenced for type/behavior expectations; actual class is in BrowserTab.browser
try:
    from .webview import WebView  # noqa: F401
except ImportError:
    # Don't hard-fail here; BrowserTab will own the actual WebView instance.
    pass



class BrowserWindow(QMainWindow):
    """
    Main application window with tabbed browsing.

    Design:
      - Single source of truth for tab creation: _new_tab()
      - _blank/window.open() handled by WebView.createWindow via:
            tab.browser.set_create_window_handler(self._create_new_tab_and_return_view)
      - Optional legacy newTabRequested(QUrl) routed to open_url_in_new_tab()
    """

    def __init__(self, settings_manager=None, parent: Optional[QWidget] = None):
        super().__init__(parent)

        # Wrap provided settings manager (can be None) with a safe shim
        #self.settings_manager = _SafeSettings(settings_manager)
        self.settings_manager = SettingsManager()

        self.setWindowTitle("Qt Browser")
        self.resize(1200, 800)

        self._setup_ui()

        # Scripts folder under app config
        self.scripts_dir = self.settings_manager.config_dir / "scripts"
        self.scripts_dir.mkdir(parents=True, exist_ok=True)

        # Populate the combo at startup
        self._load_script_list()


    def _setup_ui(self):
        # --- Central layout with tabs --------------------------------------------
        central = QWidget(self)
        self.setCentralWidget(central)

        vbox = QVBoxLayout(central)
        vbox.setContentsMargins(0, 0, 0, 0)

        # ---Menu  ---------------------------------------------------
        menu_bar = self._create_menu_bar()
        vbox.addWidget(menu_bar)

        # --- Create Tool bar ---------------------------------------------------
        toolbar = self._create_tool_bar()
        vbox.addWidget(toolbar)

        # q. how to get menu above the nav tool bar?
        #vbox.add

        # --- Create Tabs ---------------------------------------------------
        self.tabs = QTabWidget(self)
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self._on_tab_close_requested)
        self.tabs.currentChanged.connect(self._on_current_tab_changed)
        vbox.addWidget(self.tabs)

        # --- Create Status bar ---------------------------------------------------
        self.status_bar = QStatusBar(self)
        vbox.addWidget(self.status_bar)

        self._restore_window_state()

        # Initial tab
        self._create_initial_tab()

    def _create_tool_bar(self):
        tb = QToolBar("Main Toolbar", self)

        # Save HTML action
        save_html_action = QAction("Save HTML", self)
        save_html_action.setToolTip("Save the current tab's Document HTML")
        save_html_action.triggered.connect(self.save_current_tab_html)
        tb.addAction(save_html_action)

        #Save Screenshot (visible area)
        save_shot_action = QAction("Save Screenshot", self)
        save_shot_action.setToolTip("Save a PNG screenshot of the current tab's visible page")
        save_shot_action.triggered.connect(self.save_current_tab_screenshot)
        tb.addAction(save_shot_action)

        save_full_action = QAction("Save Full Page", self)
        save_full_action.setToolTip("Capture the entire page (beyond viewport) as PNG")
        save_full_action.triggered.connect(self.save_full_page_screenshot)
        tb.addAction(save_full_action)

        # ------------------ NEW: Scripts combo + buttons ------------------
        tb.addSeparator()

        # Script picker
        self.scripts_combo = QComboBox(tb)
        self.scripts_combo.setMinimumWidth(240)
        tb.addWidget(self.scripts_combo)

        # Refresh list
        refresh_scripts_action = QAction("Refresh", self)
        refresh_scripts_action.setToolTip("Reload the list of .js files from the scripts folder")
        refresh_scripts_action.triggered.connect(self.refresh_scripts_list)
        tb.addAction(refresh_scripts_action)

        # Execute selected
        exec_script_action = QAction("Execute", self)
        exec_script_action.setToolTip("Execute the selected JavaScript file in the current page")
        exec_script_action.triggered.connect(self.execute_selected_script)
        tb.addAction(exec_script_action)

        # Open Scripts Folder
        open_scripts_action = QAction("Open Scripts Folder", self)
        open_scripts_action.setToolTip("Open the scripts directory in your file manager")
        open_scripts_action.triggered.connect(self.open_scripts_folder)
        tb.addAction(open_scripts_action)
        

        return tb

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

    def save_current_tab_html(self):
        try:
            current = self.tabs.currentWidget()
            if not current:
                QMessageBox.information(self, "No Tab", "There is no active tab to save.")
                return
            if not current.is_loaded():
                QMessageBox.warning(self, "Page Loading", "Wait until the page finishes loading before saving.")
                return

            save_dir = self.settings_manager.config_dir / "save"
            save_dir.mkdir(parents=True, exist_ok=True)

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            title = current.browser.title() or current.browser.url().host() or "page"
            safe_title = "".join(ch for ch in title if ch.isalnum() or ch in ("-", "_")).strip() or "page"
            target = save_dir / f"{ts}_{safe_title}.html"

            def _write_html(html: str):
                try:
                    target.write_text(html, encoding="utf-8")
                    self.show_status(f"Saved HTML → {target}", level="INFO")
                except Exception as e:
                    self.show_status(f"Failed to write HTML: {e}", level="ERROR")

            current.get_html(_write_html)

        except Exception as e: 
            self.settings_manager.log_error(f"Save HTML failed: {e}")

    def save_current_tab_screenshot(self):
        try:
            current = self.tabs.currentWidget()
            if not current:
                self.show_status("No active tab to capture.", level="WARNING")
                return

            # Optional: require page loaded (you can remove this if you want to allow mid-load)
            if hasattr(current, "is_loaded") and not current.is_loaded():
                self.show_status("Page still loading… try again when it finishes.", level="WARNING")
                return

            view = getattr(current, "browser", None)
            if view is None:
                self.show_status("No browser view found in current tab.", level="ERROR")
                return

            # Grab the visible widget area (viewport)
            pixmap = view.grab()  # QWidget.grab(): returns QPixmap of visible area

            save_dir = self.settings_manager.config_dir / "save"
            save_dir.mkdir(parents=True, exist_ok=True)

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            title = view.title() or view.url().host() or "page"
            safe_title = "".join(ch for ch in title if ch.isalnum() or ch in ("-", "_")).strip() or "page"
            target = save_dir / f"{ts}_{safe_title}.png"

            if pixmap.isNull():
                self.show_status("Screenshot failed (empty pixmap).", level="ERROR")
                return

            if not pixmap.save(str(target), "PNG"):
                self.show_status("Failed to save screenshot.", level="ERROR")
                return

            self.show_status(f"Saved Screenshot → {target}", level="INFO")

        except Exception as e:
            self.show_status(f"Screenshot failed: {e}", level="ERROR")

    # =========================================================================
    # full page screenshot
    # =========================================================================
    def save_full_page_screenshot(self):
        """Capture the entire scrollable page to a single PNG (stitched tiles)."""
        try:
            current = self.tabs.currentWidget()
            if not current:
                self.show_status("No active tab to capture.", level="WARNING")
                return
            if hasattr(current, "is_loaded") and not current.is_loaded():
                self.show_status("Page still loading… try again when it finishes.", level="WARNING")
                return

            page = current.browser.page()

            # Where to save
            save_dir = self.settings_manager.config_dir / "save"
            save_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            title = current.browser.title() or current.browser.url().host() or "page"
            safe_title = "".join(ch for ch in title if ch.isalnum() or ch in ("-", "_")).strip() or "page"
            target = save_dir / f"{ts}_{safe_title}_fullpage.png"

            # Disallow re-entry
            if getattr(self, "_fps_busy", False):
                self.show_status("Full-page capture already in progress…", level="WARNING")
                return
            self._fps_busy = True
            self._fps_target = target
            self._fps_tab = current

            # Modified JavaScript - returns JSON string instead of object
            js = """
            (function() {
                try {
                    var e = document.documentElement;
                    var b = document.body;
                    
                    var totalWidth = Math.max(
                        e ? e.scrollWidth || 0 : 0,
                        b ? b.scrollWidth || 0 : 0
                    );
                    var totalHeight = Math.max(
                        e ? e.scrollHeight || 0 : 0,
                        b ? b.scrollHeight || 0 : 0
                    );
                    var viewportWidth = window.innerWidth || 0;
                    var viewportHeight = window.innerHeight || 0;
                    var dpr = window.devicePixelRatio || 1;
                    
                    var result = {
                        totalWidth: totalWidth,
                        totalHeight: totalHeight,
                        viewportWidth: viewportWidth,
                        viewportHeight: viewportHeight,
                        dpr: dpr
                    };
                    
                    return JSON.stringify(result);
                    
                } catch (err) {
                    return JSON.stringify({error: err.toString()});
                }
            })();
            """
            
            self.show_status("Measuring page for full capture…", level="INFO")
            QTimer.singleShot(1000, lambda: page.runJavaScript(js, self._fps_start))

        except Exception as e:
            self._fps_fail(f"Full-page capture failed: {e}")
            self._fps_reset()

    def _fps_start(self, metrics_json):
        """Initialize stitching based on JS metrics and kick off the first tile."""
        try:
            print(f"DEBUG: Raw JSON: '{metrics_json}'")
            
            if not metrics_json or metrics_json == '':
                self._fps_fail("JavaScript returned empty result.")
                self._fps_reset()
                return

            # Parse JSON string to get the metrics object
            try:
                import json
                metrics = json.loads(metrics_json)
            except (json.JSONDecodeError, TypeError) as e:
                self._fps_fail(f"Could not parse JavaScript result: {e}")
                self._fps_reset()
                return
            
            print(f"DEBUG: Parsed metrics: {metrics}")
            
            # Check for JavaScript errors
            if 'error' in metrics:
                self._fps_fail(f"JavaScript error: {metrics['error']}")
                self._fps_reset()
                return

            tw = int(metrics.get("totalWidth", 0))
            th = int(metrics.get("totalHeight", 0))
            vw = int(metrics.get("viewportWidth", 0))
            vh = int(metrics.get("viewportHeight", 0))
            dpr = float(metrics.get("dpr", 1.0))

            if not (tw and th and vw and vh):
                self._fps_fail("Invalid page metrics.")
                self._fps_reset()
                return

            # Rest of your existing code unchanged...
            w_px = int(tw * dpr)
            h_px = int(th * dpr)
            self._fps_img = QImage(w_px, h_px, QImage.Format_ARGB32)
            self._fps_img.fill(0)
            self._fps_painter = QPainter(self._fps_img)

            cols = (tw + vw - 1) // vw
            rows = (th + vh - 1) // vh
            positions = []
            for r in range(rows):
                for c in range(cols):
                    x = c * vw
                    y = r * vh
                    positions.append((x, y))
            self._fps_positions = positions
            self._fps_dpr = dpr
            self._fps_vw = vw
            self._fps_vh = vh
            self._fps_tw = tw
            self._fps_th = th

            self.show_status(f"Capturing full page {tw}×{th}px ({len(positions)} tiles)…", level="INFO")
            self._fps_next_tile()

        except Exception as e:
            self._fps_fail(f"Init error: {e}")
            self._fps_reset()

    def _fps_next_tile(self):
        """Scroll to next tile and schedule a grab of the visible widget."""
        try:
            if not self._fps_positions:
                self._fps_finish()
                return

            x, y = self._fps_positions.pop(0)
            # Progress ping
            total = (self._fps_tw + self._fps_vh - 1) // self._fps_vh * ((self._fps_tw + self._fps_vw - 1) // self._fps_vw)
            done = total - len(self._fps_positions)
            self.show_status(f"Capturing tile {done}/{total}…", level="INFO")

            js_scroll = f"window.scrollTo({x}, {y}); true;"
            page = self._fps_tab.browser.page()
            page.runJavaScript(js_scroll, lambda _: QTimer.singleShot(120, lambda: self._fps_grab_tile(x, y)))

        except Exception as e:
            self._fps_fail(f"Tile error: {e}")
            self._fps_reset()

    def _fps_grab_tile(self, x, y):
        """Grab current viewport and paint it to the stitched image at (x,y)."""
        try:
            view = self._fps_tab.browser
            pm = view.grab()  # QPixmap of *visible* widget

            if pm.isNull():
                self._fps_fail("Grabbed empty frame.")
                self._fps_reset()
                return

            # Convert to QImage in device pixels (neutralize devicePixelRatio for reliable math)
            try:
                pm.setDevicePixelRatio(1.0)
            except Exception:
                pass
            img = pm.toImage()

            dpr = self._fps_dpr
            vw, vh = self._fps_vw, self._fps_vh
            tw, th = self._fps_tw, self._fps_th

            dest_x = int(x * dpr)
            dest_y = int(y * dpr)

            # Visible pixmap in *device pixels*
            src_w = img.width()
            src_h = img.height()

            # Clip on right/bottom edges (last tiles)
            remain_w = int(tw * dpr) - dest_x
            remain_h = int(th * dpr) - dest_y
            copy_w = src_w if src_w < remain_w else remain_w
            copy_h = src_h if src_h < remain_h else remain_h

            if copy_w > 0 and copy_h > 0:
                self._fps_painter.drawImage(
                    QRect(dest_x, dest_y, copy_w, copy_h),
                    img,
                    QRect(0, 0, copy_w, copy_h)
                )

            # Next tile
            self._fps_next_tile()

        except Exception as e:
            self._fps_fail(f"Grab error: {e}")
            self._fps_reset()

    def _fps_finish(self):
        """All tiles captured: finalize and save."""
        try:
            self._fps_painter.end()
            ok = self._fps_img.save(str(self._fps_target), "PNG")
            if not ok:
                self._fps_fail("Failed to save stitched image.")
            else:
                self.show_status(f"Saved Full Page → {self._fps_target}", level="INFO")
        except Exception as e:
            self._fps_fail(f"Save error: {e}")
        finally:
            self._fps_reset()

    def _fps_fail(self, msg: str):
        self.show_status(msg, level="ERROR")

    def _fps_reset(self):
        # Clean up capture state
        for attr in ("_fps_busy", "_fps_img", "_fps_painter", "_fps_positions", "_fps_dpr",
                    "_fps_vw", "_fps_vh", "_fps_tw", "_fps_th", "_fps_target", "_fps_tab"):
            if hasattr(self, attr):
                setattr(self, attr, None)
        self._fps_busy = False

    def show_status(self, message: str, timeout_ms: int = 5000, level: str = "INFO"):
        """
        Show a transient message in the status bar and log it.
        level: "INFO" | "WARNING" | "ERROR"
        """
        if hasattr(self, "status_bar"):
            self.status_bar.showMessage(message, timeout_ms)

        # Log alongside showing it
        if level == "ERROR":
            self.settings_manager.log_error(message)
        elif level == "WARNING":
            self.settings_manager.log_system_event("Warning", message)
        else:
            self.settings_manager.log_system_event("Status", message)

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



    # =========================================================================
    # Public actions
    # =========================================================================
    def create_new_tab(self):
        """Create an empty tab from menu/toolbar."""
        self._new_tab(switch=True)
        self._log("New tab created from menu")

    def open_url_in_new_tab(self, url: Union[QUrl, str]):
        """
        Open the given URL in a fresh tab. Accepts QUrl or str.
        Also used by optional WebView.newTabRequested(QUrl).
        """
        from PySide6.QtCore import QUrl as _QUrl

        tab = self._new_tab(switch=True)

        # Normalize URL
        qurl = url if isinstance(url, _QUrl) else _QUrl(str(url))
        if not qurl.isValid():
            qurl = self._normalize_to_url(str(url))

        # Load
        self._load_in_tab(tab, qurl)
        self._log("New tab created (open_url_in_new_tab)", qurl.toString())
        return tab

    def close_current_tab(self):
        idx = self.tabs.currentIndex()
        if idx >= 0:
            w = self.tabs.widget(idx)
            self.tabs.removeTab(idx)
            if w:
                w.deleteLater()

    def back(self):
        tab = self._get_current_tab()
        if tab and hasattr(tab, "browser"):
            try:
                tab.browser.back()
            except Exception:
                pass

    def forward(self):
        tab = self._get_current_tab()
        if tab and hasattr(tab, "browser"):
            try:
                tab.browser.forward()
            except Exception:
                pass

    def reload(self):
        tab = self._get_current_tab()
        if tab and hasattr(tab, "browser"):
            try:
                tab.browser.reload()
            except Exception:
                pass

    def home(self):
        self.navigate_current(self.settings_manager.get("home_url", "about:blank"))

    def navigate_current(self, url: Union[str, QUrl]):
        tab = self._get_current_tab()
        if not tab:
            tab = self._new_tab(switch=True)
        qurl = url if isinstance(url, QUrl) else self._normalize_to_url(url)
        self._load_in_tab(tab, qurl)

    # =========================================================================
    # Internal wiring and helpers
    # =========================================================================
    def _create_initial_tab(self):
        """Create the very first tab (blank)."""
        self._new_tab(switch=True)

    def _get_current_tab(self):
        """Return the current BrowserTab or None."""
        w = self.tabs.currentWidget()
        return w if w and hasattr(w, "browser") else None

    def _wire_tab(self, tab):
        """
        Connect signals and wire WebView so target=_blank/window.open() creates a real tab.
        Call this exactly once for every new tab.
        """
        # Optional signals provided by BrowserTab
        try:
            tab.loadStarted.connect(self.on_tab_load_started)
        except Exception:
            pass
        try:
            tab.loadFinished.connect(self.on_tab_load_finished)
        except Exception:
            pass

        # Critical: provide a factory for QWebEngineView.createWindow()
        if hasattr(tab, "browser") and hasattr(tab.browser, "set_create_window_handler"):
            tab.browser.set_create_window_handler(self._create_new_tab_and_return_view)

        # Optional legacy: signal-based new tab requests
        if hasattr(tab, "browser") and hasattr(tab.browser, "newTabRequested"):
            tab.browser.newTabRequested.connect(self.open_url_in_new_tab)

        # Keep URL bar in sync if possible
        try:
            tab.browser.urlChanged.connect(self._on_browser_url_changed)
        except Exception:
            pass

        # Keep tab title in sync
        try:
            tab.browser.titleChanged.connect(self._on_browser_title_changed)
        except Exception:
            pass

    def _new_tab(self, url: Optional[str] = None, switch: bool = True):
        """
        Create a new BrowserTab, wire it, optionally load a URL, and add to the QTabWidget.
        Returns the new BrowserTab.
        """
        # IMPORTANT: pass the *shimmed* settings manager, never None
        tab = BrowserTab(self.tabs, settings_manager=self.settings_manager)
        self._wire_tab(tab)

        idx = self.tabs.addTab(tab, "New Tab")
        if switch:
            self.tabs.setCurrentIndex(idx)

        if url:
            try:
                if hasattr(tab, "navigate"):
                    tab.navigate(url)
                else:
                    tab.browser.load(self._normalize_to_url(url))
            except Exception:
                pass
        return tab

    def _create_new_tab_and_return_view(self):
        """
        Factory handed to WebView.createWindow().
        Must return the *WebView* of a brand new tab for Qt to load into.
        """
        new_tab = self._new_tab(switch=True)  # no URL; Qt navigates this view
        return new_tab.browser

    def _load_in_tab(self, tab, qurl: QUrl):
        """Load a QUrl into the given tab using whichever API is available."""
        try:
            tab.browser.load(qurl)
        except Exception:
            try:
                tab.navigate(qurl.toString())
            except Exception:
                pass

    def _normalize_to_url(self, text: str) -> QUrl:
        """Best-effort conversion of user text to a QUrl."""
        text = (text or "").strip()
        if not text:
            return QUrl("about:blank")

        url = QUrl(text)
        if url.isValid() and not url.scheme():
            url.setScheme("http")
        if not url.isValid():
            # Treat as a search query (basic fallback)
            url = QUrl("https://www.google.com/search?q=" + QUrl.toPercentEncoding(text).data().decode("utf-8"))
        return url

    def _on_tab_close_requested(self, index: int):
        if index < 0:
            return
        w = self.tabs.widget(index)
        self.tabs.removeTab(index)
        if w:
            w.deleteLater()

    def _on_current_tab_changed(self, index: int):
        tab = self._get_current_tab()
        if not tab:
            self.urlbar.clear()
            return
        try:
            current_url = tab.browser.url()
            if isinstance(current_url, QUrl):
                self.urlbar.setText(current_url.toString())
        except Exception:
            pass

    def _on_browser_url_changed(self, qurl: QUrl):
        # Update URL bar only when the active tab changes URL
        current = self._get_current_tab()
        if current and self.sender() == getattr(current, "browser", None):
            self.urlbar.setText(qurl.toString())

    def _on_browser_title_changed(self, title: str):
        idx = self.tabs.currentIndex()
        if idx >= 0:
            self.tabs.setTabText(idx, title if title else "New Tab")

    def _on_urlbar_return_pressed(self):
        text = self.urlbar.text()
        if not text:
            return
        self.navigate_current(text)

    # Optional hooks; safe no-ops if you don't override them elsewhere
    def on_tab_load_started(self):  # pragma: no cover
        pass

    def on_tab_load_finished(self):  # pragma: no cover
        pass

    def closeEvent(self, event):
        # Persist geometry/state before closing
        self._persist_window_state()
        try:
            super().closeEvent(event)
        except Exception:
            # If a parent class doesn’t implement it, we’re fine
            pass

    # Logging helper
    def _log(self, msg: str, extra: str = ""):
        try:
            self.settings_manager.log_system_event(msg, extra)
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


    # def open_settings(self):
    #     """
    #     Open the app's Settings UI.

    #     Priority:
    #     1) Call a settings_manager method if available (open/show dialog)
    #     2) Fall back to a local SettingsDialog class, if present
    #     3) Otherwise inform the user
    #     """
    #     # 1) Try settings_manager-provided dialogs
    #     for attr in ("open_settings", "show_settings", "open_settings_dialog", "show_settings_dialog"):
    #         fn = getattr(self.settings_manager, attr, None)
    #         if callable(fn):
    #             try:
    #                 # Prefer passing parent=self if supported
    #                 try:
    #                     fn(parent=self)
    #                 except TypeError:
    #                     fn()
    #                 return
    #             except Exception:
    #                 pass

    #     # 2) Try a local dialog class
    #     try:
    #         from .settings_dialog import SettingsDialog  # adjust path/name if your dialog differs
    #         try:
    #             dlg = SettingsDialog(self.settings_manager, parent=self)
    #         except TypeError:
    #             # Some dialogs may not accept settings in ctor
    #             dlg = SettingsDialog(parent=self)
    #         # exec_ for PyQt5, exec for PySide6
    #         if hasattr(dlg, "exec"):
    #             dlg.exec()
    #         else:
    #             dlg.exec_()
    #         return
    #     except Exception:
    #         pass

    #     # 3) Last resort
    #     try:
    #         QMessageBox.information(self, "Settings", "Settings UI is not available in this build.")
    #     except Exception:
    #         pass

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
            self.settings_manager.log_system_event("Scripts list refreshed", f"{self.scripts_dir}")
        except Exception as e:
            self.show_status(f"Failed to load scripts: {e}", level="ERROR")
            self.settings_manager.log_error(f"Load scripts failed: {e}")

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
            self.settings_manager.log_error(f"Execute script failed: {e}")

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
                    self.settings_manager.log_error(f"Script function missing: {missing} in {script_name}")
                    return
                if isinstance(result, str) and result.startswith("__ERR__:"):
                    msg = result.split(":", 1)[1] if ":" in result else "Unknown error"
                    self.show_status(f"{func_name}() threw: {msg}", level="ERROR")
                    self.settings_manager.log_error(f"Script error {script_name}/{func_name}: {msg}")
                    return

                # Success (result may be None if the function returns nothing)
                preview = ""
                if result is not None:
                    text = str(result)
                    if len(text) > 120:
                        text = text[:117] + "..."
                    preview = f" (result: {text})"
                self.show_status(f"Executed {func_name}() from {script_name}{preview}", level="INFO")
                self.settings_manager.log_system_event("Script executed", f"{script_name} -> {func_name}()")
            except Exception as e:
                self.show_status(f"Execution callback error: {e}", level="ERROR")
                self.settings_manager.log_error(f"Script callback error: {e}", script_name)
        return cb


    def open_scripts_folder(self):
        """Open the scripts directory in the OS file manager."""
        try:
            # Ensure folder exists
            self.scripts_dir.mkdir(parents=True, exist_ok=True)
            folder = str(self.scripts_dir.resolve())

            import platform, subprocess
            system = platform.system()
            if system == "Windows":
                subprocess.run(["explorer", folder])
            elif system == "Darwin":  # macOS
                subprocess.run(["open", folder])
            else:  # Linux / BSD
                subprocess.run(["xdg-open", folder])

            self.show_status(f"Opened scripts folder → {folder}", level="INFO")
            self.settings_manager.log_system_event("Scripts folder opened", folder)
        except Exception as e:
            self.show_status(f"Failed to open scripts folder: {e}", level="ERROR")
            self.settings_manager.log_error(f"Open scripts folder failed: {e}")



# --- Optional manual run for smoke testing -----------------------------------
if __name__ == "__main__":  # pragma: no cover
    import sys

    app = QApplication(sys.argv)
    win = BrowserWindow()
    win.show()
    sys.exit(app.exec())
