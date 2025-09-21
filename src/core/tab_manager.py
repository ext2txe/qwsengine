from typing import Optional
from PySide6.QtWidgets import QTabWidget
from .web_engine import BrowserTab


class TabManager:
    def __init__(self):
        self.tab_widget: Optional[QTabWidget] = None
        self.tabs = []
    
    def set_tab_widget(self, tab_widget: QTabWidget):
        self.tab_widget = tab_widget
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
    
    def create_new_tab(self, url: str = "https://flanq.com") -> BrowserTab:
        if not self.tab_widget:
            return None
            
        new_tab = BrowserTab(self, url)
        index = self.tab_widget.addTab(new_tab, "New Tab")
        self.tab_widget.setCurrentIndex(index)
        self.tabs.append(new_tab)
        return new_tab
    
    def close_tab(self, index: int):
        if self.tab_widget.count() > 1:
            widget = self.tab_widget.widget(index)
            if widget in self.tabs:
                self.tabs.remove(widget)
            widget.deleteLater()
            self.tab_widget.removeTab(index)
    
    def update_tab_title(self, tab: 'BrowserTab', title: str):
        if not self.tab_widget:
            return
            
        index = self.tab_widget.indexOf(tab)
        if index >= 0:
            short_title = title[:15] + ("…" if len(title) > 15 else "")
            self.tab_widget.setTabText(index, short_title)