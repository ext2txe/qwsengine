# config8r_v4.py
# Left panel: Listing Analyzer with path bar and vertical splitter (candidates/matches).
# Right panel: Control tabs -> (1) Render (QWebEngineView), (2) Raw HTML of selected match.
# Fallback detector included. Requires PySide6, lxml, cssselect, PySide6-QtWebEngine.

from __future__ import annotations
import os, sys, json, datetime as _dt
from pathlib import Path
from typing import Optional, List, Dict, Any
from copy import deepcopy

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, QSize, QUrl
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QMessageBox, QDockWidget,
    QWidget, QVBoxLayout, QHBoxLayout, QTableView, QPushButton, QGroupBox,
    QToolBar, QStatusBar, QLabel, QListWidget, QSplitter, QTabWidget, QTextEdit
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings

from lxml import html as lxml_html, etree
from .scopes import HtmlDoc
from .processors import run_pipeline


# ---------------- Helper functions (adapted from poc_v0) ----------------

KEY_ATTR_PRESENCE = {"role", "itemtype", "itemscope"}
DATA_PREFIXES = ("data-", "aria-")

def compact_html(text: str, drop_all_blank_lines: bool = True) -> str:
    lines = text.splitlines()
    if drop_all_blank_lines:
        lines = [ln.rstrip() for ln in lines if ln.strip() != ""]
    else:
        out, blank = [], False
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

def outer_html(el: etree._Element, pretty: bool = False) -> str:
    return etree.tostring(el, encoding="unicode", method="html", pretty_print=pretty)

def normalize_lazy_media(el):
    # Images
    for img in el.xpath(".//img"):
        if not img.get("src"):
            for a in ("data-src","data-original","data-lazy","data-url","data-img"):
                val = img.get(a)
                if val:
                    img.set("src", val); break
        if not img.get("srcset"):
            ds = img.get("data-srcset")
            if ds: img.set("srcset", ds)
    # <source> in <picture>
    for source in el.xpath(".//picture/source"):
        if not source.get("srcset"):
            ds = source.get("data-srcset")
            if ds: source.set("srcset", ds)
    # Stylesheets deferring href
    for ln in el.xpath(".//link[@rel='stylesheet' and not(@href)]"):
        dh = ln.get("data-href") or ln.get("data-url")
        if dh: ln.set("href", dh)
    # Inline lazy backgrounds
    for node in el.xpath(".//*[@data-bg] | .//*[@data-background] | .//*[@data-bg-src]"):
        bg = node.get("data-bg") or node.get("data-background") or node.get("data-bg-src")
        if bg:
            style = node.get("style","")
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
<style>
html, body {{ margin:0; padding:16px; font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; }}
img {{ max-width:100%; height:auto; display:block; }}
</style>
</head>
<body>
<div class="container">{inner_html}</div>
</body>
</html>"""

# ---------------- Table model ----------------

class CandidateModel(QAbstractTableModel):
    COLS = ("CSS", "XPath", "Count", "Score")
    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: List[Dict[str, Any]] = []
    def set_rows(self, rows: List[Dict[str, Any]]):
        self.beginResetModel()
        self._rows = [
            {"css": str(r.get("css","")), "xpath": str(r.get("xpath","")),
             "count": int(r.get("count",0)), "score": float(r.get("score",0.0))}
            for r in (rows or [])
        ]
        self.endResetModel()
    def rowCount(self, parent=QModelIndex()): return 0 if parent.isValid() else len(self._rows)
    def columnCount(self, parent=QModelIndex()): return 0 if parent.isValid() else len(self.COLS)
    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid(): return None
        row = self._rows[index.row()]; c = index.column()
        if role==Qt.DisplayRole:
            return [row["css"], row["xpath"], row["count"], f"{row['score']:.3f}"][c]
        return None
    def headerData(self, s,o,r=Qt.DisplayRole):
        if r!=Qt.DisplayRole: return None
        return self.COLS[s] if o==Qt.Horizontal else str(s+1)
    def candidate_at(self,row): return self._rows[row] if 0<=row<len(self._rows) else None

# ---------------- Detection (with fallback) ----------------

def _as_root(obj): return getattr(obj,"doc",obj)

def _detect_candidates(obj)->List[Dict[str,Any]]:
    root=_as_root(obj)
    try:
        from poc import detect_repeating_items as _poc; return _poc(root)
    except Exception:
        pass
    counts={}
    for el in root.iter():
        if not isinstance(el.tag,str): continue
        cls=(el.get("class") or "").strip()
        cls_f="."+".".join(cls.split()) if cls else ""
        css=f"{el.tag}{cls_f}"
        rec=counts.setdefault(css,{"css":css,"xpath":f"//{el.tag}","count":0})
        rec["count"]+=1
    rows=[dict(r,score=float(r["count"])) for r in counts.values() if r["count"]>=3]
    rows.sort(key=lambda x:(-x["count"],-x["score"]))
    return rows[:60]

# ---------------- Main window ----------------

class Config8rWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Config8r – Listing Analyzer v4")
        self.resize(1320,780)
        self.project={"listing":{},"detail":{"fields":[]},"custom_processors":[]}
        self.current_listing_path: Optional[str]=None
        self.current_doc: Optional[HtmlDoc]=None
        self._current_matches_nodes: List[etree._Element] = []

        # central placeholder
        self.setCentralWidget(QWidget(self))

        # Left dock (analyzer)
        self._build_left_dock()

        # Right dock (control tabs)
        self._build_right_dock()

        # Toolbar + status
        self._build_toolbar(); self.setStatusBar(QStatusBar(self))

        # Model
        self.candidateModel=CandidateModel(self)
        self.tblCandidates.setModel(self.candidateModel)
        self.tblCandidates.setSortingEnabled(True)

    # ---- UI builders
    def _build_toolbar(self):
        tb=QToolBar("Main",self); tb.setIconSize(QSize(16,16))
        self.addToolBar(Qt.TopToolBarArea,tb)
        for text,slot in [("Open Listing HTML…",self.open_listing_html),
                          ("Analyze Listing",self.on_click_analyze_listing),
                          ("Save Config…",self.save_config)]:
            a=QAction(text,self); a.triggered.connect(slot); tb.addAction(a)

    def _build_left_dock(self):
        self.dckLeft=QDockWidget("Listing Analyzer",self)
        body=QWidget(self.dckLeft); v=QVBoxLayout(body)

        # Top path bar
        bar=QWidget(body); hb=QHBoxLayout(bar); hb.setContentsMargins(0,0,0,0)
        self.lblPath=QLabel("— no file selected —",bar)
        self.lblPath.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.btnOpenSrc=QPushButton("Open in editor",bar)
        self.btnOpenSrc.clicked.connect(self._open_in_editor)
        hb.addWidget(self.lblPath,1); hb.addWidget(self.btnOpenSrc,0,Qt.AlignRight)
        v.addWidget(bar,0)

        # Splitter (vertical): top=candidates, bottom=matches
        splitter=QSplitter(Qt.Vertical,body)

        # top: candidates
        topW=QWidget(); tv=QVBoxLayout(topW)
        grp=QGroupBox("Item candidates",topW); gv=QVBoxLayout(grp)
        self.tblCandidates=QTableView(grp)
        self.tblCandidates.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.tblCandidates.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.tblCandidates.doubleClicked.connect(self.on_candidate_row_activated)
        gv.addWidget(self.tblCandidates)
        row=QHBoxLayout(); self.btnConfirmCandidate=QPushButton("Confirm Item Selector",grp)
        self.btnReanalyze=QPushButton("Re-run Detection",grp)
        row.addWidget(self.btnConfirmCandidate); row.addWidget(self.btnReanalyze); gv.addLayout(row)
        grp.setLayout(gv); tv.addWidget(grp); topW.setLayout(tv)

        # bottom: matches
        bottomW=QWidget(); bv=QVBoxLayout(bottomW)
        self.lblMatches=QLabel("Matches (select a candidate)",bottomW)
        self.lstMatches=QListWidget(bottomW)
        self.lstMatches.currentRowChanged.connect(self._on_match_selected)
        bv.addWidget(self.lblMatches); bv.addWidget(self.lstMatches,1)
        bottomW.setLayout(bv)

        splitter.addWidget(topW); splitter.addWidget(bottomW)
        splitter.setSizes([440, 320])
        v.addWidget(splitter,1)

        body.setLayout(v); self.dckLeft.setWidget(body)
        self.addDockWidget(Qt.LeftDockWidgetArea,self.dckLeft)

        # Signals
        self.btnConfirmCandidate.clicked.connect(self.on_confirm_candidate_clicked)
        self.btnReanalyze.clicked.connect(self.on_click_analyze_listing)
        def _on_sel_changed():
            idxs=self.tblCandidates.selectionModel().selectedRows()
            if not idxs: self._show_matches_for_css(None); return
            cand=self.candidateModel.candidate_at(idxs[0].row())
            self._show_matches_for_css(cand["css"] if cand else None)
        self._connect_selection_handler=_on_sel_changed

    def _build_right_dock(self):
        self.dckRight=QDockWidget("Control",self)
        body=QWidget(self.dckRight); v=QVBoxLayout(body)
        self.tabs=QTabWidget(body)

        # Tab 1: Rendered view
        self.web=QWebEngineView()
        self.web.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        self.web.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        self.web.settings().setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        self.tabs.addTab(self.web,"Rendered")

        # Tab 2: Raw HTML
        self.txtRaw=QTextEdit()
        self.txtRaw.setReadOnly(True); self.txtRaw.setLineWrapMode(QTextEdit.NoWrap)
        self.tabs.addTab(self.txtRaw, "Raw HTML")

        v.addWidget(self.tabs,1)
        body.setLayout(v); self.dckRight.setWidget(body)
        self.addDockWidget(Qt.RightDockWidgetArea,self.dckRight)

    # ---- File ops
    def _shorten_path(self,p,max_len=100):
        if not p: return "— no file selected —"
        return p if len(p)<=max_len else f"{p[:max_len//2-2]}…{p[-max_len//2+2:]}"

    def _open_in_editor(self):
        p=self.current_listing_path
        if not p or not os.path.exists(p):
            QMessageBox.warning(self,"Open","Source file path invalid."); return
        try:
            if sys.platform.startswith("win"): os.startfile(p)  # type: ignore
            elif sys.platform=="darwin": import subprocess; subprocess.Popen(["open",p])
            else: import subprocess; subprocess.Popen(["xdg-open",p])
        except Exception as e: QMessageBox.critical(self,"Open error",str(e))

    def open_listing_html(self):
        path,_=QFileDialog.getOpenFileName(self,"Open Listing HTML","","HTML Files (*.html *.htm);;All Files (*)")
        if not path: return
        try:
            text=open(path,"r",encoding="utf-8",errors="ignore").read()
            doc=lxml_html.fromstring(text)
            self.current_doc=HtmlDoc(doc=doc,url=path)
            self.current_listing_path=path
            self.lblPath.setText(self._shorten_path(path)); self.lblPath.setToolTip(path)
            self.statusBar().showMessage(f"Loaded: {os.path.basename(path)}",3000)
        except Exception as e: QMessageBox.critical(self,"Open failed",str(e))

    # ---- Analyze & selection
    def on_click_analyze_listing(self):
        if self.current_doc is None:
            QMessageBox.information(self,"No listing","Open a listing HTML first."); return
        try: rows=_detect_candidates(self.current_doc)
        except Exception as e: QMessageBox.critical(self,"Analyze failed",str(e)); return
        self.candidateModel.set_rows(rows or [])
        sel_model=self.tblCandidates.selectionModel()
        if sel_model:
            try: sel_model.selectionChanged.disconnect()
            except Exception: pass
            sel_model.selectionChanged.connect(lambda *_: self._connect_selection_handler())
        try: self.tblCandidates.sortByColumn(2,Qt.SortOrder.DescendingOrder)
        except Exception: pass
        self.statusBar().showMessage(f"Found {len(rows or [])} candidates.",2500)

    def on_candidate_row_activated(self,index):
        if not index.isValid(): return
        cand=self.candidateModel.candidate_at(index.row())
        if cand: self._apply_confirmed_candidate(cand)

    def on_confirm_candidate_clicked(self):
        sel=self.tblCandidates.selectionModel().selectedRows()
        if not sel: self.statusBar().showMessage("Select a candidate first.",3000); return
        cand=self.candidateModel.candidate_at(sel[0].row())
        if cand: self._apply_confirmed_candidate(cand)

    def _apply_confirmed_candidate(self,cand):
        self.project.setdefault("listing",{})
        self.project["listing"]["item_selector"]={"css":cand["css"],"xpath":cand["xpath"]}
        self.project["listing"]["_detector_meta"]={"count":cand["count"],"score":float(cand["score"])}
        self.statusBar().showMessage("Item selector confirmed.",2500)

    # ---- Matches handling
    def _show_matches_for_css(self,css):
        self.lstMatches.clear()
        self._current_matches_nodes = []
        if not css: self.lblMatches.setText("Matches (select a candidate)"); return
        if self.current_doc is None: self.lblMatches.setText("Matches (no document loaded)"); return
        root=_as_root(self.current_doc)
        try: nodes=root.cssselect(css)
        except Exception as e:
            self.lstMatches.addItem(f"Selector error: {e}"); self.lblMatches.setText(f"Matches (error) — {css}"); return
        self._current_matches_nodes = nodes or []
        if not nodes: self.lblMatches.setText(f"Matches (0) — {css}"); self.lstMatches.addItem("No matches."); return
        self.lblMatches.setText(f"Matches ({len(nodes)}) — {css}")
        for i,node in enumerate(nodes, start=1):
            try:
                summary = " ".join(" ".join(node.itertext()).split())[:80]
            except Exception:
                summary = ""
            self.lstMatches.addItem(f"#{i} <{getattr(node,'tag','')}>  {summary}")
        # auto-select first for preview
        if nodes: self.lstMatches.setCurrentRow(0)

    def _on_match_selected(self, row:int):
        # Clear views
        self.txtRaw.clear()
        try:
            self.web.setHtml("<html><body><em>No selection</em></body></html>", QUrl())
        except Exception:
            pass
        if row < 0 or row >= len(self._current_matches_nodes):
            return
        try:
            node = deepcopy(self._current_matches_nodes[row])
            # optional media normalization
            normalize_lazy_media(node)
            html_str = outer_html(node, pretty=False)
            html_compact = compact_html(html_str, drop_all_blank_lines=True)
            self.txtRaw.setPlainText(html_compact)
            # Rendered view
            doc_html = build_minimal_doc(html_str)
            base_url = QUrl()
            if self.current_listing_path:
                base_url = QUrl.fromLocalFile(os.path.dirname(self.current_listing_path) + "/")
            self.web.setHtml(doc_html, base_url)
        except Exception as e:
            self.txtRaw.setPlainText(f"Error: {e}")
            try:
                self.web.setHtml(f"<html><body><pre>{e}</pre></body></html>", QUrl())
            except Exception:
                pass

    # ---- Save config
    def _suggest_config_name(self):
        stem=Path(self.current_listing_path).stem if self.current_listing_path else "listing"
        ts=_dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        return f"{stem}__config__{ts}.json"

    def save_config(self):
        if not self.project.get("listing",{}).get("item_selector"):
            QMessageBox.information(self,"Nothing to save","Confirm an item selector first."); return
        default=self._suggest_config_name()
        start=os.path.dirname(self.current_listing_path) if self.current_listing_path else ""
        path,_=QFileDialog.getSaveFileName(self,"Save Config",os.path.join(start,default),"JSON (*.json)")
        if not path: return
        try:
            with open(path,"w",encoding="utf-8") as f: json.dump(self.project,f,indent=2,ensure_ascii=False)
            self.statusBar().showMessage(f"Saved: {os.path.basename(path)}",3000)
        except Exception as e: QMessageBox.critical(self,"Save failed",str(e))


def main():
    app=QApplication(sys.argv)
    w=Config8rWindow(); w.show()
    sys.exit(app.exec())

if __name__=="__main__": main()
