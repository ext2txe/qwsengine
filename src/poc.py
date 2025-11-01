#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import math
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict

from PySide6.QtCore import QUrl, Qt
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings

from PySide6 import QtCore, QtWidgets
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QTextBrowser, QTabWidget, QSplitter, QPushButton, QFileDialog, 
    QComboBox, QListWidget, QTextEdit, QLabel, QCheckBox
)

from lxml import html, etree
from copy import deepcopy


# ---------------------------
# API 
# ---------------------------


# poc.py
def detect_repeating_items(dom_root) -> list[dict]:
    """
    Returns candidates: [{"css": str, "xpath": str, "score": float, "count": int}]
    Implement using your existing subtree-hash/sibling-similarity helpers.
    """
    ...

def infer_selector_from_clicks(clicked_nodes) -> dict:
    """
    clicked_nodes: list of DOM nodes from the WebEngine bridge
    Returns {"css": str, "xpath": str}
    """
    ...

# ---------------------------
# Heuristics & DOM utilities
# ---------------------------

@dataclass
class Candidate:
    # The repeating "item" node signature (e.g., "article.aditem[data-id]")
    item_signature: str
    # A CSS-ish description for the container in which repetition was detected
    container_desc: str
    # The XPath of the container node (for lookup)
    container_xpath: str
    # The tag/classes/attr signature the container's children share (the item)
    count: int
    # Index of the first matched element in document order (for preview if desired)
    sample_outer_html: str


KEY_ATTR_PRESENCE = {"role", "itemtype", "itemscope",
                     # common data-* indicators that are useful but value-specific
                     # we only record PRESENCE, not the actual value
                    }
# If an attribute begins with any of these, we record its presence as [data-...]
DATA_PREFIXES = ("data-", "aria-")

def compact_html(text: str, drop_all_blank_lines: bool = True) -> str:
    """
    Compact HTML for display/export.
    - drop_all_blank_lines=True -> removes every completely blank line
    - False -> collapses multiple blank lines into a single blank line
    """
    lines = text.splitlines()
    if drop_all_blank_lines:
        lines = [ln.rstrip() for ln in lines if ln.strip() != ""]
    else:
        out = []
        blank = False
        for ln in lines:
            if ln.strip() == "":
                if not blank:
                    out.append("")   # keep a single blank
                blank = True
            else:
                out.append(ln.rstrip())
                blank = False
        lines = out
    return "\n".join(lines)

def element_signature(el: etree._Element) -> str:
    """
    Build a CSS-ish signature: tag + .class1.class2 + [data-*]/[aria-*]/[role]/[itemtype]/[itemscope] (presence only)
    We intentionally skip id= as it's typically unique and harms generalization.
    """
    tag = el.tag.lower() if isinstance(el.tag, str) else "unknown"
    classes = []
    attrs_presence = []
    for k, v in el.attrib.items():
        lk = k.lower()
        if lk == "id":
            continue
        if lk == "class":
            classes = [c for c in v.strip().split() if c]
        elif lk in KEY_ATTR_PRESENCE:
            attrs_presence.append(f"[{lk}]")
        else:
            for pref in DATA_PREFIXES:
                if lk.startswith(pref):
                    attrs_presence.append(f"[{pref.rstrip('-')}]")
                    break
    classes = "." + ".".join(sorted(set(classes))) if classes else ""
    attrs_presence = "".join(sorted(set(attrs_presence)))
    return f"{tag}{classes}{attrs_presence}"

def container_description(el: etree._Element, max_up: int = 3) -> str:
    """
    Produce a short, human-friendly description of a node and up to 'max_up' ancestors.
    Example: "div.results > ul.list" or "main > section.cards"
    """
    chain = []
    cur = el
    steps = 0
    while cur is not None and isinstance(cur.tag, str) and steps < max_up:
        chain.append(simple_selector(cur))
        cur = cur.getparent()
        steps += 1
    return " > ".join(reversed(chain))

def simple_selector(el: etree._Element) -> str:
    tag = el.tag.lower() if isinstance(el.tag, str) else "unknown"
    cls = el.get("class", "").strip().split()
    if cls:
        return f"{tag}." + ".".join(sorted(set(cls)))
    return tag

def outer_html(el: etree._Element, pretty: bool = True) -> str:
    return etree.tostring(el, encoding="unicode", method="html", pretty_print=pretty)

def approx_subtree_complexity(el: etree._Element) -> int:
    """
    A simple complexity proxy: number of descendant elements (including self).
    Helps de-prioritize trivial repeats like <li><span>•</span></li>.
    """
    cnt = 1
    for _ in el.iterdescendants():
        cnt += 1
    return cnt

def find_repeating_item_candidates(root: etree._Element,
                                   min_repeats: int = 2,
                                   min_complexity: int = 5,
                                   max_candidates: int = 25) -> List[Candidate]:
    """
    Look for containers where a child signature repeats >= min_repeats times and has enough complexity.
    Score candidates by count * log(avg_complexity) to rank likely item blocks.
    """
    scored: List[Tuple[float, Candidate]] = []

    # Traverse all elements as potential containers
    for container in root.iter():
        if not isinstance(container.tag, str):
            continue

        # Build signature counts of direct children
        sig_counts: Dict[str, List[etree._Element]] = {}
        for child in container:
            if not isinstance(child.tag, str):
                continue
            sig = element_signature(child)
            sig_counts.setdefault(sig, []).append(child)

        # Evaluate repeating signatures
        for sig, children in sig_counts.items():
            if len(children) < min_repeats:
                continue

            # Filter out trivially simple children
            complexities = [approx_subtree_complexity(ch) for ch in children]
            avg_complexity = sum(complexities) / len(complexities)
            if avg_complexity < min_complexity:
                continue

            # Heuristic score
            score = len(children) * math.log(max(avg_complexity, 2), 2)

            cand = Candidate(
                item_signature=sig,
                container_desc=container_description(container),
                container_xpath=root.getroottree().getpath(container),
                count=len(children),
                sample_outer_html=outer_html(children[0], pretty=True)
            )
            scored.append((score, cand))

    # Sort by score descending and de-duplicate by (container_xpath, item_signature)
    scored.sort(key=lambda x: x[0], reverse=True)
    seen = set()
    results: List[Candidate] = []
    for _score, cand in scored:
        key = (cand.container_xpath, cand.item_signature)
        if key in seen:
            continue
        seen.add(key)
        results.append(cand)
        if len(results) >= max_candidates:
            break

    return results

def select_items_by_candidate(root: etree._Element, cand: Candidate) -> List[etree._Element]:
    """
    Given a candidate (container + repeating child signature), return the list of matching children.
    """
    container = root.xpath(cand.container_xpath)
    if not container:
        return []
    container_el = container[0]

    items = []
    for child in container_el:
        if not isinstance(child.tag, str):
            continue
        if element_signature(child) == cand.item_signature:
            items.append(child)
    return items

def normalize_lazy_media(el):
    """
    Promote common 'lazy' attributes to real ones so images/styles load without the site's JS.
    Works in-place on the passed element.
    """
    # Images: move known lazy attrs to src/srcset
    for img in el.xpath(".//img"):
        if not img.get("src"):
            for a in ("data-src", "data-original", "data-lazy", "data-url", "data-img"):
                val = img.get(a)
                if val:
                    img.set("src", val)
                    break
        if not img.get("srcset"):
            ds = img.get("data-srcset")
            if ds:
                img.set("srcset", ds)

    # <source> inside <picture>
    for source in el.xpath(".//picture/source"):
        if not source.get("srcset"):
            ds = source.get("data-srcset")
            if ds:
                source.set("srcset", ds)

    # Stylesheets that defer href
    for ln in el.xpath(".//link[@rel='stylesheet' and not(@href)]"):
        dh = ln.get("data-href") or ln.get("data-url")
        if dh:
            ln.set("href", dh)

    # Inline lazy backgrounds: use XPath union (|), not commas
    for node in el.xpath(".//*[@data-bg] | .//*[@data-background] | .//*[@data-bg-src]"):
        bg = node.get("data-bg") or node.get("data-background") or node.get("data-bg-src")
        if bg:
            style = node.get("style", "")
            if "background-image" not in style:
                style = (style + "; " if style and not style.strip().endswith(";") else style)
                style += f"background-image:url('{bg}')"
                node.set("style", style)

def build_minimal_doc(inner_html: str) -> str:
    return f"""<!doctype html>
    <html>
    <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <base href="./">  <!-- helpful hint; setHtml(baseUrl) is still authoritative -->
    <style>
        html, body {{
        margin: 0;
        padding: 16px;
        font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
        line-height: 1.5;
        background: #fff;
        color: #222;
        }}
        .container {{ max-width: 960px; margin: 0 auto; }}
        img {{ max-width: 100%; height: auto; display: block; }}
    </style>
    </head>
    <body>
    <div class="container">
        {inner_html}
    </div>
    </body>
    </html>"""

# ---------------------------
# GUI
# ---------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("HTML Item Extractor (PoC)")
        self.resize(1200, 800)

        self.html_text: Optional[str] = None
        self.doc_root: Optional[etree._Element] = None
        self.candidates: List[Candidate] = []
        self.current_items: List[etree._Element] = []
        self.opened_path: OPtional[str] = None

        # Widgets
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Top bar
        top_bar = QHBoxLayout()
        self.btn_open = QPushButton("Open HTML…")
        self.btn_open.clicked.connect(self.on_open)
        self.btn_analyze = QPushButton("Analyze Structure")
        self.btn_analyze.clicked.connect(self.on_analyze)
        self.btn_analyze.setEnabled(False)

        self.chk_strip_scripts = QCheckBox("Strip <script> & <style> when viewing")
        self.chk_strip_scripts.setChecked(False)

        top_bar.addWidget(self.btn_open)
        top_bar.addWidget(self.btn_analyze)
        top_bar.addStretch(1)
        top_bar.addWidget(self.chk_strip_scripts)
        layout.addLayout(top_bar)

        self.chk_compact = QCheckBox("Compact output (drop empty lines)")
        self.chk_compact.setChecked(True)

        self.chk_wrap_doc = QCheckBox("Render in minimal HTML shell")
        self.chk_wrap_doc.setChecked(True)
        top_bar.addWidget(self.chk_wrap_doc)

        top_bar.addWidget(self.chk_strip_scripts)
        top_bar.addWidget(self.chk_compact)

        # Candidates row
        cand_row = QHBoxLayout()
        cand_row.addWidget(QLabel("Candidate item parent:"))
        self.cmb_candidates = QComboBox()
        self.cmb_candidates.setMinimumWidth(600)
        self.cmb_candidates.currentIndexChanged.connect(self.on_candidate_changed)
        self.cmb_candidates.setEnabled(False)
        cand_row.addWidget(self.cmb_candidates)

        self.lbl_cand_count = QLabel("")
        cand_row.addWidget(self.lbl_cand_count)
        cand_row.addStretch(1)

        layout.addLayout(cand_row)

        # Splitter (left items | right tabs)
        splitter = QSplitter(Qt.Horizontal)

        # LEFT PANE (container widget + layout)
        leftPane = QWidget()
        leftLayout = QVBoxLayout(leftPane)
        leftLayout.setContentsMargins(0, 0, 0, 0)

        lbl_items = QLabel("Items")
        if not hasattr(self, "lst_items"):
            self.lst_items = QListWidget()
            self.lst_items.currentRowChanged.connect(self.on_item_selected)

        leftLayout.addWidget(lbl_items)
        leftLayout.addWidget(self.lst_items)

        splitter.addWidget(leftPane)

        # RIGHT PANE (container widget + layout)
        rightPane = QWidget()
        rightLayout = QVBoxLayout(rightPane)
        rightLayout.setContentsMargins(0, 0, 0, 0)

        # Right: preview - tabs => (1) Raw HTML, (2) Rendered
        self.tabs = QTabWidget()

        # Raw HTML tab
        src_box = QWidget()
        src_layout = QVBoxLayout(src_box)
        if not hasattr(self, "txt_preview"):
            self.txt_preview = QTextEdit()
            self.txt_preview.setReadOnly(True)
            self.txt_preview.setLineWrapMode(QTextEdit.NoWrap)
        src_layout.addWidget(self.txt_preview)
        self.tabs.addTab(src_box, "Raw HTML")

        # Rendered tab (full browser)
        self.web = QWebEngineView()
        # Allow local fragments to load remote assets (images/CSS/fonts)
        self.web.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        self.web.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        self.web.settings().setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        self.tabs.addTab(self.web, "Rendered")

        rightLayout.addWidget(self.tabs)
        splitter.addWidget(rightPane)

        rightLayout.addWidget(self.tabs)
        splitter.addWidget(rightPane)

        # Stretch so left stays visible; right gets more space
        splitter.setStretchFactor(0, 1)  # left
        splitter.setStretchFactor(1, 3)  # right

        # Optional: ensure left has a reasonable minimum width
        leftPane.setMinimumWidth(240)

        # Finally, add the splitter to your main page layout
        layout.addWidget(splitter)

        # Status
        self.status = self.statusBar()

    # ---------------------------
    # Slots
    # ---------------------------



    def on_open(self):
        fn, _ = QFileDialog.getOpenFileName(self, "Open HTML file", "", "HTML or text files (*.html *.htm *.txt);;All files (*)")
        if not fn:
            return
        try:
            with open(fn, "r", encoding="utf-8", errors="replace") as f:
                self.html_text = f.read()
            self.opened_path = fn
            # Parse upfront (robust to broken HTML)
            self.doc_root = html.fromstring(self.html_text)
            self.candidates.clear()
            self.cmb_candidates.clear()
            self.lst_items.clear()
            self.txt_preview.clear()
            self.btn_analyze.setEnabled(True)
            self.cmb_candidates.setEnabled(False)
            self.status.showMessage(f"Loaded {fn}", 5000)
        except Exception as e:
            self.status.showMessage(f"Error reading file: {e}", 8000)

    def on_analyze(self):
        if self.doc_root is None:
            self.status.showMessage("No document loaded.", 5000)
            return

        # Fresh parse for analysis to ensure consistent state
        try:
            root = html.fromstring(self.html_text or "")
        except Exception as e:
            self.status.showMessage(f"Parse error: {e}", 8000)
            return

        self.candidates = find_repeating_item_candidates(root)
        self.cmb_candidates.clear()
        self.lst_items.clear()
        self.txt_preview.clear()
        self.current_items = []

        if not self.candidates:
            self.cmb_candidates.setEnabled(False)
            self.status.showMessage("No repeating item candidates found.", 8000)
            return

        # Populate dropdown
        for cand in self.candidates:
            label = f"{cand.item_signature}  — in  {cand.container_desc}  (count: {cand.count})"
            self.cmb_candidates.addItem(label)

        self.cmb_candidates.setEnabled(True)
        self.cmb_candidates.setCurrentIndex(0)
        self.status.showMessage(f"Found {len(self.candidates)} candidate(s).")

    def on_candidate_changed(self, idx: int):
        if idx < 0 or idx >= len(self.candidates) or self.doc_root is None:
            self.lst_items.clear()
            self.txt_preview.clear()
            self.lbl_cand_count.setText("")
            self.current_items = []
            return

        cand = self.candidates[idx]
        self.lbl_cand_count.setText(f"{cand.count} matches")
        # Extract items for this candidate
        root = html.fromstring(self.html_text or "")
        items = select_items_by_candidate(root, cand)

        self.current_items = items
        self.lst_items.clear()
        self.txt_preview.clear()

        for i, _ in enumerate(items):
            self.lst_items.addItem(f"Item {i+1}")

        if items:
            self.lst_items.setCurrentRow(0)

    def on_item_selected(self, row: int):
        # Clear current views
        self.txt_preview.clear()
        try:
            # Give the render tab a neutral state
            try:
                # QWebEngineView signature
                self.web.setHtml("<html><body><em>No selection</em></body></html>", QUrl())
            except TypeError:
                # QTextBrowser fallback signature
                self.web.setHtml("<html><body><em>No selection</em></body></html>")
        except Exception:
            pass

        # Nothing selected or out of range
        if row < 0 or row >= len(self.current_items):
            return

        try:
            # Work on a copy so we can safely mutate (strip/normalize) for viewing
            el = deepcopy(self.current_items[row])

            # Optional: strip <script>/<style> (VIEW-ONLY)
            if getattr(self, "chk_strip_scripts", None) and self.chk_strip_scripts.isChecked():
                for scrap in el.xpath(".//script|.//style"):
                    p = scrap.getparent()
                    if p is not None:
                        p.remove(scrap)

            # Ensure lazy-loaded media shows without site JS (VIEW-ONLY)
            if "normalize_lazy_media" in globals():
                normalize_lazy_media(el)

            # Serialize as HTML fragment (no reparsing)
            html_str = outer_html(el, pretty=False)

            # Optional: compact blank lines for readability
            if getattr(self, "chk_compact", None) and self.chk_compact.isChecked():
                html_str = compact_html(html_str, drop_all_blank_lines=True)

            # ---- Tab 1: Raw HTML
            self.txt_preview.setPlainText(html_str)

            # ---- Tab 2: Rendered
            doc_html = build_minimal_doc(html_str)

            # Base URL so relative src/href resolve to the opened file's directory
            base_url = QUrl()
            if getattr(self, "opened_path", None):
                base_url = QUrl.fromLocalFile(os.path.dirname(self.opened_path) + "/")

            # QWebEngineView path (preferred)
            try:
                # Allow local fragments to reach remote/file URLs if you enabled these settings at creation time
                self.web.setHtml(doc_html, base_url)
            except TypeError:
                # QTextBrowser fallback path
                try:
                    self.web.document().setBaseUrl(base_url)
                except Exception:
                    pass
                self.web.setHtml(doc_html)

        except Exception as e:
            # Show the error in RAW tab and also in Rendered tab
            self.txt_preview.setPlainText(f"Error rendering item: {e}")
            try:
                # WebEngine signature first
                self.web.setHtml(f"<html><body><pre>{e}</pre></body></html>", QUrl())
            except TypeError:
                # QTextBrowser fallback
                self.web.setHtml(f"<html><body><pre>{e}</pre></body></html>")

# ---------------------------
# Entrypoint
# ---------------------------

def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
