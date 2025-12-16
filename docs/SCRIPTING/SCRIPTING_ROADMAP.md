# Scripting System - Implementation Roadmap

Quick start guide to implement the minimal scripting feature.

---

## 🎯 Goal

Implement scriptable automation for:
1. Load URL
2. Save HTML
3. Pause x seconds

Designed to easily extend with more commands later.

---

## 📋 Step-by-Step Implementation

### Phase 1: Create Core Infrastructure (Day 1)

#### Step 1.1: Create Package Structure
```bash
mkdir qwsengine/scripting
mkdir qwsengine/scripting/commands
touch qwsengine/scripting/__init__.py
touch qwsengine/scripting/command.py
touch qwsengine/scripting/registry.py
touch qwsengine/scripting/context.py
touch qwsengine/scripting/executor.py
touch qwsengine/scripting/commands/__init__.py
```

#### Step 1.2: Implement Base Classes
1. Copy `command.py` code from SCRIPTING_IMPLEMENTATION.md
2. Copy `registry.py` code
3. Copy `context.py` code
4. Copy `executor.py` code
5. Verify imports work: `python -c "from qwsengine.scripting import ScriptExecutor"`

**Estimated time:** 30 minutes

---

### Phase 2: Implement Commands (Day 1-2)

#### Step 2.1: Load URL Command
1. Copy `commands/load_url.py` code
2. Test: Can it navigate to a URL?
3. Adjust if needed for your browser architecture

#### Step 2.2: Save HTML Command
1. Copy `commands/save_html.py` code
2. Test: Can it save the current page HTML?
3. May need to adjust for your page.toHtml() implementation

#### Step 2.3: Pause Command
1. Copy `commands/pause.py` code
2. Test: Does it pause correctly?
3. This one should be straightforward

#### Step 2.4: Register Commands
1. Copy `commands/__init__.py` code
2. Verify all commands are registered
3. Test: `CommandRegistry.list_commands()` shows all three

**Estimated time:** 1-2 hours

---

### Phase 3: Basic Testing (Day 2)

#### Step 3.1: Unit Tests
```python
# test_commands.py
import pytest
from qwsengine.scripting import CommandRegistry, ExecutionContext
from qwsengine.scripting.commands.pause import PauseCommand

def test_pause_command():
    import time
    cmd = PauseCommand(0.1)
    context = ExecutionContext()
    
    start = time.time()
    cmd.execute(context)
    elapsed = time.time() - start
    
    assert elapsed >= 0.1
    assert "Pausing" in context.logs[0]

def test_load_url_command_serialization():
    from qwsengine.scripting.commands.load_url import LoadURLCommand
    
    data = {"command": "load_url", "url": "https://example.com"}
    cmd = LoadURLCommand.from_dict(data)
    
    assert cmd.url == "https://example.com"
    assert cmd.to_dict() == data
```

#### Step 3.2: Integration Test
```python
# test_executor.py
def test_executor_loads_and_executes():
    from qwsengine.scripting import ScriptExecutor
    
    executor = ScriptExecutor()
    
    script = {
        "commands": [
            {"command": "pause", "seconds": 0.1},
            {"command": "pause", "seconds": 0.1}
        ]
    }
    
    executor.load_from_json(script)
    success = executor.execute()
    
    assert success
    assert len(executor.get_errors()) == 0
```

**Estimated time:** 1 hour

---

### Phase 4: UI Integration (Day 3)

#### Step 4.1: Add Script Editor to UI
In your `browser_controller_window.py` or scripting panel:

```python
# In ScriptingPanel (or add to controller window)

def create_script_executor_section(self):
    """Create script execution controls."""
    group = QGroupBox("Script Executor")
    layout = QVBoxLayout()
    
    # Script file selection
    load_btn = QPushButton("Load Script File")
    load_btn.clicked.connect(self.on_load_script)
    layout.addWidget(load_btn)
    
    # Script display
    self.script_display = QTextEdit()
    self.script_display.setReadOnly(True)  # For now, read-only
    layout.addWidget(self.script_display)
    
    # Execution buttons
    exec_layout = QHBoxLayout()
    
    self.exec_btn = QPushButton("Execute")
    self.exec_btn.clicked.connect(self.on_execute_script)
    exec_layout.addWidget(self.exec_btn)
    
    self.pause_btn = QPushButton("Pause")
    self.pause_btn.clicked.connect(self.on_pause_script)
    self.pause_btn.setEnabled(False)
    exec_layout.addWidget(self.pause_btn)
    
    self.stop_btn = QPushButton("Stop")
    self.stop_btn.clicked.connect(self.on_stop_script)
    self.stop_btn.setEnabled(False)
    exec_layout.addWidget(self.stop_btn)
    
    layout.addLayout(exec_layout)
    
    # Progress
    self.progress_label = QLabel("Ready")
    layout.addWidget(self.progress_label)
    
    # Execution log
    log_label = QLabel("Execution Log:")
    layout.addWidget(log_label)
    
    self.exec_log = QTextEdit()
    self.exec_log.setReadOnly(True)
    self.exec_log.setMaximumHeight(150)
    layout.addWidget(self.exec_log)
    
    group.setLayout(layout)
    return group

def on_load_script(self):
    """Load script from file."""
    filepath, _ = QFileDialog.getOpenFileName(
        self, "Load Script", "", "JSON Files (*.json);;All Files (*)"
    )
    if filepath:
        try:
            from qwsengine.scripting import ScriptExecutor
            self.executor = ScriptExecutor(
                ExecutionContext(
                    browser_window=self.browser_window,
                    settings_manager=self.settings_manager
                )
            )
            self.executor.load_from_file(filepath)
            self._display_script()
            self.update_status(f"Loaded script: {filepath}")
        except Exception as e:
            self.update_status(f"Failed to load script: {e}", level="ERROR")

def _display_script(self):
    """Display loaded script in UI."""
    script_text = "Commands:\n"
    for i, cmd in enumerate(self.executor.commands):
        script_text += f"{i+1}. {cmd}\n"
    self.script_display.setPlainText(script_text)

def on_execute_script(self):
    """Execute the loaded script."""
    if not hasattr(self, 'executor') or not self.executor.commands:
        self.update_status("No script loaded", level="WARNING")
        return
    
    self.exec_btn.setEnabled(False)
    self.pause_btn.setEnabled(True)
    self.stop_btn.setEnabled(True)
    
    def on_progress(current, total, description):
        self.progress_label.setText(
            f"[{current+1}/{total}] {description}"
        )
        self.exec_log.append(description)
    
    try:
        success = self.executor.execute(on_progress=on_progress)
        if success:
            self.update_status("Script executed successfully")
        else:
            errors = self.executor.get_errors()
            self.update_status(f"Script failed with {len(errors)} errors", level="ERROR")
    except Exception as e:
        self.update_status(f"Script execution error: {e}", level="ERROR")
    finally:
        self.exec_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)

def on_pause_script(self):
    """Pause script execution."""
    if hasattr(self, 'executor') and self.executor.is_running:
        self.executor.pause()
        self.update_status("Script paused")

def on_stop_script(self):
    """Stop script execution."""
    if hasattr(self, 'executor') and self.executor.is_running:
        self.executor.stop()
        self.update_status("Script stopped")
```

**Estimated time:** 2 hours

---

### Phase 5: Testing & Polish (Day 4)

#### Step 5.1: End-to-End Test
1. Create a test script file (JSON)
2. Load it in the UI
3. Execute it
4. Verify all commands execute correctly

#### Step 5.2: Error Handling Test
1. Load invalid script
2. Test command with missing parameters
3. Test command when browser not available
4. Verify error messages are clear

#### Step 5.3: Documentation
1. Update user documentation
2. Provide example scripts
3. Document how to add new commands

**Estimated time:** 2 hours

---

## 📊 Total Implementation Time

| Phase | Task | Hours |
|-------|------|-------|
| 1 | Core Infrastructure | 0.5 |
| 2 | Commands | 1-2 |
| 3 | Testing | 1 |
| 4 | UI Integration | 2 |
| 5 | Polish | 2 |
| **Total** | | **6.5-7.5 hours** |

**Timeline:** 4 days working 2 hours/day, or 1 day full-time

---

## 🧪 Quick Validation Checklist

Before moving forward:

```
Phase 1 Complete:
□ Package created with all files
□ Imports work without errors
□ CommandRegistry can be instantiated

Phase 2 Complete:
□ All 3 commands implement ScriptCommand interface
□ Each command can be created from dict and to dict
□ Commands are registered in CommandRegistry
□ list_commands() shows all three

Phase 3 Complete:
□ Unit tests pass
□ Integration tests pass
□ No import errors

Phase 4 Complete:
□ Script executor section appears in UI
□ Can load a script file
□ Script displays in UI
□ Execute button works
□ Progress updates during execution

Phase 5 Complete:
□ Pause button works
□ Stop button works
□ Error messages are clear
□ Logs display correctly
```

---

## 📝 Example Script File to Test With

Save as `test_script.json`:

```json
{
  "version": "1.0",
  "commands": [
    {
      "command": "load_url",
      "url": "https://www.example.com"
    },
    {
      "command": "pause",
      "seconds": 3
    },
    {
      "command": "save_html",
      "filename": "example.html",
      "path": "./output"
    },
    {
      "command": "pause",
      "seconds": 2
    },
    {
      "command": "load_url",
      "url": "https://www.google.com"
    },
    {
      "command": "save_html",
      "filename": "google.html",
      "path": "./output"
    }
  ]
}
```

---

## 🚀 Next Phase: Adding More Commands

Once the core is working, adding new commands is straightforward:

1. Create new command file: `commands/my_command.py`
2. Implement `execute()`, `from_dict()`, `to_dict()` methods
3. Register in `commands/__init__.py`
4. Use in JSON scripts

Example commands to add next:
- `click_element` - Click DOM elements
- `extract_text` - Extract text from page
- `wait_for_element` - Wait for element to appear
- `execute_javascript` - Run JavaScript
- `set_cookie` - Set cookies
- `scroll_to` - Scroll to position
- `wait_for_url_change` - Wait for navigation

---

## 💡 Pro Tips

### Tip 1: Start Simple
- Get the 3 basic commands working first
- Then add UI integration
- Then extend with more commands

### Tip 2: Use the Registry for Discovery
```python
# See what commands are available
print(CommandRegistry.list_commands())

# Dynamically register new commands
CommandRegistry.register('my_command', MyCommandClass)
```

### Tip 3: Logging is Your Friend
```python
# All execution is logged
executor.execute()
for log in executor.context.get_logs():
    print(log)
```

### Tip 4: Test Commands in Isolation
```python
# Test command without full executor
cmd = LoadURLCommand("https://example.com")
context = ExecutionContext(browser_window=my_browser)
cmd.execute(context)
print(context.get_logs())
```

### Tip 5: Save Scripts for Reuse
```python
# Users can save scripts and reload them
executor.save_to_file("my_script.json")

# Later...
executor2 = ScriptExecutor()
executor2.load_from_file("my_script.json")
executor2.execute()
```

---

## 🔧 Troubleshooting

### Issue: Command not found when executing
**Solution:** Make sure `commands/__init__.py` imports and registers the command

### Issue: SaveHTML not finding tab
**Solution:** Verify your `tab_manager.get_current_tab()` returns correct tab object

### Issue: LoadURL not navigating
**Solution:** Check that `tab_manager.navigate_current()` is the correct method in your browser

### Issue: Pause doesn't work
**Solution:** Check that time.sleep() works (sometimes blocked in tests)

---

## 📚 Related Files to Reference

- **SCRIPTING_STRATEGY.md** - Detailed strategy comparison
- **SCRIPTING_IMPLEMENTATION.md** - Complete code for all files
- This document - Quick implementation roadmap

Start with this document, refer to others as needed.

