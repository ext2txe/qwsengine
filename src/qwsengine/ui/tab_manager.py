# ui/tab_manager.py
from PySide6.QtWidgets import QWidget, QTabWidget
from PySide6.QtCore import QUrl, QTimer
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineProfile
from typing import TYPE_CHECKING, Optional, Union

if TYPE_CHECKING:
    from ..main_window import BrowserWindow

from ..browser_tab import BrowserTab


class TabManager:
    """
    Manages browser tabs for BrowserWindow.
    
    Handles:
    - Tab creation and lifecycle
    - Tab switching and closing
    - Signal wiring between tabs and window
    - Tab title/URL tracking
    """
    
    def __init__(self, window: 'BrowserWindow'):
        """
        Initialize tab manager.
        
        Args:
            window: Parent BrowserWindow instance
        """
        self.window = window
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        
        # Connect tab widget signals
        self.tabs.tabCloseRequested.connect(self._on_tab_close_requested)
        self.tabs.currentChanged.connect(self._on_current_tab_changed)
    
    def get_tab_widget(self) -> QTabWidget:
        """
        Get the QTabWidget.
        
        Returns:
            The tab widget
        """
        return self.tabs
    
    def create_initial_tab(self):
        """Create the first tab when window opens."""
        initial_url = self.window._initial_url()
        self._new_tab(url=initial_url, switch=True)
    
    def new_tab(self, url: Optional[Union[str, QUrl]] = None, switch: bool = True) -> BrowserTab:
        """
        Create a new browser tab (public interface).
        
        Args:
            url: Optional URL to load
            switch: Whether to switch to the new tab
        
        Returns:
            The created BrowserTab
        """
        return self._new_tab(url=url, switch=switch)
    
    def _new_tab(
        self,
        url: Union[QUrl, str, None] = None,
        switch: bool = True,
        profile: Optional[QWebEngineProfile] = None,
        background: bool = False
    ) -> BrowserTab:
        """
        Internal tab creation with full control.
        
        Args:
            url: URL to load
            switch: Switch to new tab
            profile: Web engine profile (uses default if None)
            background: Create tab in background
        
        Returns:
            Created BrowserTab instance
        """
        # Use window's profile if not specified
        if profile is None:
            profile = self.window.settings_manager.profile
        
        # Create tab
        tab = BrowserTab(
            settings_manager=self.window.settings_manager,
            profile=profile,
            on_create_window=self._handle_new_window_request,
            parent=self.tabs
        )
        
        # Wire up signals
        self._wire_tab(tab)
        
        # Add to tab widget
        title = "New Tab"
        index = self.tabs.addTab(tab, title)
        
        # Switch to tab if requested
        if switch and not background:
            self.tabs.setCurrentIndex(index)
        
        # Load URL if provided
        if url:
            qurl = self._normalize_to_url(url)
            self._load_in_tab(tab, qurl)
        
        self.window._log(f"Created new tab (index={index}, switch={switch})")
        
        return tab
    
    def _wire_tab(self, tab: BrowserTab):
        """
        Connect tab signals to window handlers.
        
        Args:
            tab: BrowserTab to wire up
        """
        view = tab.view
        
        # URL changed
        view.urlChanged.connect(
            lambda qurl: self._on_browser_url_changed(qurl)
        )
        
        # Title changed
        view.titleChanged.connect(
            lambda title: self._on_browser_title_changed(title)
        )
        
        # Load progress
        view.loadStarted.connect(self.window.on_tab_load_started)
        view.loadFinished.connect(self.window.on_tab_load_finished)
        
        # Also wire tab-level signals if they exist
        if hasattr(tab, 'loadStarted'):
            tab.loadStarted.connect(
                lambda url: self.window._log(f"Tab load started: {url}")
            )
        
        if hasattr(tab, 'loadFinished'):
            tab.loadFinished.connect(
                lambda url, success, title: self.window._log(
                    f"Tab load finished: {url} (success={success})"
                )
            )
    
    def _load_in_tab(self, tab: BrowserTab, qurl: QUrl, retries: int = 20):
        """
        Load URL in a tab with retry logic.
        
        Args:
            tab: Tab to load URL in
            qurl: URL to load
            retries: Retries if tab not ready
        """
        view = tab.view
        if view and hasattr(view, 'load'):
            view.load(qurl)
            self.window._log(f"Loaded {qurl.toString()} in tab")
        elif retries > 0:
            # Tab might not be fully initialized, retry
            QTimer.singleShot(50, lambda: self._load_in_tab(tab, qurl, retries - 1))
        else:
            self.window._log(f"Failed to load {qurl.toString()} - tab not ready")
    
    def _normalize_to_url(self, url: Union[str, QUrl]) -> QUrl:
        """
        Convert string to QUrl with smart handling.
        
        Args:
            url: String or QUrl
        
        Returns:
            Normalized QUrl
        """
        if isinstance(url, QUrl):
            return url
        
        text = str(url).strip()
        
        # Empty = about:blank
        if not text:
            return QUrl("about:blank")
        
        # Already has scheme
        if "://" in text:
            return QUrl(text)
        
        # Local file
        if text.startswith("/") or text.startswith("file:"):
            return QUrl.fromLocalFile(text.replace("file:", ""))
        
        # Special protocols
        if text.startswith(("about:", "data:", "javascript:")):
            return QUrl(text)
        
        # Looks like a search query
        if " " in text or ("." not in text and "/" not in text):
            # Use DuckDuckGo as default search
            query = text.replace(" ", "+")
            return QUrl(f"https://duckduckgo.com/?q={query}")
        
        # Assume HTTPS for everything else
        return QUrl(f"https://{text}")
    
    def get_current_tab(self) -> Optional[BrowserTab]:
        """
        Get the currently active tab.
        
        Returns:
            Current BrowserTab or None
        """
        index = self.tabs.currentIndex()
        if index >= 0:
            widget = self.tabs.widget(index)
            if isinstance(widget, BrowserTab):
                return widget
        return None
    
    def get_current_view(self) -> Optional[QWebEngineView]:
        """
        Get webview from current tab.
        
        Returns:
            QWebEngineView or None
        """
        tab = self.get_current_tab()
        return tab.view if tab else None
    
    def close_tab(self, index: int):
        """
        Close tab at given index (public interface).
        
        Args:
            index: Tab index to close
        """
        self._on_tab_close_requested(index)
    
    def _on_tab_close_requested(self, index: int):
        """
        Handle tab close request.
        
        Args:
            index: Index of tab to close
        """
        # Don't close last tab
        if self.tabs.count() <= 1:
            self.window._log("Cannot close last tab")
            return
        
        # Get and remove tab
        widget = self.tabs.widget(index)
        self.tabs.removeTab(index)
        
        # Clean up
        if widget:
            widget.deleteLater()
        
        self.window._log(f"Closed tab at index {index}")
    
    def _on_current_tab_changed(self, index: int):
        """
        Handle tab switch.
        
        Args:
            index: New current tab index
        """
        if index < 0:
            return
        
        # Update URL bar with current tab's URL
        tab = self.get_current_tab()
        if tab and tab.view:
            url = tab.view.url()
            self._sync_urlbar_with_tab(url)
        
        self.window._log(f"Switched to tab {index}")
    
    def _sync_urlbar_with_tab(self, qurl: QUrl):
        """
        Update URL bar to match given URL.
        
        Args:
            qurl: URL to display
        """
        # Update in toolbar's URL bar
        if hasattr(self.window, 'urlbar') and self.window.urlbar:
            self.window.urlbar.setText(qurl.toString())
        
        # Also update in old url_edit if it exists (backward compatibility)
        if hasattr(self.window, 'url_edit') and self.window.url_edit:
            self.window.url_edit.setText(qurl.toString())
    
    def _on_browser_url_changed(self, qurl: QUrl):
        """
        Handle URL change in any tab.
        
        Args:
            qurl: New URL
        """
        # Update URL bar if this is the current tab
        current = self.get_current_tab()
        if current and current.view and current.view.url() == qurl:
            self._sync_urlbar_with_tab(qurl)
    
    def _on_browser_title_changed(self, title: str):
        """
        Handle title change in any tab.
        
        Args:
            title: New page title
        """
        # Find which tab this title belongs to
        current_index = self.tabs.currentIndex()
        if current_index >= 0:
            # Truncate long titles
            short_title = title[:20] + "..." if len(title) > 20 else title
            if short_title:  # Only update if non-empty
                self.tabs.setTabText(current_index, short_title)
    
    def _handle_new_window_request(self) -> QWebEngineView:
        """
        Handle request to open new window (target=_blank, window.open).
        
        Returns:
            WebView for the new tab
        """
        # Create tab in background
        new_tab = self._new_tab(switch=False, background=True)
        self.window._log("Created new tab for popup/new window")
        return new_tab.view
    
    def create_tab_for_popup(self) -> BrowserTab:
        """
        Create a tab specifically for popup windows.
        
        Returns:
            New BrowserTab
        """
        return self._new_tab(switch=True)
    
    def open_url_in_new_tab(self, url: Union[str, QUrl], switch: bool = True) -> BrowserTab:
        """
        Open URL in a new tab.
        
        Args:
            url: URL to open
            switch: Whether to switch to the new tab
        
        Returns:
            Created tab
        """
        return self._new_tab(url=url, switch=switch)
    
    def navigate_current(self, url: Union[str, QUrl]):
        """
        Navigate current tab to URL.
        
        Args:
            url: URL to navigate to
        """
        tab = self.get_current_tab()
        if tab:
            qurl = self._normalize_to_url(url)
            self._load_in_tab(tab, qurl)
        else:
            self.window._log("No current tab to navigate")
    
    def get_tab_count(self) -> int:
        """
        Get number of open tabs.
        
        Returns:
            Tab count
        """
        return self.tabs.count()
    
    def get_tab_at_index(self, index: int) -> Optional[BrowserTab]:
        """
        Get tab at specific index.
        
        Args:
            index: Tab index
        
        Returns:
            BrowserTab or None
        """
        if 0 <= index < self.tabs.count():
            widget = self.tabs.widget(index)
            if isinstance(widget, BrowserTab):
                return widget
        return None