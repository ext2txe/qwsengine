# Script System Architecture - Strategy Discussion

## Your Minimal Feature Set
```
1. Load URL1
2. Save HTML
3. PAUSE x seconds
4. Load URL2
5. Save HTML
6. PAUSE
```

**Key Requirement:** Design for incremental command extension (easy to add new commands)

---

## 📊 Strategy Comparison (4 Approaches)

### **STRATEGY 1: Command Pattern with Command Registry** ✅ RECOMMENDED

**Concept:** Each command is a class implementing a standard interface. Commands registered in a registry and instantiated dynamically.

#### Implementation Pattern

```python
# Base interface
class ScriptCommand(ABC):
    """Base class for all script commands."""
    
    @abstractmethod
    def execute(self, context):
        """Execute the command in the given context."""
        pass
    
    @classmethod
    @abstractmethod
    def from_dict(cls, data: dict):
        """Create command from dictionary (for deserialization)."""
        pass
    
    @abstractmethod
    def to_dict(self) -> dict:
        """Convert command to dictionary (for serialization)."""
        pass


# Concrete commands (minimal set)
class LoadURLCommand(ScriptCommand):
    def __init__(self, url: str):
        self.url = url
    
    def execute(self, context):
        """Load URL in the browser."""
        if context.browser_window:
            context.browser_window.navigate(self.url)
        else:
            raise RuntimeError("No browser window available")
    
    @classmethod
    def from_dict(cls, data):
        return cls(data['url'])
    
    def to_dict(self):
        return {'command': 'load_url', 'url': self.url}


class SaveHTMLCommand(ScriptCommand):
    def __init__(self, filename: str = None, path: str = None):
        self.filename = filename
        self.path = path or "."
    
    def execute(self, context):
        """Save current page HTML to file."""
        if context.browser_window:
            context.browser_window.save_html(self.filename or "page.html", self.path)
        else:
            raise RuntimeError("No browser window available")
    
    @classmethod
    def from_dict(cls, data):
        return cls(data.get('filename'), data.get('path'))
    
    def to_dict(self):
        return {
            'command': 'save_html',
            'filename': self.filename,
            'path': self.path
        }


class PauseCommand(ScriptCommand):
    def __init__(self, seconds: float):
        self.seconds = seconds
    
    def execute(self, context):
        """Pause execution for specified seconds."""
        import time
        context.log(f"Pausing for {self.seconds} seconds...")
        time.sleep(self.seconds)
    
    @classmethod
    def from_dict(cls, data):
        return cls(float(data['seconds']))
    
    def to_dict(self):
        return {'command': 'pause', 'seconds': self.seconds}


# Command registry (factory pattern)
class CommandRegistry:
    """Registry for available commands - allows dynamic registration."""
    
    _registry = {}
    
    @classmethod
    def register(cls, command_name: str, command_class):
        """Register a command class."""
        cls._registry[command_name] = command_class
        print(f"Registered command: {command_name}")
    
    @classmethod
    def unregister(cls, command_name: str):
        """Unregister a command."""
        if command_name in cls._registry:
            del cls._registry[command_name]
    
    @classmethod
    def get(cls, command_name: str):
        """Get command class by name."""
        return cls._registry.get(command_name)
    
    @classmethod
    def list_commands(cls):
        """List all available commands."""
        return list(cls._registry.keys())
    
    @classmethod
    def create_command(cls, command_name: str, data: dict):
        """Factory method: create command from name and data."""
        command_class = cls.get(command_name)
        if not command_class:
            raise ValueError(f"Unknown command: {command_name}")
        return command_class.from_dict(data)


# Register initial commands
CommandRegistry.register('load_url', LoadURLCommand)
CommandRegistry.register('save_html', SaveHTMLCommand)
CommandRegistry.register('pause', PauseCommand)
```

#### Script Execution Engine

```python
class ScriptExecutor:
    """Executes a sequence of commands."""
    
    def __init__(self, context=None):
        self.context = context or ExecutionContext()
        self.commands = []
        self.current_index = 0
        self.is_running = False
        self.is_paused = False
        self.errors = []
    
    def load_from_json(self, json_data: dict):
        """Load script from JSON format."""
        self.commands = []
        for cmd_data in json_data.get('commands', []):
            try:
                command_name = cmd_data.get('command')
                cmd = CommandRegistry.create_command(command_name, cmd_data)
                self.commands.append(cmd)
            except Exception as e:
                self.errors.append(f"Error loading command: {e}")
    
    def load_from_file(self, filepath: str):
        """Load script from JSON file."""
        import json
        with open(filepath, 'r') as f:
            json_data = json.load(f)
        self.load_from_json(json_data)
    
    def save_to_file(self, filepath: str):
        """Save script to JSON file."""
        import json
        script_data = {
            'version': '1.0',
            'commands': [cmd.to_dict() for cmd in self.commands]
        }
        with open(filepath, 'w') as f:
            json.dump(script_data, f, indent=2)
    
    def execute(self, on_progress=None):
        """Execute all commands sequentially."""
        self.is_running = True
        self.errors = []
        
        for i, cmd in enumerate(self.commands):
            self.current_index = i
            
            # Check for pause/stop
            while self.is_paused and self.is_running:
                import time
                time.sleep(0.1)
            
            if not self.is_running:
                break
            
            try:
                if on_progress:
                    on_progress(i, len(self.commands), str(cmd))
                
                cmd.execute(self.context)
                self.context.log(f"✓ Executed: {cmd}")
                
            except Exception as e:
                error_msg = f"Command failed at index {i}: {e}"
                self.errors.append(error_msg)
                self.context.log(f"✗ {error_msg}")
                
                # On error: stop or continue?
                if self.context.stop_on_error:
                    break
        
        self.is_running = False
    
    def pause(self):
        """Pause execution."""
        self.is_paused = True
    
    def resume(self):
        """Resume execution."""
        self.is_paused = False
    
    def stop(self):
        """Stop execution."""
        self.is_running = False


# Execution context (provides utilities to commands)
class ExecutionContext:
    """Context passed to commands - provides access to browser and logging."""
    
    def __init__(self, browser_window=None, settings_manager=None):
        self.browser_window = browser_window
        self.settings_manager = settings_manager
        self.stop_on_error = False
        self.logs = []
    
    def log(self, message: str):
        """Log a message."""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.logs.append(log_entry)
        print(log_entry)
```

#### Usage Example

```python
# Create executor
context = ExecutionContext(browser_window=my_browser, settings_manager=my_settings)
executor = ScriptExecutor(context)

# Load from JSON
script_json = {
    "version": "1.0",
    "commands": [
        {"command": "load_url", "url": "https://example.com/page1"},
        {"command": "save_html", "filename": "page1.html"},
        {"command": "pause", "seconds": 3},
        {"command": "load_url", "url": "https://example.com/page2"},
        {"command": "save_html", "filename": "page2.html"},
        {"command": "pause", "seconds": 2}
    ]
}

executor.load_from_json(script_json)

# Execute with progress callback
def on_progress(current, total, cmd_description):
    print(f"Progress: {current+1}/{total} - {cmd_description}")

executor.execute(on_progress=on_progress)

# Check for errors
if executor.errors:
    print(f"Errors: {executor.errors}")
```

#### Pros ✅
- **Highly extensible** - Add new command in 20 lines of code
- **Type-safe** - Clear interface, less error-prone
- **Testable** - Each command can be tested independently
- **Maintainable** - Commands are isolated, easy to understand
- **Dynamic registration** - Commands can be registered at runtime
- **Self-documenting** - Code structure shows what's possible
- **Flexible execution** - Easy to add pause, stop, progress tracking

#### Cons ❌
- **More code** - Requires class structure for each command
- **Learning curve** - New commands need to understand the pattern
- **Boilerplate** - Each command needs from_dict/to_dict methods

---

### **STRATEGY 2: Dictionary/Function Based** (Simpler, Less Flexible)

**Concept:** Each command is a dictionary, executed by a function lookup.

```python
# Command executors (as functions)
def execute_load_url(context, data):
    context.browser_window.navigate(data['url'])

def execute_save_html(context, data):
    context.browser_window.save_html(data.get('filename', 'page.html'))

def execute_pause(context, data):
    import time
    time.sleep(data['seconds'])

# Command dispatcher
COMMAND_EXECUTORS = {
    'load_url': execute_load_url,
    'save_html': execute_save_html,
    'pause': execute_pause,
}

# Simple executor
def execute_script(script_json, context):
    for cmd_data in script_json['commands']:
        command_type = cmd_data['command']
        executor = COMMAND_EXECUTORS.get(command_type)
        if executor:
            executor(context, cmd_data)
        else:
            raise ValueError(f"Unknown command: {command_type}")

# Add new command
def execute_click(context, data):
    context.browser_window.click(data['selector'])

COMMAND_EXECUTORS['click'] = execute_click
```

#### Pros ✅
- **Simple** - Easy to understand
- **Quick to implement** - Less code upfront
- **Low overhead** - Minimal structure

#### Cons ❌
- **Less extensible** - Functions scattered, no standard pattern
- **Hard to maintain** - No central place to see all commands
- **No serialization** - Can't easily save/load from JSON
- **Testing** - Harder to test individual commands
- **Documentation** - Less self-documenting

**Verdict:** OK for simple cases, but will become messy as you add commands

---

### **STRATEGY 3: YAML-Based DSL** (More Human-Readable)

```yaml
version: 1.0
name: "Scrape two pages"
commands:
  - load_url:
      url: https://example.com/page1
  
  - save_html:
      filename: page1.html
      path: ./downloads
  
  - pause:
      seconds: 5
  
  - load_url:
      url: https://example.com/page2
  
  - save_html:
      filename: page2.html
  
  - pause:
      seconds: 2
```

#### Pros ✅
- **Very readable** - Even non-programmers can understand
- **Easy to write** - Less brackets than JSON
- **Still structured** - Clear hierarchy

#### Cons ❌
- **YAML parsing** - Need extra library
- **Indentation errors** - YAML is whitespace-sensitive
- **Less common** - Team might prefer JSON

**Verdict:** Good if you want human-readable scripts, but adds parsing complexity

---

### **STRATEGY 4: Python Code Execution** (Most Powerful, Riskiest)

```python
# User writes a Python file
script_code = """
from qwsengine.scripting import LoadURL, SaveHTML, Pause

commands = [
    LoadURL("https://example.com/page1"),
    SaveHTML("page1.html"),
    Pause(5),
    LoadURL("https://example.com/page2"),
    SaveHTML("page2.html"),
    Pause(2),
]
"""

# Execute it
exec(script_code, {'LoadURL': LoadURLCommand, 'SaveHTML': SaveHTMLCommand, 'Pause': PauseCommand})
```

#### Pros ✅
- **Most powerful** - Full Python capabilities
- **Familiar** - Python developers understand it

#### Cons ❌
- **Security risk** - Execute arbitrary code
- **Hard to validate** - Can't check what it will do before running
- **Complex** - Overkill for most use cases
- **Debugging** - Python errors can be cryptic

**Verdict:** Not recommended for this use case (security + complexity)

---

## 🎯 RECOMMENDATION: Strategy 1 (Command Pattern)

**Why Strategy 1 is best for you:**

1. **Extensibility** (Your main requirement)
   - Add new command in 20 lines
   - Register with one function call
   - Clear pattern for new developers

2. **Structure**
   - All commands in one place conceptually
   - Self-documenting via registry
   - Clear interface contract

3. **Persistence**
   - Serialize/deserialize easily
   - Save scripts as JSON files
   - Load from any source

4. **Testability**
   - Test each command independently
   - Mock context for testing
   - Easy CI/CD integration

5. **UI Integration**
   - Build UI for command parameters
   - Validate before execution
   - Show list of available commands

6. **Error Handling**
   - Catch command-specific errors
   - Continue or stop on error
   - Detailed error reporting

---

## 📐 Project Structure (Recommended)

```
qwsengine/scripting/
├── __init__.py
├── command.py              # Base ScriptCommand class
├── registry.py             # CommandRegistry
├── executor.py             # ScriptExecutor
├── context.py              # ExecutionContext
├── commands/
│   ├── __init__.py
│   ├── load_url.py         # LoadURLCommand
│   ├── save_html.py        # SaveHTMLCommand
│   ├── pause.py            # PauseCommand
│   └── ... (future commands)
├── tests/
│   ├── test_commands.py
│   ├── test_executor.py
│   └── test_integration.py
└── examples/
    └── scripts/
        └── example_script.json
```

#### File Organization

**command.py:**
```python
# Base command class only
```

**registry.py:**
```python
# CommandRegistry only
# Single source of truth for available commands
```

**executor.py:**
```python
# ScriptExecutor only
# Orchestrates command execution
```

**commands/load_url.py:**
```python
# LoadURLCommand only
# Each command in its own file for clarity
```

**Benefit:** Easy to find code, understand what commands are available, add new commands

---

## 🔄 Adding New Commands (Future Extensibility)

### Example: Adding "Click Element" Command

**File: `commands/click_element.py`**
```python
from ..command import ScriptCommand

class ClickElementCommand(ScriptCommand):
    def __init__(self, selector: str):
        self.selector = selector
    
    def execute(self, context):
        if context.browser_window:
            # Find and click element
            context.browser_window.click_element(self.selector)
        else:
            raise RuntimeError("No browser window available")
    
    @classmethod
    def from_dict(cls, data):
        return cls(data['selector'])
    
    def to_dict(self):
        return {'command': 'click_element', 'selector': self.selector}
```

**File: `commands/__init__.py` (register it)**
```python
from .click_element import ClickElementCommand
from ..registry import CommandRegistry

# Auto-register when imported
CommandRegistry.register('click_element', ClickElementCommand)
```

**That's it!** Now you can use it:
```json
{
  "command": "click_element",
  "selector": ".submit-button"
}
```

---

## 🎬 Execution Flow

```
┌─────────────────────────────────────────┐
│ User: Load script from file or UI       │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│ ScriptExecutor.load_from_json()         │
├─────────────────────────────────────────┤
│ For each command in JSON:               │
│  1. Get command type name               │
│  2. Lookup in CommandRegistry           │
│  3. Create command instance via         │
│     CommandClass.from_dict()            │
│  4. Add to commands list                │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│ User: Click "Execute" or API call       │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│ ScriptExecutor.execute()                │
├─────────────────────────────────────────┤
│ For each command:                       │
│  1. Update UI progress                  │
│  2. Call command.execute(context)       │
│  3. Log result                          │
│  4. Catch exceptions, decide continue   │
│  5. Check for pause/stop                │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│ Show results: Success/Errors/Logs       │
└─────────────────────────────────────────┘
```

---

## 💾 Storage Format (JSON)

```json
{
  "version": "1.0",
  "name": "Scrape Example Site",
  "description": "Loads two pages and saves HTML",
  "metadata": {
    "created": "2025-12-15",
    "author": "user@example.com",
    "tags": ["example", "scraping"]
  },
  "commands": [
    {
      "command": "load_url",
      "url": "https://example.com/page1"
    },
    {
      "command": "save_html",
      "filename": "page1.html",
      "path": "./output"
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
      "filename": "page2.html"
    },
    {
      "command": "pause",
      "seconds": 2
    }
  ]
}
```

---

## 🧪 Testing Strategy

```python
# test_commands.py
import pytest
from execution_context import ExecutionContext
from commands.pause import PauseCommand

def test_pause_command():
    context = ExecutionContext()
    cmd = PauseCommand(0.1)  # Use short time for testing
    
    import time
    start = time.time()
    cmd.execute(context)
    elapsed = time.time() - start
    
    assert elapsed >= 0.1

def test_load_url_command():
    # Mock browser window
    class MockBrowser:
        def __init__(self):
            self.last_url = None
        
        def navigate(self, url):
            self.last_url = url
    
    context = ExecutionContext(browser_window=MockBrowser())
    from commands.load_url import LoadURLCommand
    
    cmd = LoadURLCommand("https://example.com")
    cmd.execute(context)
    
    assert context.browser_window.last_url == "https://example.com"
```

---

## 🚀 Phased Implementation Plan

### Phase 1 (Week 1): Core Infrastructure
- [ ] ScriptCommand base class
- [ ] CommandRegistry
- [ ] ScriptExecutor
- [ ] ExecutionContext
- [ ] Minimal tests

### Phase 2 (Week 2): Initial Commands
- [ ] LoadURLCommand
- [ ] SaveHTMLCommand
- [ ] PauseCommand
- [ ] Integration tests
- [ ] UI integration

### Phase 3 (Week 3): UI & Script Management
- [ ] Script editor in UI
- [ ] Load/save scripts to files
- [ ] Execute script from UI
- [ ] Show execution progress
- [ ] Display logs

### Phase 4 (Week 4+): Additional Commands
- [ ] ClickElement
- [ ] ExtractImages
- [ ] SetCookie
- [ ] CheckElement
- [ ] ExecuteJavaScript
- [ ] WaitForElement
- [ ] etc.

---

## ⚠️ Important Considerations

### Asynchronous Operations
Your current model is synchronous (blocking). For WebEngine:
- Use `QTimer` or threads for pause
- Use callbacks for page loads (they're async)
- Consider async/await patterns

### Error Handling Strategy
- **On error:** Stop or Continue?
- **Timeout:** What happens if page doesn't load?
- **Validation:** Check parameters before executing

### Logging & Debugging
- Log every command execution
- Show execution progress in UI
- Allow step-by-step execution (not in MVP)

### Security
- Validate all parameters
- Don't allow arbitrary code execution
- Consider sandboxing

---

## 📝 Summary: Recommended Approach

| Aspect | Decision |
|--------|----------|
| **Architecture** | Command Pattern + Registry |
| **Format** | JSON for persistence |
| **Organization** | One command per file + registry |
| **Extensibility** | Dynamic registration |
| **Testing** | Unit test each command |
| **UI** | Script editor + executor + progress |
| **Error Handling** | Log errors, option to stop or continue |

**Start with:** LoadURL, SaveHTML, Pause  
**Pattern is set:** Adding commands becomes formulaic  
**Scales to:** Hundreds of commands if needed

