"""
Multi-directory loader for Siemens TIA Openness - trims to only the assemblies we actually use.

PATCH-ID: TIAEXP-20250919-MULTIDIR-PRELOAD-ALL
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Iterable, Tuple

import clr  # pythonnet
from System import AppDomain
from System.Reflection import Assembly, AssemblyName
from System import ResolveEventHandler

_TIAEXP_RESOLVE_INSTALLED = False
_RESOLVE_STATE: Dict[str, Dict[Tuple[str, str], str]] = {"asm_index": {}}

_CULTURES = (
    "en-US", "de-DE", "fr-FR", "es-ES", "it-IT", "pt-BR", "ru-RU", "pl-PL",
    "cs-CZ", "zh-CN", "ja-JP", "tr-TR", "ko-KR",
)


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
    public_dir = pad
    portal_root = public_dir.parent.parent if public_dir.name.lower() == "v17" else public_dir.parent.parent
    bin_dir = portal_root / "bin"
    bin64_dir = portal_root / "bin64"
    dirs: list[str] = [str(public_dir), str(bin_dir), str(bin64_dir), str(portal_root)]
    # Include sibling PublicAPI folders (e.g., V16, V15.1) for mixed installs
    try:
        for sibling in public_dir.parent.iterdir():
            if sibling == public_dir:
                continue
            name_lower = sibling.name.lower()
            if sibling.is_dir() and "publicapi" in name_lower:
                dirs.append(str(sibling))
    except Exception:
        pass
    for culture in _CULTURES:
        cd = public_dir / culture
        if cd.is_dir():
            dirs.append(str(cd))
    return _dedupe_dirs(dirs)


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
    asm_index: Dict[Tuple[str, str], str] = {}
    names_by_path: Dict[str, str] = {}
    for d in search_dirs:
        dp = Path(d)
        if not dp.is_dir():
            continue
        for dll in dp.glob("*.dll"):
            try:
                an = AssemblyName.GetAssemblyName(str(dll))
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
    _RESOLVE_STATE["asm_index"] = asm_index
    if _TIAEXP_RESOLVE_INSTALLED:
        return

    def _resolve(sender, args):
        try:
            an = AssemblyName(args.Name)
            cache = _RESOLVE_STATE["asm_index"]
            key_c = (an.Name, str(an.CultureName) if an.CultureName else "")
            key_n = (an.Name, "")
            path = cache.get(key_c) or cache.get(key_n)
            if path and os.path.exists(path):
                return Assembly.LoadFrom(path)
        except Exception:
            return None
        return None

    AppDomain.CurrentDomain.AssemblyResolve += ResolveEventHandler(_resolve)
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
            clr.AddReference(candidate)
            loaded[name] = candidate
        except Exception as exc:
            failures[name] = f"{type(exc).__name__}: {exc}"
        return candidate

    core_path = _load("Siemens.Engineering")
    core_version = None
    if core_path:
        try:
            core_version = str(AssemblyName.GetAssemblyName(core_path).Version)
        except Exception:
            core_version = None

    # Preload only assemblies the exporter touches directly today
    for optional in ("Siemens.Engineering.HW",):
        _load(optional)

    try:
        import Siemens.Engineering  # noqa: F401
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
