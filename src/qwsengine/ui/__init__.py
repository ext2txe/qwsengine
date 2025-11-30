"""
UI components for BrowserWindow.

This package contains modular UI components extracted from the
monolithic main_window.py for better maintainability.
"""

from .menu_builder import MenuBuilder
from .toolbar_builder import ToolbarBuilder
from .tab_manager import TabManager
#from .navigation_manager import NavigationManager
#from .script_manager import ScriptManager

__all__ = [
    'MenuBuilder',
    'ToolbarBuilder',
    'TabManager',
    # 'NavigationManager',
    # 'ScriptManager',
]