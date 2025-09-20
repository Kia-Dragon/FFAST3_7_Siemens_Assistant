"""
Boot-first entry point that prepares TIA Openness resolution before launching the app.

PATCH-ID: TIAEXP-20250919-BOOTFIRST-MULTIDIR
"""
from __future__ import annotations

import os
from pathlib import Path

# Run loader BEFORE importing anything that might touch Siemens.Engineering
try:
    from tia_tags_exporter.config_store import ProfileStore
    from tia_tags_exporter.loader_multi import prepare_and_load

    _pub = None
    try:
        store_root = Path.home() / ".tia-tags-exporter"
        _store = ProfileStore(store_root)
        _prof = _store.get_profile("V17")
        if _prof:
            _pub = _prof.get("public_api_dir") if hasattr(_prof, "get") else getattr(_prof, "public_api_dir", None)
    except Exception:
        _pub = None

    _diag = prepare_and_load(_pub)
    os.environ["TIA_TAGS_EXPORTER_LOADER_READY"] = "1"
    if _diag is not None:
        os.environ["TIA_TAGS_EXPORTER_LOADER_INFO"] = str(_diag)
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
except Exception as _e:
    # Non-fatal: app import may still provide diagnostics later
    pass

# Now run the original app module EXACTLY as if launched with -m tia_tags_exporter.app
import runpy
runpy.run_module("tia_tags_exporter.app", run_name="__main__")
