from __future__ import annotations

from pathlib import Path
import json
import os
from typing import Any, Dict, Optional

from PySide6.QtCore import QStandardPaths
from PySide6.QtCore import QByteArray, QRect
from PySide6.QtWebEngineCore import QWebEngineProfile

# Single source of truth for app identity & paths
from qwsengine.app_info import app_dir, SETTINGS_PATH, CACHE_DIR, DATA_DIR, LOG_DIR
from .request_interceptor import HeaderInterceptor  # <-- correct name

# Optional imports (don’t crash if not present)
try:
    from .log_manager import LogManager  # your existing logger (if any)
except Exception:
    LogManager = None  # type: ignore


class SettingsManager:
    """
    App settings + persistent QWebEngineProfile.
    Preferred: self.web_profile
    Back-compat: self.profile (property) and _setup_web_profile()
    """
    # Legacy → current keys
    _KEY_ALIASES = {
        "window/geometry":      "window_geometry",
        "window/maximized":     "window_maximized",
        "window/fullscreen":    "window_fullscreen",
        "window/normal_rect":   "window_normal_rect",
        # add more mappings here if your code uses other "a/b" keys
    }

    def __init__(self) -> None:
        # ----- directories (used by logger & others) -----------------------
        self.config_dir: Path = DATA_DIR # app_dir(QStandardPaths.AppConfigLocation)
        self.settings_path = SETTINGS_PATH
        self.cache_dir: Path  = CACHE_DIR
        self.data_dir: Path   = DATA_DIR

        # ----- Defaults (EXACTLY as provided) ------------------------------
        self.default_settings: Dict[str, Any] = {
            "start_url": "https://codaland.com/ipdefault", #check.php",
            "window_width": 1024,
            "window_height": 768,
            "logging_enabled": True,
            "log_navigation": True,
            "log_tab_actions": True,
            "log_errors": True,
            "persist_cookies": True,
            "persist_cache": True,

            "window_geometry": "",        # base64-encoded QByteArray
            "window_maximized": False,
            "window_fullscreen": False,
            "window_normal_rect": None,   # [x, y, w, h]

            "user_agent": "",             # empty = use default UA
            "proxy_mode": "manual",       # "system" | "manual" | "none"
            "proxy_type": "http",         # "http" | "socks5" (manual only)
            "proxy_host": "",
            "proxy_port": 0,
            "proxy_user": "",
            "proxy_password": "",

            # Add these two new settings here:
            "auto_launch_browser": True,  # Whether to auto-launch browser on startup

            # if accept_language is "", then headers will not be inserted
            "accept_language": "en-US,en;q=0.9",
            "send_dnt": False,
            "spoof_chrome_client_hints": False,

            "headers_global": {},         # {"X-Api-Key": "abc123", ...}
            "headers_per_host": {},       # {"example.com": {"X-Site": "ex"}}
        }

        # ----- Load settings JSON, merged with defaults --------------------
        self.settings: Dict[str, Any] = self._load_settings()

        # ----- Logging -----------------------------------------------------
        self.log_manager = None
        if self.settings.get("logging_enabled", True) and LogManager is not None:
            try:
                self.log_manager = LogManager(self.config_dir, "qwsEngine")
            except Exception:
                self.log_manager = None  # don’t crash if logger fails

        # ----- (Optional) process-wide proxy setup BEFORE WebEngine starts --
        # NOTE: QtWebEngine honors Chromium flags; QtNetwork proxies do not affect it.
        # We set best-effort env flags here. If you prefer, move this earlier in app boot.
        self.apply_proxy_settings()

        # ----- Persistent WebEngine profile --------------------------------
        self.web_profile: QWebEngineProfile = self._setup_web_profile()

    # ----------------------------------------------------------------------
    # Back-compat surface
    @property
    def profile(self) -> QWebEngineProfile:
        return self.web_profile

    def _setup_web_profile(self) -> QWebEngineProfile:
        """Alias kept for backward compatibility."""
        return self._create_web_profile()


    # ----------------------------------------------------------------------
    # Public getters
    def start_url(self) -> str:
        return self.settings.get("start_url", "about:blank")

    def user_agent(self) -> Optional[str]:
        ua = self.settings.get("user_agent", "")
        return ua or None

    def accept_language(self) -> Optional[str]:
        al = self.settings.get("accept_language", "")
        return al or None

    def extra_headers_global(self) -> Dict[str, str]:
        return dict(self.settings.get("headers_global", {}) or {})

    def extra_headers_per_host(self) -> Dict[str, Dict[str, str]]:
        return dict(self.settings.get("headers_per_host", {}) or {})

    # ----------------------------------------------------------------------
    # Logging shims (so existing calls work even if LogManager is None)
    def log_tab_action(self, action: str, tab_id: Any, note: str = "") -> None:
        if self.log_manager and self.settings.get("log_tab_actions", True):
            try:
                self.log_manager.log_tab_action(action, tab_id, note)
            except Exception:
                pass

    def log_navigation(self, url: str, title: str = "", meta: Optional[dict] = None) -> None:
        if self.log_manager and self.settings.get("log_navigation", True):
            try:
                self.log_manager.log_navigation(url, title, meta or {})
            except Exception:
                pass

    def log_info(self, where: str, message: str, meta: dict | None = None) -> None:
        if self.log_manager:
            try:
                if hasattr(self.log_manager, "log_info"):
                    self.log_manager.log_info(where, message, meta or {})
                else:
                    # fallback: use navigation/info-like channel
                    self.log_manager.log_navigation(where, message, meta or {})
            except Exception:
                pass

    def log_debug(self, where: str, message: str, meta: dict | None = None) -> None:
        if self.log_manager and hasattr(self.log_manager, "log_debug"):
            try:
                self.log_manager.log_debug(where, message, meta or {})
            except Exception:
                pass

    def log_error(self, where: str, message: str, meta: dict | None = None) -> None:
        if self.log_manager:
            try:
                self.log_manager.log_error(where, message, meta or {})
            except Exception:
                pass

    def log_system_event(self, where: str, message: str, meta: dict | None = None) -> None:
        """Semantic alias for app/system messages; same signature."""
        self.log_info(where, message, meta)

    def get_log_dir(self) -> Path:
        """Directory where log files are stored."""
        return self.logs_dir

    def get_log_file_path(self, ensure_exists: bool = False) -> Path | None:
        """
        Return the *current* log file path if known.
        Falls back to a conventional file in the logs dir.
        """
        # If your LogManager exposes a path, prefer it:
        if self.log_manager:
            # common variants — use whatever your LogManager actually has
            for attr in ("current_log_path", "log_path", "path"):
                if hasattr(self.log_manager, attr):
                    p = getattr(self.log_manager, attr)
                    try:
                        p = Path(p)  # in case it's a string
                    except Exception:
                        p = None
                    else:
                        if ensure_exists:
                            p.parent.mkdir(parents=True, exist_ok=True)
                            p.touch(exist_ok=True)
                        return p
            # method-style accessors
            for meth in ("get_current_log_path", "get_log_file_path"):
                if hasattr(self.log_manager, meth):
                    try:
                        p = Path(getattr(self.log_manager, meth)())
                        if ensure_exists:
                            p.parent.mkdir(parents=True, exist_ok=True)
                            p.touch(exist_ok=True)
                        return p
                    except Exception:
                        pass

        # Fallback: conventional single-file log
        fallback = LOG_DIR / "qwsengine.log"
        if ensure_exists:
            fallback.parent.mkdir(parents=True, exist_ok=True)
            fallback.touch(exist_ok=True)
        return fallback

    # ----------------------------------------------------------------------
    # Settings IO
    def _load_settings(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {}
        if SETTINGS_PATH.exists():
            try:
                data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            except Exception:
                data = {}

        # shallow merge + one-level nested dicts
        merged = dict(self.default_settings)
        for k, v in data.items():
            if isinstance(v, dict) and isinstance(merged.get(k), dict):
                merged[k] = {**merged[k], **v}
            else:
                merged[k] = v
        return merged

    def save_settings(self) -> bool:
        """Persist settings atomically; verify; return True on success."""
        try:
            url = self.settings['start_url']
            self.log_info("Settings_Manager", url)
            SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = SETTINGS_PATH.with_suffix(".tmp")

            # 1) write tmp
            with tmp_path.open("w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2)
                # 2) fsync to reduce Windows lock weirdness
                try:
                    f.flush()
                    os_fno = f.fileno()
                    os.fsync(os_fno)
                except Exception:
                    pass  # best effort

            # 3) replace
            tmp_path.replace(SETTINGS_PATH)

            # 4) verify read-back (optional but recommended)
            try:
                loaded = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
                # minimal check: ensure it's a dict
                if not isinstance(loaded, dict):
                    self.log_error("SettingsManager", "Settings saved but verification failed: invalid JSON structure")
                    return False
            except Exception as e:
                self.log_error("SettingsManager", f"Settings saved but verify failed: {e}")
                return False

            return True

        except Exception as e:
            self.log_error("SettingsManager", f"Failed to save settings to file: {e}")
            return False

    def apply_user_agent(self, ua: str | None = None) -> bool:
        """
        Back-compat for settings_dialog.py.
        - If `ua` is provided: set it, save settings, and apply.
        - If `ua` is None: just apply the current value from settings.
        Returns True if settings were saved (or no save needed), False on save failure.
        """
        if ua is not None:
            self.settings["user_agent"] = ua or ""
            ok = self.save_settings()
        else:
            ok = True  # nothing to persist

        # Re-apply UA + related headers/interceptor to the live profile
        try:
            self.apply_network_overrides()
        except Exception as e:
            self.log_error("SettingsManager", f"Failed to apply user-agent: {e}")

        return ok

    def apply_proxy_settings(self) -> bool:
        """
        Apply current proxy_* settings to the running process.
        Returns True if WebEngine proxy flags changed (i.e., restart recommended).
        Notes:
        - QtWebEngine reads proxy via Chromium flags at process start.
            We set QTWEBENGINE_CHROMIUM_FLAGS here; a restart is typically required
            for WebEngine to fully adopt changes.
        - QtNetwork traffic (requests via QtNetwork) is applied live below.
        """
        mode = (self.settings.get("proxy_mode") or "system").lower()
        ptype = (self.settings.get("proxy_type") or "http").lower()
        host  = self.settings.get("proxy_host") or ""
        port  = int(self.settings.get("proxy_port") or 0)
        user  = self.settings.get("proxy_user") or ""
        pwd   = self.settings.get("proxy_password") or ""

        flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "").strip()
        parts = flags.split()
        changed = False

        def add_flag(s: str):
            nonlocal parts, changed
            if s not in parts:
                parts.append(s)
                changed = True

        def remove_flag(prefix: str):
            nonlocal parts, changed
            new = [p for p in parts if not p.startswith(prefix)]
            if new != parts:
                parts = new
                changed = True

        # --- Configure Chromium flags for WebEngine ---
        if mode == "system":
            remove_flag("--no-proxy-server")
            remove_flag("--proxy-server=")
        elif mode == "none":
            add_flag("--no-proxy-server")
            remove_flag("--proxy-server=")
        elif mode == "manual":
            scheme = "socks5" if "socks" in ptype else "http"
            if host and port:
                auth = f"{user}:{pwd}@" if user else ""
                remove_flag("--no-proxy-server")
                remove_flag("--proxy-server=")  # clear any prior value
                add_flag(f"--proxy-server={scheme}://{auth}{host}:{port}")
            else:
                # incomplete manual config → fall back to system
                remove_flag("--no-proxy-server")
                remove_flag("--proxy-server=")

        # Persist env var
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = " ".join(parts).strip()

        # --- Apply QtNetwork proxy live (this affects QtNetwork, not WebEngine) ---
        try:
            from PySide6.QtNetwork import QNetworkProxy, QNetworkProxyFactory
            if mode == "system":
                QNetworkProxyFactory.setUseSystemConfiguration(True)
                QNetworkProxy.setApplicationProxy(QNetworkProxy())  # reset explicit proxy
            elif mode == "none":
                QNetworkProxyFactory.setUseSystemConfiguration(False)
                QNetworkProxy.setApplicationProxy(QNetworkProxy(QNetworkProxy.NoProxy))
            elif mode == "manual" and host and port:
                QNetworkProxyFactory.setUseSystemConfiguration(False)
                proxy_type = QNetworkProxy.Socks5Proxy if "socks" in ptype else QNetworkProxy.HttpProxy
                qp = QNetworkProxy(proxy_type, host, port, user, pwd)
                QNetworkProxy.setApplicationProxy(qp)
        except Exception:
            # If QtNetwork isn't used, ignore
            pass

        # If flags changed, a restart is recommended for WebEngine to pick them up
        return changed

    def set_proxy_settings(
            self,
            *,
            mode: str,
            proxy_type: str | None = None,
            host: str | None = None,
            port: int | None = None,
            user: str | None = None,
            password: str | None = None,
            persist: bool = True,
            apply_now: bool = True,
        ) -> bool:
            """
            Update settings.json with new proxy config and apply.
            Returns True if saved successfully (not whether restart is needed).
            """
            self.settings["proxy_mode"] = (mode or "system").lower()
            if proxy_type is not None:
                self.settings["proxy_type"] = proxy_type
            if host is not None:
                self.settings["proxy_host"] = host
            if port is not None:
                self.settings["proxy_port"] = int(port)
            if user is not None:
                self.settings["proxy_user"] = user
            if password is not None:
                self.settings["proxy_password"] = password

            ok = True
            if persist:
                ok = self.save_settings()

            if apply_now:
                self.apply_proxy_settings()

            return ok

    def _qa_to_b64(self, ba: QByteArray) -> str:
        # QByteArray → base64 str for JSON
        import base64
        return base64.b64encode(bytes(ba)).decode("ascii")

    def _b64_to_qa(self, s: str) -> QByteArray:
        import base64
        try:
            raw = base64.b64decode(s.encode("ascii"))
            return QByteArray(raw)
        except Exception:
            return QByteArray()

    def save_window_state(self, window) -> None:
        """
        Persist geometry + window mode (normal/maximized/fullscreen).
        Stores:
        - window_geometry: base64(QByteArray)
        - window_maximized: bool
        - window_fullscreen: bool
        - window_normal_rect: [x, y, w, h]  (only when in normal state)
        """
        try:
            self.settings["window_geometry"] = self._qa_to_b64(window.saveGeometry())
            self.settings["window_maximized"] = bool(window.isMaximized())
            self.settings["window_fullscreen"] = bool(window.isFullScreen())

            # Capture the last known *normal* rect so we can restore when not maximized/fullscreen
            if not window.isMaximized() and not window.isFullScreen():
                r = window.normalGeometry() if hasattr(window, "normalGeometry") else window.geometry()
                self.settings["window_normal_rect"] = [int(r.x()), int(r.y()), int(r.width()), int(r.height())]

            self.save_settings()
        except Exception as e:
            self.log_error("SettingsManager", f"Failed to save window state: {e}")

    def restore_window_state(self, window) -> None:
        """
        Restore geometry and window mode.
        Call this after widgets are constructed but before first show().
        """
        try:
            geom_b64 = self.settings.get("window_geometry_b64") or ""
            maximized = bool(self.settings.get("window_maximized", False))
            fullscreen = bool(self.settings.get("window_fullscreen", False))
            normal_rect = self.settings.get("window_normal_rect")

            # 1) Restore raw geometry if available
            if geom_b64:
                ba = self._b64_to_qa(geom_b64)
                if not ba.isEmpty():
                    window.restoreGeometry(ba)

            # 2) If a concrete normal rect is stored and we’re not going to maximize/fullscreen, apply it
            if normal_rect and not maximized and not fullscreen:
                try:
                    x, y, w, h = [int(v) for v in normal_rect]
                    window.setGeometry(QRect(x, y, w, h))
                except Exception:
                    pass

            # 3) Restore window mode last
            if fullscreen:
                window.showFullScreen()
            elif maximized:
                window.showMaximized()
            else:
                # don’t call showNormal() here; just let the caller show()
                pass
        except Exception as e:
            self.log_error("SettingsManager", f"Failed to restore window state: {e}")

    # --- add these helper methods inside SettingsManager ---
    def _normalize_key(self, key: str) -> str:
        """
        Translate legacy slash-separated keys to our flat JSON keys.
        Fallback: replace '/' with '_' if no explicit alias is present.
        """
        if key in self._KEY_ALIASES:
            return self._KEY_ALIASES[key]
        if "/" in key:
            cand = key.replace("/", "_")
            if cand in self.settings:
                return cand
        return key

    def get(self, key: str, default=None):
        """
        Back-compat getter (QSettings-like). Supports 'a/b' keys.
        """
        k = self._normalize_key(key)
        return self.settings.get(k, default)

    def set(self, key: str, value, persist: bool = True):
        """
        Back-compat setter (QSettings-like). Supports 'a/b' keys.
        """
        k = self._normalize_key(key)
        self.settings[k] = value
        if persist:

            self.save_settings()

    def set_user_agent(self, ua: str) -> bool:
        self.settings["user_agent"] = ua or ""
        ok = self.save_settings()
        # apply regardless; failure to apply != failure to save
        self.apply_network_overrides()
        return ok

    # ----------------------------------------------------------------------
    # Proxy (best-effort for QtWebEngine via Chromium flags)
    def _maybe_configure_process_proxy(self) -> None:
        mode = (self.settings.get("proxy_mode") or "system").lower()
        if mode == "system":
            return  # use OS defaults
        flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")

        if mode == "none":
            if "--no-proxy-server" not in flags:
                flags = (flags + " --no-proxy-server").strip()
            os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = flags
            return

        if mode == "manual":
            ptype = (self.settings.get("proxy_type") or "http").lower()  # "http" | "socks5"
            host  = self.settings.get("proxy_host") or ""
            port  = int(self.settings.get("proxy_port") or 0)
            user  = self.settings.get("proxy_user") or ""
            pwd   = self.settings.get("proxy_password") or ""
            if not host or not port:
                return

            # proxy URL format: scheme://[user[:pwd]@]host:port
            scheme = "socks5" if "socks" in ptype else "http"
            auth   = f"{user}:{pwd}@" if user else ""
            proxy_url = f"{scheme}://{auth}{host}:{port}"

            piece = f"--proxy-server={proxy_url}"
            if piece not in flags:
                flags = (flags + " " + piece).strip()
            os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = flags

    # ----------------------------------------------------------------------
    # WebEngine profile
    def _create_web_profile(self) -> QWebEngineProfile:
        profile = QWebEngineProfile(self.__class__.__name__)  # named profile

        # Cache & persistent storage
        cache_dir   = self.cache_dir / "web_cache"
        storage_dir = self.data_dir  / "web_storage"
        cache_dir.mkdir(parents=True, exist_ok=True)
        storage_dir.mkdir(parents=True, exist_ok=True)

        # Persist cache?
        try:
            # Qt 6: enum lives on QWebEngineProfile
            if self.settings.get("persist_cache", True):
                profile.setHttpCacheType(QWebEngineProfile.DiskHttpCache)
                profile.setCachePath(str(cache_dir))
            else:
                profile.setHttpCacheType(QWebEngineProfile.MemoryHttpCache)
        except Exception:
            # Fallback: set path only if persisting
            if self.settings.get("persist_cache", True):
                profile.setCachePath(str(cache_dir))

        # Persist cookies & HTML5 storage?
        if self.settings.get("persist_cookies", True):
            try:
                profile.setPersistentCookiesPolicy(QWebEngineProfile.ForcePersistentCookies)
            except Exception:
                try:
                    profile.setPersistentCookiesPolicy(QWebEngineProfile.AllowPersistentCookies)
                except Exception:
                    pass
            profile.setPersistentStoragePath(str(storage_dir))
        else:
            try:
                profile.setPersistentCookiesPolicy(QWebEngineProfile.NoPersistentCookies)
            except Exception:
                pass
            # leave storage path unset for purely in-memory session

        # User-Agent
        ua = self.user_agent()
        if ua:
            try:
                profile.setHttpUserAgent(ua)
            except Exception:
                pass

        # Accept-Language (Qt ≥ 6.5) or via interceptor headers
        al = self.accept_language()
        if al:
            try:
                # Available in newer Qt; if not, our interceptor will handle headers
                profile.setHttpAcceptLanguage(al)  # type: ignore[attr-defined]
            except Exception:
                pass

        # Request interceptor: headers (global/per-host), DNT, client hints spoofing
        self._install_request_interceptor(profile)

        return profile

    # settings.py
    def _install_request_interceptor(self, profile: QWebEngineProfile) -> None:
        """
        Install our HeaderInterceptor so Accept-Language / DNT / custom headers are sent.
        """
        try:
            # Your class is named HeaderInterceptor, not RequestInterceptor
            from .request_interceptor import HeaderInterceptor  # <- correct class
        except Exception:
            return

        # Create and attach
        try:
            interceptor = HeaderInterceptor(self)  # pass SettingsManager
            profile.setUrlRequestInterceptor(interceptor)
        except Exception:
            pass

    # def _install_request_interceptor(self, profile: QWebEngineProfile) -> None:
    #     """
    #     Try existing RequestInterceptor implementations:
    #     1) RequestInterceptor(self)  -> full SettingsManager access (preferred)
    #     2) RequestInterceptor(headers_dict) -> static headers only
    #     """
    #     try:
    #         from .request_interceptor import RequestInterceptor  # your implemented interceptor
    #     except Exception:
    #         return

    #     # Build a static header baseline (used if ctor wants dict):
    #     baseline_headers: Dict[str, str] = {}
    #     # Accept-Language (if not empty)
    #     if self.settings.get("accept_language"):
    #         baseline_headers["Accept-Language"] = self.settings["accept_language"]
    #     # DNT
    #     if self.settings.get("send_dnt", False):
    #         baseline_headers["DNT"] = "1"
    #     # Global headers
    #     for k, v in (self.settings.get("headers_global") or {}).items():
    #         baseline_headers[str(k)] = str(v)

    #     # Optional: spoof a minimal set of UA Client Hints (many servers ignore if UA not matching)
    #     if self.settings.get("spoof_chrome_client_hints", False):
    #         # Very basic, static hints — your interceptor can refine per-platform
    #         baseline_headers.setdefault("Sec-CH-UA", '"Chromium";v="120", "Not.A/Brand";v="24"')
    #         baseline_headers.setdefault("Sec-CH-UA-Platform", '"Windows"')
    #         baseline_headers.setdefault("Sec-CH-UA-Mobile", "?0")

    #     # Try constructor with SettingsManager first (most powerful)
    #     interceptor = None
    #     try:
    #         interceptor = RequestInterceptor(self)  # type: ignore[arg-type]
    #     except Exception:
    #         try:
    #             interceptor = RequestInterceptor(baseline_headers)  # type: ignore[arg-type]
    #         except Exception:
    #             interceptor = None

        if interceptor is not None:
            try:
                profile.setUrlRequestInterceptor(interceptor)
            except Exception:
                pass

    # ----------------------------------------------------------------------
    # Live updates (when settings UI changes values)
    def update_settings(self, patch: Dict[str, Any], persist: bool = True, reconfigure_profile: bool = True) -> None:
        """Deep-merge patch into self.settings; optionally save & re-apply UA/interceptor."""
        def deep_merge(dst: Dict[str, Any], src: Dict[str, Any]) -> Dict[str, Any]:
            for k, v in src.items():
                if isinstance(v, dict) and isinstance(dst.get(k), dict):
                    dst[k] = deep_merge(dict(dst[k]), v)
                else:
                    dst[k] = v
            return dst

        self.settings = deep_merge(dict(self.settings), patch)
        if persist:
            self.save_settings()
        if reconfigure_profile:
            self.apply_network_overrides()

    def apply_network_overrides(self) -> None:
        """Re-apply UA, language, and interceptor without recreating the profile."""
        if not isinstance(self.web_profile, QWebEngineProfile):
            return

        # UA
        try:
            self.web_profile.setHttpUserAgent(self.user_agent() or "")
        except Exception:
            pass

        # Accept-Language
        al = self.accept_language() or ""
        try:
            self.web_profile.setHttpAcceptLanguage(al)  # type: ignore[attr-defined]
        except Exception:
            pass

        # Interceptor (replace / update)
        self._install_request_interceptor(self.web_profile)
