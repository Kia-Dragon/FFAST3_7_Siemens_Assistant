"""
Robust multi-directory loader for Siemens TIA Openness — PRELOAD ALL MANAGED DLLS.

PATCH-ID: TIAEXP-20250919-MULTIDIR-PRELOAD-ALL
"""

from __future__ import annotations
import os
from pathlib import Path
import clr  # pythonnet
from System import AppDomain
from System.Reflection import Assembly, AssemblyName
from System import ResolveEventHandler

_TIAEXP_RESOLVE_INSTALLED = False

_CULTURES = (
    "en-US","de-DE","fr-FR","es-ES","it-IT","pt-BR","ru-RU","pl-PL",
    "cs-CZ","zh-CN","ja-JP","tr-TR","ko-KR"
)

def _dedupe_dirs(cands):
    seen = set(); out = []
    for d in cands:
        if not d:
            continue
        try:
            p = Path(d)
            if not p.exists():
                continue
            key = str(p.resolve()).lower()
            if key not in seen:
                seen.add(key); out.append(str(p.resolve()))
        except Exception:
            continue
    return out

def _default_public_api_v17():
    pf = os.environ.get("ProgramW6432") or os.environ.get("ProgramFiles") or r"C:\Program Files"
    return str(Path(pf) / "Siemens" / "Automation" / "Portal V17" / "PublicAPI" / "V17")

def _discover_dirs(public_api_dir: str | None):
    pad = Path(public_api_dir) if public_api_dir else Path(_default_public_api_v17())
    public_dir = pad
    portal_root = public_dir.parent.parent if public_dir.name.lower() == "v17" else public_dir.parent.parent
    bin_dir  = portal_root / "bin"
    bin64_dir = portal_root / "bin64"
    dirs = [public_dir, bin_dir, bin64_dir, portal_root]
    # Include sibling PublicAPI folders (e.g., V16, V15.1) for mixed installs
    try:
        for sibling in public_dir.parent.iterdir():
            if sibling == public_dir:
                continue
            name_lower = sibling.name.lower()
            if sibling.is_dir() and "publicapi" in name_lower:
                dirs.append(sibling)
    except Exception:
        pass
    for c in _CULTURES:
        cd = public_dir / c
        if cd.is_dir():
            dirs.append(str(cd))
    return _dedupe_dirs(dirs)

def _index_managed(search_dirs):
    """
    Return:
      - asm_index: {(Name, Culture or ''): path}
      - names_by_path: {path: Name}
    Only managed assemblies are indexed (AssemblyName.GetAssemblyName succeeds).
    """
    asm_index = {}
    names_by_path = {}
    for d in search_dirs:
        dp = Path(d)
        if not dp.is_dir():
            continue
        for dll in dp.glob("*.dll"):
            try:
                an = AssemblyName.GetAssemblyName(str(dll))
                name = an.Name
                cult = str(an.CultureName) if an.CultureName else ""
                full = str(dll)
                asm_index[(name, cult)] = full
                names_by_path[full] = name
                if cult:
                    asm_index.setdefault((name, ""), full)
            except Exception:
                # native/unmanaged/resource-only — ignore
                continue
    return asm_index, names_by_path

def prepare_and_load(public_api_dir: str | None):
    """
    Multi-folder, strict loader for TIA Openness.

    - Build search set: PublicAPI\\V17, Portal V17\\bin/bin64, Portal root, culture subfolders
    - Index all *managed* Siemens assemblies via AssemblyName.GetAssemblyName (no eager loads)
    - Install strict AssemblyResolve to resolve ONLY from our indexed files
    - Remove known-offender user bin paths (e.g., '*\\Software Installs\\bin') from PATH in THIS process
    - Prepend Siemens dirs to PATH and add to native loader via os.add_dll_directory
    - **Preload ALL managed Siemens assemblies** in deterministic order
    """
    global _TIAEXP_RESOLVE_INSTALLED

    # Discover folders
    search_dirs = _discover_dirs(public_api_dir)

    # Clean the process PATH: remove '*\Software Installs\bin' entirely
    cur = os.environ.get("Path", "")
    parts = [p for p in cur.split(os.pathsep) if p.strip()]
    cleaned = []
    for p in parts:
        pl = p.lower().rstrip("\\/")
        if pl.endswith("\\software installs\\bin"):
            # drop it completely
            continue
        cleaned.append(p)
    parts = cleaned

    # Prepend Siemens dirs if not already present
    norm = lambda s: s.lower().rstrip("\\/")
    existing = {norm(p) for p in parts}
    prepend = [d for d in search_dirs if norm(d) not in existing]
    os.environ["Path"] = os.pathsep.join(prepend + parts)

    # Native DLL search directories
    if hasattr(os, "add_dll_directory"):
        for d in search_dirs:
            try:
                os.add_dll_directory(d)
            except Exception:
                pass

    # Index managed Siemens assemblies
    asm_index, names_by_path = _index_managed(search_dirs)

    # Install strict AssemblyResolve ONCE
    if not _TIAEXP_RESOLVE_INSTALLED:
        def _resolve(sender, args):
            try:
                an = AssemblyName(args.Name)
                key_c = (an.Name, str(an.CultureName) if an.CultureName else "")
                key_n = (an.Name, "")
                path = asm_index.get(key_c) or asm_index.get(key_n)
                if path and os.path.exists(path):
                    return Assembly.LoadFrom(path)
            except Exception:
                return None
            return None

        AppDomain.CurrentDomain.AssemblyResolve += ResolveEventHandler(_resolve)
        _TIAEXP_RESOLVE_INSTALLED = True

    # Determine load order:
    #  1) core Siemens.Engineering.dll (neutral or en-US)
    #  2) any Siemens.Engineering.* (alphabetical)
    #  3) all remaining Siemens.* (alphabetical)
    # Build a path->name map limited to Siemens.* to avoid random third parties.
    siemens_paths = {p: n for p, n in names_by_path.items() if n.startswith("Siemens.")}

    def _find(name):
        return asm_index.get((name, "")) or asm_index.get((name, "en-US"))

    core_path = _find("Siemens.Engineering")
    if not core_path:
        # last resort next to first search dir
        maybe = Path(search_dirs[0]) / "Siemens.Engineering.dll"
        core_path = str(maybe)

    # Group lists
    eng_children = sorted([p for p, n in siemens_paths.items() if n.startswith("Siemens.Engineering.")])
    others = sorted([p for p, n in siemens_paths.items()
                     if not n.startswith("Siemens.Engineering")])

    load_list = []
    if core_path and os.path.exists(core_path):
        load_list.append(core_path)
    load_list += eng_children + others

    # Preload all (managed) — use AddReference for core, Assembly.LoadFrom for the rest
    loaded = []
    seen_names = set()

    def _safe_load(p, is_core=False):
        try:
            if not os.path.exists(p):
                return False
            if is_core:
                clr.AddReferenceToFileAndPath(p)
                asm = Assembly.LoadFrom(p)  # ensure reflection works for metadata
            else:
                asm = Assembly.LoadFrom(p)
            nm = asm.GetName().Name
            if nm not in seen_names:
                seen_names.add(nm)
                loaded.append(p)
            return True
        except Exception:
            # Ignore resource-only or incompatible ones
            return False

    # Load in order
    for idx, path in enumerate(load_list):
        _safe_load(path, is_core=(idx == 0 and path == core_path))

    # Import Siemens.Engineering namespace AFTER preloading
    try:
        import Siemens.Engineering as tia  # noqa: F401
    except Exception:
        # Even if import fails here, AssemblyResolve will still kick in when types are used
        pass

    return {
        "search_dirs": search_dirs,
        "path_head": os.environ.get("Path", "").split(os.pathsep)[:12],
        "core_path": core_path if core_path and os.path.exists(core_path) else None,
        "managed_loaded_count": len(loaded),
        "managed_loaded_paths": loaded[:20],  # show first 20
    }