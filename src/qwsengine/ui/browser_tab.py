from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from PySide6.QtCore import Signal
from PySide6.QtWebEngineWidgets import QWebEngineView


class WebView(QWebEngineView):
    def __init__(self, parent=None, *, profile: QWebEngineProfile | None = None, on_create_window=None):
        super().__init__(parent)
        self._on_create_window = on_create_window
        if profile is not None:
            # Ensure this view uses the given profile
            page = QWebEnginePage(profile, self)
            self.setPage(page)

    def createWindow(self, _type: QWebEnginePage.WebWindowType) -> QWebEngineView:
        if callable(self._on_create_window):
            # hand back a *fresh* view from a brand-new tab; caller supplies profile
            return self._on_create_window()
        # Fallback: temporary view (shouldn’t happen in normal flow)
        return WebView(self, profile=self.page().profile(), on_create_window=self._on_create_window)


class BrowserTab(QWidget):
    _tab_counter = 0
    loadStarted = Signal(str)               #url
    loadFinished = Signal(str, bool, str)   #url, success, title

    """
    A simple tab container that owns a WebView.
    Keep a strong reference on self.view so _view_of(tab) is trivial.
    """
    def __init__(self, settings_manager, profile=None, on_create_window=None, parent=None):
        super().__init__(parent)
        self.settings_manager = settings_manager

        # REPLACE your existing view creation line with this:
        prof = profile or getattr(self.settings_manager, "profile", None)
        self.view = WebView(self, profile=profile, on_create_window=on_create_window)
        self.browser = self.view   # keep legacy attribute alive

        # keep your existing layout code; e.g.:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)

    def load_url(self):
        url = self.url_input.text().strip()
        if not url.startswith("http"):
            url = "https://" + url
        self.settings_manager.log_tab_action("Manual navigation", self.tab_id, f"URL: {url}")
        self.browser.load(url)

    def create_new_tab(self):
        # No need to import BrowserWindow or walk parents; we already have settings_manager.
        self.settings_manager.log_tab_action("New tab requested", self.tab_id)
        from .browser_tab import BrowserTab  # lazy import to avoid any odd cycles
        new_tab = BrowserTab(self.tab_widget, settings_manager=self.settings_manager)
        index = self.tab_widget.addTab(new_tab, "New Tab")
        self.tab_widget.setCurrentIndex(index)

    def get_browser_window(self):
        parent = self.parent()
        # Walk up QWidget parents to find a window that looks like our BrowserWindow
        while parent:
            # We avoid importing BrowserWindow here to prevent circular imports.
            # Heuristic: a BrowserWindow has a 'settings_manager' attribute.
            if hasattr(parent, 'settings_manager'):
                return parent
            parent = parent.parent()
        return None

    def update_tab_title(self, title: str):
        index = self.tab_widget.indexOf(self)
        if index >= 0:
            #short_title = title[:15] + ("�" if len(title) > 15 else "")
            short_title = title[:15] + ("..." if len(title) > 15 else "")
            self.tab_widget.setTabText(index, short_title)
            self.settings_manager.log_tab_action("Title updated", self.tab_id, f"Title: {title}")

    def update_url_bar(self, qurl):
        self.url_input.setText(qurl.toString())

    def on_load_started(self):
        url = self.browser.url().toString()
        self._page_loaded = False
        self.loadStarted.emit(url)  # NEW
        self.settings_manager.log_navigation(url, "", self.tab_id)
        if self.settings_manager.get("logging_enabled", True):
            self.check_cookie_files("before load")

    def on_load_finished(self, success: bool):
        url = self.browser.url().toString()
        title = self.browser.title()
        if success:
            self._page_loaded = True
            self.settings_manager.log_navigation(url, title, self.tab_id)
            self.loadFinished.emit(url, True, title)   # NEW
            if self.settings_manager.get("logging_enabled", True):
                self.check_cookie_files("after load")
        else:
            self.settings_manager.log_error("browser_tab", f"Failed to load page: {url}", f"Tab-{self.tab_id}")
            self.loadFinished.emit(url, False, title)  # NEW

    def _on_proxy_auth_required(self, request_url, authenticator, proxy_host):
        try:
            user = self.settings_manager.get("proxy_user", "")
            pwd  = self.settings_manager.get("proxy_password", "")
            if user or pwd:
                authenticator.setUser(user)
                authenticator.setPassword(pwd)
                self.settings_manager.log_system_event("browser_tab", "Proxy auth provided", proxy_host)
            else:
                self.settings_manager.log_system_event("browser_tab", "Proxy asked for credentials but none set", proxy_host)
        except Exception as e:
            self.settings_manager.log_error("browser_tab", f"proxy auth handler failed: {e}", f"host={proxy_host}")

    def check_cookie_files(self, when: str):
        try:
            profile_dir = Path(self.settings_manager.config_dir) / "profile"
            cookies_dir = profile_dir / "cookies"

            if cookies_dir.exists():
                if cookies_dir.is_dir():
                    contents = list(cookies_dir.iterdir())
                    if contents:
                        self.settings_manager.log(f"Cookies directory {when}: {[p.name for p in contents]}", "COOKIE")
                        for item in contents:
                            if item.is_file():
                                size = item.stat().st_size
                                self.settings_manager.log(f"Cookie file {item.name}: {size} bytes", "COOKIE")
                    else:
                        self.settings_manager.log(f"Cookies directory {when}: empty", "COOKIE")
                else:
                    # It's a file (very common: Chromium keeps cookies in a single SQLite DB)
                    size = cookies_dir.stat().st_size
                    self.settings_manager.log(f"'cookies' is a file {when}: {size} bytes", "COOKIE")
            else:
                self.settings_manager.log(f"Cookies path {when}: does not exist", "COOKIE")

            if profile_dir.exists() and profile_dir.is_dir():
                for item in profile_dir.iterdir():
                    if item.is_file():
                        name_lower = item.name.lower()
                        if (any(keyword in name_lower for keyword in ['cookie', 'network', 'state', 'history'])
                            or item.suffix.lower() in ['.db', '.sqlite', '.sqlite3']):
                            size = item.stat().st_size
                            modified = item.stat().st_mtime
                            self.settings_manager.log(f"Profile file {item.name}: {size} bytes, modified: {modified}", "COOKIE")

                for subdir in profile_dir.iterdir():
                    if subdir.is_dir() and subdir.name in ['Local Storage', 'databases', 'IndexedDB']:
                        try:
                            for item in subdir.rglob('*'):
                                if item.is_file() and item.suffix.lower() in ['.db', '.sqlite', '.sqlite3', '.ldb']:
                                    size = item.stat().st_size
                                    rel_path = item.relative_to(profile_dir)
                                    self.settings_manager.log(f"Database file {rel_path}: {size} bytes", "COOKIE")
                        except Exception:
                            pass
        except Exception as e:
            self.settings_manager.log_error("browser_tab", f"Could not check cookie files {when}: {str(e)}")

    def closeEvent(self, event):
        self.settings_manager.log_tab_action("Closed", self.tab_id)
        super().closeEvent(event)

    def is_loaded(self) -> bool:
        return bool(getattr(self, "_page_loaded", False))

    def get_html(self, callback):
        # QWebEnginePage.toHtml is async; provide callback(html: str) -> None
        try:
            page = self.browser.page()
            page.toHtml(callback)
        except Exception as e:
            self.settings_manager.log_error("browser_tab", f"toHtml failed: {e}", f"Tab-{self.tab_id}")
            callback("")
