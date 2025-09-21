import sys
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QTabWidget
)
from PySide6.QtWebEngineWidgets import QWebEngineView


class BrowserTab(QWidget):
    def __init__(self, tab_widget, url="https://flanq.com"):
        super().__init__()
        self.tab_widget = tab_widget

        # Layouts
        layout = QVBoxLayout(self)
        controls_layout = QHBoxLayout()

        # URL input field
        self.url_input = QLineEdit()
        self.url_input.setText(url)

        # Go button
        go_button = QPushButton("Go")
        go_button.clicked.connect(self.load_url)

        # "+" button to create a new tab
        new_tab_button = QPushButton("+")
        new_tab_button.clicked.connect(self.create_new_tab)

        # Add controls
        controls_layout.addWidget(self.url_input)
        controls_layout.addWidget(go_button)
        controls_layout.addWidget(new_tab_button)

        # Browser view
        self.browser = QWebEngineView()
        self.browser.load(url)

        # Update tab title when page title changes
        self.browser.titleChanged.connect(self.update_tab_title)

        # Add widgets to layout
        layout.addLayout(controls_layout)
        layout.addWidget(self.browser)

    def load_url(self):
        url = self.url_input.text().strip()
        if not url.startswith("http"):
            url = "https://" + url
        self.browser.load(url)

    def create_new_tab(self):
        new_tab = BrowserTab(self.tab_widget)
        index = self.tab_widget.addTab(new_tab, "New Tab")
        self.tab_widget.setCurrentIndex(index)

    def update_tab_title(self, title):
        index = self.tab_widget.indexOf(self)
        if index >= 0:
            self.tab_widget.setTabText(index, title[:15] + ("…" if len(title) > 15 else ""))


class BrowserWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PySide6 Multi-tab Browser")
        self.resize(1024, 768)

        layout = QVBoxLayout(self)

        # Tab control
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        layout.addWidget(self.tabs)

        # Start with one browser tab
        first_tab = BrowserTab(self.tabs)
        self.tabs.addTab(first_tab, "Home")

    def close_tab(self, index):
        if self.tabs.count() > 1:
            widget = self.tabs.widget(index)
            widget.deleteLater()
            self.tabs.removeTab(index)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = BrowserWindow()
    window.show()
    sys.exit(app.exec())
