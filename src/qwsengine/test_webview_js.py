import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton
from PySide6.QtCore import QUrl, QTimer
from PySide6.QtWebEngineCore import QWebEngineProfile

# Import your WebView class
from webview import WebView

class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("WebView JavaScript Test")
        self.setGeometry(100, 100, 800, 600)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Create your WebView
        self.webview = WebView()
        layout.addWidget(self.webview)
        
        # Add test buttons
        btn_simple = QPushButton("Test Simple JS")
        btn_simple.clicked.connect(self.test_simple_js)
        layout.addWidget(btn_simple)
        
        btn_metrics = QPushButton("Test Metrics JS")
        btn_metrics.clicked.connect(self.test_metrics_js)
        layout.addWidget(btn_metrics)
        
        btn_page_state = QPushButton("Check Page State")
        btn_page_state.clicked.connect(self.check_page_state)
        layout.addWidget(btn_page_state)
        
        btn_page_state = QPushButton("Debug Metrics JS")
        btn_page_state.clicked.connect(self.debug_metrics_js)
        layout.addWidget(btn_page_state)
        
        btn_page_state = QPushButton("Test Simplifed Metrics Test")
        btn_page_state.clicked.connect(self.test_simplified_metrics)
        layout.addWidget(btn_page_state)
        
        btn_page_state = QPushButton("Test Step by Step Metrics")
        btn_page_state.clicked.connect(self.test_step_by_step_metrics)
        layout.addWidget(btn_page_state)

        btn_page_state = QPushButton("Test JSON Metrics")
        btn_page_state.clicked.connect(self.test_json_metrics)
        layout.addWidget(btn_page_state)

        # Load a test page
        self.webview.load(QUrl("https://example.com"))
        
    def test_simple_js(self):
        print("=== SIMPLE JS TEST ===")
        page = self.webview.page()
        
        def callback(result):
            print(f"✓ Simple JS result: {result} (type: {type(result)})")
        
        page.runJavaScript("2 + 2", callback)
        print("Simple JS executed, waiting for callback...")
    
    def test_metrics_js(self):
        print("=== METRICS JS TEST ===")
        page = self.webview.page()
        
        js = """
        (function() {
            try {
                var e = document.documentElement;
                var b = document.body || {scrollWidth:0, scrollHeight:0};
                return {
                    totalWidth: Math.max(e.scrollWidth || 0, b.scrollWidth || 0),
                    totalHeight: Math.max(e.scrollHeight || 0, b.scrollHeight || 0),
                    viewportWidth: window.innerWidth || 0,
                    viewportHeight: window.innerHeight || 0,
                    dpr: window.devicePixelRatio || 1
                };
            } catch (err) {
                return {error: err.toString()};
            }
        })();
        """
        
        def callback(result):
            print(f"✓ Metrics result: {result}")
            print(f"✓ Metrics type: {type(result)}")
        
        page.runJavaScript(js, callback)
        print("Metrics JS executed, waiting for callback...")
    
    def check_page_state(self):
        print("=== PAGE STATE CHECK ===")
        page = self.webview.page()
        
        print(f"Page loading: {page.isLoading()}")
        print(f"URL: {self.webview.url().toString()}")
        
        def ready_state_callback(state):
            print(f"Document ready state: '{state}'")
        
        def title_callback(title):
            print(f"Page title: '{title}'")
        
        page.runJavaScript("document.readyState", ready_state_callback)
        page.runJavaScript("document.title", title_callback)

    def debug_metrics_js(self):
        print("=== DEBUG METRICS JS ===")
        page = self.webview.page()
        
        # Test each part step by step
        tests = [
            ("document.documentElement", "document.documentElement"),
            ("document.body", "document.body"),
            ("scrollWidth", "document.documentElement.scrollWidth"),
            ("scrollHeight", "document.documentElement.scrollHeight"),
            ("window.innerWidth", "window.innerWidth"),
            ("window.innerHeight", "window.innerHeight"),
            ("devicePixelRatio", "window.devicePixelRatio"),
        ]
        
        for name, js in tests:
            def make_callback(test_name):
                def callback(result):
                    print(f"✓ {test_name}: {result} (type: {type(result)})")
                return callback
            
            page.runJavaScript(js, make_callback(name))

    def test_simplified_metrics(self):
        print("=== SIMPLIFIED METRICS TEST ===")
        page = self.webview.page()
        
        # Very simple version first
        simple_js = """
        var result = {
            width: window.innerWidth,
            height: window.innerHeight
        };
        result;
        """
        
        def callback(result):
            print(f"✓ Simplified metrics: {result} (type: {type(result)})")
        
        page.runJavaScript(simple_js, callback)

    def test_step_by_step_metrics(self):
        print("=== STEP BY STEP METRICS ===")
        page = self.webview.page()
        
        # Build the object piece by piece
        js = """
        (function() {
            console.log("Starting metrics function...");
            
            var e = document.documentElement;
            console.log("documentElement:", e);
            
            var b = document.body;
            console.log("body:", b);
            
            if (!e) {
                console.log("No documentElement!");
                return {error: "No documentElement"};
            }
            
            var totalWidth = e.scrollWidth;
            console.log("totalWidth:", totalWidth);
            
            var totalHeight = e.scrollHeight;
            console.log("totalHeight:", totalHeight);
            
            var viewportWidth = window.innerWidth;
            console.log("viewportWidth:", viewportWidth);
            
            var viewportHeight = window.innerHeight;
            console.log("viewportHeight:", viewportHeight);
            
            var result = {
                totalWidth: totalWidth,
                totalHeight: totalHeight,
                viewportWidth: viewportWidth,
                viewportHeight: viewportHeight
            };
            
            console.log("Final result:", result);
            return result;
        })();
        """
        
        def callback(result):
            print(f"✓ Step-by-step metrics: {result} (type: {type(result)})")
        
        page.runJavaScript(js, callback)

    def test_json_metrics(self):
        print("=== JSON METRICS TEST ===")
        page = self.webview.page()
        
        # Return JSON string instead of object
        js = """
        (function() {
            try {
                var e = document.documentElement;
                var b = document.body;
                
                var result = {
                    totalWidth: e ? e.scrollWidth : 0,
                    totalHeight: e ? e.scrollHeight : 0,
                    viewportWidth: window.innerWidth || 0,
                    viewportHeight: window.innerHeight || 0,
                    dpr: window.devicePixelRatio || 1
                };
                
                return JSON.stringify(result);
                
            } catch (err) {
                return JSON.stringify({error: err.toString()});
            }
        })();
        """
        
        def callback(result):
            print(f"✓ JSON metrics: {result} (type: {type(result)})")
            if result:
                try:
                    import json
                    parsed = json.loads(result)
                    print(f"✓ Parsed object: {parsed}")
                except Exception as e:
                    print(f"✗ JSON parse error: {e}")
        
        page.runJavaScript(js, callback)

def main():
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()