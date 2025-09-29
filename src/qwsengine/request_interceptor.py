# src/qwsengine/request_interceptor.py
from PySide6.QtWebEngineCore import QWebEngineUrlRequestInterceptor, QWebEngineUrlRequestInfo

def _to_bytes(s) -> bytes:
    if isinstance(s, bytes):
        return s
    return str(s).encode("utf-8", errors="ignore")

class HeaderInterceptor(QWebEngineUrlRequestInterceptor):
    """
    Intercepts every HTTP(s) request and lets us override/add headers.
    Config is read from the SettingsManager:
      - accept_language (str)         -> "en-US,en;q=0.9" etc.
      - send_dnt (bool)               -> if True, send "DNT: 1"
      - headers_global (dict)         -> {"Header-Name": "value", ...}
      - headers_per_host (dict)       -> {"example.com": {"Header": "value"}}
      - spoof_chrome_client_hints (bool) -> if True, adds sec-ch-ua* headers (best-effort)
    """
    def __init__(self, settings_manager):
        super().__init__()
        self.s = settings_manager

    def interceptRequest(self, info: QWebEngineUrlRequestInfo) -> None:
        url = info.requestUrl()
        host = (url.host() or "").lower()

        # 1) Accept-Language (explicit per-request; also set globally via profile if available)
        al = (self.s.get("accept_language", "") or "").strip()
        if al:
            info.setHttpHeader(b"Accept-Language", _to_bytes(al))

        # 2) DNT
        if self.s.get("send_dnt", False):
            info.setHttpHeader(b"DNT", b"1")

        # 3) Global headers
        global_headers = self.s.get("headers_global", {}) or {}
        for k, v in global_headers.items():
            if k:
                info.setHttpHeader(_to_bytes(k), _to_bytes(v))

        # 4) Per-host headers (takes precedence over global if same key)
        per_host = self.s.get("headers_per_host", {}) or {}
        if host in per_host:
            for k, v in (per_host.get(host) or {}).items():
                if k:
                    info.setHttpHeader(_to_bytes(k), _to_bytes(v))

        # 5) OPTIONAL: Chrome-like client hints.
        # Note: Chromium may still control some of these based on origin policy.
        if self.s.get("spoof_chrome_client_hints", False):
            # Values below are examples; adjust as needed.
            # Keep them short and realistic; many sites don't require these.
            info.setHttpHeader(b"sec-ch-ua", _to_bytes('"Chromium";v="128", "Not=A?Brand";v="99"'))
            info.setHttpHeader(b"sec-ch-ua-mobile", b"?0")
            # Pick one based on your platform if you like: "Windows" | "macOS" | "Linux"
            info.setHttpHeader(b"sec-ch-ua-platform", b'"Windows"')
