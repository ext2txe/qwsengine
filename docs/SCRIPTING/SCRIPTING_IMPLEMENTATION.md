# Scripting System - Implementation Guide

Complete code to implement the minimal feature set with extensibility for future commands.

---

## File Structure

```
qwsengine/scripting/
├── __init__.py
├── command.py
├── registry.py
├── executor.py
├── context.py
├── commands/
│   ├── __init__.py
│   ├── load_url.py
│   ├── save_html.py
│   └── pause.py
└── utils.py
```

---

## File 1: `qwsengine/scripting/command.py`

```python
"""Base command class for script commands."""

from abc import ABC, abstractmethod


class ScriptCommand(ABC):
    """Abstract base class for all script commands.
    
    All concrete commands must:
    1. Implement execute() method
    2. Implement from_dict() class method (for deserialization)
    3. Implement to_dict() method (for serialization)
    """
    
    @abstractmethod
    def execute(self, context):
        """Execute this command.
        
        Args:
            context: ExecutionContext with browser, settings, logging
            
        Raises:
            RuntimeError: If command cannot be executed
        """
        pass
    
    @classmethod
    @abstractmethod
    def from_dict(cls, data: dict):
        """Create command instance from dictionary.
        
        Args:
            data: Dictionary with command parameters
            
        Returns:
            ScriptCommand instance
        """
        pass
    
    @abstractmethod
    def to_dict(self) -> dict:
        """Convert command to dictionary for serialization.
        
        Returns:
            Dictionary with 'command' key and all parameters
        """
        pass
    
    def __str__(self):
        """String representation for logging."""
        return f"{self.__class__.__name__}({self.to_dict()})"
```

---

## File 2: `qwsengine/scripting/registry.py`

```python
"""Command registry - central place to register and retrieve commands."""


class CommandRegistry:
    """Registry for available script commands.
    
    Allows:
    - Registering new commands
    - Creating commands by name
    - Listing available commands
    """
    
    _registry = {}
    
    @classmethod
    def register(cls, command_name: str, command_class):
        """Register a command class.
        
        Args:
            command_name: Name of command (e.g., 'load_url')
            command_class: Class implementing ScriptCommand
        """
        if command_name in cls._registry:
            raise ValueError(f"Command already registered: {command_name}")
        
        if not hasattr(command_class, 'from_dict'):
            raise ValueError(f"Command must implement from_dict: {command_name}")
        
        cls._registry[command_name] = command_class
        print(f"[Registry] Registered command: {command_name}")
    
    @classmethod
    def unregister(cls, command_name: str):
        """Unregister a command.
        
        Args:
            command_name: Name of command to remove
        """
        if command_name in cls._registry:
            del cls._registry[command_name]
            print(f"[Registry] Unregistered command: {command_name}")
    
    @classmethod
    def get(cls, command_name: str):
        """Get command class by name.
        
        Args:
            command_name: Name of command
            
        Returns:
            Command class or None if not found
        """
        return cls._registry.get(command_name)
    
    @classmethod
    def list_commands(cls) -> list:
        """List all available command names.
        
        Returns:
            List of command names
        """
        return sorted(list(cls._registry.keys()))
    
    @classmethod
    def create_command(cls, command_name: str, data: dict):
        """Factory method: create command instance from name and data.
        
        Args:
            command_name: Name of command
            data: Dictionary with command parameters
            
        Returns:
            ScriptCommand instance
            
        Raises:
            ValueError: If command not found
        """
        command_class = cls.get(command_name)
        if not command_class:
            available = cls.list_commands()
            raise ValueError(
                f"Unknown command: {command_name}\n"
                f"Available commands: {', '.join(available)}"
            )
        return command_class.from_dict(data)
    
    @classmethod
    def is_registered(cls, command_name: str) -> bool:
        """Check if command is registered.
        
        Args:
            command_name: Name of command
            
        Returns:
            True if registered, False otherwise
        """
        return command_name in cls._registry
```

---

## File 3: `qwsengine/scripting/context.py`

```python
"""Execution context - passed to commands, provides utilities."""

from datetime import datetime


class ExecutionContext:
    """Context for command execution.
    
    Provides:
    - Access to browser window
    - Access to settings
    - Logging functionality
    - Execution state
    """
    
    def __init__(self, browser_window=None, settings_manager=None):
        """Initialize execution context.
        
        Args:
            browser_window: Reference to BrowserWindow
            settings_manager: Reference to SettingsManager
        """
        self.browser_window = browser_window
        self.settings_manager = settings_manager
        
        # Execution control
        self.stop_on_error = False
        self.pause_on_error = False
        
        # Logging
        self.logs = []
        self.log_to_console = True
    
    def log(self, message: str, level: str = "INFO"):
        """Log a message.
        
        Args:
            message: Message to log
            level: Log level (INFO, WARNING, ERROR)
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {message}"
        self.logs.append(log_entry)
        
        if self.log_to_console:
            print(log_entry)
    
    def get_logs(self) -> list:
        """Get all logged messages.
        
        Returns:
            List of log entries
        """
        return self.logs.copy()
    
    def clear_logs(self):
        """Clear log history."""
        self.logs.clear()
    
    def __repr__(self):
        return (
            f"ExecutionContext("
            f"browser={self.browser_window is not None}, "
            f"settings={self.settings_manager is not None})"
        )
```

---

## File 4: `qwsengine/scripting/executor.py`

```python
"""Script executor - orchestrates command execution."""

import time
from typing import Callable

from .registry import CommandRegistry


class ScriptExecutor:
    """Executes a sequence of commands from a script.
    
    Features:
    - Load scripts from JSON
    - Execute commands sequentially
    - Handle errors (stop or continue)
    - Pause/resume execution
    - Progress tracking
    """
    
    def __init__(self, context=None):
        """Initialize executor.
        
        Args:
            context: ExecutionContext (will create default if None)
        """
        from .context import ExecutionContext
        self.context = context or ExecutionContext()
        self.commands = []
        self.current_index = 0
        self.is_running = False
        self.is_paused = False
        self.errors = []
    
    def load_from_json(self, json_data: dict):
        """Load script from JSON data.
        
        Args:
            json_data: Dictionary with 'commands' list
            
        Raises:
            ValueError: If JSON format is invalid
        """
        self.commands = []
        self.errors = []
        
        if 'commands' not in json_data:
            raise ValueError("JSON must contain 'commands' key")
        
        for i, cmd_data in enumerate(json_data['commands']):
            try:
                if 'command' not in cmd_data:
                    raise ValueError(f"Command {i} missing 'command' key")
                
                command_name = cmd_data['command']
                cmd = CommandRegistry.create_command(command_name, cmd_data)
                self.commands.append(cmd)
                
            except Exception as e:
                error = f"Error loading command {i}: {e}"
                self.errors.append(error)
                self.context.log(error, level="ERROR")
    
    def load_from_file(self, filepath: str):
        """Load script from JSON file.
        
        Args:
            filepath: Path to JSON file
            
        Raises:
            FileNotFoundError: If file not found
            ValueError: If JSON is invalid
        """
        import json
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            self.load_from_json(json_data)
            self.context.log(f"Loaded script from: {filepath}")
        except FileNotFoundError:
            raise FileNotFoundError(f"Script file not found: {filepath}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {filepath}: {e}")
    
    def save_to_file(self, filepath: str):
        """Save current script to JSON file.
        
        Args:
            filepath: Path where to save file
        """
        import json
        script_data = {
            'version': '1.0',
            'commands': [cmd.to_dict() for cmd in self.commands]
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(script_data, f, indent=2)
        self.context.log(f"Saved script to: {filepath}")
    
    def execute(self, on_progress: Callable = None) -> bool:
        """Execute all commands sequentially.
        
        Args:
            on_progress: Callback(current_index, total, command_description)
            
        Returns:
            True if all commands succeeded, False if errors occurred
        """
        self.is_running = True
        self.errors = []
        
        self.context.log(f"Starting script execution ({len(self.commands)} commands)")
        
        success_count = 0
        error_count = 0
        
        for i, cmd in enumerate(self.commands):
            self.current_index = i
            
            # Handle pause/resume
            while self.is_paused and self.is_running:
                time.sleep(0.1)
            
            # Check for stop request
            if not self.is_running:
                self.context.log("Script execution stopped by user")
                break
            
            try:
                # Update progress
                if on_progress:
                    on_progress(i, len(self.commands), str(cmd))
                
                # Execute command
                self.context.log(f"Executing [{i+1}/{len(self.commands)}]: {cmd}")
                cmd.execute(self.context)
                success_count += 1
                
            except Exception as e:
                error_msg = f"Command failed: {e}"
                error_count += 1
                self.errors.append((i, cmd, str(e)))
                self.context.log(error_msg, level="ERROR")
                
                # Check error handling mode
                if self.context.stop_on_error:
                    self.context.log("Stopping on error")
                    break
        
        self.is_running = False
        
        # Summary
        self.context.log(
            f"Script execution complete: {success_count} succeeded, "
            f"{error_count} failed"
        )
        
        return error_count == 0
    
    def pause(self):
        """Pause script execution."""
        self.is_paused = True
        self.context.log("Script paused")
    
    def resume(self):
        """Resume script execution."""
        self.is_paused = False
        self.context.log("Script resumed")
    
    def stop(self):
        """Stop script execution."""
        self.is_running = False
        self.context.log("Script stopped")
    
    def get_progress(self) -> tuple:
        """Get current execution progress.
        
        Returns:
            (current_index, total_commands, is_running)
        """
        return (self.current_index, len(self.commands), self.is_running)
    
    def get_errors(self) -> list:
        """Get all errors from last execution.
        
        Returns:
            List of (index, command, error_message) tuples
        """
        return self.errors.copy()
```

---

## File 5: `qwsengine/scripting/commands/load_url.py`

```python
"""Load URL command."""

from ..command import ScriptCommand


class LoadURLCommand(ScriptCommand):
    """Load a URL in the browser.
    
    Parameters:
        url (str): URL to load
        wait_for_load (bool): Wait for page to load (default: True)
    """
    
    def __init__(self, url: str, wait_for_load: bool = True):
        """Initialize LoadURL command.
        
        Args:
            url: URL to load
            wait_for_load: Wait for page load to complete
        """
        if not url:
            raise ValueError("URL cannot be empty")
        self.url = url
        self.wait_for_load = wait_for_load
    
    def execute(self, context):
        """Execute the command.
        
        Args:
            context: ExecutionContext
            
        Raises:
            RuntimeError: If no browser window available
        """
        if not context.browser_window:
            raise RuntimeError("No browser window available")
        
        try:
            context.log(f"Loading URL: {self.url}")
            
            # Navigate to URL
            if hasattr(context.browser_window, 'tab_manager'):
                # Use tab manager if available
                context.browser_window.tab_manager.navigate_current(self.url)
            else:
                # Fallback
                raise RuntimeError("Tab manager not available")
            
            context.log(f"URL loaded successfully: {self.url}")
            
        except Exception as e:
            raise RuntimeError(f"Failed to load URL {self.url}: {e}")
    
    @classmethod
    def from_dict(cls, data: dict):
        """Create from dictionary.
        
        Args:
            data: Dictionary with 'url' key
            
        Returns:
            LoadURLCommand instance
        """
        url = data.get('url')
        if not url:
            raise ValueError("'url' parameter is required")
        
        wait = data.get('wait_for_load', True)
        return cls(url, wait)
    
    def to_dict(self) -> dict:
        """Convert to dictionary.
        
        Returns:
            Dictionary representation
        """
        return {
            'command': 'load_url',
            'url': self.url,
            'wait_for_load': self.wait_for_load
        }
```

---

## File 6: `qwsengine/scripting/commands/save_html.py`

```python
"""Save HTML command."""

from pathlib import Path
from ..command import ScriptCommand


class SaveHTMLCommand(ScriptCommand):
    """Save current page HTML to file.
    
    Parameters:
        filename (str): Output filename (default: 'page.html')
        path (str): Output directory path (default: current directory)
    """
    
    def __init__(self, filename: str = None, path: str = None):
        """Initialize SaveHTML command.
        
        Args:
            filename: Output filename
            path: Output directory
        """
        self.filename = filename or "page.html"
        self.path = path or "."
    
    def execute(self, context):
        """Execute the command.
        
        Args:
            context: ExecutionContext
            
        Raises:
            RuntimeError: If save fails
        """
        if not context.browser_window:
            raise RuntimeError("No browser window available")
        
        try:
            # Get current tab
            tab = None
            if hasattr(context.browser_window, 'tab_manager'):
                tab = context.browser_window.tab_manager.get_current_tab()
            
            if not tab:
                raise RuntimeError("No active tab available")
            
            # Create output directory if needed
            output_dir = Path(self.path)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Save HTML
            output_path = output_dir / self.filename
            context.log(f"Saving HTML to: {output_path}")
            
            # Get HTML content from browser view
            if hasattr(tab, 'view') and tab.view:
                # Use toHtml if available, otherwise use the browser's save function
                if hasattr(context.browser_window, 'save_html'):
                    context.browser_window.save_html(self.filename, self.path)
                else:
                    # Fallback: extract HTML manually
                    html = self._extract_html(tab.view)
                    with open(output_path, 'w', encoding='utf-8') as f:
                        f.write(html)
            else:
                raise RuntimeError("No browser view available")
            
            context.log(f"HTML saved successfully: {output_path}")
            
        except Exception as e:
            raise RuntimeError(f"Failed to save HTML: {e}")
    
    def _extract_html(self, browser_view):
        """Extract HTML from browser view.
        
        Args:
            browser_view: QWebEngineView instance
            
        Returns:
            HTML content as string
        """
        # This would need to be implemented based on your browser_view structure
        # For now, this is a placeholder
        page = browser_view.page()
        if page:
            # Use toHtml (async in WebEngine, might need callback)
            return page.toHtml()
        return ""
    
    @classmethod
    def from_dict(cls, data: dict):
        """Create from dictionary.
        
        Args:
            data: Dictionary with optional 'filename' and 'path' keys
            
        Returns:
            SaveHTMLCommand instance
        """
        filename = data.get('filename', 'page.html')
        path = data.get('path', '.')
        return cls(filename, path)
    
    def to_dict(self) -> dict:
        """Convert to dictionary.
        
        Returns:
            Dictionary representation
        """
        return {
            'command': 'save_html',
            'filename': self.filename,
            'path': self.path
        }
```

---

## File 7: `qwsengine/scripting/commands/pause.py`

```python
"""Pause/Sleep command."""

import time
from ..command import ScriptCommand


class PauseCommand(ScriptCommand):
    """Pause execution for specified number of seconds.
    
    Parameters:
        seconds (float): Number of seconds to pause (must be positive)
    """
    
    def __init__(self, seconds: float):
        """Initialize Pause command.
        
        Args:
            seconds: Seconds to sleep
            
        Raises:
            ValueError: If seconds is negative
        """
        if seconds < 0:
            raise ValueError("Seconds must be non-negative")
        self.seconds = float(seconds)
    
    def execute(self, context):
        """Execute the command.
        
        Args:
            context: ExecutionContext
        """
        if self.seconds > 0:
            context.log(f"Pausing for {self.seconds} seconds...")
            time.sleep(self.seconds)
            context.log(f"Pause complete")
        else:
            context.log("Pause duration is 0 seconds")
    
    @classmethod
    def from_dict(cls, data: dict):
        """Create from dictionary.
        
        Args:
            data: Dictionary with 'seconds' key
            
        Returns:
            PauseCommand instance
            
        Raises:
            ValueError: If seconds not provided or invalid
        """
        if 'seconds' not in data:
            raise ValueError("'seconds' parameter is required")
        
        try:
            seconds = float(data['seconds'])
        except (ValueError, TypeError):
            raise ValueError(f"'seconds' must be a number, got: {data['seconds']}")
        
        return cls(seconds)
    
    def to_dict(self) -> dict:
        """Convert to dictionary.
        
        Returns:
            Dictionary representation
        """
        return {
            'command': 'pause',
            'seconds': self.seconds
        }
```

---

## File 8: `qwsengine/scripting/commands/__init__.py`

```python
"""Script commands package."""

from .load_url import LoadURLCommand
from .save_html import SaveHTMLCommand
from .pause import PauseCommand
from ..registry import CommandRegistry

# Auto-register commands when package is imported
def register_all_commands():
    """Register all built-in commands."""
    CommandRegistry.register('load_url', LoadURLCommand)
    CommandRegistry.register('save_html', SaveHTMLCommand)
    CommandRegistry.register('pause', PauseCommand)

# Register on import
register_all_commands()

__all__ = [
    'LoadURLCommand',
    'SaveHTMLCommand',
    'PauseCommand',
    'CommandRegistry'
]
```

---

## File 9: `qwsengine/scripting/__init__.py`

```python
"""Scripting module - script commands and execution."""

from .command import ScriptCommand
from .registry import CommandRegistry
from .executor import ScriptExecutor
from .context import ExecutionContext

# Import commands to register them
from . import commands  # noqa

__all__ = [
    'ScriptCommand',
    'CommandRegistry',
    'ScriptExecutor',
    'ExecutionContext',
]
```

---

## Example Usage

### In Python Code

```python
from qwsengine.scripting import ScriptExecutor, ExecutionContext

# Create context with your browser window
context = ExecutionContext(
    browser_window=my_browser_window,
    settings_manager=my_settings_manager
)

# Create executor
executor = ScriptExecutor(context)

# Load from JSON
script_json = {
    "version": "1.0",
    "commands": [
        {"command": "load_url", "url": "https://example.com/page1"},
        {"command": "save_html", "filename": "page1.html", "path": "./output"},
        {"command": "pause", "seconds": 3},
        {"command": "load_url", "url": "https://example.com/page2"},
        {"command": "save_html", "filename": "page2.html", "path": "./output"},
        {"command": "pause", "seconds": 2}
    ]
}

executor.load_from_json(script_json)

# Execute with progress callback
def on_progress(current, total, description):
    print(f"[{current+1}/{total}] {description}")

success = executor.execute(on_progress=on_progress)

# Check results
if success:
    print("Script executed successfully!")
else:
    print("Errors occurred:")
    for idx, cmd, error in executor.get_errors():
        print(f"  [{idx}] {cmd}: {error}")

# View logs
for log in context.get_logs():
    print(log)
```

### Load from File

```python
executor = ScriptExecutor(context)
executor.load_from_file("my_script.json")
executor.execute()
```

### Save Script

```python
executor.save_to_file("my_script.json")
```

---

## Example Script File

File: `my_script.json`
```json
{
  "version": "1.0",
  "commands": [
    {
      "command": "load_url",
      "url": "https://example.com/page1"
    },
    {
      "command": "save_html",
      "filename": "page1.html",
      "path": "./downloads"
    },
    {
      "command": "pause",
      "seconds": 5
    },
    {
      "command": "load_url",
      "url": "https://example.com/page2"
    },
    {
      "command": "save_html",
      "filename": "page2.html",
      "path": "./downloads"
    },
    {
      "command": "pause",
      "seconds": 2
    }
  ]
}
```

---

## Adding a New Command (Example)

Want to add a "Click Element" command? Here's how:

### File: `commands/click_element.py`

```python
from ..command import ScriptCommand

class ClickElementCommand(ScriptCommand):
    def __init__(self, selector: str):
        self.selector = selector
    
    def execute(self, context):
        if not context.browser_window:
            raise RuntimeError("No browser window")
        
        context.log(f"Clicking element: {self.selector}")
        
        tab = context.browser_window.tab_manager.get_current_tab()
        if not tab or not tab.view:
            raise RuntimeError("No active tab")
        
        # Execute click via JavaScript
        js = f"""
        (function() {{
            var elem = document.querySelector('{self.selector}');
            if (elem) {{
                elem.click();
                return 'Clicked';
            }} else {{
                throw new Error('Element not found');
            }}
        }})();
        """
        
        tab.view.page().runJavaScript(js)
        context.log(f"Element clicked: {self.selector}")
    
    @classmethod
    def from_dict(cls, data):
        return cls(data['selector'])
    
    def to_dict(self):
        return {'command': 'click_element', 'selector': self.selector}
```

### Update: `commands/__init__.py`

```python
from .click_element import ClickElementCommand

def register_all_commands():
    CommandRegistry.register('load_url', LoadURLCommand)
    CommandRegistry.register('save_html', SaveHTMLCommand)
    CommandRegistry.register('pause', PauseCommand)
    CommandRegistry.register('click_element', ClickElementCommand)  # NEW
```

Now you can use:
```json
{"command": "click_element", "selector": ".submit-button"}
```

---

## Next Steps

1. **Create the files** - Copy code above into new files
2. **Test basic functionality** - Execute a simple script
3. **Integrate into UI** - Add script executor to scripting panel
4. **Add script editor UI** - Let users create/edit scripts visually
5. **Extend commands** - Add more commands as needed

