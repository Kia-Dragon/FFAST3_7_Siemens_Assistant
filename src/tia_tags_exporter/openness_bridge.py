from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import sys

@dataclass
class ClrLoadResult:
    ok: bool
    message: str
    token: Optional[str] = None
    version: Optional[str] = None


def ensure_clr_and_load(engineering_dll: Path) -> ClrLoadResult:
    """Load CLR via pythonnet and bind Siemens.Engineering from a specific folder."""
    try:
        import clr  # type: ignore
    except ImportError as e:
        return ClrLoadResult(False, f"pythonnet (clr) not available: {e}")

    dll_dir = engineering_dll.parent
    dll_dir_str = str(dll_dir)

    def _reflect(prefix: str) -> ClrLoadResult:
        try:
            from System.Reflection import Assembly
            asm = Assembly.LoadFrom(str(engineering_dll))
            name = asm.GetName()
            token_bytes = name.GetPublicKeyToken()
            token = ''.join([f"{b:x}" for b in token_bytes]) if token_bytes else None
            ver = str(name.Version)
            return ClrLoadResult(True, prefix, token=token, version=ver)
        except Exception as ref_err:
            return ClrLoadResult(False, f"{prefix} but reflection failed: {ref_err}")

    def _needs_multi() -> bool:
        required = ["Siemens.Engineering.Hmi.dll", "Siemens.Engineering.AddIn.dll"]
        return any(not (dll_dir / name).exists() for name in required)

    def _load_multi_folder() -> ClrLoadResult:
        try:
            from .loader_multi import prepare_and_load
            prepare_and_load(dll_dir_str)
            return _reflect("Loaded Siemens.Engineering (multi-folder)")
        except Exception as err:
            return ClrLoadResult(False, f"Multi-folder loader failed: {err}")

    # Decide strategy: direct first if dependencies sit beside core DLL, otherwise multi-folder first.
    if not _needs_multi():
        if dll_dir_str not in sys.path:
            sys.path.insert(0, dll_dir_str)
        try:
            clr.AddReference(str(engineering_dll))
        except Exception as direct_err:
            multi_attempt = _load_multi_folder()
            if multi_attempt.ok:
                return multi_attempt
            return ClrLoadResult(False, f"Failed to AddReference to {engineering_dll}: {direct_err} (multi-folder fallback: {multi_attempt.message})")
        return _reflect("Loaded Siemens.Engineering")

    # Multi-folder required
    multi_attempt = _load_multi_folder()
    if multi_attempt.ok:
        return multi_attempt

    # Multi-folder failed; fall back to direct load as last resort
    if dll_dir_str not in sys.path:
        sys.path.insert(0, dll_dir_str)
    try:
        clr.AddReference(str(engineering_dll))
    except Exception as direct_err:
        return ClrLoadResult(False, f"Multi-folder loader failed ({multi_attempt.message}); direct AddReference also failed: {direct_err}")

    return _reflect("Loaded Siemens.Engineering (direct fallback)")
