from pathlib import Path
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePage
from PySide6.QtCore import Signal
from typing import TYPE_CHECKING

# Forward reference (runtime import to avoid circulars)
from .settings import SettingsManager  # type: ignore

class BrowserTab(QWidget):
    _tab_counter = 0

   
    loadStarted = Signal(str)               #url
    loadFinished = Signal(str, bool, str)   #url, success, title

    def __init__(self, tab_widget, url=None, settings_manager: SettingsManager = None):
        super().__init__()
        self.tab_widget = tab_widget
        self.settings_manager = settings_manager

        BrowserTab._tab_counter += 1
        self.tab_id = BrowserTab._tab_counter

        if url is None:
            url = self.settings_manager.get("start_url", "https://flanq.com")

        self.settings_manager.log_tab_action("Created", self.tab_id, f"URL: {url}")

        layout = QVBoxLayout(self)
        controls_layout = QHBoxLayout()

        self.url_input = QLineEdit()
        self.url_input.setText(url)
        self.url_input.returnPressed.connect(self.load_url)

        go_button = QPushButton("Go")
        go_button.clicked.connect(self.load_url)

        new_tab_button = QPushButton("+")
        new_tab_button.clicked.connect(self.create_new_tab)
        new_tab_button.setToolTip("Create new tab (Ctrl+T)")

        controls_layout.addWidget(self.url_input)
        controls_layout.addWidget(go_button)
        controls_layout.addWidget(new_tab_button)

        profile = self.settings_manager.get_web_profile()
        page = QWebEnginePage(profile, self)
        self.browser = QWebEngineView()
        self.browser.setPage(page)

        if self.settings_manager.get("logging_enabled", True):
            try:
                cookie_store = profile.cookieStore()
                cookie_store.cookieAdded.connect(lambda cookie:
                    self.settings_manager.log(f"Cookie added: {cookie.name().data().decode()} = {cookie.value().data().decode()[:50]}... for {cookie.domain()}", "COOKIE"))
                cookie_store.cookieRemoved.connect(lambda cookie:
                    self.settings_manager.log(f"Cookie removed: {cookie.name().data().decode()} from {cookie.domain()}", "COOKIE"))
                self.settings_manager.log(f"Cookie store initialized for tab {self.tab_id}", "COOKIE")
            except Exception as e:
                self.settings_manager.log_error(f"Could not setup cookie debugging: {str(e)}")

        self.browser.titleChanged.connect(self.update_tab_title)
        self.browser.urlChanged.connect(self.update_url_bar)
        self.browser.loadStarted.connect(self.on_load_started)
        self.browser.loadFinished.connect(self.on_load_finished)

        self._page_loaded = False
        self.browser.load(url)

        layout.addLayout(controls_layout)
        layout.addWidget(self.browser)

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
            self.settings_manager.log_error(f"Failed to load page: {url}", f"Tab-{self.tab_id}")
            self.loadFinished.emit(url, False, title)  # NEW


    def check_cookie_files(self, when: str):
        try:
            profile_dir = Path(self.settings_manager.config_dir) / "profile"
            cookies_dir = profile_dir / "cookies"
            if cookies_dir.exists():
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
                self.settings_manager.log(f"Cookies directory {when}: does not exist", "COOKIE")

            if profile_dir.exists():
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
            self.settings_manager.log_error(f"Could not check cookie files {when}: {str(e)}")

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
            self.settings_manager.log_error(f"toHtml failed: {e}", f"Tab-{self.tab_id}")
            callback("")
