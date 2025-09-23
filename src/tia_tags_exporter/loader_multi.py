"""
Multi-directory loader for Siemens TIA Openness - trims to only the assemblies we actually use.

PATCH-ID: TIAEXP-20250919-MULTIDIR-PRELOAD-ALL
"""

from __future__ import annotations

import os
from importlib import import_module
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, Iterable, Tuple

_CLR_MODULE: ModuleType | None = None
_SYSTEM_TYPES: Tuple[Any, Any] | None = None
_REFLECTION_TYPES: Tuple[Any, Any] | None = None

_TIAEXP_RESOLVE_INSTALLED = False
_RESOLVE_STATE: Dict[str, Dict[Tuple[str, str], str]] = {"asm_index": {}}

_CULTURES = (
    "en-US", "de-DE", "fr-FR", "es-ES", "it-IT", "pt-BR", "ru-RU", "pl-PL",
    "cs-CZ", "zh-CN", "ja-JP", "tr-TR", "ko-KR",
)


def _load_clr_module() -> ModuleType:
    global _CLR_MODULE
    if _CLR_MODULE is None:
        try:
            _CLR_MODULE = import_module("clr")
        except ImportError as exc:  # pragma: no cover - requires pythonnet runtime
            raise RuntimeError(f"pythonnet (clr) not available: {exc}") from exc
    return _CLR_MODULE


def _get_add_reference():
    clr_module = _load_clr_module()
    add_reference = getattr(clr_module, "AddReference", None)
    if not callable(add_reference):
        raise RuntimeError("pythonnet clr module does not expose AddReference")
    return add_reference


def _load_system_types() -> Tuple[Any, Any]:
    global _SYSTEM_TYPES
    if _SYSTEM_TYPES is None:
        try:
            system = import_module("System")
        except ImportError as exc:  # pragma: no cover - requires CLR runtime
            raise RuntimeError(f"System namespace not available: {exc}") from exc
        app_domain = getattr(system, "AppDomain", None)
        resolve_handler = getattr(system, "ResolveEventHandler", None)
        if app_domain is None or resolve_handler is None:
            raise RuntimeError("System.AppDomain or ResolveEventHandler not available")
        _SYSTEM_TYPES = (app_domain, resolve_handler)
    return _SYSTEM_TYPES


def _load_reflection_types() -> Tuple[Any, Any]:
    global _REFLECTION_TYPES
    if _REFLECTION_TYPES is None:
        try:
            reflection = import_module("System.Reflection")
        except ImportError as exc:  # pragma: no cover - requires CLR runtime
            raise RuntimeError(f"System.Reflection not available: {exc}") from exc
        assembly = getattr(reflection, "Assembly", None)
        assembly_name = getattr(reflection, "AssemblyName", None)
        if assembly is None or assembly_name is None:
            raise RuntimeError("System.Reflection Assembly types not available")
        _REFLECTION_TYPES = (assembly, assembly_name)
    return _REFLECTION_TYPES


def _dedupe_dirs(cands: Iterable[str]) -> list[str]:
    seen = set()
    out: list[str] = []
    for d in cands:
        if not d:
            continue
        try:
            p = Path(d)
            if not p.exists():
                continue
            key = str(p.resolve()).lower()
            if key not in seen:
                seen.add(key)
                out.append(str(p.resolve()))
        except Exception:
            continue
    return out


def _default_public_api_v17() -> str:
    pf = os.environ.get("ProgramW6432") or os.environ.get("ProgramFiles") or r"C:\\Program Files"
    return str(Path(pf) / "Siemens" / "Automation" / "Portal V17" / "PublicAPI" / "V17")


def _discover_dirs(public_api_dir: str | None) -> list[str]:
    pad = Path(public_api_dir) if public_api_dir else Path(_default_public_api_v17())
    public_dir = pad if pad.is_dir() else pad.parent
    public_root = public_dir.parent if public_dir.parent != public_dir else public_dir
    portal_root = public_root.parent if public_root.parent != public_root else public_root
    bin_dir = portal_root / "bin"
    bin64_dir = portal_root / "bin64"

    version_name = public_dir.name
    candidates = [
        public_dir,
        public_root,
        portal_root,
        bin_dir,
        bin64_dir,
    ]

    bin_public_api = bin_dir / "PublicAPI"
    bin_public_api_version = bin_public_api / version_name
    bin64_public_api = bin64_dir / "PublicAPI"
    bin64_public_api_version = bin64_public_api / version_name
    candidates.extend(
        [
            bin_public_api,
            bin_public_api_version,
            bin64_public_api,
            bin64_public_api_version,
        ]
    )

    sibling_public_api = []
    try:
        for sibling in public_root.iterdir():
            if sibling == public_dir:
                continue
            name_lower = sibling.name.lower()
            if sibling.is_dir() and "publicapi" in name_lower:
                candidates.append(sibling)
                sibling_public_api.append(sibling)
                versioned = sibling / version_name
                candidates.append(versioned)
                sibling_public_api.append(versioned)
    except Exception:
        pass

    culture_roots = [
        public_dir,
        public_root,
        bin_public_api,
        bin_public_api_version,
        bin64_public_api,
        bin64_public_api_version,
        *sibling_public_api,
    ]

    for base in culture_roots:
        for culture in _CULTURES:
            candidates.append(base / culture)

    return _dedupe_dirs(str(path) for path in candidates)



def _prepare_env(search_dirs: Iterable[str]) -> None:
    cur = os.environ.get("Path", "")
    parts = [p for p in cur.split(os.pathsep) if p.strip()]
    cleaned = []
    for p in parts:
        pl = p.lower().rstrip("\\/")
        if pl.endswith("\\software installs\\bin"):
            continue  # remove known-problematic vendor bin folders
        cleaned.append(p)
    parts = cleaned

    def _norm(s: str) -> str:
        return s.lower().rstrip("\\/")

    existing = {_norm(p) for p in parts}
    prepend = [d for d in search_dirs if _norm(d) not in existing]
    os.environ["Path"] = os.pathsep.join(prepend + parts)

    if hasattr(os, "add_dll_directory"):
        for d in search_dirs:
            try:
                os.add_dll_directory(d)
            except Exception:
                pass


def _index_managed(search_dirs: Iterable[str]) -> Tuple[Dict[Tuple[str, str], str], Dict[str, str]]:
    _, assembly_name = _load_reflection_types()
    asm_index: Dict[Tuple[str, str], str] = {}
    names_by_path: Dict[str, str] = {}
    for d in search_dirs:
        dp = Path(d)
        if not dp.is_dir():
            continue
        for dll in dp.glob("*.dll"):
            try:
                an = assembly_name.GetAssemblyName(str(dll))
                name = an.Name
                culture = str(an.CultureName) if an.CultureName else ""
                full = str(dll)
                asm_index[(name, culture)] = full
                names_by_path[full] = name
                if culture:
                    asm_index.setdefault((name, ""), full)
            except Exception:
                continue
    return asm_index, names_by_path


def _install_resolver(asm_index: Dict[Tuple[str, str], str]) -> None:
    global _TIAEXP_RESOLVE_INSTALLED
    app_domain, resolve_event_handler = _load_system_types()
    assembly, assembly_name = _load_reflection_types()
    _RESOLVE_STATE["asm_index"] = asm_index
    if _TIAEXP_RESOLVE_INSTALLED:
        return

    def _resolve(sender, args):
        try:
            an = assembly_name(args.Name)
            cache = _RESOLVE_STATE["asm_index"]
            key_c = (an.Name, str(an.CultureName) if an.CultureName else "")
            key_n = (an.Name, "")
            path = cache.get(key_c) or cache.get(key_n)
            if path and os.path.exists(path):
                return assembly.LoadFrom(path)
        except Exception:
            return None
        return None

    app_domain.CurrentDomain.AssemblyResolve += resolve_event_handler(_resolve)
    _TIAEXP_RESOLVE_INSTALLED = True


def _select_candidate(name: str, asm_index: Dict[Tuple[str, str], str], search_dirs: Iterable[str]) -> str | None:
    path = asm_index.get((name, "")) or asm_index.get((name, "en-US"))
    if path and os.path.exists(path):
        return path
    for d in search_dirs:
        maybe = Path(d) / f"{name}.dll"
        if maybe.exists():
            return str(maybe)
    return None


def prepare_and_load(public_api_dir: str | None):
    """Setup search paths and load the Siemens.Engineering assembly."""
    add_reference = _get_add_reference()
    _load_system_types()
    _load_reflection_types()

    search_dirs = _discover_dirs(public_api_dir)
    _prepare_env(search_dirs)

    asm_index, _ = _index_managed(search_dirs)
    _install_resolver(asm_index)

    loaded: Dict[str, str] = {}
    failures: Dict[str, str] = {}

    def _load(name: str) -> str | None:
        candidate = _select_candidate(name, asm_index, search_dirs)
        if not candidate:
            return None
        try:
            add_reference(candidate)
            loaded[name] = candidate
        except Exception as exc:
            failures[name] = f"{type(exc).__name__}: {exc}"
        return candidate

    core_path = _load("Siemens.Engineering")
    core_version = None
    if core_path:
        _, assembly_name = _load_reflection_types()
        try:
            core_version = str(assembly_name.GetAssemblyName(core_path).Version)
        except Exception:
            core_version = None

    # Preload only assemblies the exporter touches directly today
    optional_assemblies = ("Siemens.Engineering.Contract", "Siemens.Engineering.HW", "Siemens.Engineering.HW.Features", "Siemens.Engineering.Hmi", "Siemens.Engineering.AddIn")
    for optional in optional_assemblies:
        _load(optional)

    try:
        import_module("Siemens.Engineering")
    except Exception:
        pass

    return {
        "search_dirs": search_dirs,
        "core_path": core_path,
        "version": core_version,
        "prefetched": loaded,
        "prefetch_errors": failures,
        "path_head": os.environ.get("Path", "").split(os.pathsep)[:12],
    }

