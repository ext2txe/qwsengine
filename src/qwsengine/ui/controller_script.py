# qwsengine/controller_script.py
"""
Scripting engine for browser controller.
Allows automation of browser commands with delays.
"""

from PySide6.QtCore import QObject, Signal, QTimer, Qt
from PySide6.QtWidgets import QMessageBox
from datetime import datetime
import re


class ControllerScript(QObject):
    """
    Executes a script of controller commands.
    
    Script format (one command per line):
        navigate https://example.com
        wait 2000
        reload
        wait 1000
        screenshot
        back
        forward
        stop
        set_user_agent Mozilla/5.0...
        enable_proxy
        disable_proxy
        auto_reload start 30
        auto_reload stop
        auto_reload_screenshot on
        auto_reload_screenshot off
    """
    
    script_started = Signal()
    script_finished = Signal()
    script_paused = Signal()
    script_resumed = Signal()
    command_executed = Signal(str)  # command description
    script_error = Signal(str)  # error message
    progress_update = Signal(int, int)  # current_line, total_lines
    
    def __init__(self, controller_window, parent=None):
        super().__init__(parent)
        self.controller = controller_window
        self.browser_window = controller_window.browser_window
        self.settings_manager = controller_window.settings_manager
        
        self.script_lines = []
        self.current_line = 0
        self.is_running = False
        self.is_paused = False
        
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.execute_next_command)
        
    def load_script(self, script_text):
        """Load a script from text"""
        # Remove empty lines and comments
        lines = []
        for line in script_text.split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                lines.append(line)
        
        self.script_lines = lines
        self.current_line = 0
        return len(lines)
        
    def start(self):
        """Start script execution"""
        if not self.script_lines:
            self.script_error.emit("No script loaded")
            return
            
        if self.is_running:
            self.script_error.emit("Script already running")
            return
            
        self.is_running = True
        self.is_paused = False
        self.current_line = 0
        self.script_started.emit()
        
        self.log_script("Script execution started")
        self.execute_next_command()
        
    def pause(self):
        """Pause script execution"""
        if self.is_running and not self.is_paused:
            self.is_paused = True
            self.timer.stop()
            self.script_paused.emit()
            self.log_script("Script paused")
            
    def resume(self):
        """Resume script execution"""
        if self.is_running and self.is_paused:
            self.is_paused = False
            self.script_resumed.emit()
            self.log_script("Script resumed")
            self.execute_next_command()
            
    def stop(self):
        """Stop script execution"""
        if self.is_running:
            self.is_running = False
            self.is_paused = False
            self.timer.stop()
            self.script_finished.emit()
            self.log_script("Script stopped by user")
            
    def execute_next_command(self):
        """Execute the next command in the script"""
        if not self.is_running or self.is_paused:
            return
            
        if self.current_line >= len(self.script_lines):
            # Script complete
            self.is_running = False
            self.script_finished.emit()
            self.log_script("Script execution completed")
            return
            
        # Get current command
        command_line = self.script_lines[self.current_line]
        self.progress_update.emit(self.current_line + 1, len(self.script_lines))
        
        try:
            self.execute_command(command_line)
        except Exception as e:
            error = f"Error at line {self.current_line + 1}: {e}"
            self.script_error.emit(error)
            self.log_script(error)
            self.stop()
            return
            
        self.current_line += 1
        
        # Continue with next command (will be delayed if wait command was used)
        if self.is_running and not self.is_paused:
            QTimer.singleShot(10, self.execute_next_command)
            
    def execute_command(self, command_line):
        """Execute a single command"""
        parts = command_line.split(None, 1)
        if not parts:
            return
            
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_script(f"[{timestamp}] Executing: {command_line}")
        
        # Update controller status with current command
        if self.controller:
            self.controller.update_status(f"[{timestamp}] {command_line}")
        
        # Debug: log what command is being checked
        print(f"DEBUG: Command = '{cmd}', Args = '{args}'")
        
        if cmd == "navigate":
            self.cmd_navigate(args)
        elif cmd == "wait":
            self.cmd_wait(args)
        elif cmd == "reload":
            self.cmd_reload()
        elif cmd == "back":
            self.cmd_back()
        elif cmd == "forward":
            self.cmd_forward()
        elif cmd == "stop":
            self.cmd_stop()
        elif cmd == "screenshot":
            self.cmd_screenshot()
        elif cmd == "screenshot_full":
            self.cmd_screenshot_full()
        elif cmd == "save_html":
            self.cmd_save_html()
        elif cmd == "set_user_agent":
            self.cmd_set_user_agent(args)
        elif cmd == "enable_proxy":
            self.cmd_enable_proxy()
        elif cmd == "disable_proxy":
            self.cmd_disable_proxy()
        elif cmd == "auto_reload":
            self.cmd_auto_reload(args)
        elif cmd == "auto_reload_screenshot":
            self.cmd_auto_reload_screenshot(args)
        elif cmd == "status":
            self.cmd_status(args)
        else:
            print(f"DEBUG: Unknown command error for '{cmd}'")
            raise ValueError(f"Unknown command: {cmd}")
            
        self.command_executed.emit(command_line)
        
    def cmd_navigate(self, url):
        """Navigate to URL"""
        if not url:
            raise ValueError("navigate requires URL")
            
        # Add protocol if missing
        if not url.startswith(('http://', 'https://', 'about:', 'file:')):
            url = 'https://' + url
            
        # Get current tab and navigate directly
        current_tab = self.browser_window.tabs.currentWidget()
        if not current_tab:
            raise ValueError("No active tab found")
            
        # Get the webview from the tab
        view = getattr(current_tab, 'view', None) or getattr(current_tab, 'browser', None)
        if not view:
            raise ValueError("Could not find browser view in tab")
            
        # Navigate using QUrl
        from PySide6.QtCore import QUrl
        qurl = QUrl(url)
        if not qurl.isValid():
            raise ValueError(f"Invalid URL: {url}")
            
        view.setUrl(qurl)
        self.log_script(f"Navigation started: {url}")
        
    def cmd_wait(self, ms):
        """Wait for specified milliseconds"""
        try:
            delay = int(ms)
        except ValueError:
            raise ValueError(f"wait requires integer milliseconds, got: {ms}")
            
        if delay < 0:
            raise ValueError(f"wait delay must be positive, got: {delay}")
            
        # Pause execution for the specified time
        self.timer.stop()
        self.timer.setInterval(delay)
        self.timer.start()
        
    def cmd_reload(self):
        """Reload current page"""
        self.controller.on_reload()
        
    def cmd_back(self):
        """Navigate back"""
        self.controller.on_back()
        
    def cmd_forward(self):
        """Navigate forward"""
        self.controller.on_forward()
        
    def cmd_stop(self):
        """Stop loading"""
        self.controller.on_stop()
        
    def cmd_screenshot(self):
        """Take screenshot"""
        current_tab = self.browser_window.tabs.currentWidget()
        if not current_tab:
            raise ValueError("No active tab found")
            
        view = getattr(current_tab, 'view', None) or getattr(current_tab, 'browser', None)
        if not view:
            raise ValueError("Could not find browser view")
            
        # Capture screenshot
        pixmap = view.grab()
        if pixmap.isNull():
            raise ValueError("Screenshot capture failed (empty pixmap)")
            
        # Save to file
        save_dir = self.settings_manager.config_dir / "save"
        save_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        title = view.title() or view.url().host() or "page"
        safe_title = "".join(ch for ch in title if ch.isalnum() or ch in ("-", "_")).strip() or "page"
        filename = save_dir / f"{timestamp}_{safe_title}.png"
        
        if not pixmap.save(str(filename), "PNG"):
            raise ValueError("Failed to save screenshot file")
            
        self.log_script(f"Screenshot saved: {filename}")
        
        # Update preview in controller
        if self.controller and hasattr(self.controller, 'screenshot_label'):
            scaled_pixmap = pixmap.scaled(
                self.controller.screenshot_label.width() - 10,
                self.controller.screenshot_label.height() - 10,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.controller.screenshot_label.setPixmap(scaled_pixmap)
        
    def cmd_screenshot_full(self):
        """Take full page screenshot"""
        self.controller.on_full_screenshot()
        
    def cmd_save_html(self):
        """Save HTML"""
        self.controller.on_save_html()
        
    def cmd_set_user_agent(self, ua):
        """Set user agent"""
        if not ua:
            raise ValueError("set_user_agent requires user agent string")
        self.controller.ua_input.setText(ua)
        self.controller.on_apply_user_agent()
        
    def cmd_enable_proxy(self):
        """Enable proxy"""
        self.controller.proxy_enabled_cb.setChecked(True)
        self.controller.on_apply_proxy()
        
    def cmd_disable_proxy(self):
        """Disable proxy"""
        self.controller.proxy_enabled_cb.setChecked(False)
        self.controller.on_apply_proxy()
        
    def cmd_auto_reload(self, args):
        """Control auto-reload: start <seconds> | stop"""
        parts = args.split()
        if not parts:
            raise ValueError("auto_reload requires 'start <seconds>' or 'stop'")
            
        action = parts[0].lower()
        if action == "start":
            if len(parts) < 2:
                raise ValueError("auto_reload start requires interval in seconds")
            try:
                interval = int(parts[1])
            except ValueError:
                raise ValueError(f"auto_reload interval must be integer, got: {parts[1]}")
                
            self.controller.interval_spin.setValue(interval)
            if not self.controller.auto_reload_enabled:
                self.controller.on_toggle_auto_reload()
                
        elif action == "stop":
            if self.controller.auto_reload_enabled:
                self.controller.on_toggle_auto_reload()
        else:
            raise ValueError(f"auto_reload action must be 'start' or 'stop', got: {action}")
            
    def cmd_auto_reload_screenshot(self, args):
        """Enable/disable screenshot on auto-reload: on | off"""
        action = args.lower().strip()
        if action == "on":
            # This will be implemented when we add the feature to controller
            self.settings_manager.set("auto_reload_screenshot", True)
            if self.controller and hasattr(self.controller, 'auto_reload_screenshot_cb'):
                self.controller.auto_reload_screenshot_cb.setChecked(True)
            self.log_script("Auto-reload screenshot enabled")
        elif action == "off":
            self.settings_manager.set("auto_reload_screenshot", False)
            if self.controller and hasattr(self.controller, 'auto_reload_screenshot_cb'):
                self.controller.auto_reload_screenshot_cb.setChecked(False)
            self.log_script("Auto-reload screenshot disabled")
        else:
            raise ValueError(f"auto_reload_screenshot requires 'on' or 'off', got: {args}")
            
    def cmd_status(self, message):
        """Display a status message"""
        if not message:
            raise ValueError("status requires a message")
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        full_message = f"[{timestamp}] {message}"
        
        if self.controller:
            self.controller.update_status(full_message)
        
        self.log_script(f"Status: {message}")
            
    def log_script(self, message):
        """Log script activity"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        if self.controller:
            self.controller.log_text.append(f"[SCRIPT {timestamp}] {message}")
        if self.settings_manager:
            self.settings_manager.log_system_event("controller_script", "Script", message)


class ScriptValidator:
    """Validates script syntax before execution"""
    
    VALID_COMMANDS = {
        'navigate': 1,  # requires 1 argument
        'wait': 1,
        'reload': 0,
        'back': 0,
        'forward': 0,
        'stop': 0,
        'screenshot': 0,
        'screenshot_full': 0,
        'save_html': 0,
        'set_user_agent': 1,
        'enable_proxy': 0,
        'disable_proxy': 0,
        'auto_reload': -1,  # variable args
        'auto_reload_screenshot': 1,
        'status': 1,  # requires message
    }
    
    @classmethod
    def validate(cls, script_text):
        """
        Validate script syntax.
        Returns (is_valid, errors_list)
        """
        errors = []
        line_num = 0
        
        for line in script_text.split('\n'):
            line_num += 1
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
                
            parts = line.split(None, 1)
            if not parts:
                continue
                
            cmd = parts[0].lower()
            
            if cmd not in cls.VALID_COMMANDS:
                errors.append(f"Line {line_num}: Unknown command '{cmd}'")
                continue
                
            expected_args = cls.VALID_COMMANDS[cmd]
            has_args = len(parts) > 1
            
            if expected_args > 0 and not has_args:
                errors.append(f"Line {line_num}: Command '{cmd}' requires arguments")
            elif expected_args == 0 and has_args:
                errors.append(f"Line {line_num}: Command '{cmd}' takes no arguments")
                
            # Specific validation
            if cmd == "wait" and has_args:
                try:
                    int(parts[1])
                except ValueError:
                    errors.append(f"Line {line_num}: 'wait' requires integer milliseconds")
                    
        return (len(errors) == 0, errors)