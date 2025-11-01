# config8r_v2.py
# Clean version per 2025-11-01 requirements.
# PySide6 UI for analyzing local listing HTML and identifying repeating items.

from __future__ import annotations
import os
import sys
import json
import datetime as _dt
from pathlib import Path
from typing import Optional, List, Dict, Any

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, QSize
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QMessageBox, QDockWidget,
    QWidget, QVBoxLayout, QHBoxLayout, QTableView, QPushButton, QGroupBox,
    QToolBar, QStatusBar, QLabel, QListWidget
)

from lxml import html as lxml_html, etree
from scopes import HtmlDoc


# -----------------------------------------------------------------------------
# Candidate model
# -----------------------------------------------------------------------------
class CandidateModel(QAbstractTableModel):
    COLS = ("CSS", "XPath", "Count", "Score")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: List[Dict[str, Any]] = []

    def set_rows(self, rows: List[Dict[str, Any]]):
        self.beginResetModel()
        self._rows = [
            {
                "css": str(r.get("css", "")),
                "xpath": str(r.get("xpath", "")),
                "count": int(r.get("count", 0)),
                "score": float(r.get("score", 0.0)),
            }
            for r in (rows or [])
        ]
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.COLS)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        r, c = index.row(), index.column()
        row = self._rows[r]
        if role == Qt.DisplayRole:
            if c == 0: return row["css"]
            if c == 1: return row["xpath"]
            if c == 2: return row["count"]
            if c == 3: return f"{row['score']:.3f}"
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return self.COLS[section]
        return str(section + 1)

    def candidate_at(self, row: int) -> Optional[Dict[str, Any]]:
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return None


# -----------------------------------------------------------------------------
# Detection adapter (robust to HtmlDoc OR lxml root)
# -----------------------------------------------------------------------------
def _as_root(obj) -> etree._Element:
    return getattr(obj, "doc", obj)

def _detect_candidates(obj) -> List[Dict[str, Any]]:
    root = _as_root(obj)
    try:
        from poc import detect_repeating_items as _poc_detect  # type: ignore
        return _poc_detect(root)
    except Exception:
        pass
    counts: Dict[str, Dict[str, Any]] = {}
    for el in root.iter():
        if not isinstance(el.tag, str):
            continue
        cls = (el.get("class") or "").strip()
        cls_f = "." + ".".join(cls.split()) if cls else ""
        css = f"{el.tag}{cls_f}"
        rec = counts.setdefault(css, {"css": css, "xpath": f"//{el.tag}", "count": 0})
        rec["count"] += 1
    rows = [dict(r, score=float(r["count"])) for r in counts.values() if r["count"] >= 3]
    rows.sort(key=lambda x: (-x["count"], -x["score"]))
    return rows[:60]


# -----------------------------------------------------------------------------
# Main window
# -----------------------------------------------------------------------------
class Config8rWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Config8r – Listing Analyzer")
        self.resize(1100, 720)

        self.project: Dict[str, Any] = {"listing": {}, "detail": {"fields": []}, "custom_processors": []}
        self.current_listing_path: Optional[str] = None
        self.current_doc: Optional[HtmlDoc] = None

        # Central widget placeholder (no HTML viewer)
        self.setCentralWidget(QWidget(self))

        # Listing analyzer dock (left)
        self._build_listing_analyzer_dock()

        # Toolbar + status bar
        self._build_toolbar()
        self.setStatusBar(QStatusBar(self))

        # Model
        self.candidateModel = CandidateModel(self)
        self.tblCandidates.setModel(self.candidateModel)
        self.tblCandidates.setSortingEnabled(True)

    # -- UI builders ----------------------------------------------------------
    def _build_toolbar(self):
        tb = QToolBar("Main", self)
        tb.setIconSize(QSize(16, 16))
        self.addToolBar(Qt.TopToolBarArea, tb)

        actOpen = QAction("Open Listing HTML…", self)
        actOpen.triggered.connect(self.open_listing_html)
        tb.addAction(actOpen)

        actAnalyze = QAction("Analyze Listing", self)
        actAnalyze.triggered.connect(self.on_click_analyze_listing)
        tb.addAction(actAnalyze)

        actSave = QAction("Save Config…", self)
        actSave.triggered.connect(self.save_config)
        tb.addAction(actSave)

    def _build_listing_analyzer_dock(self):
        self.dckListingAnalyzer = QDockWidget("Listing Analyzer", self)
        self.dckListingAnalyzer.setObjectName("dckListingAnalyzer")
        body = QWidget(self.dckListingAnalyzer)
        v = QVBoxLayout(body)

        # --- File path bar ---
        path_bar = QWidget(body)
        hpath = QHBoxLayout(path_bar)
        hpath.setContentsMargins(0, 0, 0, 0)
        self.lblPath = QLabel("— no file selected —", path_bar)
        self.lblPath.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.btnOpenSrc = QPushButton("Open in editor", path_bar)
        self.btnOpenSrc.clicked.connect(self._open_in_editor)
        hpath.addWidget(self.lblPath, 1)
        hpath.addWidget(self.btnOpenSrc, 0, Qt.AlignRight)
        v.addWidget(path_bar)

        # --- Candidate group ---
        grp = QGroupBox("Item candidates", body)
        gv = QVBoxLayout(grp)

        self.tblCandidates = QTableView(grp)
        self.tblCandidates.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.tblCandidates.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.tblCandidates.doubleClicked.connect(self.on_candidate_row_activated)
        gv.addWidget(self.tblCandidates)

        row = QHBoxLayout()
        self.btnConfirmCandidate = QPushButton("Confirm Item Selector", grp)
        self.btnReanalyze = QPushButton("Re-run Detection", grp)
        row.addWidget(self.btnConfirmCandidate)
        row.addWidget(self.btnReanalyze)
        gv.addLayout(row)

        grp.setLayout(gv)
        v.addWidget(grp)

        # --- Matches ---
        self.lblMatches = QLabel("Matches (select a candidate)", body)
        self.lstMatches = QListWidget(body)
        v.addWidget(self.lblMatches)
        v.addWidget(self.lstMatches, 1)

        body.setLayout(v)
        self.dckListingAnalyzer.setWidget(body)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dckListingAnalyzer)

        # Signals
        self.btnConfirmCandidate.clicked.connect(self.on_confirm_candidate_clicked)
        self.btnReanalyze.clicked.connect(self.on_click_analyze_listing)

        def _on_sel_changed():
            idxs = self.tblCandidates.selectionModel().selectedRows()
            if not idxs:
                self._show_matches_for_css(None)
                return
            cand = self.candidateModel.candidate_at(idxs[0].row())
            self._show_matches_for_css(cand["css"] if cand else None)

        self._connect_selection_handler = _on_sel_changed

    # -- File operations ------------------------------------------------------
    def _shorten_path(self, p: str, max_len: int = 100) -> str:
        if not p:
            return "— no file selected —"
        return p if len(p) <= max_len else f"{p[:max_len//2-2]}…{p[-max_len//2+2:]}"

    def _open_in_editor(self):
        p = self.current_listing_path
        if not p or not os.path.exists(p):
            QMessageBox.warning(self, "Open", "Source file path is invalid.")
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(p)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                import subprocess; subprocess.Popen(["open", p])
            else:
                import subprocess; subprocess.Popen(["xdg-open", p])
        except Exception as e:
            QMessageBox.critical(self, "Open error", str(e))

    def open_listing_html(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Listing HTML", "", "HTML Files (*.html *.htm);;All Files (*)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                text = fh.read()
            doc = lxml_html.fromstring(text)
            self.current_doc = HtmlDoc(doc=doc, url=path)
            self.current_listing_path = path
            self.lblPath.setText(self._shorten_path(path))
            self.lblPath.setToolTip(path)
            self.statusBar().showMessage(f"Loaded: {os.path.basename(path)}", 3000)
        except Exception as e:
            QMessageBox.critical(self, "Open failed", str(e))

    # -- Analyze and selection ------------------------------------------------
    def on_click_analyze_listing(self):
        if self.current_doc is None:
            QMessageBox.information(self, "No listing", "Open a listing HTML first.")
            return
        try:
            rows = _detect_candidates(self.current_doc)
        except Exception as e:
            QMessageBox.critical(self, "Analyze failed", str(e))
            return

        self.candidateModel.set_rows(rows or [])
        sel_model = self.tblCandidates.selectionModel()
        if sel_model:
            try:
                sel_model.selectionChanged.disconnect()
            except Exception:
                pass
            sel_model.selectionChanged.connect(lambda *_: self._connect_selection_handler())
        try:
            self.tblCandidates.sortByColumn(2, Qt.SortOrder.DescendingOrder)
        except Exception:
            pass
        self.statusBar().showMessage(f"Found {len(rows or [])} candidates.", 2500)

    def on_candidate_row_activated(self, index: QModelIndex):
        if not index.isValid():
            return
        cand = self.candidateModel.candidate_at(index.row())
        if cand:
            self._apply_confirmed_candidate(cand)

    def on_confirm_candidate_clicked(self):
        sel = self.tblCandidates.selectionModel().selectedRows()
        if not sel:
            self.statusBar().showMessage("Select a candidate first.", 3000)
            return
        cand = self.candidateModel.candidate_at(sel[0].row())
        if cand:
            self._apply_confirmed_candidate(cand)

    def _apply_confirmed_candidate(self, cand: Dict[str, Any]):
        self.project.setdefault("listing", {})
        self.project["listing"]["item_selector"] = {"css": cand["css"], "xpath": cand["xpath"]}
        self.project["listing"]["_detector_meta"] = {"count": cand["count"], "score": float(cand["score"])}
        self.statusBar().showMessage("Item selector confirmed.", 2500)

    # -- Matches list ---------------------------------------------------------
    def _show_matches_for_css(self, css: Optional[str]):
        self.lstMatches.clear()
        if not css:
            self.lblMatches.setText("Matches (select a candidate)")
            return
        if self.current_doc is None:
            self.lblMatches.setText("Matches (no document loaded)")
            return
        root = _as_root(self.current_doc)
        try:
            nodes = root.cssselect(css)
        except Exception as e:
            self.lstMatches.addItem(f"Selector error: {e}")
            self.lblMatches.setText(f"Matches (error) — {css}")
            return
        if not nodes:
            self.lblMatches.setText(f"Matches (0) — {css}")
            self.lstMatches.addItem("No matches.")
            return
        self.lblMatches.setText(f"Matches ({len(nodes)}) — {css}")
        for node in nodes:
            tag = getattr(node, "tag", "")
            try:
                txt = " ".join(" ".join(node.itertext()).split())
            except Exception:
                txt = ""
            try:
                frag = lxml_html.tostring(node, encoding="unicode")[:200].replace("\\n", " ")
            except Exception:
                frag = ""
            self.lstMatches.addItem(f"<{tag}> | {txt[:120]} | {frag}…")

    # -- Save config ----------------------------------------------------------
    def _suggest_config_name(self) -> str:
        stem = Path(self.current_listing_path).stem if self.current_listing_path else "listing"
        ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        return f"{stem}__config__{ts}.json"

    def save_config(self):
        if not self.project.get("listing", {}).get("item_selector"):
            QMessageBox.information(self, "Nothing to save", "Confirm an item selector first.")
            return
        default_name = self._suggest_config_name()
        start_dir = os.path.dirname(self.current_listing_path) if self.current_listing_path else ""
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Config", os.path.join(start_dir, default_name), "JSON (*.json)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(self.project, fh, indent=2, ensure_ascii=False)
            self.statusBar().showMessage(f"Saved: {os.path.basename(path)}", 3000)
        except Exception as e:
            QMessageBox.critical(self, "Save failed", str(e))


# -----------------------------------------------------------------------------
def main():
    app = QApplication(sys.argv)
    w = Config8rWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
