✅ 1. DEVELOPER_QUICKSTART.md

Below is the complete file ready to save at project root:

Developer Quick Start Guide

Welcome to the QwsEngine development environment!
This guide gets you from zero → productive in 5 minutes.

🚀 Quick Start
1. Clone the Repository
git clone <repo-url>
cd qwsengine


(If you downloaded a zip, simply extract and cd into the folder.)

2. Install Python 3.10+

Check version:

python3 --version

3. Install Dependencies
pip install -r requirements.txt


requirements.txt includes both runtime & dev dependencies.

4. Run the Application
Standard launch:
python src/app.py

Running inside a VNC/containerized environment:
./run_qwsengine_vnc.sh


You should now see:

Browser Window (main UI)

Controller Window (automation controls)

🧩 Understanding the Codebase (Fast Orientation)
src/
  app.py                    # Entrypoint
  qwsengine/
      main_window.py        # BrowserWindow (main UI)
      browser_tab.py        # Individual tab logic
      browser_operations.py # High-level browser automation
      controller_window.py  # Automation/controller UI
      controller_script.py  # Script execution engine
      script_manager.py     # Load, validate, store scripts
      script_management_ui.py # UI for script handling
      settings.py           # App settings
      settings_dialog.py    # UI for settings
      request_interceptor.py# Intercepts HTTP requests
      log_manager.py        # Logging utilities
      ui/                   # Menu, toolbar, tab helpers


Experimental tools:

src/config8r.py
src/processors.py
src/scopes.py
playground/

🛠 Useful Commands
Run black formatter
black .

Run pylint
pylint src/qwsengine

Run pytest (future tests)
pytest

📌 Key Extension Points (Fast Reference)
Goal	Modify
Add toolbar action	ui/toolbar_builder.py + main_window.py
Add menu action	ui/menu_builder.py
Add script action	script_manager.py, controller_script.py
Add controller action	controller_window.py
Add browser operation	browser_operations.py
Add settings	settings.py + settings_dialog.py
📂 Scripts

JSON scripts live in:

scripts/


User scripts stored automatically in:

~/.qwsengine/scripts/


Run them through the Controller Window.

🎯 Developer Workflow Cheat Sheet

Start app → python src/app.py

Modify code → edit module in src/qwsengine

Reload app → rerun command

Test feature via BrowserWindow or ControllerWindow

Commit changes with clear message

Update docs if feature changes script or UI behavior

🙋 Need More Help?

See:

README.md (project summary)

ARCHITECTURE.md (system structure)

CONTRIBUTING.md (how to contribute)

SCRIPT_SPEC.md (script definition)

🎉 You're Ready!

Happy hacking—and welcome to QwsEngine development.

✅ 2. Project Folder & File Structure Layout

This version is clean, organized, and suitable for documentation or onboarding.

You can include this as PROJECT_STRUCTURE.md, or embed into README.md.

QwsEngine Project Structure
qwsengine/
│
├── README.md                      # Main documentation (root)
├── ARCHITECTURE.md                # Architecture overview
├── CONTRIBUTING.md                # Contribution guidelines
├── DEVELOPER_QUICKSTART.md        # Rapid onboarding guide
├── SCRIPT_SPEC.md                 # Script JSON format
│
├── requirements.txt               # Runtime + dev dependencies
├── run_qwsengine_vnc.sh           # Launch script for container/VNC environments
│
├── docs/                          # User & integration documentation
│   ├── INSTALL.md
│   ├── USER_GUIDE.md
│   ├── INTEGRATION.md
│   └── requirements-dev.txt
│
├── resources/                     # Icons, images, bundled assets
│   ├── icons/
│   └── resources.qrc              # Qt resource collection
│
├── scripts/                       # Example & bundled automation scripts
│   └── sample_navigation_script.json
│
├── playground/                    # Experimental & PoC scripts
│   ├── poc.py
│   ├── PoC2.py
│   └── poc_v0.py
│
└── src/
    ├── app.py                     # Application entrypoint
    ├── __init__.py
    │
    ├── config8r.py                # Experimental config UI
    ├── processors.py              # Experimental HTML/DOM processors
    ├── scopes.py                  # Experimental DOM scoping
    │
    └── qwsengine/                 # Main package
        ├── __init__.py
        ├── about_dialog.py
        ├── app_info.py
        ├── main_window.py
        ├── browser_tab.py
        ├── browser_operations.py
        ├── controller_window.py
        ├── controller_script.py
        ├── script_manager.py
        ├── script_management_ui.py
        ├── settings.py
        ├── settings_dialog.py
        ├── log_manager.py
        ├── request_interceptor.py
        │
        └── ui/                    # Modular UI subsystem
            ├── __init__.py
            ├── menu_builder.py
            ├── toolbar_builder.py
            ├── tab_manager.py
