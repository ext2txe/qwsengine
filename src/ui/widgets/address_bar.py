from PySide6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QPushButton
from PySide6.QtCore import QUrl


class AddressBar(QWidget):
    def __init__(self, browser_tab):
        super().__init__()
        self.browser_tab = browser_tab
        self.setup_ui()
    
    def setup_ui(self):
        layout = QHBoxLayout(self)
        
        # URL input field
        self.url_input = QLineEdit()
        self.url_input.setText("https://flanq.com")
        self.url_input.returnPressed.connect(self.load_url)
        
        # Go button
        go_button = QPushButton("Go")
        go_button.clicked.connect(self.load_url)
        
        # New tab button
        new_tab_button = QPushButton("+")
        new_tab_button.clicked.connect(self.browser_tab.create_new_tab)
        
        # Add widgets
        layout.addWidget(self.url_input)
        layout.addWidget(go_button)
        layout.addWidget(new_tab_button)
    
    def load_url(self):
        url = self.url_input.text().strip()
        self.browser_tab.load_url(url)
    
    def update_url(self, qurl: QUrl):
        self.url_input.setText(qurl.toString())