📘 CONTRIBUTING.md
Contributing to QwsEngine

Thank you for your interest in improving QwsEngine!
This document explains how to set up the development environment, run the application, and safely make changes.

1. Developer Setup
Requirements

Python 3.10+

pip

A modern OS (Windows, macOS, Linux)

Install dependencies
pip install -r requirements.txt

2. Running the App
python src/app.py


Optional: Run inside VNC container

./run_qwsengine_vnc.sh

3. Code Structure Cheat Sheet
src/
  app.py                 # Entrypoint
  qwsengine/
      main_window.py     # Main UI
      browser_tab.py     # Tab logic
      browser_operations.py
      controller_window.py
      controller_script.py
      script_manager.py
      script_management_ui.py
      settings.py
      settings_dialog.py
      log_manager.py
      request_interceptor.py
      ui/
         menu_builder.py
         toolbar_builder.py
         tab_manager.py


Experimental tools (not part of core app):

src/config8r.py
src/processors.py
src/scopes.py
playground/*.py

4. Contributing Rules
4.1 Follow the Layered Architecture
Layer	Purpose
UI (ui/, dialogs)	Buttons, menus, windows
Application (main_window, controller_window)	Application logic, state
Automation (browser_operations, controller_script)	Browser operations & script execution
Core utilities	Settings, logging

Do not put automation code into UI files.
Do not put UI behavior into automation layers.

4.2 Adding New Features
Add a toolbar/menu action

Modify:

ui/toolbar_builder.py

ui/menu_builder.py

Add implementation in:

BrowserWindow

BrowserTab (if needed)

Add controller features

Modify:

controller_window.py

controller_script.py

Optionally add to browser operations.

Add new script actions

Modify:

script_manager.py

controller_script.py

Document the JSON schema in:

docs/USER_GUIDE.md

SCRIPT_SPEC.md (this repo)

Add settings

Modify:

settings.py (SettingsManager)

settings_dialog.py (UI)

4.3 Logging Guidelines

Use:

from .log_manager import log
log.info("message")
log.error("error message")


Avoid:

print()

Custom ad-hoc loggers

4.4 Code Style

Follow PEP8

Use type hints where possible

Keep functions small and single-purpose

5. Testing

Tests (when added) will go under:

tests/


For now, manual testing via controller + browser is recommended.

6. Submitting PRs

Before submitting:
    - Include a clear description of the feature or fix
    - Reference which extension point you built on
    - Ensure the app launches cleanly
    - Update docs if you changed behavior
