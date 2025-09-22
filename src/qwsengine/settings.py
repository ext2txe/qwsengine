import json
import shutil
from pathlib import Path
from PySide6.QtCore import QStandardPaths
from PySide6.QtWebEngineCore import QWebEngineProfile

from .logging_utils import LogManager

class SettingsManager:
    def __init__(self):
        self.config_dir = Path(QStandardPaths.writableLocation(QStandardPaths.ConfigLocation)) / "qwsengine"
        self.config_file = self.config_dir / "settings.json"
        self.default_settings = {
            "start_url": "https://flanq.com",
            "window_width": 1024,
            "window_height": 768,
            "logging_enabled": True,
            "log_navigation": True,
            "log_tab_actions": True,
            "log_errors": True,
            "persist_cookies": True,
            "persist_cache": True,
        }
        self.settings = self._load_settings()

        # Logging
        self.log_manager = LogManager(self.config_dir) if self.get("logging_enabled", True) else None

        # Persistent web profile
        self.web_profile = self._setup_web_profile()

    # ---------------- Persistence ----------------
    def _load_settings(self):
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding="utf-8") as f:
                    loaded = json.load(f)
                settings = self.default_settings.copy()
                settings.update(loaded)
                return settings
        except Exception as e:
            print(f"Error loading settings: {e}")
        return self.default_settings.copy()

    def save_settings(self) -> bool:
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, 'w', encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving settings: {e}")
            return False

    # ---------------- Accessors ----------------
    def get(self, key, default=None):
        return self.settings.get(key, default)

    def set(self, key, value) -> None:
        self.settings[key] = value

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

    # ---------------- Web Profile ----------------
    def _setup_web_profile(self):
        try:
            profile_dir = self.config_dir / "profile"
            profile_dir.mkdir(parents=True, exist_ok=True)

            if self.get("persist_cookies", True):
                profile = QWebEngineProfile("QWSEnginePersistent")
                absolute_profile_path = str(profile_dir.resolve())
                profile.setPersistentStoragePath(absolute_profile_path)
                profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
                if self.log_manager:
                    self.log_manager.log(f"Created NAMED persistent profile: QWSEnginePersistent", "SYSTEM")
                    self.log_manager.log(f"Absolute storage path: {absolute_profile_path}", "SYSTEM")
            else:
                profile = QWebEngineProfile()
                if self.log_manager:
                    self.log_manager.log("Using off-the-record profile (no persistence)", "SYSTEM")

            if self.get("persist_cache", True):
                cache_path = profile_dir / "cache"
                cache_path.mkdir(exist_ok=True)
                absolute_cache_path = str(cache_path.resolve())
                profile.setCachePath(absolute_cache_path)
                profile.setHttpCacheMaximumSize(100 * 1024 * 1024)
                profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.DiskHttpCache)
                if self.log_manager:
                    self.log_manager.log(f"Absolute cache path: {absolute_cache_path}", "SYSTEM")

            download_path = profile_dir / "downloads"
            download_path.mkdir(exist_ok=True)
            absolute_download_path = str(download_path.resolve())
            profile.setDownloadPath(absolute_download_path)
            if self.log_manager:
                self.log_manager.log(f"Profile configured - Storage: {profile.persistentStoragePath()}", "SYSTEM")
                self.log_manager.log(f"Download path: {absolute_download_path}", "SYSTEM")

            return profile
        except Exception as e:
            if self.log_manager:
                self.log_manager.log_error(f"Failed to setup web profile: {str(e)}")
            return QWebEngineProfile()

    def get_web_profile(self):
        return self.web_profile

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
