#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, sys, time, random, pathlib, urllib.parse, json
from typing import Optional, List, Dict

# ---------- Third-party ----------
from bs4 import BeautifulSoup
import requests

# ---------- Qt ----------
from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import Qt, QUrl
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QListWidget, QTableWidget, QTableWidgetItem,
    QSplitter, QLabel, QCheckBox, QTextEdit, QMessageBox, QLineEdit,
    QAbstractItemView
)

# Try WebEngine (preferred for rendered preview & JS testing); fallback to QTextBrowser
WEBENGINE_OK = True
try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWebEngineCore import QWebEngineSettings
except Exception:
    WEBENGINE_OK = False
from PySide6.QtWidgets import QTextBrowser, QTabWidget


# =========================================================
# Helpers: HTML processing
# =========================================================

def compact_html(text: str, drop_all_blank_lines: bool = True) -> str:
    lines = text.splitlines()
    if drop_all_blank_lines:
        lines = [ln.rstrip() for ln in lines if ln.strip() != ""]
    else:
        out = []
        blank = False
        for ln in lines:
            if ln.strip() == "":
                if not blank:
                    out.append("")
                blank = True
            else:
                out.append(ln.rstrip())
                blank = False
        lines = out
    return "\n".join(lines)

def build_minimal_doc(inner_html: str) -> str:
    """Wrap fragment for rendering; keep neutral styling to avoid unreadable colors."""
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <style>
    html, body {{
      margin: 0; padding: 16px;
      background: #ffffff; color: #222;
      font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
      line-height: 1.5;
    }}
    .container {{ max-width: 960px; margin: 0 auto; }}
    img {{ max-width: 100%; height: auto; display: block; }}
    a {{ color: #0645ad; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    pre, code {{ background:#f5f5f5; padding:2px 4px; border-radius:4px; }}
  </style>
</head>
<body>
  <div class="container">
    {inner_html}
  </div>
</body>
</html>"""

def list_item_links(list_html: str, base_url: str = "") -> List[str]:
    """
    Extract likely detail links from a listing (SRP) page.
    - Looks at article[data-href] and <h2><a href=...>
    """
    soup = BeautifulSoup(list_html, "lxml")
    links = []

    # <article class="aditem" data-href="/s-anzeige/...">
    for art in soup.select("article.aditem[data-href]"):
        href = art.get("data-href")
        if href:
            links.append(urllib.parse.urljoin(base_url, href) if base_url else href)

    # fallback: anchor inside headings
    for a in soup.select("h2 a[href]"):
        href = a.get("href")
        if href:
            links.append(urllib.parse.urljoin(base_url, href) if base_url else href)

    # dedupe, preserve order
    seen, out = set(), []
    for u in links:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out

def fetch_pages(urls: List[str], out_dir: str, delay=(0.6, 1.4)) -> List[str]:
    """Download item pages; return local file paths."""
    pathlib.Path(out_dir).mkdir(parents=True, exist_ok=True)
    ses = requests.Session()
    ses.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/126.0 Safari/537.36"
    })
    local_paths = []
    for i, u in enumerate(urls):
        fn = os.path.join(out_dir, f"item_{i:04d}.html")
        try:
            r = ses.get(u, timeout=20)
            r.raise_for_status()
            with open(fn, "wb") as f:
                f.write(r.content)
            local_paths.append(fn)
        except Exception as e:
            print(f"Failed {u}: {e}")
        time.sleep(random.uniform(*delay))
    return local_paths

def detect_candidates(detail_html: str) -> Dict:
    """Heuristic selectors for common fields on a detail page."""
    soup = BeautifulSoup(detail_html, "lxml")
    cand: Dict[str, Dict] = {}

    # Title
    el = soup.select_one("#viewad-title")
    if el and el.get_text(strip=True):
        cand["title"] = {"selector": "#viewad-title", "value": el.get_text(strip=True)}

    # Price: textual node and numeric meta
    price_el = soup.select_one("#viewad-price")
    if price_el:
        cand["price_text"] = {"selector": "#viewad-price", "value": price_el.get_text(strip=True)}
    price_meta = soup.select_one('meta[itemprop="price"]')
    if price_meta and price_meta.get("content"):
        cand["price_amount"] = {"selector": 'meta[itemprop="price"]', "attr": "content", "value": price_meta["content"]}

    # Location
    loc = soup.select_one("#viewad-locality")
    if loc:
        cand["location"] = {"selector": "#viewad-locality", "value": loc.get_text(strip=True)}

    # Facts (label/value rows)
    facts = []
    for li in soup.select(".addetailslist--detail"):
        label = None
        # label is usually the first text node in li
        if li.contents:
            try:
                label = (li.contents[0] or "").strip()
            except Exception:
                label = None
        val_el = li.select_one(".addetailslist--detail--value")
        value = val_el.get_text(strip=True) if val_el else None
        if (label and value) or value:
            facts.append({"label": (label or ""), "value": (value or "")})
    if facts:
        cand["facts"] = {"type": "list", "selector": ".addetailslist--detail", "items": facts}

    # Features (tag list)
    features = [t.get_text(strip=True) for t in soup.select(".checktaglist .checktag")]
    if features:
        cand["features"] = {"type": "list", "selector": ".checktaglist .checktag", "items": features}

    return cand

def generate_extractor_js(spec: dict) -> str:
    """Generate a JS self-invoking extractor function."""
    has_title  = "title"       in spec and spec["title"].get("selector")
    has_ptxt   = "price_text"  in spec and spec["price_text"].get("selector")
    has_pamt   = "price_amount" in spec and spec["price_amount"].get("selector")
    has_loc    = "location"    in spec and spec["location"].get("selector")
    has_facts  = "facts"       in spec and spec["facts"].get("selector")
    has_feats  = "features"    in spec and spec["features"].get("selector")

    js = """(function() {
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));
  const txt = (el) => (el && (el.textContent||"").trim()) || null;
  const attr = (el, a) => (el && el.getAttribute(a)) || null;
  const num = (s) => {
    if (!s) return null;
    const m = String(s).replace(/\\./g, '').replace(',', '.').match(/-?\\d+(?:\\.\\d+)?/);
    return m ? parseFloat(m[0]) : null;
  };

  const out = {};

  out.title = %s;
  out.price_text = %s;
  out.price_amount = (function(){
    const el = %s;
    return el ? num(attr(el,'content')) : null;
  })();
  out.location = %s;

  out.facts = (function(){
    if (!%s) return [];
    const rows = $$('.addetailslist--detail');
    return rows.map(li => {
      const label = (li.childNodes[0]?.nodeValue||'').trim();
      const valEl = li.querySelector('.addetailslist--detail--value');
      return { label, value: txt(valEl) };
    }).filter(x => x.label || x.value);
  })();

  out.features = (function(){
    if (!%s) return [];
    return $$('.checktaglist .checktag').map(el => txt(el)).filter(Boolean);
  })();

  return out;
})();""" % (
        "txt($('#viewad-title'))" if has_title else "null",
        "txt($('#viewad-price'))" if has_ptxt else "null",
        "$('meta[itemprop=\"price\"]')" if has_pamt else "null",
        "txt($('#viewad-locality'))" if has_loc else "null",
        str(bool(has_facts)).lower(),
        str(bool(has_feats)).lower(),
    )

    return js

# =========================================================
# UI
# =========================================================

class PoC2(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("poc2 – Detail Page Capture & Extractor Generator")
        self.resize(1400, 900)

        self.list_html_path: Optional[str] = None
        self.detail_paths: List[str] = []     # local file paths to detail html
        self.current_detail_path: Optional[str] = None
        self.current_detail_html: Optional[str] = None

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        # --- Top bar ---
        top = QHBoxLayout()
        self.btn_open_list = QPushButton("Open List (SRP) HTML…")
        self.btn_open_list.clicked.connect(self.open_list_html)

        self.btn_fetch = QPushButton("Fetch Details")
        self.btn_fetch.clicked.connect(self.fetch_details)
        self.btn_fetch.setEnabled(False)

        self.btn_open_details = QPushButton("Open Detail HTML(s)…")
        self.btn_open_details.clicked.connect(self.open_detail_files)

        self.inp_base_url = QLineEdit()
        self.inp_base_url.setPlaceholderText("Base URL (optional, for resolving relative SRP links)")
        self.inp_base_url.setMinimumWidth(320)

        self.chk_compact = QCheckBox("Compact")
        self.chk_compact.setChecked(True)

        self.btn_detect = QPushButton("Detect Fields")
        self.btn_detect.clicked.connect(self.detect_fields)
        self.btn_generate_js = QPushButton("Generate JS")
        self.btn_generate_js.clicked.connect(self.generate_js)
        self.btn_test_js = QPushButton("Test Extract (Rendered)")
        self.btn_test_js.clicked.connect(self.test_js)

        top.addWidget(self.btn_open_list)
        top.addWidget(self.btn_fetch)
        top.addWidget(self.btn_open_details)
        top.addWidget(self.inp_base_url, 1)
        top.addStretch(1)
        top.addWidget(self.chk_compact)
        top.addWidget(self.btn_detect)
        top.addWidget(self.btn_generate_js)
        top.addWidget(self.btn_test_js)
        root.addLayout(top)

        # --- Splitter: left = details list; right = tabs ---
        splitter = QSplitter(Qt.Horizontal)

        # Left: list of detail files / URLs
        leftPane = QWidget()
        leftLay = QVBoxLayout(leftPane)
        leftLay.setContentsMargins(0,0,0,0)
        leftLay.addWidget(QLabel("Detail pages"))
        self.lst_details = QListWidget()
        self.lst_details.currentRowChanged.connect(self.on_detail_selected)
        leftLay.addWidget(self.lst_details)
        splitter.addWidget(leftPane)
        leftPane.setMinimumWidth(260)

        # Right: vertical split -> top tabs (HTML preview), bottom (candidates + JS)
        rightSplit = QSplitter(Qt.Vertical)

        # Tabs: Raw HTML | Rendered
        tabsPane = QWidget()
        tabsLay = QVBoxLayout(tabsPane)
        tabsLay.setContentsMargins(0,0,0,0)

        self.tabs = QTabWidget()
        # Raw HTML
        raw_box = QWidget()
        raw_lay = QVBoxLayout(raw_box)
        raw_lay.setContentsMargins(0,0,0,0)
        self.txt_raw = QTextEdit()
        self.txt_raw.setReadOnly(True)
        self.txt_raw.setLineWrapMode(QTextEdit.NoWrap)
        raw_lay.addWidget(self.txt_raw)
        self.tabs.addTab(raw_box, "Raw HTML")

        # Rendered
        if WEBENGINE_OK:
            self.view = QWebEngineView()
            self.view.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
            self.view.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
            self.view.settings().setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        else:
            self.view = QTextBrowser()
        self.tabs.addTab(self.view, "Rendered")
        tabsLay.addWidget(self.tabs)
        rightSplit.addWidget(tabsPane)

        # Bottom: field candidates + JS output
        bottomPane = QWidget()
        bottomLay = QVBoxLayout(bottomPane)
        bottomLay.setContentsMargins(0,0,0,0)

        # Candidates table
        self.tbl = QTableWidget(0, 5)
        self.tbl.setHorizontalHeaderLabels(["Include", "Field", "Selector", "Attr (opt.)", "Preview"])
        
        #self.tbl.horizontalHeader().setStretchLastSection(True)
        #self.tbl.setSelectionBehavior(self.tbl.SelectRows)
        
        # Selection: select entire rows
        try:
            # PySide6 6.4+ style
            self.tbl.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        except AttributeError:
            # Older style
            self.tbl.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)

        # Optional: single-row selection (nice for this UI)
        try:
            self.tbl.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        except AttributeError:
            self.tbl.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)

        # Edit triggers: allow editing selector/attr cells
        try:
            self.tbl.setEditTriggers(
                QtWidgets.QAbstractItemView.EditTrigger.DoubleClicked
                | QtWidgets.QAbstractItemView.EditTrigger.EditKeyPressed
                | QtWidgets.QAbstractItemView.EditTrigger.SelectedClicked
            )
        except AttributeError:
            self.tbl.setEditTriggers(
                QtWidgets.QAbstractItemView.DoubleClicked
                | QtWidgets.QAbstractItemView.EditKeyPressed
                | QtWidgets.QAbstractItemView.SelectedClicked
            )



        #self.tbl.setEditTriggers(self.tbl.DoubleClicked | self.tbl.EditKeyPressed | self.tbl.SelectedClicked)

#        from PySide6.QtWidgets import QAbstractItemView  # (put at top with other imports)

        try:
            ET = QtWidgets.QAbstractItemView.EditTrigger  # modern enum namespace
            self.tbl.setEditTriggers(
                ET.DoubleClicked | ET.EditKeyPressed | ET.SelectedClicked
            )
        except AttributeError:
            # Fallback for very old PySide6 builds
            self.tbl.setEditTriggers(
                QAbstractItemView.DoubleClicked
                | QAbstractItemView.EditKeyPressed
                | QAbstractItemView.SelectedClicked
            )


        bottomLay.addWidget(QLabel("Detected fields (edit selectors as needed)"))
        bottomLay.addWidget(self.tbl, 3)

        # JS output
        bottomLay.addWidget(QLabel("Generated JavaScript"))
        self.txt_js = QTextEdit()
        self.txt_js.setReadOnly(False)
        self.txt_js.setLineWrapMode(QTextEdit.NoWrap)
        bottomLay.addWidget(self.txt_js, 2)

        rightSplit.addWidget(bottomPane)

        splitter.addWidget(rightSplit)
        splitter.setStretchFactor(0, 1)  # left
        splitter.setStretchFactor(1, 3)  # right

        root.addWidget(splitter)

        self.status = self.statusBar()
        self.generated_spec: Dict = {}

    # --------------------------------------
    # File actions
    # --------------------------------------
    def open_list_html(self):
        fn, _ = QFileDialog.getOpenFileName(self, "Open list (SRP) HTML", "", "HTML files (*.html *.htm);;All files (*)")
        if not fn:
            return
        self.list_html_path = fn
        with open(fn, "r", encoding="utf-8", errors="ignore") as f:
            html_text = f.read()
        base = self.inp_base_url.text().strip()
        urls = list_item_links(html_text, base_url=base or "")
        self.lst_details.clear()
        self.detail_paths.clear()
        # Just list URLs for now; "Fetch Details" will download
        for u in urls:
            self.lst_details.addItem(u)
        self.btn_fetch.setEnabled(bool(urls))
        self.status.showMessage(f"Found {len(urls)} candidate links on SRP.", 5000)

    def fetch_details(self):
        if not self.list_html_path:
            QMessageBox.information(self, "Info", "Open a list (SRP) HTML first.")
            return
        # Collect URLs from the list widget
        urls = []
        for i in range(self.lst_details.count()):
            txt = self.lst_details.item(i).text()
            if txt.lower().startswith("http") or txt.startswith("/"):
                urls.append(txt)
        if not urls:
            QMessageBox.information(self, "Info", "No HTTP/relative links in the list to fetch.")
            return

        out_dir = os.path.join(os.path.dirname(self.list_html_path), "details")
        paths = fetch_pages(urls, out_dir=out_dir)
        if not paths:
            QMessageBox.warning(self, "Fetch", "No pages fetched.")
            return

        self.lst_details.clear()
        self.detail_paths = paths
        for p in paths:
            self.lst_details.addItem(p)
        self.status.showMessage(f"Fetched {len(paths)} detail pages → {out_dir}", 8000)

    def open_detail_files(self):
        fns, _ = QFileDialog.getOpenFileNames(self, "Open detail HTML files", "", "HTML files (*.html *.htm);;All files (*)")
        if not fns:
            return
        self.lst_details.clear()
        self.detail_paths = list(fns)
        for p in self.detail_paths:
            self.lst_details.addItem(p)
        self.status.showMessage(f"Loaded {len(self.detail_paths)} local detail files.", 5000)

    # --------------------------------------
    # Selection & display
    # --------------------------------------
    def on_detail_selected(self, row: int):
        self.txt_raw.clear()
        self.generated_spec = {}
        if row < 0:
            return

        item_text = self.lst_details.item(row).text()
        path = item_text
        html_text = ""

        # Load from local file if path exists; else treat as URL (not auto-fetched here)
        if os.path.exists(path):
            self.current_detail_path = path
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                html_text = f.read()
        else:
            # If user selected URL from SRP list (before fetch), just show a placeholder
            self.current_detail_path = None
            html_text = f"<!-- URL not fetched yet: {path} -->"

        self.current_detail_html = html_text

        # Raw tab
        if self.chk_compact.isChecked():
            self.txt_raw.setPlainText(compact_html(html_text))
        else:
            self.txt_raw.setPlainText(html_text)

        # Rendered tab
        doc_html = build_minimal_doc(html_text)
        base_url = QUrl()
        if self.current_detail_path:
            base_url = QUrl.fromLocalFile(os.path.dirname(self.current_detail_path) + "/")
        if WEBENGINE_OK and isinstance(self.view, QWebEngineView):
            self.view.setHtml(doc_html, base_url)
        else:
            if isinstance(self.view, QTextBrowser):
                try:
                    self.view.document().setBaseUrl(base_url)
                except Exception:
                    pass
                self.view.setHtml(doc_html)

        # Auto-detect candidates quickly
        self.detect_fields()

    # --------------------------------------
    # Field detection & JS generation
    # --------------------------------------
    def detect_fields(self):
        self.tbl.setRowCount(0)
        if not self.current_detail_html:
            return
        cand = detect_candidates(self.current_detail_html)

        # Build table rows
        def add_row(key, selector, attr, preview, include=True):
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            # Include checkbox
            check = QTableWidgetItem()
            check.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            check.setCheckState(Qt.Checked if include else Qt.Unchecked)
            self.tbl.setItem(r, 0, check)
            # Field name
            self.tbl.setItem(r, 1, QTableWidgetItem(key))
            # Selector (editable)
            item_sel = QTableWidgetItem(selector or "")
            self.tbl.setItem(r, 2, item_sel)
            # Attr (optional)
            self.tbl.setItem(r, 3, QTableWidgetItem(attr or ""))
            # Preview (readonly)
            prev = QTableWidgetItem(preview if preview is not None else "")
            prev.setFlags(prev.flags() & ~Qt.ItemIsEditable)
            self.tbl.setItem(r, 4, prev)

        # Simple fields
        if "title" in cand:
            add_row("title", cand["title"]["selector"], "", cand["title"]["value"])
        if "price_text" in cand:
            add_row("price_text", cand["price_text"]["selector"], "", cand["price_text"]["value"])
        if "price_amount" in cand:
            add_row("price_amount", cand["price_amount"]["selector"], "content", cand["price_amount"]["value"])
        if "location" in cand:
            add_row("location", cand["location"]["selector"], "", cand["location"]["value"])

        # Lists
        if "facts" in cand:
            prev = ", ".join([f"{x.get('label')}: {x.get('value')}" for x in cand["facts"]["items"][:6]])
            add_row("facts", cand["facts"]["selector"], "", prev)
        if "features" in cand:
            prev = ", ".join(cand["features"]["items"][:10])
            add_row("features", cand["features"]["selector"], "", prev)

        self.status.showMessage("Field candidates detected. Edit selectors as needed, then Generate JS.", 6000)

    def spec_from_table(self) -> Dict:
        spec: Dict = {}
        for r in range(self.tbl.rowCount()):
            include = (self.tbl.item(r, 0).checkState() == Qt.Checked)
            key = self.tbl.item(r, 1).text().strip()
            selector = self.tbl.item(r, 2).text().strip()
            attr = self.tbl.item(r, 3).text().strip()
            if not include or not key or not selector:
                continue
            if key in ("facts", "features"):
                spec[key] = {"type": "list", "selector": selector}
            else:
                ent = {"selector": selector}
                if attr:
                    ent["attr"] = attr
                spec[key] = ent
        return spec

    def generate_js(self):
        spec = self.spec_from_table()
        self.generated_spec = spec
        js = generate_extractor_js(spec)
        self.txt_js.setPlainText(js)
        self.status.showMessage("JavaScript extractor generated.", 5000)

    # --------------------------------------
    # JS test (WebEngine-only)
    # --------------------------------------
    def test_js(self):
        if not WEBENGINE_OK or not isinstance(self.view, QWebEngineView):
            QMessageBox.information(self, "Test Extract", "WebEngine not available. Install PySide6 with WebEngine to test JS.")
            return
        if not self.current_detail_html:
            QMessageBox.information(self, "Test Extract", "Load a detail page first.")
            return
        if not self.txt_js.toPlainText().strip():
            self.generate_js()

        js = self.txt_js.toPlainText()
        # Ensure a result is returned and serialized
        test_js = js + "\n" + "try { JSON.stringify((typeof _res !== 'undefined') ? _res : (typeof result !== 'undefined' ? result : (function(){return (typeof window !== 'undefined') ? (window.__ex = (" + js.strip() + ")) : (" + js.strip() + ");})())); } catch(e){ JSON.stringify({error:String(e)}) }"
        # A simpler runner:
        runner = f"(function(){{ try {{ return JSON.stringify({js}); }} catch(e) {{ return JSON.stringify({{'error': String(e)}}); }} }})();"

        # Re-load the page to ensure a clean DOM before executing
        base_url = QUrl()
        if self.current_detail_path:
            base_url = QUrl.fromLocalFile(os.path.dirname(self.current_detail_path) + "/")
        self.view.setHtml(build_minimal_doc(self.current_detail_html), base_url)

        # After load finishes, run the extractor and show JSON
        def _on_loaded(ok):
            if not ok:
                QMessageBox.warning(self, "Test Extract", "Failed to load HTML in WebEngine.")
                return
            self.view.page().runJavaScript(runner, self._show_js_result)

        if hasattr(self.view, "loadFinished"):
            try:
                self.view.loadFinished.disconnect()
            except Exception:
                pass
            self.view.loadFinished.connect(_on_loaded)
        # If loadFinished doesn't fire (rare), call after a small delay
        QtCore.QTimer.singleShot(250, lambda: self.view.page().runJavaScript(runner, self._show_js_result))

    def _show_js_result(self, result):
        try:
            if isinstance(result, str):
                data = json.loads(result)
            else:
                data = result
        except Exception:
            data = {"raw": result}
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Extractor Result")
        lay = QVBoxLayout(dlg)
        txt = QTextEdit()
        txt.setReadOnly(True)
        txt.setPlainText(json.dumps(data, indent=2, ensure_ascii=False))
        lay.addWidget(txt)
        btn = QPushButton("Close")
        btn.clicked.connect(dlg.accept)
        lay.addWidget(btn, alignment=Qt.AlignRight)
        dlg.resize(640, 480)
        dlg.exec()

# =========================================================
# Entry
# =========================================================

def main():
    app = QApplication(sys.argv)
    w = PoC2()
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
