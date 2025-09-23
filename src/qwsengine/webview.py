# qwsengine/webview.py
from typing import Callable, Optional

from PySide6.QtCore import Signal, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWebEngineCore import (
    QWebEngineProfile,
    QWebEnginePage,
    QWebEngineSettings,
)
from PySide6.QtWebEngineWidgets import QWebEngineView


class AppPage(QWebEnginePage):
    """
    Custom page that:
      - routes external schemes (mailto:, tel:, etc.) to the OS,
      - uses the standard Qt pop-up flow (via WebView.createWindow).
    """

    def __init__(self, profile: QWebEngineProfile, parent=None):
        super().__init__(profile, parent)

        # Don’t accidentally delegate normal clicks; we only want _blank / window.open
        # handled via createWindow.
        # (If you set DelegateAllLinks somewhere else, undo it.)
        try:
            self.setLinkDelegationPolicy(QWebEnginePage.LinkDelegationPolicy.DontDelegateLinks)
        except Exception:
            pass  # Older bindings may not expose this; safe to ignore.

        # Allow JS-initiated windows (required for target=_blank/window.open)
        self.settings().setAttribute(QWebEngineSettings.JavascriptCanOpenWindows, True)

    # Intercept truly external schemes and pass to the OS (optional but nice)
    def acceptNavigationRequest(self, url: QUrl, nav_type, is_main_frame: bool) -> bool:
        if url.scheme() in {"mailto", "tel"}:
            QDesktopServices.openUrl(url)
            return False
        return super().acceptNavigationRequest(url, nav_type, is_main_frame)


class WebView(QWebEngineView):
    """
    QWebEngineView that properly returns a view from createWindow so that
    target=_blank and window.open open in a new tab.
    """

    # Useful if the rest of the app prefers listening rather than providing a handler
    newTabRequested = Signal(QUrl)

    def __init__(self, parent=None, profile: Optional[QWebEngineProfile] = None):
        super().__init__(parent)
        self._profile = profile or QWebEngineProfile.defaultProfile()
        self.setPage(AppPage(self._profile, self))

        # Also set the view-level setting (proxies to page.settings())
        self.settings().setAttribute(QWebEngineSettings.JavascriptCanOpenWindows, True)

        # A callable that the main window sets: () -> WebView
        self._create_window_handler: Optional[Callable[[], "WebView"]] = None

    def set_create_window_handler(self, handler: Callable[[], "WebView"]) -> None:
        """
        The BrowserWindow/MainWindow should provide a factory that both:
          1) creates a new tab,
          2) returns the tab's internal WebView.
        """
        self._create_window_handler = handler

    # ★ The critical piece: return a real WebView for popups/new windows
    def createWindow(self, _type) -> "WebView":
        # If the app provided a handler, use it to create/return the tab's view.
        if self._create_window_handler is not None:
            return self._create_window_handler()

        # Fallback: create a detached view (not ideal, but better than silently failing).
        fallback = WebView(profile=self._profile)
        fallback.setAttribute(fallback.WA_DeleteOnClose, True)
        fallback.show()
        return fallback
