from PySide6.QtWidgets import QWidget, QVBoxLayout
from ..ui.widgets.tab_widget import BrowserTabWidget
from .tab_manager import TabManager


class BrowserWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QWSEngine - PySide6 Multi-tab Browser")
        self.resize(1024, 768)
        
        # Initialize components
        self.tab_manager = TabManager()
        self.setup_ui()
        
        # Create initial tab
        self.tab_manager.create_new_tab()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Tab widget
        self.tabs = BrowserTabWidget(self.tab_manager)
        layout.addWidget(self.tabs)
        
        # Connect tab manager to UI
        self.tab_manager.set_tab_widget(self.tabs)
