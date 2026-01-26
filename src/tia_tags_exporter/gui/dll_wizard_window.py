from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtWidgets

from .wizard import DllWizard


class DllWizardWindow(QtWidgets.QMainWindow):
    """Host window for the DLL discovery wizard and upcoming tutorial content."""

    profile_updated = QtCore.Signal()

    def __init__(self, store, parent: Optional[QtWidgets.QWidget] = None, version: str = "V17") -> None:
        super().__init__(parent)
        self.store = store
        self.version = version
        self.setWindowTitle(f"DLL Discovery & Tutorial ({version})")
        self.resize(1000, 700)

        central = QtWidgets.QWidget(self)
        self.setCentralWidget(central)

        layout = QtWidgets.QVBoxLayout(central)
        header = QtWidgets.QLabel(
            "Use the walkthrough on the left to prepare your environment, then launch the "
            "automated discovery wizard."
        )
        header.setWordWrap(True)
        layout.addWidget(header)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        layout.addWidget(splitter, 1)

        self.tutorial = QtWidgets.QTextBrowser()
        self.tutorial.setOpenExternalLinks(True)
        self.tutorial.setHtml(
            "<h2>DLL Wizard Tutorial (Draft)</h2>"
            "<ol>"
            "<li>Ensure TIA Portal is installed and closed.</li>"
            "<li>Review the Siemens support article for Openness DLL locations.</li>"
            f"<li>Press <b>Run Discovery</b> to enumerate candidate folders for {version}.</li>"
            "<li>Confirm the suggested profile, then close the wizard to return here.</li>"
            "</ol>"
            "Updated guidance will appear here as the tutorial is authored."
        )
        splitter.addWidget(self.tutorial)

        right_panel = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_panel)

        self.runButton = QtWidgets.QPushButton(f"Run Discovery Wizard for {version}...")
        self.closeButton = QtWidgets.QPushButton("Close")
        self.runButton.clicked.connect(self.launch_wizard)
        self.closeButton.clicked.connect(self.close)

        button_row = QtWidgets.QHBoxLayout()
        button_row.addWidget(self.runButton)
        button_row.addWidget(self.closeButton)
        button_row.addStretch(1)
        right_layout.addLayout(button_row)

        self.statusLog = QtWidgets.QTextEdit(readOnly=True)
        self.statusLog.setPlaceholderText("Wizard status will appear here.")
        right_layout.addWidget(self.statusLog, 1)

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)

    def launch_wizard(self) -> None:
        self.statusLog.append(f"Launching DLL discovery wizard for {self.version}...")
        try:
            wizard = DllWizard(self.store, self, version=self.version)
            result = wizard.exec()
            self.statusLog.append("Wizard finished with code: {}".format(result))
        finally:
            self.profile_updated.emit()
            self.close()
