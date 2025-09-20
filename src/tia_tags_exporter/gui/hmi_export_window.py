from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6 import QtWidgets


class HmiExportWindow(QtWidgets.QMainWindow):
    """Placeholder shell for the upcoming HMI export workflow.

    This window keeps the heavy HMI UX isolated from the main launcher while we
    build out the exporter, tutorial, and progress plumbing.
    """

    def __init__(self, store, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.store = store
        self.setWindowTitle("TIA HMI Export")
        self.resize(900, 600)

        central = QtWidgets.QWidget(self)
        self.setCentralWidget(central)

        layout = QtWidgets.QVBoxLayout(central)
        intro = QtWidgets.QLabel(
            "This area will host the HMI export workflow.\n\n"
            "Upcoming features:\n"
            "  • Launch the Openness exporter for text lists, screens, alarms, recipes.\n"
            "  • Run Python flatteners for XML/AML outputs.\n"
            "  • Show tutorial steps, progress, and manifest summaries.\n"
            "Until implemented, use the CLI tooling documented in the README."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        format_row = QtWidgets.QHBoxLayout()
        format_row.addWidget(QtWidgets.QLabel("Default format:"))
        self.cmbFormat = QtWidgets.QComboBox()
        self.cmbFormat.addItem("CSV (.csv)", "csv")
        self.cmbFormat.addItem("Excel (.xlsx)", "xlsx")
        self.cmbFormat.addItem("Google Sheets", "gsheet")
        self.cmbFormat.setCurrentIndex(0)
        format_row.addWidget(self.cmbFormat)
        format_row.addStretch(1)
        layout.addLayout(format_row)

        self.btnRun = QtWidgets.QPushButton("Run HMI Export")
        self.btnRun.setEnabled(False)
        layout.addWidget(self.btnRun)

        self.log = QtWidgets.QTextEdit(readOnly=True)
        self.log.setPlaceholderText("HMI export status and logs will appear here.")
        layout.addWidget(self.log)

        layout.addStretch(1)

    def set_session_hint(self, project_path: Optional[Path]) -> None:
        """Store session context for future use (no-op placeholder)."""
        if not project_path:
            return
        self.log.append(f"Session context noted: {project_path}")
