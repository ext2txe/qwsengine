# qwsengine/main_window.py
from __future__ import annotations

from typing import Optional, Union

from PySide6.QtCore import QUrl, Qt, QSize, QByteArray, QSettings
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QTabWidget,
    QToolBar,
    QLineEdit,
    QVBoxLayout,
    QApplication,
)

# Import your tab widget (your traceback shows browser_tab.py)
from .browser_tab import BrowserTab

# WebView is referenced for type/behavior expectations; actual class is in BrowserTab.browser
try:
    from .webview import WebView  # noqa: F401
except ImportError:
    # Don't hard-fail here; BrowserTab will own the actual WebView instance.
    pass


# ---------------------------------------------------------------------------
# Safe settings shim
# ---------------------------------------------------------------------------
class _SafeSettings:
    def __init__(self, backing=None):
        self._b = backing

    # reads
    def get(self, key, default=None):
        if self._b is None:
            return default
        getter = getattr(self._b, "get", None) or getattr(self._b, "value", None)
        if callable(getter):
            try:
                return getter(key, default)
            except Exception:
                return default
        try:
            return self._b[key] if key in self._b else default
        except Exception:
            return default

    # writes
    def set(self, key, value):
        if self._b is None:
            return
        setter = getattr(self._b, "set", None) or getattr(self._b, "setValue", None)
        if callable(setter):
            try:
                setter(key, value)
            except Exception:
                pass

    # existing logging helpers (keep yours)
    def log_system_event(self, msg, extra=""):
        fn = getattr(self._b, "log_system_event", None)
        if callable(fn):
            try: fn(msg, extra)
            except Exception: pass

    def log_tab_action(self, action, tab_id, details=""):
        fn = getattr(self._b, "log_tab_action", None)
        if callable(fn):
            try: fn(action, tab_id, details)
            except Exception: pass

    def __getattr__(self, name):
        if self._b is not None:
            try:
                return getattr(self._b, name)
            except Exception:
                pass
        def _noop(*args, **kwargs): return None
        return _noop


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
        self.settings_manager = _SafeSettings(settings_manager)

        self.setWindowTitle("Qt Browser")
        self.resize(1200, 800)

        # --- Central layout with tabs --------------------------------------------
        central = QWidget(self)
        self.setCentralWidget(central)
        vbox = QVBoxLayout(central)
        vbox.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget(self)
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self._on_tab_close_requested)
        self.tabs.currentChanged.connect(self._on_current_tab_changed)
        vbox.addWidget(self.tabs)

        # --- Navigation toolbar ---------------------------------------------------
        self.navbar = QToolBar("Navigation", self)
        self.navbar.setIconSize(QSize(16, 16))
        self.addToolBar(Qt.TopToolBarArea, self.navbar)

        self.action_back = QAction(QIcon.fromTheme("go-previous"), "Back", self)
        self.action_forward = QAction(QIcon.fromTheme("go-next"), "Forward", self)
        self.action_reload = QAction(QIcon.fromTheme("view-refresh"), "Reload", self)
        self.action_home = QAction(QIcon.fromTheme("go-home"), "Home", self)
        self.action_new_tab = QAction(QIcon.fromTheme("tab-new"), "New Tab", self)
        self.action_close_tab = QAction(QIcon.fromTheme("tab-close"), "Close Tab", self)

        for act in (
            self.action_back,
            self.action_forward,
            self.action_reload,
            self.action_home,
            self.action_new_tab,
            self.action_close_tab,
        ):
            self.navbar.addAction(act)

        self.urlbar = QLineEdit(self)
        self.urlbar.setClearButtonEnabled(True)
        self.urlbar.returnPressed.connect(self._on_urlbar_return_pressed)
        self.navbar.addWidget(self.urlbar)

        # Wire actions
        self.action_back.triggered.connect(self.back)
        self.action_forward.triggered.connect(self.forward)
        self.action_reload.triggered.connect(self.reload)
        self.action_home.triggered.connect(self.home)
        self.action_new_tab.triggered.connect(self.create_new_tab)
        self.action_close_tab.triggered.connect(self.close_current_tab)

        self._restore_window_state()

        # Initial tab
        self._create_initial_tab()

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




# --- Optional manual run for smoke testing -----------------------------------
if __name__ == "__main__":  # pragma: no cover
    import sys

    app = QApplication(sys.argv)
    win = BrowserWindow()
    win.show()
    sys.exit(app.exec())
