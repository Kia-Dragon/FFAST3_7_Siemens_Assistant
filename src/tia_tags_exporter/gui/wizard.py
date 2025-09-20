from __future__ import annotations
from PySide6 import QtCore, QtWidgets
from pathlib import Path
from typing import List, Optional

from ..discovery import discover_candidates, fixed_drives
from ..validation import Candidate, REQUIRED_DLLS, validate_candidate, assess_quality
from ..config_store import ProfileStore
from ..settings import DllProfile
from ..openness_bridge import ensure_clr_and_load

SUPPORT_URL = "https://support.industry.siemens.com/cs/document/109815895/tia-portal-openness-referencing-the-siemens-engineering-dlls-and-assembly-resolve?dti=0&lc=en-WW"

class DiscoveryWorker(QtCore.QThread):
    progress = QtCore.Signal(str)
    found = QtCore.Signal(object)
    finished = QtCore.Signal()

    def __init__(self, selected_drives: List[Path], parent=None):
        super().__init__(parent)
        self.selected_drives = selected_drives
        self._abort = False
        self.found_global = {name: set() for name in REQUIRED_DLLS}

    def run(self):

        # Full-depth candidate enumeration

        try:

            for cand in discover_candidates(self.selected_drives):

                self._record_found(cand)

                if self._abort:

                    break

                core_display = cand.engineering_dll if cand.engineering_dll else "<missing core DLL>"

                self.progress.emit(
                    f"Evaluated {cand.folder} | core={core_display} | valid={cand.is_valid} | reason={cand.reason}"
                )

                self.found.emit(cand)

        finally:

            # Always emit once when scanning has fully ended (or aborted)

            self.finished.emit()

    def _record_found(self, cand: Candidate) -> None:
        mapping = (
            ("Siemens.Engineering.dll", cand.engineering_dll),
            ("Siemens.Engineering.Hmi.dll", cand.hmi_dll),
            ("Siemens.Engineering.AddIn.dll", cand.addin_dll),
        )
        for name, item in mapping:
            if item:
                try:
                    resolved = str(item.resolve())
                except Exception:
                    resolved = str(item)
                self.found_global[name].add(resolved)

    def abort(self):
        self._abort = True


def _score_candidate(c: Candidate) -> int:
    """Scoring for auto-pick/preselect."""
    base = {"exact": 100, "v17-path": 75, "good": 50, "heuristic": 25}.get(c.quality or "heuristic", 25)
    p = str(c.folder).lower().replace("/", "\\")
    bonus = 0
    if p.endswith("\\publicapi\\v17"):
        bonus += 15
    if "portal v17" in p:
        bonus += 10
    if "publicapi" in p:
        bonus += 5
    if "automation" in p and "portal" in p:
        bonus += 5
    if c.token:
        bonus += 3
    if c.version:
        bonus += 1
    return base + bonus


class DllWizard(QtWidgets.QDialog):
    """
    Improvements:
      - Indeterminate progress bar + heartbeat dots during scanning.
      - Columns are draggable; 'Fit Columns' button.
      - Auto-save selection on: auto-pick, Select Highlighted, row double-click, or Close with a valid row highlighted.
      - Main results table shows full details; chooser pre-selects best.
    """

    def __init__(self, store: ProfileStore, parent=None):
        super().__init__(parent)
        self.setWindowTitle("DLL Discovery & Configuration Wizard (V17)")
        self.resize(1200, 760)
        self.store = store

        # --- Drives selection ---
        self.driveGroup = QtWidgets.QGroupBox("Select drives to scan (full depth):")
        driveLayout = QtWidgets.QHBoxLayout(self.driveGroup)
        self.driveChecks: List[QtWidgets.QCheckBox] = []
        for d in fixed_drives():
            cb = QtWidgets.QCheckBox(str(d))
            cb.setChecked(True)
            self.driveChecks.append(cb)
            driveLayout.addWidget(cb)
        driveLayout.addStretch(1)

        # --- Busy indicators ---
        busyRow = QtWidgets.QHBoxLayout()
        self.prog = QtWidgets.QProgressBar()
        self.prog.setTextVisible(False)
        self.prog.setRange(0, 1)  # idle state
        self.heartbeat = QtWidgets.QLabel("")  # animated dots while scanning
        busyRow.addWidget(self.prog, 3)
        busyRow.addWidget(self.heartbeat, 1)

        # Heartbeat timer
        self._hb_timer = QtCore.QTimer(self)
        self._hb_timer.setInterval(300)
        self._hb_state = 0
        self._hb_timer.timeout.connect(self._tick_heartbeat)

        # --- Results table ---
        self.table = QtWidgets.QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Folder (full path)", "FileVersion", "Token", "Quality", "LastWrite", "Valid"]
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)  # draggable columns
        header.setStretchLastSection(False)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        # Double-click = save & close
        self.table.itemDoubleClicked.connect(self._save_current_and_close)

        # --- Buttons & status ---
        self.btnScan   = QtWidgets.QPushButton("Rescan")
        self.btnAbort  = QtWidgets.QPushButton("Abort")
        self.btnSelect = QtWidgets.QPushButton("Select Highlighted")
        self.btnFit    = QtWidgets.QPushButton("Fit Columns")
        self.btnClose  = QtWidgets.QPushButton("Close")

        self.btnScan.clicked.connect(self.on_scan)
        self.btnAbort.clicked.connect(self.on_abort)
        self.btnSelect.clicked.connect(self.on_select)
        self.btnFit.clicked.connect(self.on_fit_columns)
        self.btnClose.clicked.connect(self.close)

        self.status = QtWidgets.QLabel("Profile: not saved")

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.driveGroup)
        layout.addLayout(busyRow)
        layout.addWidget(self.table)
        layout.addWidget(self.status)
        row = QtWidgets.QHBoxLayout()
        for b in (self.btnScan, self.btnAbort, self.btnSelect, self.btnFit, self.btnClose):
            row.addWidget(b)
        layout.addLayout(row)

        # State
        self.worker: Optional[DiscoveryWorker] = None
        self.candidates: List[Candidate] = []
        self.valid_candidates: List[Candidate] = []
        self.found_dlls: dict[str, List[str]] = {name: [] for name in REQUIRED_DLLS}
        self._profile_saved = False

        # Auto-start after the dialog is shown
        QtCore.QTimer.singleShot(0, self.on_scan)


    # ---- Busy/heartbeat ----

    def _tick_heartbeat(self):
        dots = "." * (1 + (self._hb_state % 3))
        self._hb_state += 1
        self.heartbeat.setText(f"Scanning{dots}")

    def _busy(self, on: bool):
        if on:
            self.prog.setRange(0, 0)  # indeterminate
            self._hb_state = 0
            self._hb_timer.start()
        else:
            self.prog.setRange(0, 1)  # idle
            self.heartbeat.clear()
            self._hb_timer.stop()

    # ---- Actions ----

    def _selected_drives(self) -> List[Path]:
        sel = [Path(cb.text()) for cb in self.driveChecks if cb.isChecked()]
        if not sel:
            QtWidgets.QMessageBox.warning(self, "Drives", "Select at least one drive to scan.")
        return sel

    def on_scan(self):
        drives = self._selected_drives()
        if not drives:
            return

        if self.worker:
            self.worker.abort()
            self.worker.wait(100)

        self.candidates.clear()
        self.valid_candidates.clear()
        self.found_dlls = {name: [] for name in REQUIRED_DLLS}
        self.table.setRowCount(0)
        self.status.setText("Profile: not saved")
        self._profile_saved = False
        self._busy(True)

        self.worker = DiscoveryWorker(drives)
        self.worker.progress.connect(lambda msg: None)  # logs are optional now
        self.worker.found.connect(self.on_found)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def on_abort(self):

        if self.worker: 
            self.worker.abort() 
            self.worker.wait(2000)
        self._busy(False) 
    def on_fit_columns(self):
        self.table.resizeColumnsToContents()

    def _save_profile(self, cand: Candidate):
        """Persist without closing the dialog."""
        token = cand.token
        if not token:
            res = ensure_clr_and_load(cand.engineering_dll)
            token = res.token if res.ok else None

        prof = DllProfile(
            tia_version="V17",
            public_api_dir=cand.folder,
            file_version=cand.version,
            public_key_token=token,
        )
        self.store.set_profile(prof)
        self._profile_saved = True
        self.status.setText(f"Profile saved: {cand.folder}")

    def _save_current_and_close(self, *_):
        cand = self._current_valid_candidate()
        if cand:
            self._save_profile(cand)
            self.accept()

    def on_select(self):

        cand = self._current_valid_candidate()

        if not cand:

            r = self.table.currentRow()

            if r >= 0:

                item0 = self.table.item(r, 0)

                if item0 is not None:

                    cand = item0.data(QtCore.Qt.UserRole)

        if not cand:

            QtWidgets.QMessageBox.warning(self, "Select", "Select a valid candidate row first.")

            return

        # Save & close

        _ = self._save_profile(cand)

        self.accept()

    def _current_valid_candidate(self) -> Optional[Candidate]:
        r = self.table.currentRow()
        if r < 0:
            return None
        folder = Path(self.table.item(r, 0).text())
        cand = next((c for c in self.valid_candidates if str(c.folder) == str(folder)), None)
        return cand

    def on_found(self, cand: Candidate):

        # Fetch token via reflection (best-effort) for display & scoring

        token = ""

        if cand.is_valid:

            res = ensure_clr_and_load(cand.engineering_dll)

            if res.ok:

                token = res.token or ""

            cand.token = token


        r = self.table.rowCount()

        self.table.insertRow(r)


        # Column 0: folder (bind Candidate on UserRole for reliable selection)

        item0 = QtWidgets.QTableWidgetItem(str(cand.folder))

        item0.setData(QtCore.Qt.UserRole, cand)

        self.table.setItem(r, 0, item0)


        # Other columns

        self.table.setItem(r, 1, QtWidgets.QTableWidgetItem(cand.version or ""))

        self.table.setItem(r, 2, QtWidgets.QTableWidgetItem(token))

        self.table.setItem(r, 3, QtWidgets.QTableWidgetItem(cand.quality))

        self.table.setItem(r, 4, QtWidgets.QTableWidgetItem(cand.last_write or ""))

        if cand.is_valid:
            valid_text = "Yes" if not cand.note else f"Yes ({cand.note})"
        else:
            valid_text = f"No ({cand.reason})"
        self.table.setItem(r, 5, QtWidgets.QTableWidgetItem(valid_text))


        self.candidates.append(cand)

        if cand.is_valid:

            self.valid_candidates.append(cand)
    def on_finished(self):
        self._busy(False)

        if self.worker is not None:
            self.found_dlls = {
                name: sorted(self.worker.found_global.get(name, set()))
                for name in REQUIRED_DLLS
            }
        else:
            self.found_dlls = {name: [] for name in REQUIRED_DLLS}

        self.worker = None

        if not self.valid_candidates:
            multi = self._build_multidir_candidate()
            if multi:
                self.on_found(multi)
                row = self.table.rowCount() - 1
                if row >= 0:
                    self.table.selectRow(row)
                    item = self.table.item(row, 0)
                    if item is not None:
                        self.table.scrollToItem(item, QtWidgets.QAbstractItemView.PositionAtCenter)
            else:
                self._show_missing_summary()
                return

        # Rank all valid candidates
        ranked = sorted(
            self.valid_candidates,
            key=lambda c: (_score_candidate(c), c.last_write or "", str(c.folder)),
            reverse=True
        )

        best = ranked[0]
        best_score = _score_candidate(best)
        second_score = _score_candidate(ranked[1]) if len(ranked) > 1 else -1

        # Auto-save only if unambiguous best; keep dialog open for visibility
        if len(ranked) == 1 or best_score > second_score:
            self._save_profile(best)
            # Do not auto-close; user may want to review. They can just press Close now.

        # Else: keep results; user can double-click row or use Select Highlighted

    def _portal_root(self, path: Path) -> Path:
        parts = list(path.parts)
        lowers = [p.lower() for p in parts]
        for i in range(len(parts) - 1, -1, -1):
            if 'portal' in lowers[i]:
                try:
                    return Path(*parts[: i + 1])
                except TypeError:
                    break
        return path.parent

    def _score_path_option(self, dll_name: str, path: Path, preferred_root: Path | None) -> tuple[int, float]:
        lower = str(path).replace('\\', '/').lower()
        score = 0
        if preferred_root and self._portal_root(path) == preferred_root:
            score += 9
        if 'portal' in lower:
            score += 7
        if 'publicapi' in lower:
            score += 6
        if 'v17' in lower:
            score += 10
        elif 'v16' in lower:
            score += 6
        elif 'v15' in lower:
            score += 3
        if dll_name.lower().endswith('engineering.dll'):
            qual = assess_quality(path)
            score += {'exact': 20, 'v17-path': 12, 'good': 6}.get(qual, 0)
        if dll_name.lower().endswith('addin.dll') and 'addin' in lower:
            score += 2
        if dll_name.lower().endswith('hmi.dll') and 'hmi' in lower:
            score += 2
        try:
            mtime = path.stat().st_mtime
        except Exception:
            mtime = 0.0
        return score, mtime

    def _build_multidir_candidate(self) -> Candidate | None:
        if not getattr(self, 'found_dlls', None):
            return None
        resolved: dict[str, list[Path]] = {}
        for name in REQUIRED_DLLS:
            entries = [Path(p) for p in self.found_dlls.get(name, [])]
            entries = [p for p in entries if p.exists()]
            if not entries:
                return None
            resolved[name] = entries

        def pick(paths: list[Path], name: str, root_hint: Path | None) -> Path:
            scored = sorted(paths, key=lambda p: self._score_path_option(name, p, root_hint))
            return scored[-1]

        eng_paths = resolved.get('Siemens.Engineering.dll')
        if not eng_paths:
            return None
        best_eng = pick(eng_paths, 'Siemens.Engineering.dll', None)
        root_hint = self._portal_root(best_eng)
        best_hmi = pick(resolved['Siemens.Engineering.Hmi.dll'], 'Siemens.Engineering.Hmi.dll', root_hint)
        best_addin = pick(resolved['Siemens.Engineering.AddIn.dll'], 'Siemens.Engineering.AddIn.dll', root_hint)

        cand = Candidate(
            folder=best_eng.parent,
            engineering_dll=best_eng,
            hmi_dll=best_hmi,
            addin_dll=best_addin,
            note='multi-folder (auto)'
        )
        cand = validate_candidate(cand)
        if not cand.is_valid:
            return None
        cand.quality = f"{cand.quality}+multi" if cand.quality else 'multi'
        return cand

    def _show_missing_summary(self) -> None:
        missing = [name for name in REQUIRED_DLLS if not self.found_dlls.get(name)]
        if missing:
            header = "DLL Wizard must abort: the required Siemens Openness DLLs were not all located."
        else:
            header = (
                "DLL Wizard must abort: the Siemens Openness DLLs were located but not in a single directory."
            )
        lines: List[str] = []
        for name in REQUIRED_DLLS:
            paths = self.found_dlls.get(name, [])
            if paths:
                first = paths[0]
                extra = f" (+{len(paths) - 1} more)" if len(paths) > 1 else ""
                lines.append(f"{name}: FOUND at {first}{extra}")
            else:
                lines.append(f"{name}: MISSING")
        summary = "\n".join(lines)
        message = (
            f"{header}\n\n{summary}\n\n"
            f"See Siemens support article for guidance:\n{SUPPORT_URL}"
        )
        QtWidgets.QMessageBox.critical(self, "Discovery", message)
        self.status.setText("Profile: not saved")
        self._profile_saved = False

    # ---- Close behavior ----

    def closeEvent(self, event):
        # If user closes without having saved, but a valid row is selected, save it now.
        if not self._profile_saved:
            cand = self._current_valid_candidate()
            if cand:
                self._save_profile(cand)
        super().closeEvent(event)




