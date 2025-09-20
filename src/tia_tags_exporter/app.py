from __future__ import annotations

import os
from pathlib import Path

# -----------------------------------------------------------------------------
# PATCH-ID: TIAEXP-20250919-MULTIDIR-LOADER-V2
# Ensure TIA Openness multi-directory loader runs AFTER any from __future__ imports.
if os.environ.get("TIA_TAGS_EXPORTER_LOADER_READY") != "1":
    try:
        from tia_tags_exporter.config_store import ProfileStore as _BootProfileStore
        from tia_tags_exporter.loader_multi import prepare_and_load

        _pub = None
        try:
            _store = _BootProfileStore(Path.home() / ".tia-tags-exporter")
            _prof = _store.get_profile("V17")
            if _prof:
                _pub = _prof.get("public_api_dir") if hasattr(_prof, "get") else getattr(_prof, "public_api_dir", None)
        except Exception:
            _pub = None
        _diag = prepare_and_load(_pub)
        os.environ["TIA_TAGS_EXPORTER_LOADER_READY"] = "1"
        try:
            print(
                "TIAExporter loader ready:",
                {
                    "core": _diag.get("core_path") if isinstance(_diag, dict) else None,
                    "version": _diag.get("version") if isinstance(_diag, dict) else None,
                    "PATH_head": _diag.get("path_head") if isinstance(_diag, dict) else None,
                },
            )
        except Exception:
            pass
    except Exception:
        # Non-fatal: continue even if loader init fails; attach will then raise helpful diagnostics
        pass
# -----------------------------------------------------------------------------
import sys
from PySide6 import QtWidgets
from .logging_utils import configure_logging
from .config_store import ProfileStore
from .gui.main_window import MainWindow


def main():
    configure_logging()
    app = QtWidgets.QApplication(sys.argv)
    store = ProfileStore(Path.home()/'.tia-tags-exporter')
    w = MainWindow(store)
    w.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
