from PySide6.QtWidgets import QTabWidget


class BrowserTabWidget(QTabWidget):
    def __init__(self, tab_manager):
        super().__init__()
        self.tab_manager = tab_manager
        self.setup_ui()
    
    def setup_ui(self):
        # Tab widget styling and behavior can be customized here
        pass