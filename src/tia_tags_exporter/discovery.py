from __future__ import annotations
import os
from pathlib import Path
from typing import Iterator, List, Optional

from .validation import Candidate, validate_candidate, REQUIRED_DLLS, CORE_DLL_NAME

KEYWORDS = ("siemens", "portal", "tia", "automation", "publicapi", "openness", "v17")
ALWAYS_ALLOW_NAMES = {
    "program files",
    "program files (x86)",
    "programdata",
    "siemens",
    "automation",
    "users",
    "public",
    "documents",
    "public documents",
    "portal",
    "tia portal",
    "tia-portal",
}
SKIP_DIR_NAMES = {
    "$recycle.bin",
    "system volume information",
    "msocache",
    "config.msi",
    "windows",
    "temp",
    "tmp",
    "appdata",
    "perflogs",
    "recovery",
}


def _path_key(path: Path) -> str:
    try:
        resolved = path.resolve()
    except Exception:
        resolved = path
    value = str(resolved).replace("\\", "/").lower()
    if value.endswith("/"):
        value = value.rstrip("/")
    return value


def _path_has_keyword(path: Path) -> bool:
    lowered = _path_key(path)
    return any(token in lowered for token in KEYWORDS)


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


def _should_descend(parent: Path, child_name: str) -> bool:
    lower = child_name.lower()
    if lower in SKIP_DIR_NAMES or lower.startswith("~"):
        return False
    candidate = parent / child_name
    try:
        if candidate.is_symlink():
            return False
    except OSError:
        return False
    if _path_has_keyword(candidate):
        return True
    if lower in ALWAYS_ALLOW_NAMES:
        return True
    if _path_has_keyword(parent):
        return True
    return False


def iter_dirs(root: Path) -> Iterator[Path]:
    """Yield directories under root while pruning obviously irrelevant branches."""
    for dirpath, dirnames, _ in os.walk(root, topdown=True, followlinks=False, onerror=lambda _: None):
        current = Path(dirpath)
        yield current
        dirnames[:] = [name for name in dirnames if _should_descend(current, name)]


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


def _candidate_roots(drive: Path) -> List[Path]:
    roots: dict[str, Path] = {}

    def add(path: Path) -> None:
        try:
            if not path.exists() or not path.is_dir():
                return
        except Exception:
            return
        key = _path_key(path)
        if not key:
            return
        for existing_key in list(roots.keys()):
            if key.startswith(existing_key + "/"):
                return
            if existing_key.startswith(key + "/"):
                roots.pop(existing_key, None)
        roots[key] = path

    base_guesses = [
        drive / "Program Files" / "Siemens",
        drive / "Program Files" / "Siemens" / "Automation",
        drive / "Program Files" / "Siemens" / "Automation" / "Portal V17",
        drive / "Program Files (x86)" / "Siemens",
        drive / "Program Files (x86)" / "Siemens" / "Automation",
        drive / "ProgramData" / "Siemens",
        drive / "ProgramData" / "Siemens" / "Automation",
        drive / "ProgramData" / "Siemens" / "Automation" / "Portal V17",
        drive / "Siemens",
        drive / "Portal V17",
        drive / "TIA Portal",
    ]
    for guess in base_guesses:
        add(guess)

    keyword_names = ("siemens", "portal", "tia", "automation", "publicapi", "openness")
    parent_candidates = [
        drive,
        drive / "Program Files",
        drive / "Program Files (x86)",
        drive / "ProgramData",
    ]
    for parent in parent_candidates:
        try:
            for child in parent.iterdir():
                try:
                    if not child.is_dir():
                        continue
                except Exception:
                    continue
                lower = child.name.lower()
                if any(token in lower for token in keyword_names):
                    add(child)
        except Exception:
            continue

    return [roots[key] for key in sorted(roots.keys())]


def discover_candidates(selected_drives: Optional[List[Path]] = None) -> Iterator[Candidate]:
    """Discover Siemens Openness DLL directories with lightweight pruning."""
    drives = selected_drives or fixed_drives()

    seen_dirs: set[str] = set()
    seen_core_files: set[str] = set()

    def _try_emit(folder: Path):
        folder_key = _path_key(folder)
        if not folder_key or folder_key in seen_dirs:
            return None

        found = _collect_required(folder)
        if not found:
            return None

        core_path = found.get(CORE_DLL_NAME)
        if core_path is not None:
            core_key = _path_key(core_path)
            if core_key and core_key in seen_core_files:
                return None
            if core_key:
                seen_core_files.add(core_key)

        seen_dirs.add(folder_key)

        cand = Candidate(
            folder=folder,
            engineering_dll=found.get("Siemens.Engineering.dll"),
            hmi_dll=found.get("Siemens.Engineering.Hmi.dll"),
            addin_dll=found.get("Siemens.Engineering.AddIn.dll"),
        )
        return validate_candidate(cand)

    guesses: List[Path] = []
    for drive in drives:
        guesses.extend([
            drive / "Program Files" / "Siemens" / "Automation" / "Portal V17" / "PublicAPI" / "V17",
            drive / "Program Files (x86)" / "Siemens" / "Automation" / "Portal V17" / "PublicAPI" / "V17",
            drive / "ProgramData" / "Siemens",
        ])

    for g in guesses:
        cand = _try_emit(g)
        if cand is not None:
            yield cand

    for drive in drives:
        roots = _candidate_roots(drive)
        if not roots:
            roots = [drive]
        for root in roots:
            for path in iter_dirs(root):
                cand = _try_emit(path)
                if cand is not None:
                    yield cand
