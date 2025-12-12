"""
Script Manager for QWS Engine

This module provides functionality for creating, loading, and executing scripts.
Initially focusing on simple navigation in the current tab.
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable

from PySide6.QtCore import QObject, Signal, QTimer, QUrl
from PySide6.QtWidgets import QWidget, QMessageBox
from PySide6.QtWebEngineWidgets import QWebEngineView

from qwsengine.core.log_manager import LogManager


class ScriptAction:
    """Base class for all script actions"""
    
    def __init__(self, action_type: str):
        self.action_type = action_type
        self.timestamp = time.time()
    
    def to_dict(self) -> dict:
        """Convert action to dictionary for serialization"""
        return {
            "action_type": self.action_type,
            "timestamp": self.timestamp
        }
    
    @staticmethod
    def from_dict(data: dict) -> 'ScriptAction':
        """Create action from dictionary"""
        action_type = data.get("action_type", "unknown")
        
        # Create specific action types based on the action_type
        if action_type == "navigate":
            return NavigateAction(data["url"])
        elif action_type == "navigate_new_tab":
            return NavigateNewTabAction(data["url"])
        elif action_type == "resize":
            return ResizeAction(data["width"], data["height"])
        elif action_type == "save_html":
            return SaveHtmlAction(data.get("filename", ""))
        elif action_type == "save_screenshot":
            return SaveScreenshotAction(data.get("filename", ""))
        elif action_type == "log_message":
            return LogMessageAction(data["message"])
        else:
            # Default fallback for unknown action types
            action = ScriptAction(action_type)
            action.timestamp = data.get("timestamp", time.time())
            return action


class NavigateAction(ScriptAction):
    """Action to navigate to a URL in the current tab"""
    
    def __init__(self, url: str):
        super().__init__("navigate")
        self.url = url
    
    def to_dict(self) -> dict:
        data = super().to_dict()
        data["url"] = self.url
        return data


class NavigateNewTabAction(ScriptAction):
    """Action to open a new tab and navigate to a URL"""
    
    def __init__(self, url: str):
        super().__init__("navigate_new_tab")
        self.url = url
    
    def to_dict(self) -> dict:
        data = super().to_dict()
        data["url"] = self.url
        return data


class ResizeAction(ScriptAction):
    """Action to resize the browser window"""
    
    def __init__(self, width: int, height: int):
        super().__init__("resize")
        self.width = width
        self.height = height
    
    def to_dict(self) -> dict:
        data = super().to_dict()
        data["width"] = self.width
        data["height"] = self.height
        return data


class SaveHtmlAction(ScriptAction):
    """Action to save the current page's HTML"""
    
    def __init__(self, filename: str = ""):
        super().__init__("save_html")
        self.filename = filename
    
    def to_dict(self) -> dict:
        data = super().to_dict()
        data["filename"] = self.filename
        return data


class SaveScreenshotAction(ScriptAction):
    """Action to save a screenshot of the current page"""
    
    def __init__(self, filename: str = ""):
        super().__init__("save_screenshot")
        self.filename = filename
    
    def to_dict(self) -> dict:
        data = super().to_dict()
        data["filename"] = self.filename
        return data


class LogMessageAction(ScriptAction):
    """Action to log a message"""
    
    def __init__(self, message: str):
        super().__init__("log_message")
        self.message = message
    
    def to_dict(self) -> dict:
        data = super().to_dict()
        data["message"] = self.message
        return data


class Script:
    """Class representing a script with a sequence of actions"""
    
    def __init__(self, name: str = ""):
        self.name = name
        self.actions: List[ScriptAction] = []
        self.created_at = datetime.now().isoformat()
        self.version = "1.0"
    
    def add_action(self, action: ScriptAction):
        """Add an action to the script"""
        self.actions.append(action)
    
    def to_dict(self) -> dict:
        """Convert script to dictionary for serialization"""
        return {
            "name": self.name,
            "version": self.version,
            "created_at": self.created_at,
            "actions": [action.to_dict() for action in self.actions]
        }
    
    @staticmethod
    def from_dict(data: dict) -> 'Script':
        """Create script from dictionary"""
        script = Script(data.get("name", ""))
        script.version = data.get("version", "1.0")
        script.created_at = data.get("created_at", datetime.now().isoformat())
        
        # Convert action dictionaries to ScriptAction objects
        for action_data in data.get("actions", []):
            action = ScriptAction.from_dict(action_data)
            script.add_action(action)
        
        return script
    
    @staticmethod
    def load(file_path: Path) -> 'Script':
        """Load a script from a file"""
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        return Script.from_dict(data)
    
    def save(self, file_path: Path):
        """Save script to a file"""
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)


class ScriptPlayer(QObject):
    """Class for playing scripts"""
    
    # Signals for player events
    playback_started = Signal(Script)
    playback_finished = Signal(Script, bool)  # Script, success
    playback_error = Signal(str, ScriptAction)  # Error message, current action
    action_started = Signal(int, ScriptAction)  # Index, action
    action_finished = Signal(int, ScriptAction)  # Index, action
    
    def __init__(self, main_window=None, settings_manager=None, browser_ops=None, log_manager=None):
        super().__init__()
        self.main_window = main_window
        self.settings_manager = settings_manager
        self.browser_ops = browser_ops
        
        # Initialize log manager if not provided
        self.log_manager = log_manager
        if not self.log_manager and self.settings_manager and hasattr(self.settings_manager, "config_dir"):
            self.log_manager = LogManager(self.settings_manager.config_dir, "script_player")
        
        # Player state
        self.current_script = None
        self.current_index = -1
        self.playing = False
        self.success = True
        
        # Timer for delayed execution of actions
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._execute_next_action)
    
    def play_script(self, script: Script):
        """Start playing a script"""
        if self.playing:
            self._log_info("Already playing a script")
            return False
        
        self.current_script = script
        self.current_index = -1
        self.playing = True
        self.success = True
        
        self._log_info(f"Started playback of script: {script.name}")
        self.playback_started.emit(script)
        
        # Start playing the script
        self._execute_next_action()
        
        return True
    
    def stop(self):
        """Stop script playback"""
        if not self.playing:
            return
        
        self.playing = False
        if self.timer.isActive():
            self.timer.stop()
        
        self._log_info(f"Stopped playback of script: {self.current_script.name}")
        self.playback_finished.emit(self.current_script, self.success)
    
    def _execute_next_action(self):
        """Execute the next action in the script"""
        if not self.playing or not self.current_script:
            return
        
        # Move to the next action
        self.current_index += 1
        
        # Check if we reached the end
        if self.current_index >= len(self.current_script.actions):
            self._log_info(f"Finished playback of script: {self.current_script.name}")
            self.playing = False
            self.playback_finished.emit(self.current_script, self.success)
            return
        
        # Get the current action
        action = self.current_script.actions[self.current_index]
        
        # Emit signal
        self.action_started.emit(self.current_index, action)
        
        try:
            # Execute the action based on its type
            self._log_info(f"Executing action: {action.action_type}")
            
            if action.action_type == "navigate":
                self._execute_navigate(action)
            elif action.action_type == "navigate_new_tab":
                self._execute_navigate_new_tab(action)
            elif action.action_type == "resize":
                self._execute_resize(action)
            elif action.action_type == "save_html":
                self._execute_save_html(action)
            elif action.action_type == "save_screenshot":
                self._execute_save_screenshot(action)
            elif action.action_type == "log_message":
                self._execute_log_message(action)
            else:
                raise ValueError(f"Unknown action type: {action.action_type}")
            
            # Action completed successfully
            self.action_finished.emit(self.current_index, action)
            
        except Exception as e:
            # Handle error
            error_message = f"Error executing {action.action_type}: {str(e)}"
            self._log_error(error_message)
            self.success = False
            self.playback_error.emit(error_message, action)
            
            # Continue with next action
            self.timer.start(1000)  # 1-second delay before next action
    
    def _execute_navigate(self, action: NavigateAction):
        """Execute a navigate action"""
        if not self.main_window:
            raise ValueError("Main window is not available")
        
        # Get the current tab
        current_tab = self._get_current_tab()
        if not current_tab or not hasattr(current_tab, "browser"):
            raise ValueError("No active browser tab")
        
        # Navigate to the URL
        current_tab.browser.load(QUrl(action.url))
        
        # Schedule next action after a delay to allow page to start loading
        self.timer.start(2000)  # 2-second delay
    
    def _execute_navigate_new_tab(self, action: NavigateNewTabAction):
        """Execute a navigate_new_tab action"""
        # This will be implemented next
        raise NotImplementedError("navigate_new_tab action is not implemented yet")
    
    def _execute_resize(self, action: ResizeAction):
        """Execute a resize action"""
        # This will be implemented next
        raise NotImplementedError("resize action is not implemented yet")
    
    def _execute_save_html(self, action: SaveHtmlAction):
        """Execute a save_html action"""
        # This will be implemented next
        raise NotImplementedError("save_html action is not implemented yet")
    
    def _execute_save_screenshot(self, action: SaveScreenshotAction):
        """Execute a save_screenshot action"""
        # This will be implemented next
        raise NotImplementedError("save_screenshot action is not implemented yet")
    
    def _execute_log_message(self, action: LogMessageAction):
        """Execute a log_message action"""
        # This will be implemented next
        raise NotImplementedError("log_message action is not implemented yet")
    
    def _get_current_tab(self):
        """Get the current active tab from the main window"""
        if not self.main_window:
            return None
        
        # Try to get through tab manager
        tab_manager = getattr(self.main_window, "tab_manager", None)
        if tab_manager and hasattr(tab_manager, "get_current_tab"):
            return tab_manager.get_current_tab()
        
        # Fallback to tabs widget
        tabs = getattr(self.main_window, "tabs", None)
        if tabs:
            return tabs.currentWidget()
        
        return None
    
    def _log_info(self, message: str):
        """Log an information message"""
        if self.log_manager:
            self.log_manager.log_info("script_player", message)
        elif self.settings_manager and hasattr(self.settings_manager, "log_system_event"):
            self.settings_manager.log_system_event("script_player", message)
    
    def _log_error(self, message: str):
        """Log an error message"""
        if self.log_manager:
            self.log_manager.log_info("script_player", f"ERROR: {message}")
        elif self.settings_manager and hasattr(self.settings_manager, "log_error"):
            self.settings_manager.log_error("script_player", message)


class ScriptManager:
    """Manager class for creating and running scripts"""
    
    def __init__(self, main_window=None, settings_manager=None, browser_ops=None, log_manager=None):
        self.main_window = main_window
        self.settings_manager = settings_manager
        self.browser_ops = browser_ops
        
        # Initialize log manager if not provided
        self.log_manager = log_manager
        if not self.log_manager and self.settings_manager and hasattr(self.settings_manager, "config_dir"):
            self.log_manager = LogManager(self.settings_manager.config_dir, "script_manager")
        
        # Create script player
        self.player = ScriptPlayer(
            main_window=main_window,
            settings_manager=settings_manager,
            browser_ops=browser_ops,
            log_manager=self.log_manager
        )
        
        # Scripts directory
        if self.settings_manager and hasattr(self.settings_manager, "config_dir"):
            self.scripts_dir = Path(self.settings_manager.config_dir) / "scripts"
        else:
            self.scripts_dir = Path.home() / ".qwsengine" / "scripts"
        
        # Create scripts directory if it doesn't exist
        self.scripts_dir.mkdir(parents=True, exist_ok=True)
    
    def create_script(self, name: str) -> Script:
        """Create a new script"""
        return Script(name)
    
    def load_script(self, filename: str) -> Script:
        """Load a script from a file"""
        path = self.scripts_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"Script file not found: {filename}")
        
        return Script.load(path)
    
    def save_script(self, script: Script, filename: str = None) -> Path:
        """Save a script to a file"""
        if not filename:
            # Generate filename from script name if not provided
            filename = f"{script.name.replace(' ', '_').lower()}.json"
        
        # Ensure .json extension
        if not filename.lower().endswith(".json"):
            filename += ".json"
        
        path = self.scripts_dir / filename
        script.save(path)
        
        return path
    
    def play_script(self, script: Script) -> bool:
        """Play a script"""
        return self.player.play_script(script)
    
    def play_script_file(self, filename: str) -> bool:
        """Load and play a script from a file"""
        try:
            script = self.load_script(filename)
            return self.play_script(script)
        except Exception as e:
            if self.log_manager:
                self.log_manager.log_info("script_manager", f"ERROR: Failed to play script file: {e}")
            elif self.settings_manager and hasattr(self.settings_manager, "log_error"):
                self.settings_manager.log_error("script_manager", f"Failed to play script file: {e}")
            return False
    
    def stop_playback(self):
        """Stop script playback"""
        self.player.stop()
    
    def list_scripts(self) -> List[str]:
        """List available script files"""
        return [f.name for f in self.scripts_dir.glob("*.json")]
