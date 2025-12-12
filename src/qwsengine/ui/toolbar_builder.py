# ui/toolbar_builder.py
from PySide6.QtWidgets import QToolBar, QLineEdit, QComboBox
from PySide6.QtGui import QAction, QKeySequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .main_window import BrowserWindow


class ToolbarBuilder:
    """
    Builds navigation toolbar for BrowserWindow.
    
    Extracted from main_window.py to separate toolbar construction
    from business logic.
    """
    
    def __init__(self, window: 'BrowserWindow'):
        """
        Initialize toolbar builder.
        
        Args:
            window: Parent BrowserWindow instance
        """
        self.window = window
        self.urlbar = None
        self.scripts_combo = None
    
    def create_navigation_toolbar(self) -> QToolBar:
        """
        Create and return the navigation toolbar.
        
        Returns:
            Configured toolbar with navigation controls
        """
        tb = QToolBar("Main Toolbar", self.window)
        tb.setMovable(True)
        
        # Navigation buttons
        self._add_navigation_buttons(tb)
        
        tb.addSeparator()
        
        # URL bar
        self._add_url_bar(tb)
        
        # New tab button
        self._add_new_tab_button(tb)
        
        # Home button
        self._add_home_button(tb)
        
        # Save actions
        self._add_save_actions(tb)
        
        tb.addSeparator()
        
        # Scripts UI
        self._add_scripts_controls(tb)
        
        return tb
    
    def _add_navigation_buttons(self, toolbar: QToolBar):
        """Add Back/Forward/Reload/Stop buttons."""
        # Back
        back_action = QAction("Back", self.window)
        back_action.setShortcut(QKeySequence.Back)
        back_action.triggered.connect(self.window.back)
        toolbar.addAction(back_action)
        
        # Forward
        fwd_action = QAction("Forward", self.window)
        fwd_action.setShortcut(QKeySequence.Forward)
        fwd_action.triggered.connect(self.window.forward)
        toolbar.addAction(fwd_action)
        
        # Reload
        reload_action = QAction("Reload", self.window)
        reload_action.setShortcut(QKeySequence.Refresh)
        reload_action.triggered.connect(self.window.reload)
        toolbar.addAction(reload_action)
        
        # Stop
        stop_action = QAction("Stop", self.window)
        stop_action.triggered.connect(self.window.stop)
        toolbar.addAction(stop_action)
    
    def _add_url_bar(self, toolbar: QToolBar):
        """Add URL address bar."""
        self.urlbar = QLineEdit(toolbar)
        self.urlbar.setPlaceholderText("Enter URL and press Enter…")
        self.urlbar.returnPressed.connect(self.window._on_urlbar_return_pressed)
        self.urlbar.setClearButtonEnabled(True)
        self.urlbar.setMinimumWidth(420)
        
        # Sync URL to controller when Enter is pressed
        self.urlbar.returnPressed.connect(lambda: self._on_url_text_changed(self.urlbar.text()))
        
        toolbar.addWidget(self.urlbar)
        
        # Go button
        go_action = QAction("Go", self.window)
        go_action.setShortcut("Return")
        go_action.setStatusTip("Navigate to the URL in the address bar")
        go_action.triggered.connect(lambda checked=False: self.window.navigate_current(self.urlbar.text()))
        
        # ALSO sync to controller when Go button is clicked
        go_action.triggered.connect(lambda: self._on_url_text_changed(self.urlbar.text()))
        
        toolbar.addAction(go_action)
    
    def _add_new_tab_button(self, toolbar: QToolBar):
        """Add new tab (+) button."""
        plus_action = QAction("+", self.window)
        plus_action.setStatusTip("Open a new tab")
        plus_action.setShortcut("Ctrl+T")
        plus_action.triggered.connect(lambda checked=False: self.window._new_tab(switch=True))
        toolbar.addAction(plus_action)
    
    def _add_home_button(self, toolbar: QToolBar):
        """Add home button."""
        home_action = QAction("Home", self.window)
        home_action.setToolTip("Go to Start URL (from Settings)")
        
        def _go_home():
            url = self.window.settings_manager.get("start_url", "") or "about:blank"
            self.window.navigate_current(url)
        
        home_action.triggered.connect(_go_home)
        toolbar.addAction(home_action)
    
    def _add_save_actions(self, toolbar: QToolBar):
        """Add save HTML and screenshot actions."""
        # Save HTML
        save_html_action = QAction("Save HTML", self.window)
        save_html_action.setToolTip("Save the current tab's Document HTML")
        save_html_action.triggered.connect(self.window.save_current_tab_html)
        toolbar.addAction(save_html_action)
        
        # Save Screenshot
        save_shot_action = QAction("Save Screenshot", self.window)
        save_shot_action.setToolTip("Save a PNG screenshot of the current tab's visible page")
        save_shot_action.triggered.connect(self.window.save_current_tab_screenshot)
        toolbar.addAction(save_shot_action)
        
        # Save Full Page
        save_full_action = QAction("Save Full Page", self.window)
        save_full_action.setToolTip("Capture the entire page (beyond viewport) as PNG")
        save_full_action.triggered.connect(self.window.save_full_page_screenshot)
        toolbar.addAction(save_full_action)
    
    def _add_scripts_controls(self, toolbar: QToolBar):
        """Add script selection and execution controls."""
        # Scripts combo box
        self.scripts_combo = QComboBox(toolbar)
        self.scripts_combo.setMinimumWidth(240)
        toolbar.addWidget(self.scripts_combo)
        
        # Store reference on window
        self.window.scripts_combo = self.scripts_combo
        
        # Refresh scripts list
        refresh_scripts_action = QAction("Refresh", self.window)
        refresh_scripts_action.setToolTip("Reload the list of .js files from the scripts folder")
        refresh_scripts_action.triggered.connect(self.window.refresh_scripts_list)
        toolbar.addAction(refresh_scripts_action)
        
        # Execute script
        exec_script_action = QAction("Execute", self.window)
        exec_script_action.setToolTip("Execute the selected JavaScript file in the current page")
        exec_script_action.triggered.connect(self.window.execute_selected_script)
        toolbar.addAction(exec_script_action)
        
        # Open scripts folder
        open_scripts_action = QAction("Open Scripts Folder", self.window)
        open_scripts_action.setToolTip("Open the scripts directory in your file manager")
        open_scripts_action.triggered.connect(self.window.open_scripts_folder)
        toolbar.addAction(open_scripts_action)
    
    def get_urlbar(self) -> QLineEdit:
        """
        Get the URL bar widget.
        
        Returns:
            URL bar line edit
        """
        return self.urlbar
    
    def get_scripts_combo(self) -> QComboBox:
        """
        Get the scripts combo box.
        
        Returns:
            Scripts combo box
        """
        return self.scripts_combo
    
    def _on_url_text_changed(self, text: str):
        """
        Handle URL text changes and sync to controller window.
        
        Args:
            text: New URL text
        """
        from PySide6.QtWidgets import QApplication
        
        # Find controller window
        for widget in QApplication.topLevelWidgets():
            class_name = widget.__class__.__name__
            
            # Check if it's the controller window
            if class_name == "BrowserControllerWindow":
                # Update the navigation URL field in controller
                if hasattr(widget, 'url_input'):
                    widget.url_input.setText(text)
                break