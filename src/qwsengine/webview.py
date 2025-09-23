# qwsengine/webview.py
from PySide6.QtCore import Signal, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView


class AppPage(QWebEnginePage):
    """
    Custom page that:
      - routes external schemes (mailto:, tel:) to the OS,
      - forwards popup/new-window requests to the parent WebView via its newTabRequested signal.
    """

    def __init__(self, profile: QWebEngineProfile, parent=None):
        super().__init__(profile, parent)

        # If available (Qt 6.5+), this is the most reliable hook:
        if hasattr(self, "newWindowRequested"):
            try:
                # Signal signature: newWindowRequested(QWebEngineNewWindowRequest)
                self.newWindowRequested.connect(self._on_new_window_requested)
            except TypeError:
                # Some bindings expose it but not connectable—safe to ignore.
                pass

    def acceptNavigationRequest(self, url: QUrl, nav_type, isMainFrame: bool) -> bool:
        # Open external schemes in the OS (optional nicety)
        if url.scheme() in ("mailto", "tel"):
            QDesktopServices.openUrl(url)
            return False
        return super().acceptNavigationRequest(url, nav_type, isMainFrame)

    # ---- New-window handling (preferred path) ----
    def _on_new_window_requested(self, request):
        """Handle QWebEngineNewWindowRequest if the binding exposes it."""
        # PySide6 typically names it requestedUrl(); some versions expose url().
        url = None
        for attr in ("requestedUrl", "url"):
            if hasattr(request, attr):
                candidate = getattr(request, attr)()
                if isinstance(candidate, QUrl):
                    url = candidate
                    break

        # If we got a URL, emit to parent WebView; accept the request to prevent blocking.
        if url and url.isValid():
            parent = self.parent()
            if parent and hasattr(parent, "newTabRequested"):
                try:
                    parent.newTabRequested.emit(url)
                except Exception:
                    pass
            # Try to accept; older bindings may not have accept()/reject().
            try:
                request.accept()
            except Exception:
                pass
        else:
            try:
                request.reject()
            except Exception:
                pass

    # ---- Fallback for engines that don't expose newWindowRequested ----
    def createWindow(self, _window_type):
        """
        Called when the page wants a new window (target=_blank, window.open).
        We return a temporary AppPage; when it navigates, we forward the URL up.
        """
        tmp = AppPage(self.profile(), self)

        def forward(u: QUrl):
            if u and u.isValid():
                parent = self.parent()
                if parent and hasattr(parent, "newTabRequested"):
                    try:
                        parent.newTabRequested.emit(u)
                    except Exception:
                        pass
            tmp.deleteLater()

        tmp.urlChanged.connect(forward)
        return tmp


class WebView(QWebEngineView):
    """
    QWebEngineView that exposes newTabRequested(QUrl) when pages request a new window.
    """
    newTabRequested = Signal(QUrl)

    def __init__(self, parent=None, profile: QWebEngineProfile | None = None):
        super().__init__(parent)
        self._profile = profile or QWebEngineProfile.defaultProfile()
        self.setPage(AppPage(self._profile, self))

        # Ensure popups are allowed; without this, window.open/target=_blank may be blocked.
        self.settings().setAttribute(QWebEngineSettings.JavascriptCanOpenWindows, True)
