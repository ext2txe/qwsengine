# qwsengine/request_interceptor.py
from __future__ import annotations
from typing import Any, Dict
from PySide6.QtWebEngineCore import QWebEngineUrlRequestInterceptor, QWebEngineUrlRequestInfo

def _to_bytes(s) -> bytes:
    if isinstance(s, bytes):
        return s
    return str(s).encode("utf-8", errors="ignore")

def _host_only(url: str) -> str:
    # "example.com:443" -> "example.com"
    if not url:
        return ""
    # QUrl.host() already strips scheme, but some internal URLs arrive as raw strings
    return url.split(":")[0].lower()

class HeaderInterceptor(QWebEngineUrlRequestInterceptor):
    """
    Intercepts every HTTP(S) request and injects headers per config.

    Settings expected on SettingsManager.settings:
      - user_agent (str)                 -> applied elsewhere, not here
      - accept_language (str|None)       -> e.g. "en-US,en;q=0.9"
      - send_dnt (bool)                  -> if True, send "DNT: 1"
      - headers_global (dict[str,str])   -> added to every request
      - headers_per_host (dict[str,dict[str,str]]) -> host-specific overrides
      - spoof_chrome_client_hints (bool) -> optional low-noise hints

    Notes:
    - We never short-circuit based on accept_language. If it’s empty, we just
      skip that one header instead of skipping all header injection.
    - Host matching is done against the request URL host (lower-cased, no port).
    """

    def __init__(self, settings_manager):
        super().__init__()
        self._sm = settings_manager  # keep reference; interceptor lives as long as profile

    def _cfg(self) -> Dict[str, Any]:
        # Always read the live dict so changes take effect without restart.
        return getattr(self._sm, "settings", {}) or {}

    def interceptRequest(self, info: QWebEngineUrlRequestInfo) -> None:
        scheme = bytes(info.requestUrl().scheme().encode("ascii", "ignore")).lower()
        if scheme not in (b"http", b"https"):
            return  # ignore non-HTTP(S) schemes

        s = self._cfg()

        # 1) Language (optional)
        al = s.get("accept_language")
        if isinstance(al, str) and al.strip():
            info.setHttpHeader(b"Accept-Language", _to_bytes(al.strip()))

        # 2) DNT (optional)
        if s.get("send_dnt"):
            info.setHttpHeader(b"DNT", b"1")

        # 3) Global headers
        glb = s.get("headers_global") or s.get("headers") or {}
        if isinstance(glb, dict):
            for k, v in glb.items():
                if k:
                    info.setHttpHeader(_to_bytes(k), _to_bytes(v))

        # 4) Per-host headers
        per_host = s.get("headers_per_host") or {}
        if isinstance(per_host, dict):
            host = info.requestUrl().host().lower()
            host = _host_only(host)
            if host in per_host and isinstance(per_host[host], dict):
                for k, v in (per_host[host] or {}).items():
                    if k:
                        info.setHttpHeader(_to_bytes(k), _to_bytes(v))

        # 5) OPTIONAL: very light client hints (off by default)
        if s.get("spoof_chrome_client_hints"):
            info.setHttpHeader(b"sec-ch-ua", _to_bytes('"Chromium";v="128", "Not=A?Brand";v="99"'))
            info.setHttpHeader(b"sec-ch-ua-mobile", b"?0")
            info.setHttpHeader(b"sec-ch-ua-platform", b'"Windows"')
