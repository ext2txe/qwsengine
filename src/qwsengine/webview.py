# qwsengine/webview.py
from typing import Callable, Optional
# --- Drop-in: put near your other imports ---
from PySide6.QtCore import QUrl, Qt, Slot
from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
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



        """
    QWebEngineView with:
      - Optional construction with a specific QWebEngineProfile
      - Proper handling of new-window requests so links open in a *new tab*
        within the main BrowserWindow (context menu, target=_blank, window.open).
    """

class WebView(QWebEngineView):
    """
    Custom view so target=_blank (and window.open) create a new tab instead of a new window.
    We call back to the BrowserWindow to actually create the tab and return its view.
    """
    def __init__(self, parent=None, profile: QWebEngineProfile | None = None, on_create_window=None):
        super().__init__(parent)
        self._on_create_window = on_create_window
        if profile is not None:
            page = QWebEnginePage(profile, self)
            self.setPage(page)

    # This gets called by Qt when a page wants a new window (e.g. target=_blank)
    def createWindow(self, _type: QWebEnginePage.WebWindowType) -> QWebEngineView:
        if callable(self._on_create_window):
            # Ask the main window to create a background tab and return its view
            return self._on_create_window(profile=self.page().profile())
        # Fallback: create a temporary view if callback not wired (shouldn't happen)
        temp = WebView(self, profile=self.page().profile(), on_create_window=self._on_create_window)
        temp.setAttribute(Qt.WA_DeleteOnClose)
        return temp
