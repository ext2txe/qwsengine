#!/usr/bin/env python3
import sys
from PySide6.QtWidgets import QApplication
from .core.browser_window import BrowserWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("QWSEngine")
    app.setApplicationVersion("0.1.0")
    
    window = BrowserWindow()
    window.show()
    
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
