# QWS Engine Script Playback Feature

This package provides a simple script playback feature for QWS Engine. Currently, it supports basic navigation in the current active tab, with the infrastructure to expand to additional actions.

## Files Included

- `script_manager.py` - Core functionality for script management and playback
- `script_management_ui.py` - UI components for script management
- `controller_window_changes.py` - Changes to integrate with controller_window.py
- `__init__.py` - Updated module exports
- `sample_navigation_script.json` - Sample script demonstrating navigation

## Integration Instructions

1. **Copy the script_manager.py and script_management_ui.py files** to your QWS Engine source directory (`src/qwsengine/`).

2. **Update your controller_window.py file** as shown in controller_window_changes.py:
   - Add the import for ScriptManagementWidget
   - Add the script management tab in the init_ui method
   - Update the launch_browser method to update the script management widget reference

3. **Update your __init__.py file** to include the new modules.

4. **Copy the sample_navigation_script.json** file to your scripts directory. This will usually be in the QWS Engine configuration directory under "scripts".

## Current Features

- **Script Management UI**: A dedicated tab for script management in the controller window
- **Navigation Support**: Navigate to URLs in the current active tab
- **Script Editing**: View and edit script JSON in the UI
- **Quick Script Creation**: Create simple navigation scripts by entering URLs

## Future Enhancements

The current implementation is designed to be easily extended with additional action types:

1. **Navigate in New Tab**: Open URLs in new tabs
2. **Resize Browser Window**: Set specific window dimensions
3. **Save Page HTML**: Save the HTML of the current page
4. **Save Screenshot**: Capture a screenshot of the current page
5. **Log Message**: Add custom log messages to script execution

## Implementation Details

The script playback feature is built around three main components:

1. **ScriptManager**: Manages script loading, saving, and execution
2. **ScriptPlayer**: Handles the playback of scripts, executing actions one by one
3. **ScriptManagementWidget**: Provides a UI for managing and playing scripts

Scripts are stored as JSON files with a simple structure:

```json
{
  "name": "Script Name",
  "version": "1.0",
  "created_at": "ISO timestamp",
  "actions": [
    {
      "action_type": "navigate",
      "timestamp": 12345.678,
      "url": "https://example.com"
    }
  ]
}
```

Each action has a specific type and parameters. The current implementation supports the "navigate" action type, which navigates to a URL in the current active tab.

## Testing

To test the script playback feature:

1. Integrate the files as described above
2. Launch QWS Engine
3. Open the controller window
4. Click on the "Script Management" tab
5. Select the sample script from the dropdown
6. Click "Play" to execute the script
7. Watch as the browser navigates through the URLs in the script

## Troubleshooting

If you encounter any issues:

- Make sure all files are copied to the correct locations
- Check that the controller_window.py file is updated correctly
- Verify that the scripts directory exists and contains the sample script
- Check the script log in the UI for any error messages
- Ensure the browser window is launched before attempting to play a script

## Adding New Action Types

To add a new action type:

1. Create a new action class in script_manager.py
2. Add the action type to the from_dict method in ScriptAction
3. Implement the execution logic in the _execute_next_action method of ScriptPlayer
