from __future__ import annotations

from dataclasses import fields, is_dataclass
from pathlib import Path
from collections.abc import Iterable
import re
import sys
from typing import Any, Dict, Mapping

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from PySide6 import QtGui, QtWidgets

from tia_tags_exporter.config_store import ProfileStore
from tia_tags_exporter.excel_writer import (
    write_tags_csv,
    write_tags_google_sheets,
    write_tags_xlsx,
)
from tia_tags_exporter.openness_bridge import ensure_clr_and_load
from tia_tags_exporter.session import TiaSession
from tia_tags_exporter.settings import DllProfile
from tia_tags_exporter.tag_extractor import TagExtractor
from tia_tags_exporter.block_exporter import ProgramBlockExtractor
from tia_tags_exporter.block_writer import (
    write_blocks_csv,
    write_blocks_google_sheets,
    write_blocks_xlsx,
)
from tia_tags_exporter.gui.dll_wizard_window import DllWizardWindow
from tia_tags_exporter.gui.hmi_export_window import HmiExportWindow



def _normalize_mapping(mapping: Mapping[Any, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in mapping.items():
        result[str(key)] = value
    return result


def _row_to_dict(row: Any) -> Dict[str, Any]:
    if is_dataclass(row) and not isinstance(row, type):
        data = {field.name: getattr(row, field.name) for field in fields(row)}
        return _normalize_mapping(data)
    if isinstance(row, Mapping):
        return _normalize_mapping(row)
    if hasattr(row, "__dict__"):
        return _normalize_mapping(vars(row))
    if isinstance(row, Iterable) and not isinstance(row, (str, bytes, bytearray)):
        try:
            return _normalize_mapping(dict(row))
        except Exception:
            return {}
    return {}

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

        app = QtWidgets.QApplication.instance()
        qt_app = app if isinstance(app, QtWidgets.QApplication) else None

        self._original_palette = QtGui.QPalette(qt_app.palette()) if qt_app else None

        self._original_style_sheet = qt_app.styleSheet() if qt_app else ""

        self._original_style_name = qt_app.style().objectName() if qt_app else None

        self._dark_mode = True

        self.chkDarkMode = QtWidgets.QCheckBox("Dark mode")
        self.chkDarkMode.setChecked(True)
        self.chkDarkMode.toggled.connect(self._on_theme_toggled)

        self.lblProfile = QtWidgets.QLabel("Profile: not set")
        self.profileIndicator = QtWidgets.QFrame()
        self.profileIndicator.setObjectName("profileIndicator")
        self.profileIndicator.setFixedSize(12, 12)
        self.profileIndicator.setStyleSheet(
            "QFrame#profileIndicator { border: 1px solid #404040; border-radius: 6px; background-color: #c0392b; }"
        )

        self.btnWizard = QtWidgets.QPushButton("Run DLL Wizard.")
        self.btnWizard.clicked.connect(self.on_wizard)

        self.btnAttach = QtWidgets.QPushButton("Attach to TIA V17.")
        self.btnAttach.clicked.connect(self.on_attach)

        self.plcList = QtWidgets.QListWidget()
        self.plcList.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.MultiSelection)

        self.chkComments = QtWidgets.QCheckBox("Include Comments")
        self.chkComments.setChecked(True)

        self.chkRetentive = QtWidgets.QCheckBox("Include Retentive")
        self.chkRetentive.setChecked(True)

        self.chkAddress = QtWidgets.QCheckBox("Include Address")
        self.chkAddress.setChecked(True)

        self.btnExport = QtWidgets.QPushButton("Export PLC Tags")
        self.btnExport.clicked.connect(self.on_export)

        self.cmbExportFormat = QtWidgets.QComboBox()
        self.cmbExportFormat.addItem("CSV (.csv)", "csv")
        self.cmbExportFormat.addItem("Excel (.xlsx)", "xlsx")
        self.cmbExportFormat.addItem("Google Sheets", "gsheet")
        self.cmbExportFormat.setCurrentIndex(0)

        export_row = QtWidgets.QHBoxLayout()
        export_row.addWidget(self.btnExport)
        export_row.addWidget(QtWidgets.QLabel("Format:"))
        export_row.addWidget(self.cmbExportFormat)
        export_row.addStretch(1)

        self.btnExportBlocks = QtWidgets.QPushButton("Export Program Blocks")
        self.btnExportBlocks.clicked.connect(self.on_export_blocks)

        self.cmbBlockFormat = QtWidgets.QComboBox()
        self.cmbBlockFormat.addItem("CSV (.csv)", "csv")
        self.cmbBlockFormat.addItem("Excel (.xlsx)", "xlsx")
        self.cmbBlockFormat.addItem("Google Sheets", "gsheet")
        self.cmbBlockFormat.setCurrentIndex(0)

        blocks_row = QtWidgets.QHBoxLayout()
        blocks_row.addWidget(self.btnExportBlocks)
        blocks_row.addWidget(QtWidgets.QLabel("Format:"))
        blocks_row.addWidget(self.cmbBlockFormat)
        blocks_row.addStretch(1)

        self.btnExportHmi = QtWidgets.QPushButton("Export HMI Information")
        self.btnExportHmi.clicked.connect(self.on_export_hmi)

        self.log = QtWidgets.QTextEdit()
        self.log.setReadOnly(True)

        layout.addWidget(self.chkDarkMode)

        profile_row = QtWidgets.QHBoxLayout()
        profile_row.addWidget(self.profileIndicator)
        profile_row.addSpacing(6)
        profile_row.addWidget(self.lblProfile)
        profile_row.addStretch(1)
        layout.addLayout(profile_row)

        layout.addWidget(self.btnWizard)
        layout.addWidget(self.btnAttach)
        layout.addWidget(self.plcList)
        layout.addWidget(self.chkComments)
        layout.addWidget(self.chkRetentive)
        layout.addWidget(self.chkAddress)

        layout.addLayout(export_row)
        layout.addLayout(blocks_row)
        layout.addWidget(self.btnExportHmi)
        layout.addWidget(self.log)

        self._apply_theme(True)
        self._session: TiaSession | None = None
        self._google_credentials_path: Path | None = None
        self._google_share_email: str = ""
        self._wizard_window = None
        self._hmi_window = None

        self.refresh_profile_label()

    def refresh_profile_label(self):

        prof = self.prof
        if prof and prof.public_api_dir:
            self.lblProfile.setText(f"Profile: V17 @ {prof.public_api_dir}")
            ready = True
        else:
            self.lblProfile.setText("Profile: not set")
            ready = False
        self._set_profile_indicator(ready)

    def _set_profile_indicator(self, ready: bool) -> None:
        color = "#27ae60" if ready else "#c0392b"
        base = "QFrame#profileIndicator { border: 1px solid #404040; border-radius: 6px; background-color: %s; }"
        self.profileIndicator.setStyleSheet(base % color)

    def _on_theme_toggled(self, checked: bool) -> None:
        self._apply_theme(checked)

    def _apply_theme(self, dark: bool) -> None:
        app = QtWidgets.QApplication.instance()
        if not isinstance(app, QtWidgets.QApplication):
            return
        self._dark_mode = dark
        if dark:
            QtWidgets.QApplication.setStyle("Fusion")
            palette = QtGui.QPalette()
            palette.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor(53, 53, 53))
            palette.setColor(QtGui.QPalette.ColorRole.WindowText, QtGui.QColorConstants.White)
            palette.setColor(QtGui.QPalette.ColorRole.Base, QtGui.QColor(35, 35, 35))
            palette.setColor(QtGui.QPalette.ColorRole.AlternateBase, QtGui.QColor(53, 53, 53))
            palette.setColor(QtGui.QPalette.ColorRole.ToolTipBase, QtGui.QColor(53, 53, 53))
            palette.setColor(QtGui.QPalette.ColorRole.ToolTipText, QtGui.QColorConstants.White)
            palette.setColor(QtGui.QPalette.ColorRole.Text, QtGui.QColorConstants.White)
            palette.setColor(QtGui.QPalette.ColorRole.Button, QtGui.QColor(53, 53, 53))
            palette.setColor(QtGui.QPalette.ColorRole.ButtonText, QtGui.QColorConstants.White)
            palette.setColor(QtGui.QPalette.ColorRole.BrightText, QtGui.QColorConstants.Red)
            palette.setColor(QtGui.QPalette.ColorRole.Link, QtGui.QColor(90, 160, 255))
            palette.setColor(QtGui.QPalette.ColorRole.Highlight, QtGui.QColor(42, 130, 218))
            palette.setColor(QtGui.QPalette.ColorRole.HighlightedText, QtGui.QColorConstants.Black)
            palette.setColor(
                QtGui.QPalette.ColorGroup.Disabled,
                QtGui.QPalette.ColorRole.Text,
                QtGui.QColor(120, 120, 120),
            )
            palette.setColor(
                QtGui.QPalette.ColorGroup.Disabled,
                QtGui.QPalette.ColorRole.ButtonText,
                QtGui.QColor(120, 120, 120),
            )
            app.setPalette(palette)
            app.setStyleSheet(
                "QToolTip { color: #ffffff; background-color: #2a82da; border: 1px solid #1e1e1e; }"
            )
        else:
            if self._original_style_name:
                QtWidgets.QApplication.setStyle(self._original_style_name)
            else:
                QtWidgets.QApplication.setStyle("Fusion")
            if self._original_palette is not None:
                app.setPalette(self._original_palette)
            else:
                app.setPalette(app.style().standardPalette())
            app.setStyleSheet(self._original_style_sheet or "")

    def on_wizard(self):

        if self._wizard_window is None:
            self._wizard_window = DllWizardWindow(self.store, self)
            self._wizard_window.profile_updated.connect(self._on_wizard_profile_updated)
            self._wizard_window.destroyed.connect(self._on_wizard_closed)
        self._wizard_window.show()
        self._wizard_window.raise_()
        self._wizard_window.activateWindow()

    def _on_wizard_profile_updated(self) -> None:
        self.prof = self.store.get_profile("V17")
        self.refresh_profile_label()

    def _on_wizard_closed(self) -> None:
        self._wizard_window = None

    def on_attach(self):

        # Revalidate profile just before attach

        if not self.prof or not self.prof.public_api_dir:

            # Try to reload in case it was saved while this window was open

            self.prof = self.store.get_profile("V17")

            if not self.prof or not self.prof.public_api_dir:

                QtWidgets.QMessageBox.warning(
                    self,
                    "Profile",
                    "Run the DLL Wizard first to select Siemens.Engineering.dll.",
                )

                return

        # Load CLR/Siemens.Engineering

        res = ensure_clr_and_load(
            Path(self.prof.public_api_dir) / "Siemens.Engineering.dll"
        )

        if not res.ok:

            QtWidgets.QMessageBox.critical(self, "CLR Load", res.message)

            return

        # TIA Session

        self._session = TiaSession()

        instances = self._session.list_instances()

        if not instances:

            QtWidgets.QMessageBox.information(
                self,
                "Attach",
                "No running TIA Portal instances found.\nStart TIA V17 with a project open, then retry.",
            )

            return

        items = [f"{i.index}: {i.description}" for i in instances]

        choice, ok = QtWidgets.QInputDialog.getItem(
            self, "Attach", "Select TIA instance:", items, 0, False
        )

        if not ok:

            return

        sel_index = int(choice.split(":")[0])

        try:

            self._session.attach(sel_index)

        except Exception as e:

            QtWidgets.QMessageBox.critical(self, "Attach", f"Failed to attach:\n{e}")

            return

        self.log.append(f"Attached. Project: {self._session.project_name}")
        if self._hmi_window:
            self._hmi_window.set_session(self._session)

        # Populate PLCs

        try:

            extr = TagExtractor(self._session)

            plcs = extr.list_plcs()

        except Exception as e:

            QtWidgets.QMessageBox.critical(
                self, "PLC Discovery", f"Failed to enumerate PLCs:\n{e}"
            )

            return

        self.plcList.clear()

        for p in plcs:

            self.plcList.addItem(p)

        if not plcs:

            self.log.append(
                "No PLCs exposing PlcSoftware/TagTableGroup were found in this project."
            )

    def on_export(self):

        if not self._session:
            QtWidgets.QMessageBox.warning(self, "Attach", "Attach to TIA first.")
            return

        selected = [i.text() for i in self.plcList.selectedItems()] or None
        extr = TagExtractor(self._session)
        rows = list(extr.extract_tags(selected))
        if not rows:
            QtWidgets.QMessageBox.information(
                self, "Export", "No tags found to export."
            )
            return

        fmt = self.cmbExportFormat.currentData()

        if fmt == "xlsx":
            out, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Save Excel", "PLC_Tags.xlsx", "Excel (*.xlsx)"
            )
            if not out:
                return
            out_path = Path(out)
            if out_path.suffix.lower() != ".xlsx":
                out_path = out_path.with_suffix(".xlsx")
            write_tags_xlsx(rows, out_path)
            message = f"Exported {len(rows)} rows to:\n{out_path}"
            self.log.append(f"Exported {len(rows)} rows -> {out_path}")
            QtWidgets.QMessageBox.information(self, "Done", message)
            return

        if fmt == "csv":
            out, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Save CSV", "PLC_Tags.csv", "CSV (*.csv)"
            )
            if not out:
                return
            out_path = Path(out)
            if out_path.suffix.lower() != ".csv":
                out_path = out_path.with_suffix(".csv")
            write_tags_csv(rows, out_path)
            message = f"Exported {len(rows)} rows to:\n{out_path}"
            self.log.append(f"Exported {len(rows)} rows -> {out_path}")
            QtWidgets.QMessageBox.information(self, "Done", message)
            return

        creds_path = self._google_credentials_path
        if not creds_path or not Path(creds_path).exists():
            picked, _ = QtWidgets.QFileDialog.getOpenFileName(
                self,
                "Google service account credentials",
                str(Path.home()),
                "JSON (*.json)",
            )
            if not picked:
                return
            creds_path = Path(picked)
            self._google_credentials_path = creds_path

        title, ok = QtWidgets.QInputDialog.getText(
            self, "Google Sheets", "Spreadsheet title:", text="PLC Tags"
        )
        if not ok or not title.strip():
            return
        share_email, ok = QtWidgets.QInputDialog.getText(
            self,
            "Google Sheets",
            "Share with email (optional):",
            text=self._google_share_email,
        )
        if not ok:
            return
        share_email = share_email.strip()
        self._google_share_email = share_email

        try:
            info = write_tags_google_sheets(
                rows, creds_path, title.strip(), share_with=share_email or None
            )
        except RuntimeError as err:
            QtWidgets.QMessageBox.critical(self, "Google Sheets", str(err))
            return
        except Exception as err:
            QtWidgets.QMessageBox.critical(
                self, "Google Sheets", f"Failed to export to Google Sheets:\\n{err}"
            )
            return

        url = info.get("url", "") if isinstance(info, dict) else ""
        message = (
            f"Exported {len(rows)} rows to Google Sheets:\n{url}"
            if url
            else f"Exported {len(rows)} rows to Google Sheets."
        )
        if not share_email:
            message += "\n(Note: spreadsheet remains owned by the service account.)"
        self.log.append(message)
        QtWidgets.QMessageBox.information(self, "Done", message)

    def on_export_hmi(self):
        if self._hmi_window is None:
            self._hmi_window = HmiExportWindow(self.store, self)
        session = self._session if self._session else None
        self._hmi_window.set_session(session)
        self._hmi_window.show()
        self._hmi_window.raise_()
        self._hmi_window.activateWindow()

    def on_export_blocks(self):
        if not self._session:
            QtWidgets.QMessageBox.warning(self, "Export Program Blocks", "Attach to TIA first.")
            return

        selected = [i.text() for i in self.plcList.selectedItems()] or None
        extractor = ProgramBlockExtractor(self._session)
        try:
            rows, sources = extractor.extract_blocks(selected)
        except Exception as err:
            QtWidgets.QMessageBox.critical(
                self,
                "Export Program Blocks",
                "Failed to gather program blocks:\n{}".format(err),
            )
            return

        if not rows:
            QtWidgets.QMessageBox.information(
                self, "Export Program Blocks", "No program blocks found to export."
            )
            return

        fmt = self.cmbBlockFormat.currentData()

        if fmt == "xlsx":
            out, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Save Program Blocks Excel", "PLC_Program_Blocks.xlsx", "Excel (*.xlsx)"
            )
            if not out:
                return
            out_path = Path(out)
            if out_path.suffix.lower() != ".xlsx":
                out_path = out_path.with_suffix(".xlsx")
            extras = self._write_block_sources(out_path, sources, rows)
            write_blocks_xlsx(rows, out_path)
            message = "Exported {} rows to:\n{}".format(len(rows), out_path)
            if extras:
                message += "\nSaved {} source files to {}".format(len(extras), extras[0].parent)
            self.log.append(f"Exported {len(rows)} program block rows -> {out_path}")
            if extras:
                self.log.append(f"Block sources -> {extras[0].parent}")
            QtWidgets.QMessageBox.information(self, "Done", message)
            return

        if fmt == "csv":
            out, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Save Program Blocks CSV", "PLC_Program_Blocks.csv", "CSV (*.csv)"
            )
            if not out:
                return
            out_path = Path(out)
            if out_path.suffix.lower() != ".csv":
                out_path = out_path.with_suffix(".csv")
            extras = self._write_block_sources(out_path, sources, rows)
            write_blocks_csv(rows, out_path)
            message = "Exported {} rows to:\n{}".format(len(rows), out_path)
            if extras:
                message += "\nSaved {} source files to {}".format(len(extras), extras[0].parent)
            self.log.append(f"Exported {len(rows)} program block rows -> {out_path}")
            if extras:
                self.log.append(f"Block sources -> {extras[0].parent}")
            QtWidgets.QMessageBox.information(self, "Done", message)
            return

        creds_path = self._google_credentials_path
        if not creds_path or not Path(creds_path).exists():
            picked, _ = QtWidgets.QFileDialog.getOpenFileName(
                self,
                "Google service account credentials",
                str(Path.home()),
                "JSON (*.json)",
            )
            if not picked:
                return
            creds_path = Path(picked)
            self._google_credentials_path = creds_path

        title, ok = QtWidgets.QInputDialog.getText(
            self, "Google Sheets", "Spreadsheet title:", text="PLC Program Blocks"
        )
        if not ok or not title.strip():
            return
        share_email, ok = QtWidgets.QInputDialog.getText(
            self,
            "Google Sheets",
            "Share with email (optional):",
            text=self._google_share_email,
        )
        if not ok:
            return
        share_email = share_email.strip()
        self._google_share_email = share_email

        prepared_rows = []
        for row in rows:
            data = _row_to_dict(row)
            if data.get("SourceReference"):
                data["SourceReference"] = "Not exported (Google Sheets)"
            prepared_rows.append(data)

        try:
            info = write_blocks_google_sheets(
                prepared_rows, creds_path, title.strip(), share_with=share_email or None
            )
        except RuntimeError as err:
            QtWidgets.QMessageBox.critical(self, "Google Sheets", str(err))
            return
        except Exception as err:
            QtWidgets.QMessageBox.critical(
                self, "Google Sheets", "Failed to export program blocks:\n{}".format(err)
            )
            return

        url = info.get("url", "") if isinstance(info, dict) else ""
        if url:
            message = "Exported {} rows to Google Sheets:\n{}".format(len(rows), url)
        else:
            message = "Exported {} rows to Google Sheets.".format(len(rows))
        if share_email:
            message += "\nShared with: {}".format(share_email)
        else:
            message += "\n(Note: spreadsheet remains owned by the service account.)"
        if sources:
            message += "\nSource files are only written when exporting to Excel/CSV."
        self.log.append(message)
        QtWidgets.QMessageBox.information(self, "Done", message)

    def _write_block_sources(self, out_path: Path, sources, rows):
        if not sources:
            return []
        out_path = Path(out_path)
        target_dir = out_path.parent / "{}_sources".format(out_path.stem)
        target_dir.mkdir(parents=True, exist_ok=True)
        written = []
        for source in sources:
            base_name = self._sanitize_source_filename(source.filename)
            final_name = self._ensure_unique_filename(target_dir, base_name)
            file_path = target_dir / final_name
            try:
                file_path.write_text(source.content, encoding="utf-8", errors="replace")
            except Exception:
                file_path.write_bytes(source.content.encode("utf-8", "replace"))
            rel = "{}/{}".format(target_dir.name, final_name)
            for row in rows:
                if getattr(row, "SourceReference", "") == source.filename:
                    row.SourceReference = rel
            written.append(file_path)
        return written

    def _ensure_unique_filename(self, directory: Path, name: str) -> str:
        candidate = directory / name
        if not candidate.exists():
            return name
        stem = candidate.stem
        suffix = candidate.suffix
        index = 1
        while True:
            attempt = directory / "{}_{}{}".format(stem, index, suffix)
            if not attempt.exists():
                return attempt.name
            index += 1

    def _sanitize_source_filename(self, name: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", name)
        cleaned = cleaned.strip("._")
        return cleaned or "program_block.src"


if __name__ == "__main__":
    import os
    from tia_tags_exporter.loader_multi import prepare_and_load
    from tia_tags_exporter.logging_utils import configure_logging

    configure_logging()
    store = ProfileStore(Path.home() / ".tia-tags-exporter")
    public_api_dir = None
    prof = store.get_profile("V17")
    if prof and getattr(prof, "public_api_dir", None):
        public_api_dir = str(prof.public_api_dir)
    try:
        diag = prepare_and_load(public_api_dir)
        os.environ["TIA_TAGS_EXPORTER_LOADER_READY"] = "1"
        if diag is not None:
            os.environ["TIA_TAGS_EXPORTER_LOADER_INFO"] = str(diag)
    except Exception:
        pass

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv or ["tia-tags-exporter"])
    window = MainWindow(store)
    window.show()
    sys.exit(app.exec())


