# qwsengine/core/context.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from qwsengine.core.settings import SettingsManager


@dataclass
class AppContext:
    """
    Lightweight application context for QwsEngine.

    This is intentionally simple and side-effect free:
    it just stores references to shared services/objects.
    """

    # Optional reference to the Qt application instance
    qt_app: Optional[Any] = None

    # Settings manager for the application
    settings_manager: Optional[SettingsManager] = None

    # Add more shared objects here as needed, e.g.:
    # logger: Optional[Logger] = None
    # plugin_manager: Optional[PluginManager] = None

    @classmethod
    def create(cls, qt_app: Any | None = None) -> "AppContext":
        """
        Convenience constructor that creates a fresh SettingsManager
        and wires it into the context.
        """
        ctx = cls(qt_app=qt_app, settings_manager=SettingsManager())
        return ctx
