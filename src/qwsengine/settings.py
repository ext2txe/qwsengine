import json
import shutil
from pathlib import Path
from PySide6.QtCore import QStandardPaths, QByteArray, QRect, Qt
from PySide6.QtWebEngineCore import QWebEngineProfile
from PySide6.QtNetwork import QNetworkProxy, QNetworkProxyFactory

from .request_interceptor import HeaderInterceptor
from .logging_utils import LogManager

class SettingsManager:
    def __init__(self):
        # Paths
        self.config_dir = Path(QStandardPaths.writableLocation(QStandardPaths.ConfigLocation)) / "qwsengine"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.config_dir / "settings.json"

        # Defaults
        self.default_settings = {
            "start_url": "https://codaland.com/ipcheck.php",
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
            "proxy_mode": "system",       # "system" | "manual" | "none"
            "proxy_type": "http",         # "http" | "socks5" (manual only)
            "proxy_host": "",
            "proxy_port": 0,
            "proxy_user": "",
            "proxy_password": "",

            #if accept_language is "", then headers will not be  inserted
            "accept_language": "en-US,en;q=0.9",           # e.g. "en-US,en;q=0.9" or "de-DE,de;q=0.9,en;q=0.8"
            "send_dnt": False,
            "spoof_chrome_client_hints": False,
        }

        # Load settings JSON first
        self.settings = self._load_settings()

        # Logging
        self.log_manager = LogManager(self.config_dir) if self.settings.get("logging_enabled", True) else None

        # Persistent WebEngine profile (applies UA, cache, cookies)
        self.web_profile = self._setup_web_profile()


    # ---------------- Persistence ----------------
    # -----------------------------
    # Settings (JSON-backed)
    # -----------------------------
    def _load_settings(self) -> dict:
        data = {}
        try:
            if self.config_file.exists():
                with self.config_file.open("r", encoding="utf-8") as f:
                    data = json.load(f) or {}
        except Exception as e:
            # Backup corrupted file and continue with defaults
            try:
                backup = self.config_dir / f"settings.bad.{int(__import__('time').time())}.json"
                self.config_file.replace(backup)  # atomic move
                if hasattr(self, "log_manager") and self.log_manager:
                    self.log_manager.log_error(f"settings.json was invalid ({e}); moved to {backup.name} and regenerated.")
                else:
                    print(f"Error reading settings: {e}\nBacked up to: {backup}")
            except Exception:
                # Fall back to simple rename if replace fails
                try:
                    self.config_file.rename(self.config_file.with_suffix(".bad.json"))
                except Exception:
                    pass
            data = {}

        # Merge onto defaults (keep falsy values)
        merged = dict(self.default_settings)
        for k, v in data.items():
            if v is not None:
                merged[k] = v

        # Persist merged to ensure new keys are written
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            with self.config_file.open("w", encoding="utf-8") as f:
                json.dump(merged, f, indent=2)
        except Exception as e:
            if hasattr(self, "log_manager") and self.log_manager:
                self.log_manager.log_error(f"Failed to write settings.json: {e}")

        return merged

    # ---------- JSON persistence (private) ----------

    def save_settings(self) -> bool:
        """
        Legacy API: write current self.settings to disk. Returns True/False.
        """
        return self._save_settings(self.settings)


    def _save_settings(self, obj: dict) -> bool:
        """
        Write the provided dict to settings.json. Returns True on success.
        """
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            with self.config_file.open("w", encoding="utf-8") as f:
                json.dump(obj, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            # Use your logger if available; fall back to print
            if hasattr(self, "log_manager") and self.log_manager:
                self.log_manager.log_error(f"Failed to save settings.json: {e}")
            else:
                print(f"Error saving settings: {e}")
            return False

    def load_settings(self) -> dict:
        """
        Legacy API: reload from disk and return the merged dict.
        """
        self.settings = self._load_settings()
        return self.settings

    def _load_settings(self) -> dict:
        """
        Read settings.json, merge with defaults, and write back the merged file.
        """
        data = {}
        try:
            if self.config_file.exists():
                with self.config_file.open("r", encoding="utf-8") as f:
                    data = json.load(f) or {}
        except Exception as e:
            if hasattr(self, "log_manager") and self.log_manager:
                self.log_manager.log_error(f"Failed to read settings.json: {e}")
            else:
                print(f"Error reading settings: {e}")
            data = {}

        merged = dict(self.default_settings)
        for k, v in data.items():
            # keep explicit falsy values (0, False, "")
            if v is not None:
                merged[k] = v

        # Persist merged to include any new default keys
        self._save_settings(merged)
        return merged

    # ---------- JSON persistence (private) ----------

    def _save_settings_old(self) -> bool:
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, 'w', encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving settings: {e}")
            return False

    # Optional ultra-short alias if some code calls 'save()'
    def save(self):
        self.save_settings()

    def _load_settings_into_cache(self):
        """Pull persisted values into a simple dict cache once at startup."""
        def _get(key, default=""):
            val = self._qsettings.value(key, default)
            return val if val is not None else default

        # Normalize on 'user_agent' key; keep a fallback for older builds.
        ua = _get("user_agent", "")
        if not ua:
            ua = _get("userAgent", "")  # backward compatibility

        self._cache["user_agent"] = ua
        # ... load any other settings you need similarly

    # ---------------- Accessors ----------------
    def get(self, key, default=None):
        """
        Read a value from the loaded settings dict, falling back to defaults.
        Does not use any _cache object.
        """
        if self.settings is None:
            # extremely early use before _load_settings
            return self.default_settings.get(key, default)
        return self.settings.get(key, self.default_settings.get(key, default))

    def set(self, key, value):
        """
        Update settings dict and persist to JSON.
        """
        self.settings[key] = value
        self._save_settings(self.settings)

    def update(self, new_settings: dict) -> None:
        self.settings.update(new_settings)

    # ---------------- Logging Proxies ----------------
    def log(self, message, level="INFO"):
        if self.log_manager:
            self.log_manager.log(message, level)

    def log_navigation(self, url, title="", tab_id=None):
        if self.log_manager and self.get("log_navigation", True):
            self.log_manager.log_navigation(url, title, tab_id)

    def log_tab_action(self, action, tab_id=None, details=""):
        if self.log_manager and self.get("log_tab_actions", True):
            self.log_manager.log_tab_action(action, tab_id, details)

    def log_error(self, error_msg, context=""):
        if self.log_manager and self.get("log_errors", True):
            self.log_manager.log_error(error_msg, context)

    def log_system_event(self, event, details=""):
        if self.log_manager:
            self.log_manager.log_system_event(event, details)

    def get_log_file_path(self):
        if self.log_manager:
            return self.log_manager.get_log_file_path()
        return None

    # ---------------- User Agent  ----------------
    def apply_user_agent(self) -> None:
        """Apply the configured UA immediately to the current profile."""
        try:
            profile = self.get_web_profile()
            ua = self.get("user_agent", "").strip()
            if ua:
                profile.setHttpUserAgent(ua)
                self.log_system_event("Custom User-Agent applied", ua)
            else:
                # Reset to original default UA captured at startup
                default_ua = getattr(self, "initial_user_agent", profile.httpUserAgent())
                profile.setHttpUserAgent(default_ua)
                self.log_system_event("User-Agent reset to default", default_ua)
        except Exception as e:
            self.log_error(f"apply_user_agent failed: {e}")

    def get_user_agent(self) -> str:
        try:
            return self.get_web_profile().httpUserAgent()
        except Exception:
            return self.get("user_agent", "") or ""

    def set_user_agent(self, new_ua: str):
        new_ua = (new_ua or "").strip()
        self.set("user_agent", new_ua)  # persists to JSON
        if self.web_profile:
            self.web_profile.setHttpUserAgent(new_ua)
            if self.log_manager:
                self.log_manager.log(f"UA applied at runtime: {new_ua or '(default)'}", "SYSTEM")

    # ---------------- Web Profile ----------------
    # -----------------------------
    # Web profile (Chromium storage)
    # -----------------------------

    def _setup_web_profile(self) -> QWebEngineProfile:
        profile_dir = self.config_dir / "profile"
        profile_dir.mkdir(parents=True, exist_ok=True)

        profile = QWebEngineProfile("QWSEnginePersistent")

        # Storage & cache paths
        profile.setPersistentStoragePath(str(profile_dir.resolve()))
        (profile_dir / "cache").mkdir(exist_ok=True)
        profile.setCachePath(str((profile_dir / "cache").resolve()))
        (profile_dir / "downloads").mkdir(exist_ok=True)
        profile.setDownloadPath(str((profile_dir / "downloads").resolve()))

        # Cookie persistence
        pcp = QWebEngineProfile.PersistentCookiesPolicy
        policy = getattr(pcp, "ForcePersistentCookies", pcp.AllowPersistentCookies) \
                if self.get("persist_cookies", True) else pcp.NoPersistentCookies
        profile.setPersistentCookiesPolicy(policy)

        # Cache mode (best-effort)
        try:
            if self.get("persist_cache", True):
                profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.DiskHttpCache)
            else:
                profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.MemoryHttpCache)
        except Exception:
            pass

        # User-Agent (global)
        ua = (self.get("user_agent", "") or "").strip()
        if ua:
            profile.setHttpUserAgent(ua)

        # Accept-Language (global, if supported by your Qt build)
        al = (self.get("accept_language", "") or "").strip()
        try:
            if al and hasattr(profile, "setHttpAcceptLanguage"):
                profile.setHttpAcceptLanguage(al)  # Qt 6.5+ typically
        except Exception:
            pass

        # Install header interceptor (per-request overrides)
        self._header_interceptor = HeaderInterceptor(self)
        try:
            profile.setUrlRequestInterceptor(self._header_interceptor)
        except Exception:
            # Older Qt builds used .setRequestInterceptor; keep this for safety
            if hasattr(profile, "setRequestInterceptor"):
                profile.setRequestInterceptor(self._header_interceptor)

        # Proxies (if you have this function)
        try:
            self.apply_proxy_settings()
        except Exception as e:
            if self.log_manager:
                self.log_manager.log_error(f"apply_proxy_settings failed: {e}")

        # (Optional) Log
        if self.log_manager:
            try:
                self.log_manager.log(f"UA on startup: {profile.httpUserAgent()}", "SYSTEM")
                if al:
                    self.log_manager.log(f"Accept-Language on startup: {al}", "SYSTEM")
            except Exception:
                pass

        return profile


    def _setup_web_profile_original(self) -> QWebEngineProfile:
        profile_dir = self.config_dir / "profile"
        profile_dir.mkdir(parents=True, exist_ok=True)

        profile = QWebEngineProfile("QWSEnginePersistent")

        # Storage paths
        profile.setPersistentStoragePath(str(profile_dir.resolve()))
        cache_dir = profile_dir / "cache"
        cache_dir.mkdir(exist_ok=True)
        profile.setCachePath(str(cache_dir.resolve()))
        dl_dir = profile_dir / "downloads"
        dl_dir.mkdir(exist_ok=True)
        profile.setDownloadPath(str(dl_dir.resolve()))

        # Cookies persistence
        pcp = QWebEngineProfile.PersistentCookiesPolicy
        if self.get("persist_cookies", True):
            policy = getattr(pcp, "ForcePersistentCookies", pcp.AllowPersistentCookies)
        else:
            policy = pcp.NoPersistentCookies
        profile.setPersistentCookiesPolicy(policy)

        # Cache persistence (best-effort; not all bindings expose this)
        try:
            if self.get("persist_cache", True):
                profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.DiskHttpCache)
            else:
                profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.MemoryHttpCache)
        except Exception:
            pass

        # User-Agent from settings
        ua = (self.get("user_agent", "") or "").strip()
        if ua:
            profile.setHttpUserAgent(ua)

        # Optional logging
        if self.log_manager:
            try:
                self.log_manager.log(f"UA on startup: {profile.httpUserAgent()}", "SYSTEM")
                self.log_manager.log(f"Profile storage: {profile.persistentStoragePath()}", "SYSTEM")
                self.log_manager.log(f"Cache path: {profile.cachePath()}", "SYSTEM")
                self.log_manager.log(f"Download path: {profile.downloadPath()}", "SYSTEM")
            except Exception:
                pass

        # If you apply proxies globally, call your existing method here:
        try:
            self.apply_proxy_settings()
        except Exception as e:
            if self.log_manager:
                self.log_manager.log_error(f"apply_proxy_settings failed: {e}")

        return profile

    def get_web_profile(self):
        return self.web_profile


    def apply_proxy_settings(self) -> None:
        """Apply proxy settings from settings.json to the entire app."""
        try:
            mode = (self.get("proxy_mode", "system") or "system").lower()
            if mode == "none":
                QNetworkProxyFactory.setUseSystemConfiguration(False)
                QNetworkProxy.setApplicationProxy(QNetworkProxy(QNetworkProxy.NoProxy))
                self.log_system_event("Proxy disabled")
                return

            if mode == "system":
                # Use OS/system proxy (PAC, etc.)
                QNetworkProxyFactory.setUseSystemConfiguration(True)
                QNetworkProxy.setApplicationProxy(QNetworkProxy(QNetworkProxy.DefaultProxy))
                self.log_system_event("Using system proxy")
                return

            if mode == "manual":
                ptype = (self.get("proxy_type", "http") or "http").lower()
                qt_type = QNetworkProxy.HttpProxy if ptype == "http" else QNetworkProxy.Socks5Proxy
                host = self.get("proxy_host", "")
                port = int(self.get("proxy_port", 0) or 0)
                proxy = QNetworkProxy(qt_type, host, port)

                user = self.get("proxy_user", "")
                pwd  = self.get("proxy_password", "")
                if user or pwd:
                    proxy.setUser(user)
                    proxy.setPassword(pwd)

                QNetworkProxyFactory.setUseSystemConfiguration(False)
                QNetworkProxy.setApplicationProxy(proxy)
                pretty = f"{ptype}://{host}:{port}"
                self.log_system_event("Manual proxy applied", pretty)
                return

            self.log_error(f"Unknown proxy_mode: {mode}")

        except Exception as e:
            self.log_error(f"apply_proxy_settings failed: {e}")

    # ---------------- Browser Data ----------------
    def clear_browser_data(self) -> bool:
        """
        Clear cookies, cache, downloads, and other stored browser data
        by deleting the profile directory contents.
        """
        try:
            profile_dir = self.config_dir / "profile"
            if not profile_dir.exists():
                return True
            for child in profile_dir.iterdir():
                try:
                    if child.is_dir():
                        shutil.rmtree(child, ignore_errors=True)
                    else:
                        child.unlink(missing_ok=True)
                except Exception as e:
                    if self.log_manager:
                        self.log_manager.log_error(f"Failed to remove {child}: {e}")
            if self.log_manager:
                self.log_manager.log_system_event("Browser data cleared")
            return True
        except Exception as e:
            if self.log_manager:
                self.log_manager.log_error(f"Error clearing browser data: {e}")
            return False

    # ---------------- Browser Window Geometry ----------------
    def restore_window_geometry(self, widget) -> bool:
        """
        Restore last saved window geometry and state.
        Returns True if something was applied.
        """
        applied = False
        try:
            # 1) If we have a remembered normal rect, set that first (so un-maximizing later is correct).
            nr = self.get("window_normal_rect")
            if isinstance(nr, list) and len(nr) == 4:
                x, y, w, h = nr
                if all(isinstance(v, int) for v in (x, y, w, h)) and w > 0 and h > 0:
                    widget.setGeometry(QRect(x, y, w, h))
                    applied = True

            # 2) If we have Qt's serialized geometry, try that too.
            geo_b64 = self.get("window_geometry", "")
            if geo_b64:
                ba = QByteArray.fromBase64(geo_b64.encode("ascii"))
                if not ba.isEmpty():
                    ok = widget.restoreGeometry(ba)
                    applied = applied or ok

            # 3) Apply window state last so it wins visually.
            if self.get("window_fullscreen", False):
                widget.setWindowState(Qt.WindowFullScreen)
                applied = True
            elif self.get("window_maximized", False):
                widget.setWindowState(Qt.WindowMaximized)
                applied = True

            if applied:
                self.log_system_event("Window geometry restored")
            else:
                self.log_system_event("No saved window geometry found (using defaults)")
            return applied

        except Exception as e:
            self.log_error(f"restore_window_geometry failed: {e}")
            return False

    def save_window_geometry(self, widget) -> bool:
        """
        Save current window geometry and state (including *normal* rect when maximized/fullscreen).
        """
        try:
            # Serialized Qt geometry (works cross-platform & DPI-aware)
            ba = widget.saveGeometry()
            geo_b64 = bytes(ba.toBase64()).decode("ascii")
            self.set("window_geometry", geo_b64)

            # State
            is_max = bool(widget.isMaximized())
            is_full = bool(widget.isFullScreen())
            self.set("window_maximized", is_max)
            self.set("window_fullscreen", is_full)

            # Normal rect: if maximized/fullscreen, capture the size it would have when unmaximized
            if is_full or is_max:
                nr = widget.normalGeometry()
            else:
                nr = widget.geometry()
            self.set("window_normal_rect", [int(nr.x()), int(nr.y()), int(nr.width()), int(nr.height())])

            ok = self.save_settings()
            if ok:
                self.log_system_event("Window geometry saved")
            else:
                self.log_error("Failed to save window geometry (settings file)")
            return ok

        except Exception as e:
            self.log_error(f"save_window_geometry failed: {e}")
            return False
