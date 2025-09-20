
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import os
import sys

@dataclass
class ClrLoadResult:
    ok: bool
    message: str
    token: Optional[str] = None
    version: Optional[str] = None


def ensure_clr_and_load(engineering_dll: Path) -> ClrLoadResult:
    """Load CLR via pythonnet and bind Siemens.Engineering from a specific folder.
    Returns token/version after reflection for validation.
    """
    try:
        import clr  # type: ignore
    except ImportError as e:
        return ClrLoadResult(False, f"pythonnet (clr) not available: {e}")

    # Prepend DLL directory so dependent assemblies resolve
    dll_dir = str(engineering_dll.parent)
    if dll_dir not in sys.path:
        sys.path.insert(0, dll_dir)

    try:
        clr.AddReference(str(engineering_dll))
    except Exception as e:
        return ClrLoadResult(False, f"Failed to AddReference to {engineering_dll}: {e}")

    try:
        from System.Reflection import Assembly
        asm = Assembly.LoadFrom(str(engineering_dll))
        name = asm.GetName()
        token_bytes = name.GetPublicKeyToken()
        token = ''.join([f"{b:x}" for b in token_bytes]) if token_bytes else None
        ver = str(name.Version)
        return ClrLoadResult(True, "Loaded Siemens.Engineering", token=token, version=ver)
    except Exception as e:
        return ClrLoadResult(False, f"Loaded but reflection failed: {e}")
