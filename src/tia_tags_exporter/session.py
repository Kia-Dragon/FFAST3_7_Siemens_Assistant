from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Any, List, Optional, Tuple, cast


@dataclass
class TiaInstanceInfo:
    index: int
    description: str


_PORTAL_TYPES: Tuple[type[Any], type[Any]] | None = None


def _load_tia_portal() -> Tuple[type[Any], type[Any]]:
    """Lazily import Siemens Openness portal types."""
    global _PORTAL_TYPES
    if _PORTAL_TYPES is not None:
        return _PORTAL_TYPES

    try:
        engineering = import_module("Siemens.Engineering")
    except ImportError as exc:  # pragma: no cover - requires TIA Portal
        raise RuntimeError(
            "Siemens Openness assemblies are not available. Call ensure_clr_and_load "
            "before using TiaSession."
        ) from exc

    tia_portal = cast(type[Any], getattr(engineering, "TiaPortal"))
    tie_process = cast(type[Any], getattr(engineering, "TiaPortalProcess"))
    _PORTAL_TYPES = (tia_portal, tie_process)
    return _PORTAL_TYPES


class TiaSession:
    def __init__(self) -> None:
        self._tia: Any | None = None
        self._project: Any | None = None

    def list_instances(self) -> List[TiaInstanceInfo]:
        tia_portal, _ = _load_tia_portal()
        processes = getattr(tia_portal, "GetProcesses")()
        infos: List[TiaInstanceInfo] = []
        for idx, proc in enumerate(processes):
            proc_id = getattr(proc, "Id", "N/A")
            infos.append(TiaInstanceInfo(idx, f"Process[{idx}] - Id={proc_id}"))
        return infos

    def attach(self, index: int = 0) -> None:
        tia_portal, _ = _load_tia_portal()
        processes = getattr(tia_portal, "GetProcesses")()
        proc = processes[index]
        self._tia = proc.Attach()
        projects = getattr(self._tia, "Projects", None)
        if projects and getattr(projects, "Count", 0) > 0:
            self._project = projects[0]
        else:
            self._project = None

    @property
    def project_name(self) -> Optional[str]:
        if self._project is None:
            return None
        path = getattr(self._project, "Path", None)
        if path is not None and hasattr(path, "ToString"):
            return cast(str, path.ToString())
        name = getattr(self._project, "Name", None)
        return cast(Optional[str], name if name is None or isinstance(name, str) else str(name))

    @property
    def tia(self) -> Any | None:
        return self._tia

    @property
    def project(self) -> Any | None:
        return self._project
