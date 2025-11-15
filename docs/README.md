# QWS Engine Script Playback Feature

This document explains the implementation of the script playback feature for QWS Engine.

## Overview

The script playback feature allows users to:

1. Record browser interactions as scripts
2. Edit scripts to modify or fine-tune actions
3. Play back scripts to automate browser interactions
4. Save and load scripts for reuse

## Implementation Details

The implementation consists of several new modules:

### 1. `script_recorder.py`

This core module provides the fundamental classes:

- **ScriptAction (Base Class)**: The foundation for all script actions
- Action Types (subclasses of ScriptAction):
  - `NavigateAction`: Navigate to a URL
  - `ResizeAction`: Resize the browser window
  - `ClickAction`: Click on an element (by selector or position)
  - `InputAction`: Input text into a form field
  - `WaitAction`: Pause script execution
  - `ScreenshotAction`: Capture a screenshot

- **ScriptRecorder**: Records user actions in the browser
  - Monitors browser events (navigation, clicks, resizes)
  - Stores actions in a chronological list
  - Saves recordings to script files (.qwsscript format, JSON-based)

- **ScriptPlayer**: Plays back recorded scripts
  - Loads scripts from files
  - Executes actions in sequence
  - Handles playback control (start, stop, pause)
  - Emits signals for UI updates

### 2. `script_editor.py`

Provides a dialog for editing scripts:
- View and modify the list of actions
- Edit action parameters
- Add, delete, or reorder actions
- Save changes to script files

### 3. `script_playback_controls.py`

UI component for the controller window:
- Record button to start/stop recording
- Playback controls (play, pause, stop)
- Script selection dropdown
- Progress indicator
- Status display

### 4. Integration with `controller_window.py`

Adds a new "Script Playback" tab to the controller window with:
- Script playback controls
- Integration with browser window for recording and playback

## Supported Actions

The script playback feature supports these actions:

1. **Navigate**: Load a URL in the browser
2. **Resize**: Change browser window dimensions
3. **Click**: Click on elements (by selector or position)
4. **Input**: Enter text in form fields
5. **Wait**: Pause execution for a specified duration
6. **Screenshot**: Capture a screenshot of the current page

## Script Format

Scripts are stored in `.qwsscript` files using a JSON structure:

```json
{
  "version": "0.1",
  "created_at": "2023-04-01T12:34:56.789",
  "name": "example_script.qwsscript",
  "actions": [
    {
      "action_type": "resize",
      "timestamp": 1680350096.789,
      "width": 1024,
      "height": 768
    },
    {
      "action_type": "navigate",
      "timestamp": 1680350097.123,
      "url": "https://example.com"
    },
    {
      "action_type": "wait",
      "timestamp": 1680350098.456,
      "duration_ms": 1000
    },
    {
      "action_type": "click",
      "timestamp": 1680350099.789,
      "selector": "#submit-button",
      "x": 150,
      "y": 200,
      "use_position": false
    }
  ]
}
```

## How to Use

1. **Recording Scripts**:
   - Click the "Record" button to start recording
   - Perform actions in the browser
   - Click "Stop" when finished
   - Click "Save" to save the script
   
2. **Editing Scripts**:
   - Select a script from the dropdown
   - Click the edit button (✎)
   - Modify actions in the editor
   - Click "Save" to save changes

3. **Playing Scripts**:
   - Select a script from the dropdown
   - Click "Play" to start playback
   - Use "Pause" or "Stop" to control playback

## Technical Notes

- **Element Selection**: The recorder attempts to identify elements by CSS selectors when possible, with positional clicks as fallback
- **Event Monitoring**: Uses Qt event filters to capture browser events
- **JavaScript Execution**: Implements browser interactions via JavaScript for compatibility
- **Persistence**: Scripts are saved in a dedicated "scripts" folder under the application's config directory

## Future Enhancements

Potential improvements for the script playback feature:

1. **Conditional Actions**: Add support for if/else conditions based on page state
2. **Looping**: Allow repeating sequences of actions
3. **Variables**: Support for variables to make scripts more dynamic
4. **Error Handling**: Enhanced error recovery during playback
5. **Export/Import**: Exchange scripts between different QWS Engine installations
6. **Script Libraries**: Reuse common action sequences across scripts

## Installation

To use this feature, simply copy the provided files to your QWS Engine source directory and run the application. The script playback tab will appear in the controller window.
