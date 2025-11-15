# QWS Engine Script Playback User Guide

This guide explains how to use the script playback feature in QWS Engine.

## Introduction

The script playback feature allows you to:
- Record browser interactions as reusable scripts
- Edit scripts to modify or fine-tune actions
- Play back scripts to automate browser interactions
- Save and load scripts for future use

This is ideal for testing, demos, automation, and repetitive tasks.

## Getting Started

### Accessing the Feature

1. Launch QWS Engine
2. Open the controller window
3. Click on the "Script Playback" tab

You'll see a panel with recording and playback controls.

### The Script Playback Tab

The script playback tab contains:

- **Script Selection**: Dropdown to select existing scripts
- **Recording Controls**: Buttons to record, stop, and save scripts
- **Playback Controls**: Buttons to play, pause, and stop script execution
- **Progress Bar**: Shows playback progress
- **Status Display**: Shows current status and messages

## Recording Scripts

### Starting a Recording

1. Click the "⚫ Record" button to start recording
2. The status indicator will change to "Recording..."
3. Perform actions in the browser window that you want to record

### Recordable Actions

The recorder captures these browser interactions:
- Navigation (URL loading)
- Window resizing
- Button clicks
- Form input
- Page scrolling

### Stopping a Recording

1. Click the "⬛ Stop" button to stop recording
2. The status will update to show the number of recorded actions

### Saving a Recording

1. Click the "💾 Save" button
2. Enter a name for your script in the save dialog
3. Click "Save" to store the script

## Playing Back Scripts

### Starting Playback

1. Select a script from the dropdown menu
2. Click the "▶ Play" button
3. The script will begin executing in the browser window

### Controlling Playback

During playback, you can:
- Click "⏸ Pause" to temporarily pause execution
- Click "▶ Resume" to continue playback after pausing
- Click "⬛ Stop" to stop playback completely

### Playback Progress

The progress bar shows:
- Current position in the script
- Percentage of completion

## Editing Scripts

### Opening the Script Editor

1. Select a script from the dropdown
2. Click the edit button (✎)
3. The script editor dialog will open

### Script Editor Interface

The script editor shows:
- A list of actions in the script
- Details of the selected action
- Action parameters

### Editing Actions

To edit an action:
1. Select it in the list
2. Modify its parameters in the JSON editor
3. Click "Update Action" to apply changes

### Managing Actions

You can also:
- Add new actions
- Delete existing actions
- Reorder actions using the "Move Up" and "Move Down" buttons

### Saving Changes

1. Click "Save" to save your changes
2. Click "Save As..." to create a new script

## Understanding Action Types

### Navigate

Opens a URL in the browser:
```json
{
  "action_type": "navigate",
  "url": "https://example.com"
}
```

### Resize

Changes the browser window size:
```json
{
  "action_type": "resize",
  "width": 1024,
  "height": 768
}
```

### Click

Clicks on an element:
```json
{
  "action_type": "click",
  "selector": "#submit-button",
  "x": 150,
  "y": 200,
  "use_position": false
}
```

Setting `use_position` to `true` will click at the coordinates rather than the selector.

### Input

Enters text in a form field:
```json
{
  "action_type": "input",
  "selector": "input[name='username']",
  "text": "johndoe"
}
```

### Wait

Pauses script execution:
```json
{
  "action_type": "wait",
  "duration_ms": 1000
}
```

### Screenshot

Takes a screenshot:
```json
{
  "action_type": "screenshot",
  "filename": "login_page"
}
```

## Tips and Best Practices

### Reliable Scripts

For more reliable scripts:
- Use meaningful selectors rather than position clicks
- Add wait actions between interactions
- Keep scripts focused on a single task
- Test scripts on different window sizes

### Optimizing Scripts

To optimize your scripts:
- Remove unnecessary wait times
- Group related actions together
- Add comments in the description fields
- Use descriptive script names

### Script Management

For effective script management:
- Create a library of reusable script components
- Regularly test and update scripts
- Document script purpose and usage
- Back up important scripts

## Troubleshooting

### Recording Issues

If recording doesn't capture actions:
- Ensure the browser window is in focus
- Try interacting more slowly
- Check that the controller window shows "Recording..."

### Playback Issues

If playback doesn't work correctly:
- Check that selectors still match the page elements
- Add longer wait times between actions
- Ensure the browser window is visible and active
- Try with a different browser window size

### Editor Issues

If the editor doesn't save changes:
- Check that your JSON is valid
- Ensure you have write permissions to the scripts directory
- Click "Update Action" before saving the script

## Example Script

Here's a sample script that searches Google:

```json
{
  "version": "0.1",
  "name": "google_search.qwsscript",
  "actions": [
    {
      "action_type": "navigate",
      "url": "https://www.google.com"
    },
    {
      "action_type": "wait",
      "duration_ms": 1000
    },
    {
      "action_type": "click",
      "selector": "input[name='q']"
    },
    {
      "action_type": "input",
      "selector": "input[name='q']",
      "text": "QWS Engine"
    },
    {
      "action_type": "click",
      "selector": "input[name='btnK']"
    },
    {
      "action_type": "wait",
      "duration_ms": 2000
    },
    {
      "action_type": "screenshot",
      "filename": "search_results"
    }
  ]
}
```

## Advanced Usage

### Creating Scripts Manually

You can create scripts manually:
1. Create a JSON file with the structure shown above
2. Save it with a `.qwsscript` extension in the scripts directory
3. Refresh the script list in the script playback tab

### Running Scripts from Command Line

Support for running scripts from the command line is planned for a future release.

## Conclusion

The script playback feature provides powerful automation capabilities for QWS Engine. By recording, editing, and playing back scripts, you can save time and ensure consistency in your browser interactions.

For further assistance, refer to the documentation or contact support.
