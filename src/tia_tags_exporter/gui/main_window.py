from __future__ import annotations
from PySide6 import QtCore, QtWidgets
from pathlib import Path
from typing import List
from ..config_store import ProfileStore
from ..settings import DllProfile
from ..openness_bridge import ensure_clr_and_load
from ..session import TiaSession
from ..tag_extractor import TagExtractor
from ..excel_writer import write_tags_xlsx


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, store: ProfileStore):
        super().__init__()
        self.setWindowTitle("TIA Tags Exporter (V17)")
        self.resize(900, 600)
        self.store = store
        self.prof: DllProfile | None = store.get_profile("V17")

        # UI
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)

        self.lblProfile = QtWidgets.QLabel("Profile: not set")
        self.btnWizard = QtWidgets.QPushButton("Run DLL Wizard…")
        self.btnWizard.clicked.connect(self.on_wizard)

        self.btnAttach = QtWidgets.QPushButton("Attach to TIA V17…")
        self.btnAttach.clicked.connect(self.on_attach)

        self.plcList = QtWidgets.QListWidget()
        self.plcList.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)

        self.chkComments = QtWidgets.QCheckBox("Include Comments"); self.chkComments.setChecked(True)
        self.chkRetentive = QtWidgets.QCheckBox("Include Retentive"); self.chkRetentive.setChecked(True)
        self.chkAddress  = QtWidgets.QCheckBox("Include Address");   self.chkAddress.setChecked(True)

        self.btnExport = QtWidgets.QPushButton("Export PLC Tags → Excel")
        self.btnExport.clicked.connect(self.on_export)

        self.log = QtWidgets.QTextEdit()
        self.log.setReadOnly(True)

        for w in [
            self.lblProfile, self.btnWizard, self.btnAttach, self.plcList,
            self.chkComments, self.chkRetentive, self.chkAddress,
            self.btnExport, self.log
        ]:
            layout.addWidget(w)

        self._session: TiaSession | None = None
        self.refresh_profile_label()

    def refresh_profile_label(self):
        if self.prof and self.prof.public_api_dir:
            self.lblProfile.setText(f"Profile: V17 @ {self.prof.public_api_dir}")
        else:
            self.lblProfile.setText("Profile: not set")

    def on_wizard(self):
        from .wizard import DllWizard
        wiz = DllWizard(self.store, self)
        # We do NOT rely on Accept/Reject return code anymore.
        wiz.exec()
        # Always reload profile after wizard closes (user may have pressed Close)
        self.prof = self.store.get_profile("V17")
        self.refresh_profile_label()

    def on_attach(self):
        # Revalidate profile just before attach
        if not self.prof or not self.prof.public_api_dir:
            # Try to reload in case it was saved while this window was open
            self.prof = self.store.get_profile("V17")
            if not self.prof or not self.prof.public_api_dir:
                QtWidgets.QMessageBox.warning(self, "Profile", "Run the DLL Wizard first to select Siemens.Engineering.dll.")
                return

        # Load CLR/Siemens.Engineering
        res = ensure_clr_and_load(Path(self.prof.public_api_dir) / "Siemens.Engineering.dll")
        if not res.ok:
            QtWidgets.QMessageBox.critical(self, "CLR Load", res.message)
            return

        # TIA Session
        self._session = TiaSession()
        instances = self._session.list_instances()
        if not instances:
            QtWidgets.QMessageBox.information(self, "Attach", "No running TIA Portal instances found.\nStart TIA V17 with a project open, then retry.")
            return

        items = [f"{i.index}: {i.description}" for i in instances]
        choice, ok = QtWidgets.QInputDialog.getItem(self, "Attach", "Select TIA instance:", items, 0, False)
        if not ok:
            return
        sel_index = int(choice.split(":")[0])

        try:
            self._session.attach(sel_index)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Attach", f"Failed to attach:\n{e}")
            return

        self.log.append(f"Attached. Project: {self._session.project_name}")

        # Populate PLCs
        try:
            extr = TagExtractor(self._session)
            plcs = extr.list_plcs()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "PLC Discovery", f"Failed to enumerate PLCs:\n{e}")
            return

        self.plcList.clear()
        for p in plcs:
            self.plcList.addItem(p)

        if not plcs:
            self.log.append("No PLCs exposing PlcSoftware/TagTableGroup were found in this project.")

    def on_export(self):
        if not self._session:
            QtWidgets.QMessageBox.warning(self, "Attach", "Attach to TIA first.")
            return
        # Collect selected PLCs
        selected = [i.text() for i in self.plcList.selectedItems()] or None
        extr = TagExtractor(self._session)
        rows = list(extr.extract_tags(selected))
        if not rows:
            QtWidgets.QMessageBox.information(self, "Export", "No tags found to export.")
            return
        out, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Excel", "PLC_Tags.xlsx", "Excel (*.xlsx)")
        if not out:
            return
        write_tags_xlsx(rows, Path(out))
        self.log.append(f"Exported {len(rows)} rows → {out}")
        msg = f"Exported {len(rows)} rows to:\n{out}"
        QtWidgets.QMessageBox.information(self, "Done", msg)
