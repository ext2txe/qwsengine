# Architecture Overview

## Core Components

### **1. Application Entrypoint — `src/app.py`**

- Creates the `QApplication` instance
    
- Initializes settings and logging
    
- Launches `BrowserWindow` and `ControllerWindow`
    

### **2. Browser Window — `main_window.py`**

Responsible for:

- Tab lifecycle management
    
- Navigation controls
    
- Menu & toolbar wiring
    
- Integration with the script system and controller
    

### **3. Browser Tabs — `browser_tab.py`**

Wraps:

- Individual `QWebEngineView`
    
- Per-tab actions
    
- JS evaluation utilities
    

### **4. Browser Operations — `browser_operations.py`**

High-level cross-tab functions such as:

- Navigation helpers
    
- DOM interaction helpers
    
- Utilities used by scripts & controller
    

### **5. Controller Window — `controller_window.py`**

A standalone window that can:

- Control the browser
    
- Run / pause / stop automation scripts
    
- Display state about operations & execution
    

### **6. Scripts & Automation**

- `script_manager.py`: loads and organizes JSON workflows
    
- `script_management_ui.py`: UI to list, run, and manage scripts
    
- `controller_script.py`: glue logic between scripts and the controller window
    

### **7. Settings & Logging**

- `settings.py`: persistence model
    
- `settings_dialog.py`: user interface
    
- `log_manager.py`: runtime logging utilities
    

### **8. Request Interceptor**

Allows inspection and filtering of browser requests.

### **9. Experimental Tools**

These are **not part of the running app**, but useful during development:

- `config8r.py`
    
- `processors.py`
    
- `scopes.py`
    

---

# Extension Points (Where to Add New Features)

This section exists specifically for development and AI-assisted coding.

### **Add a new toolbar or menu action**

Edit:

- `ui/toolbar_builder.py`
    
- `ui/menu_builder.py`
    

Then implement logic in:

- `BrowserWindow`
    
- `BrowserTab` (if tab-specific)
    

---

### **Add new controller actions**

Modify:

- `controller_window.py`
    
- `controller_script.py`
    

If the action affects the browser, expose a method in:

- `BrowserWindow`
    
- Optionally: `browser_operations.py`
    

---

### **Add new script actions**

Modify:

- `script_manager.py`
    
- `controller_script.py`
    

Update the script UI in:

- `script_management_ui.py`
    

Document the new JSON schema fields in:

- `docs/USER_GUIDE.md`
    

---

### **Add or modify settings**

Update:

- `settings.py` (`SettingsManager`)
    

Expose in UI:

- `settings_dialog.py`
    

---

### **Add logging for new features**

Use:

- `log_manager.py` (central logging utilities)
    
- Logging hooks inside windows and controllers
    

---

### **Handle new resource files (icons, etc.)**

Update `resources/resources.qrc`, then regenerate:

```bash
pyside6-rcc resources/resources.qrc -o src/qwsengine/resources_rc.py
```

---

# Scripts and Automation

Automation scripts live in:

```
scripts/
    sample_navigation_script.json
```

Runtime scripts are stored in the user config directory (created automatically):

```
~/.qwsengine/scripts/
```

A script is a JSON document of the form:

```json
{
  "name": "Example",
  "actions": [
    { "action_type": "navigate", "url": "https://example.com" },
    { "action_type": "wait", "seconds": 2 }
  ]
}
```

Script execution is handled by:

- `script_manager.py`
    
- `controller_script.py`
    
- `browser_operations.py`
    

---

# Development Notes

### Experimental Modules

The following files exist but are not part of the main application flow:

- `src/config8r.py`
    
- `src/processors.py`
    
- `src/scopes.py`
    

They are useful for prototyping future features but safe to ignore when modifying the core app.

### Playground Code

The `playground/` directory contains PoC scripts and early experiments.  
They are **not imported by QwsEngine** and can be used freely for testing.

---

# License

(Insert your licensing terms here—e.g. MIT, Apache 2.0, proprietary, etc.)
