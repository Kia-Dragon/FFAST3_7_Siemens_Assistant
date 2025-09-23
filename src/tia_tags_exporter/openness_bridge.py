from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Optional
import sys


@dataclass
class ClrLoadResult:
    ok: bool
    message: str
    token: Optional[str] = None
    version: Optional[str] = None


_OPTIONAL_ASSEMBLIES = (
    "Siemens.Engineering.Contract",
    "Siemens.Engineering.HW",
    "Siemens.Engineering.HW.Features",
    "Siemens.Engineering.Hmi",
    "Siemens.Engineering.AddIn",
)


def _load_clr_module():
    try:
        return import_module("clr")
    except ImportError as exc:  # pragma: no cover - requires pythonnet runtime
        raise RuntimeError(f"pythonnet (clr) not available: {exc}") from exc


def _try_reflect(engineering_dll: Path, success_message: str) -> ClrLoadResult:
    try:
        system_reflection = import_module("System.Reflection")
    except ImportError as exc:  # pragma: no cover - runtime dependency
        return ClrLoadResult(False, f"System.Reflection not available: {exc}")

    assembly = getattr(system_reflection, "Assembly", None)
    if assembly is None:
        return ClrLoadResult(False, "System.Reflection.Assembly type not available")

    try:
        asm = assembly.LoadFrom(str(engineering_dll))
    except Exception as exc:  # pragma: no cover - relies on external DLL
        return ClrLoadResult(False, f"Reflection load failed: {exc}")

    name = asm.GetName()
    token_bytes = name.GetPublicKeyToken()
    token = "".join(f"{b:x}" for b in token_bytes) if token_bytes else None
    version = str(name.Version)
    return ClrLoadResult(True, success_message, token=token, version=version)


def ensure_clr_and_load(engineering_dll: Path) -> ClrLoadResult:
    """Load CLR via pythonnet and bind Siemens.Engineering from a specific folder."""
    try:
        clr = _load_clr_module()
    except RuntimeError as exc:
        return ClrLoadResult(False, str(exc))

    add_reference = getattr(clr, "AddReference", None)
    if not callable(add_reference):
        return ClrLoadResult(False, "pythonnet clr module does not expose AddReference")

    dll_dir = engineering_dll.parent
    dll_dir_str = str(dll_dir)

    def _needs_multi() -> bool:
        return any(not (dll_dir / f"{name}.dll").exists() for name in _OPTIONAL_ASSEMBLIES)

    def _load_optional_from_dir() -> list[str]:
        loaded: list[str] = []
        for name in _OPTIONAL_ASSEMBLIES:
            candidate = dll_dir / f"{name}.dll"
            if not candidate.exists():
                continue
            try:
                add_reference(str(candidate))
                loaded.append(name)
            except Exception:
                continue
        return loaded

    def _load_multi_folder() -> ClrLoadResult:
        try:
            from .loader_multi import prepare_and_load
        except Exception as err:  # pragma: no cover - loader import failure
            return ClrLoadResult(False, f"Multi-folder loader import failed: {err}")

        try:
            diag = prepare_and_load(dll_dir_str)
        except Exception as err:
            return ClrLoadResult(False, f"Multi-folder loader failed: {err}")

        if isinstance(diag, dict):
            prefetch_errors = diag.get("prefetch_errors") or {}
            relevant = {k: v for k, v in prefetch_errors.items() if k == "Siemens.Engineering" or k in _OPTIONAL_ASSEMBLIES}
            if relevant:
                detail = "; ".join(f"{key}: {value}" for key, value in sorted(relevant.items()))
                return ClrLoadResult(False, f"Multi-folder loader reported errors: {detail}")

        return _try_reflect(engineering_dll, "Loaded Siemens.Engineering (multi-folder)")

    def _load_direct(message: str) -> ClrLoadResult:
        if dll_dir_str not in sys.path:
            sys.path.insert(0, dll_dir_str)
        try:
            add_reference(str(engineering_dll))
        except Exception as exc:  # pragma: no cover - runtime failure
            return ClrLoadResult(False, f"AddReference failed: {exc}")
        return _try_reflect(engineering_dll, message)

    requires_multi = _needs_multi()
    multi_attempt = _load_multi_folder()
    if multi_attempt.ok:
        return multi_attempt

    multi_error = multi_attempt.message
    if requires_multi:
        return ClrLoadResult(False, multi_error)

    direct = _load_direct("Loaded Siemens.Engineering (direct fallback)")
    if direct.ok:
        loaded_optional = _load_optional_from_dir()
        missing = [name for name in _OPTIONAL_ASSEMBLIES if (dll_dir / f"{name}.dll").exists() and name not in loaded_optional]
        if missing:
            summary = ", ".join(sorted(missing))
            return ClrLoadResult(False, f"Failed to load dependent assemblies: {summary}; multi-folder loader also failed: {multi_error}")
        if multi_error:
            return ClrLoadResult(True, f"{direct.message} (multi-folder resolver unavailable: {multi_error})", token=direct.token, version=direct.version)
        return direct

    return ClrLoadResult(False, f"Multi-folder loader failed ({multi_error}); direct fallback failed: {direct.message}")
