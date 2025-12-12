# ui/menu_builder.py
from PySide6.QtWidgets import QMenuBar, QMenu
from PySide6.QtGui import QAction, QKeySequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .main_window import BrowserWindow

class MenuBuilder:
    """
    Builds menu bar for BrowserWindow.
    
    Extracted from main_window.py to separate UI construction
    from business logic.
    """

    
    def __init__(self, window: 'BrowserWindow'):
        """
        Initialize menu builder.
        
        Args:
            window: Parent BrowserWindow instance
        """
        self.window = window
    
    def build_menu_bar(self) -> QMenuBar:
        """
        Build and return the complete menu bar.
        
        Returns:
            Configured menu bar
        """
        menubar = self.window.menuBar()
        
        self._create_file_menu(menubar)
        self._create_view_menu(menubar)
        #self._create_tools_menu(menubar)
        self._create_help_menu(menubar)
        
        return menubar
        
    def _create_file_menu(self, menubar: QMenuBar):
        """Create File menu with actions."""
        file_menu = menubar.addMenu("&File")
        
        # New Tab
        new_tab = QAction("New &Tab", self.window)
        new_tab.setShortcut(QKeySequence.AddTab)
        new_tab.triggered.connect(self.window.create_new_tab)
        file_menu.addAction(new_tab)
        
        file_menu.addSeparator()
        
        # Save HTML
        save_html = QAction("Save Page &HTML...", self.window)
        save_html.triggered.connect(self.window.save_current_tab_html)
        file_menu.addAction(save_html)
        
        # Screenshot
        screenshot = QAction("Save &Screenshot...", self.window)
        screenshot.triggered.connect(self.window.save_current_tab_screenshot)
        file_menu.addAction(screenshot)
        
        # Full Page Screenshot
        full_screenshot = QAction("Save &Full Page Screenshot...", self.window)
        full_screenshot.triggered.connect(self.window.save_full_page_screenshot)
        file_menu.addAction(full_screenshot)
        
        file_menu.addSeparator()
        
        # Exit
        exit_action = QAction("E&xit", self.window)
        exit_action.setShortcut(QKeySequence.Quit)
        exit_action.triggered.connect(self.window.close)
        file_menu.addAction(exit_action)
    
    
    def _create_view_menu(self, menubar: QMenuBar):
        """Create View menu."""
        view_menu = menubar.addMenu("&View")
        
        # Refresh Scripts
        refresh = QAction("&Refresh Scripts List", self.window)
        refresh.triggered.connect(self.window.refresh_scripts_list)
        view_menu.addAction(refresh)
    
    def _create_tools_menu(self, menubar: QMenuBar):
        """Create Tools menu."""
        tools_menu = menubar.addMenu("&Tools")
        
        # Settings
        settings = QAction("&Settings...", self.window)
        settings.setShortcut(QKeySequence.Preferences)
        settings.triggered.connect(self.window.open_settings)
        tools_menu.addAction(settings)
        
        tools_menu.addSeparator()
        
        # View Settings JSON
        view_settings = QAction("View Settings &JSON...", self.window)
        view_settings.triggered.connect(self.window.view_settings_json)
        tools_menu.addAction(view_settings)
        
        # View Logs
        view_logs = QAction("View &Logs...", self.window)
        view_logs.triggered.connect(self.window.view_logs)
        tools_menu.addAction(view_logs)
        
        # Open Scripts Folder
        scripts_folder = QAction("Open Scripts &Folder...", self.window)
        scripts_folder.triggered.connect(self.window.open_scripts_folder)
        tools_menu.addAction(scripts_folder)
        
        tools_menu.addSeparator()
        
        # Clear Browser Data
        clear_data = QAction("&Clear Browser Data...", self.window)
        clear_data.triggered.connect(self.window.clear_browser_data)
        tools_menu.addAction(clear_data)
    
    def _create_help_menu(self, menubar: QMenuBar):
        """Create Help menu."""
        help_menu = menubar.addMenu("&Help")
        
        # About
        about = QAction("&About", self.window)
        about.triggered.connect(self.window.show_about_dialog)
        help_menu.addAction(about)
