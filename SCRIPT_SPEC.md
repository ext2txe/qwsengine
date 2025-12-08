📘 SCRIPT_SPEC.md
QwsEngine Script Specification

The JSON schema for automation workflows executed by QwsEngine.

1. Overview

A script is a JSON file describing a sequence of browser actions.
Scripts are run through the Controller Window and interpreted by:

ScriptManager

ControllerScript

BrowserOperations

Example script:

{
  "name": "Navigate Example",
  "actions": [
    { "action_type": "navigate", "url": "https://example.com" },
    { "action_type": "wait", "seconds": 2 },
    { "action_type": "execute_js", "script": "document.title" }
  ]
}

2. Script Discovery

Scripts are loaded from:

Repo folder:

scripts/


User folder:

~/.qwsengine/scripts/

3. JSON Schema (High-Level)

A script contains:

Field	Type	Required	Description
name	string	✓	Script display name
description	string	optional	Displayed in UI
actions	list	✓	Ordered sequence of actions
4. Action Format

Each action has at least:

Field	Description
action_type	The kind of action to perform

Additional fields depend on the action type.

5. Supported Actions (Current Implementation)
5.1 navigate
{ "action_type": "navigate", "url": "https://example.com" }


Executes:

Load URL in current tab (via BrowserOperations)

5.2 wait
{ "action_type": "wait", "seconds": 3 }


Blocks the script for N seconds.

5.3 execute_js
{ "action_type": "execute_js", "script": "document.title" }


Executes JavaScript in the active tab.

Additional actions may exist or be added based on the codebase.

The above represent the confirmed minimal set in this submission.

6. Future Expansion

To add new action types:

Implement behavior in:

controller_script.py
browser_operations.py


Extend script format in:

script_manager.py


Document new structure here.
