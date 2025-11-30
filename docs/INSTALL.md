# QWS Engine Script Playback Installation Guide

This document provides detailed instructions for integrating the script playback feature into the existing QWS Engine codebase.

## Files Overview

The script playback feature consists of these new files:

1. `script_recorder.py` - Core functionality for recording and playing back scripts
2. `script_editor.py` - Script editing dialog
3. `script_playback_controls.py` - UI component for the controller window

## Installation Steps

Follow these steps to integrate the script playback feature:

### 1. Copy New Files

Copy these files to your QWS Engine source directory:

```
qwsengine/script_recorder.py
qwsengine/script_editor.py
qwsengine/script_playback_controls.py
```

### 2. Update Module Imports

Update the imports in the `controller_window.py` file:

```python
# Add this import at the top of the file
from .script_playback_controls import ScriptPlaybackControls
```

### 3. Add Script Playback Tab

Add a new tab for script playback in the `init_ui` method of `controller_window.py`:

```python
# Add after the Settings tab
# --- Tab 4: Script Playback ---
script_playback_tab = QWidget(self)
script_playback_layout = QVBoxLayout(script_playback_tab)
script_playback_layout.setSpacing(10)

# Add script playback controls
self.script_playback_controls = ScriptPlaybackControls(
    parent=script_playback_tab,
    browser_window=self.browser_window,
    settings_manager=self.settings_manager,
    browser_ops=self.browser_ops
)
script_playback_layout.addWidget(self.script_playback_controls)
script_playback_layout.addStretch(1)
self.tab_widget.addTab(script_playback_tab, "Script Playback")
```

### 4. Update Browser Window Reference

Modify the browser window creation in the `launch_browser` method:

```python
# After creating and showing the browser window
self.browser_window = BrowserWindow(settings_manager=self.settings_manager)
self.browser_window.show()

# Add this code to update script playback controls with new browser window
if hasattr(self, "script_playback_controls"):
    self.script_playback_controls.browser_window = self.browser_window
```

### 5. Update Package Exports

Update the `__init__.py` file to expose the new modules:

```python
__version__ = "0.4.28"  # or your current version

__all__ = [
    "settings",
    "settings_dialog",
    "browser_tab",
    "main_window",
    "script_recorder",
    "script_editor",
    "script_playback_controls",
]
```

## Verifying Installation

To verify that the script playback feature is installed correctly:

1. Launch the QWS Engine application
2. Open the controller window
3. Check that there is a "Script Playback" tab
4. Click on the tab and ensure the record and playback controls are present

## Folder Structure

The script playback feature uses these folders:

- **Scripts**: Stored in `<config_dir>/scripts/`
- **Screenshots**: When taking screenshots during playback, saved to `<config_dir>/save/`

These directories are created automatically if they don't exist.

## Troubleshooting

If you encounter issues with the script playback feature:

1. **Missing Tab**: Ensure that the controller window is correctly creating the Script Playback tab. Check for any import errors in the console.

2. **Recording Issues**: If recording doesn't capture actions, check that the event filters are installed correctly. The script_recorder logs actions to the system log.

3. **Playback Issues**: If scripts don't play back correctly, check the browser console for JavaScript errors. Most playback actions are implemented via JavaScript.

4. **File Access**: Ensure the application has write permissions to create the scripts directory and save script files.

## Script Format

Scripts are saved in a JSON format with the `.qwsscript` extension. Each script contains:

- Metadata (version, creation date, name)
- A list of actions with their parameters

The script format is designed to be human-readable and editable.

## Default Script Location

Scripts are saved in the QWS Engine configuration directory:

- **Windows**: `%APPDATA%\qwsengine\scripts\`
- **macOS**: `~/Library/Application Support/qwsengine/scripts/`
- **Linux**: `~/.qwsengine/scripts/` or `~/.config/qwsengine/scripts/`

## Custom Installation

If you need to customize the script playback feature:

### Custom Script Directory

To use a different directory for scripts:

1. Modify the `ScriptRecorder` class in `script_recorder.py`:

```python
def __init__(self, browser_window=None, settings_manager=None, custom_script_dir=None):
    super().__init__()
    self.browser_window = browser_window
    self.settings_manager = settings_manager
    
    # Directory for scripts - allow custom directory
    if custom_script_dir:
        self.scripts_dir = Path(custom_script_dir)
    elif self.settings_manager:
        self.scripts_dir = self.settings_manager.config_dir / "scripts"
    else:
        self.scripts_dir = Path.home() / ".qwsengine" / "scripts"
```

2. Pass this parameter when creating the `ScriptPlaybackControls`:

```python
self.script_playback_controls = ScriptPlaybackControls(
    parent=script_playback_tab,
    browser_window=self.browser_window,
    settings_manager=self.settings_manager,
    browser_ops=self.browser_ops,
    custom_script_dir="/path/to/custom/scripts"
)
```

### Additional Action Types

To add new types of actions:

1. Create a new action class in `script_recorder.py`:

```python
class MyCustomAction(ScriptAction):
    """Custom action implementation"""
    
    def __init__(self, param1, param2):
        super().__init__("my_custom")
        self.param1 = param1
        self.param2 = param2
    
    def to_dict(self) -> dict:
        data = super().to_dict()
        data["param1"] = self.param1
        data["param2"] = self.param2
        return data
```

2. Update the `from_dict` method in the `ScriptAction` class:

```python
@staticmethod
def from_dict(data: dict) -> 'ScriptAction':
    """Create action from dictionary"""
    action_type = data.get("action_type", "unknown")
    # ... existing code ...
    elif action_type == "my_custom":
        return MyCustomAction(data["param1"], data["param2"])
    else:
        # Default fallback
        action = ScriptAction(action_type)
        action.timestamp = data.get("timestamp", time.time())
        return action
```

3. Add execution logic in the `_execute_action` method of `ScriptPlayer`:

```python
def _execute_action(self, action: ScriptAction):
    """Execute a script action"""
    
    # Different handling based on action type
    if action.action_type == "navigate":
        self._execute_navigate(action)
    # ... existing code ...
    elif action.action_type == "my_custom":
        self._execute_my_custom(action)
    else:
        # Unknown action type
        raise ValueError(f"Unknown action type: {action.action_type}")

def _execute_my_custom(self, action: MyCustomAction):
    """Execute my custom action"""
    # Custom implementation
    # ...
    
    # Schedule next action
    self.timer.start(500)
```

### Enhancing the Recording Capabilities

To capture more complex interactions:

1. Add event filters for additional event types in `ScriptRecorder.start_recording()`:

```python
# Install additional event filters for keyboard events
if self.browser_window:
    self.browser_window.installEventFilter(self)
    
    # Monitor tabs for keyboard events too
    tabs = getattr(self.browser_window, "tabs", None)
    if tabs:
        for i in range(tabs.count()):
            tab = tabs.widget(i)
            if tab and hasattr(tab, "browser"):
                tab.browser.installEventFilter(self)
                # Also monitor key events if needed
                tab.installEventFilter(self)
```

2. Handle additional event types in the `eventFilter` method:

```python
def eventFilter(self, obj, event):
    """Filter events to record user actions"""
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QResizeEvent, QMouseEvent, QKeyEvent
    
    if not self.recording:
        return False
    
    # ... existing code for resize and mouse events ...
    
    # Handle keyboard events
    elif (isinstance(obj, QWebEngineView) and 
          event.type() == QEvent.KeyPress and 
          isinstance(event, QKeyEvent)):
        
        # Record key press action
        key = event.key()
        text = event.text()
        
        if text:
            # This could trigger a custom keyboard action
            self.record_action(KeyPressAction(key, text))
    
    return False
```

## Advanced Features

The script playback implementation can be extended with these advanced features:

### 1. Conditional Actions

Implement conditional branching based on page state:

```python
class ConditionalAction(ScriptAction):
    """Action that only executes if a condition is met"""
    
    def __init__(self, condition_selector, action):
        super().__init__("conditional")
        self.condition_selector = condition_selector
        self.action = action
```

### 2. Loop Actions

Implement repetitive actions:

```python
class LoopAction(ScriptAction):
    """Action that repeats a sequence of actions"""
    
    def __init__(self, count, actions):
        super().__init__("loop")
        self.count = count
        self.actions = actions
```

### 3. Variable Support

Add support for variables to make scripts dynamic:

```python
class SetVariableAction(ScriptAction):
    """Action to set a variable value"""
    
    def __init__(self, name, value):
        super().__init__("set_variable")
        self.name = name
        self.value = value
```

## Performance Optimization

For large scripts or complex applications, consider these optimizations:

1. **Batch Processing**: Process actions in batches to improve performance
2. **Caching**: Cache element selectors for faster access
3. **Background Processing**: Execute time-consuming operations in a background thread
4. **Progressive Loading**: Load large scripts progressively to reduce memory usage

## Security Considerations

When implementing script playback:

1. **Script Validation**: Validate scripts before playback to prevent malicious actions
2. **Sandboxed Execution**: Execute JavaScript in a sandboxed environment
3. **Resource Limits**: Limit resource usage (memory, CPU) during playback
4. **Origin Policy**: Respect same-origin policy for cross-domain interactions

## Contributing

To contribute to the script playback feature:

1. Follow the coding style of the existing QWS Engine codebase
2. Add unit tests for new functionality
3. Document new features and changes
4. Submit a pull request with a clear description of the changes

## License

The script playback feature is licensed under the same license as the QWS Engine project.
