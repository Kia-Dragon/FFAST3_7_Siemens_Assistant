from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import subprocess
import time

REQUIRED_DLLS = [
    "Siemens.Engineering.dll",
    "Siemens.Engineering.Hmi.dll",
    "Siemens.Engineering.AddIn.dll",
]
CORE_DLL_NAME = REQUIRED_DLLS[0]


def get_file_version_win(path: Path) -> Optional[str]:
    """Read PE FileVersion on Windows via PowerShell (no extra deps)."""
    try:
        ps = [
            "powershell", "-NoProfile", "-Command",
            f"(Get-Item '{path.as_posix()}').VersionInfo.FileVersion"
        ]
        out = subprocess.check_output(ps, text=True).strip()
        return out or None
    except Exception:
        return None


def assess_quality(dll_path: Path) -> str:
    """
    exact      -> path contains both 'publicapi' and any segment containing 'v17', ends with Siemens.Engineering.dll
    v17-path   -> any segment contains 'v17' (case-insensitive), regardless of 'publicapi'
    good       -> path contains 'publicapi' but no 'v17'
    heuristic  -> filename match only
    """
    parts = [p.lower() for p in dll_path.parts]
    has_publicapi = any("publicapi" in seg for seg in parts)
    has_v17 = any("v17" in seg for seg in parts)
    ends_correctly = parts[-1] == "siemens.engineering.dll"

    if has_publicapi and has_v17 and ends_correctly:
        return "exact"
    if has_v17:
        return "v17-path"
    if has_publicapi:
        return "good"
    return "heuristic"


@dataclass
class Candidate:
    folder: Path
    engineering_dll: Optional[Path] = None
    hmi_dll: Optional[Path] = None
    addin_dll: Optional[Path] = None
    version: Optional[str] = None
    token: Optional[str] = None
    is_valid: bool = False
    reason: Optional[str] = None
    quality: str = "heuristic"  # "exact" | "v17-path" | "good" | "heuristic"
    last_write: Optional[str] = None
    missing: list[str] = field(default_factory=list)


def validate_candidate(c: Candidate) -> Candidate:
    """All three Siemens Openness DLLs must be present for a valid candidate."""
    missing: list[str] = []

    core = c.engineering_dll if c.engineering_dll and c.engineering_dll.exists() else None
    hmi = c.hmi_dll if c.hmi_dll and c.hmi_dll.exists() else None
    addin = c.addin_dll if c.addin_dll and c.addin_dll.exists() else None

    if core is None:
        missing.append("Siemens.Engineering.dll")
    if hmi is None:
        missing.append("Siemens.Engineering.Hmi.dll")
    if addin is None:
        missing.append("Siemens.Engineering.AddIn.dll")

    c.missing = missing

    if core is not None:
        c.version = get_file_version_win(core)
        c.quality = assess_quality(core)
        try:
            ts = core.stat().st_mtime
            c.last_write = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))
        except Exception:
            c.last_write = None
    else:
        c.version = None
        c.quality = "heuristic"
        c.last_write = None

    if missing:
        c.is_valid = False
        c.reason = "Missing: " + ", ".join(missing)
        return c

    c.is_valid = True
    c.reason = None
    return c
