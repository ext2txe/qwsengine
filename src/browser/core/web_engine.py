from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtWebEngineWidgets import QWebEngineView
from ..ui.widgets.address_bar import AddressBar


class BrowserTab(QWidget):
    def __init__(self, tab_manager, url: str = "https://flanq.com"):
        super().__init__()
        self.tab_manager = tab_manager
        self.setup_ui(url)
    
    def setup_ui(self, url: str):
        layout = QVBoxLayout(self)
        
        # Address bar and controls
        self.address_bar = AddressBar(self)
        layout.addWidget(self.address_bar)
        
        # Browser view
        self.browser = QWebEngineView()
        self.browser.load(url)
        layout.addWidget(self.browser)
        
        # Connect signals
        self.browser.titleChanged.connect(self.update_tab_title)
        self.browser.urlChanged.connect(self.address_bar.update_url)
    
    def load_url(self, url: str):
        if not url.startswith("http"):
            url = "https://" + url
        self.browser.load(url)
    
    def create_new_tab(self):
        self.tab_manager.create_new_tab()
    
    def update_tab_title(self, title: str):
        self.tab_manager.update_tab_title(self, title)
