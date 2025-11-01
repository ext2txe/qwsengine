# config8r.py
# Cross-platform Qt app that loads a local listing HTML, detects repeating items,
# shows candidates, and lets you confirm an item selector.
#
# Dependencies: PySide6, lxml
#   pip install PySide6 lxml

from __future__ import annotations
import os
import sys
from typing import Optional, List, Dict

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, QFileInfo, QSize

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTextEdit, QFileDialog, QMessageBox, QDockWidget,
    QWidget, QVBoxLayout, QHBoxLayout, QTableView, QPushButton, QGroupBox,
    QToolBar, QStatusBar
)
from PySide6.QtGui import QAction

from poc import detect_repeating_items
from scopes import HtmlDoc
from lxml import html as lxml_html


# --------- Candidate model (table on the right dock) ---------------------------------

class CandidateModel(QAbstractTableModel):
    COLS = ("CSS", "XPath", "Count", "Score")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: List[Dict] = []

    def setRows(self, rows: List[Dict]):
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

    def candidate_at(self, row: int) -> Optional[Dict]:
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return None


# --------- Main window ----------------------------------------------------------------

class Config8rWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Config8r – Listing Analyzer (Local HTML)")
        self.resize(1100, 700)

        # Project state
        self.project: Dict = {"listing": {}, "detail": {"fields": []}, "custom_processors": []}
        self.current_listing_path: Optional[str] = None
        self.current_doc: Optional[HtmlDoc] = None

        # Central view (read-only preview of HTML text; swap for WebEngine later if you like)
        self.txtPreview = QTextEdit(self)
        self.txtPreview.setReadOnly(True)
        self.setCentralWidget(self.txtPreview)

        # Status bar
        self.setStatusBar(QStatusBar(self))

        # Toolbar / actions
        self._build_toolbar()

        # Right-side dock with candidates table + buttons
        self._build_listing_analyzer_dock()

    # ----- UI builders -----

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

        self.actSaveConfig = QAction("Save Config…", self)
        self.actSaveConfig.triggered.connect(self.save_config)
        tb.addAction(self.actSaveConfig)

    def _build_listing_analyzer_dock(self):
        self.dckListingAnalyzer = QDockWidget("Listing Analyzer", self)
        self.dckListingAnalyzer.setObjectName("dckListingAnalyzer")
        body = QWidget(self.dckListingAnalyzer)
        v = QVBoxLayout(body)

        grp = QGroupBox("Item candidates", body)
        gv = QVBoxLayout(grp)

        self.tblCandidates = QTableView(grp)
        self.tblCandidates.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.tblCandidates.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        gv.addWidget(self.tblCandidates)

        row = QHBoxLayout()
        self.btnConfirmCandidate = QPushButton("Confirm Item Selector", grp)
        self.btnReanalyze = QPushButton("Re-run Detection", grp)
        row.addWidget(self.btnConfirmCandidate)
        row.addWidget(self.btnReanalyze)
        row.addStretch()
        gv.addLayout(row)

        v.addWidget(grp)
        body.setLayout(v)
        self.dckListingAnalyzer.setWidget(body)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dckListingAnalyzer)

        # Model + wiring
        self.candidateModel = CandidateModel(self)
        self.tblCandidates.setModel(self.candidateModel)
        self.tblCandidates.doubleClicked.connect(self.on_candidate_row_activated)
        self.btnConfirmCandidate.clicked.connect(self.on_confirm_candidate_clicked)
        self.btnReanalyze.clicked.connect(self.on_click_analyze_listing)

    # ----- File ops -----

    def open_listing_html(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Listing HTML", "", "HTML Files (*.html *.htm);;All Files (*)"
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                text = fh.read()
            self.txtPreview.setPlainText(text)
            doc = lxml_html.fromstring(text)
            self.current_doc = HtmlDoc(doc=doc, url=QFileInfo(path).absoluteFilePath())
            self.current_listing_path = path
            self.statusBar().showMessage(f"Loaded: {os.path.basename(path)}", 3000)
        except Exception as e:
            QMessageBox.critical(self, "Open failed", str(e))

    # ----- Detection + confirmation -----

    def on_click_analyze_listing(self):
        if self.current_doc is None:
            QMessageBox.information(self, "No listing", "Open a listing HTML first.")
            return
        try:
            candidates = detect_repeating_items(self.current_doc.doc)
            self.candidateModel.setRows(candidates)
            if self.candidateModel.rowCount() > 0:
                self.tblCandidates.selectRow(0)
            self.statusBar().showMessage(f"Detected {len(candidates)} candidate selector(s).", 3000)
        except Exception as e:
            self.candidateModel.setRows([])
            QMessageBox.critical(self, "Detection failed", str(e))

    def on_candidate_row_activated(self, index: QModelIndex):
        if not index.isValid():
            return
        cand = self.candidateModel.candidate_at(index.row())
        if not cand:
            return
        self._apply_confirmed_candidate(cand)

    def on_confirm_candidate_clicked(self):
        sel = self.tblCandidates.selectionModel().selectedRows()
        if not sel:
            self.statusBar().showMessage("Select a candidate first.", 3000)
            return
        cand = self.candidateModel.candidate_at(sel[0].row())
        if not cand:
            self.statusBar().showMessage("Invalid selection.", 3000)
            return
        self._apply_confirmed_candidate(cand)

    def _apply_confirmed_candidate(self, cand: Dict):
        self.project.setdefault("listing", {})
        self.project["listing"]["item_selector"] = {"css": cand["css"], "xpath": cand["xpath"]}
        self.project["listing"]["_detector_meta"] = {"count": cand["count"], "score": cand["score"]}
        self.statusBar().showMessage("Item selector confirmed.", 2500)

    # ----- Save config -----

    def save_config(self):
        if not self.project.get("listing", {}).get("item_selector"):
            QMessageBox.information(self, "Nothing to save", "Confirm an item selector first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Config", "config.json", "JSON (*.json)"
        )
        if not path:
            return
        try:
            import json
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(self.project, fh, ensure_ascii=False, indent=2)
            self.statusBar().showMessage(f"Saved: {os.path.basename(path)}", 3000)
        except Exception as e:
            QMessageBox.critical(self, "Save failed", str(e))


def main():
    app = QApplication(sys.argv)
    w = Config8rWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
