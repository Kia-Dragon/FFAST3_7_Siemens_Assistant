from __future__ import annotations
import os
from pathlib import Path
from typing import Iterator, List, Optional
from .validation import Candidate, validate_candidate, REQUIRED_DLLS, CORE_DLL_NAME


def fixed_drives() -> List[Path]:
    """Return absolute root paths for fixed drives (e.g., C:\\, D:\\)."""
    letters = [f"{chr(c)}:" for c in range(ord("C"), ord("Z") + 1)]
    roots: List[Path] = []
    for d in letters:
        p = Path(f"{d}\\")  # literal root backslash
        if p.exists():
            try:
                if os.path.ismount(p):
                    roots.append(p)
            except Exception:
                roots.append(p)
    return roots


def iter_dirs(root: Path) -> Iterator[Path]:
    """Yield all directories under root (full depth, no pruning)."""
    for dirpath, _, _ in os.walk(root, topdown=True):
        yield Path(dirpath)


def _collect_required(folder: Path) -> dict[str, Path]:
    found: dict[str, Path] = {}
    if not folder.exists() or not folder.is_dir():
        return found
    for name in REQUIRED_DLLS:
        candidate = folder / name
        try:
            if candidate.exists():
                found[name] = candidate
        except Exception:
            continue
    return found


def discover_candidates(selected_drives: Optional[List[Path]] = None) -> Iterator[Candidate]:
    """
    Full-depth discovery on selected drives:
      1) Probe common Siemens roots first (fast path).
      2) Exhaustive full-depth scan on the same drives.
    Yields validated Candidate objects (V17-only).
    """
    drives = selected_drives or fixed_drives()

    seen_dirs: set[str] = set()
    seen_core_files: set[str] = set()

    def _try_emit(folder: Path):
        try:
            folder_key = str(folder.resolve()).lower()
        except Exception:
            folder_key = str(folder).lower()
        if folder_key in seen_dirs:
            return None

        found = _collect_required(folder)
        if not found:
            return None

        core_path = found.get(CORE_DLL_NAME)
        if core_path is not None:
            try:
                core_key = str(core_path.resolve()).lower()
            except Exception:
                core_key = str(core_path).lower()
            if core_key in seen_core_files:
                return None
            seen_core_files.add(core_key)

        seen_dirs.add(folder_key)

        cand = Candidate(
            folder=folder,
            engineering_dll=found.get("Siemens.Engineering.dll"),
            hmi_dll=found.get("Siemens.Engineering.Hmi.dll"),
            addin_dll=found.get("Siemens.Engineering.AddIn.dll"),
        )
        return validate_candidate(cand)

    # 1) Fast path probes under each drive
    guesses: List[Path] = []
    for drive in drives:
        guesses.extend([
            drive / "Program Files" / "Siemens" / "Automation" / "Portal V17" / "PublicAPI" / "V17",
            drive / "Program Files (x86)" / "Siemens" / "Automation" / "Portal V17" / "PublicAPI" / "V17",
            drive / "ProgramData" / "Siemens"
        ])

    for g in guesses:
        cand = _try_emit(g)
        if cand is not None:
            yield cand

    # 2) Full-depth scan
    for drive in drives:
        for p in iter_dirs(drive):
            cand = _try_emit(p)
            if cand is not None:
                yield cand

