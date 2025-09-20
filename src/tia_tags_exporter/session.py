
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class TiaInstanceInfo:
    index: int
    description: str

class TiaSession:
    def __init__(self) -> None:
        self._tia = None
        self._project = None

    def list_instances(self) -> List[TiaInstanceInfo]:
        import clr
        import Siemens.Engineering as tia
        processes = tia.TiaPortal.GetProcesses()  # documented in examples
        infos: List[TiaInstanceInfo] = []
        for idx, p in enumerate(processes):
            desc = f"Process[{idx}] - Id={getattr(p, 'Id', 'N/A')}"  # best-effort
            infos.append(TiaInstanceInfo(idx, desc))
        return infos

    def attach(self, index: int = 0) -> None:
        import Siemens.Engineering as tia
        processes = tia.TiaPortal.GetProcesses()
        proc = processes[index]
        self._tia = proc.Attach()
        # pick first project
        self._project = self._tia.Projects[0] if self._tia.Projects.Count > 0 else None

    @property
    def project_name(self) -> Optional[str]:
        if self._project is None:
            return None
        return self._project.Path.ToString() if hasattr(self._project, 'Path') else getattr(self._project, 'Name', None)

    @property
    def tia(self):
        return self._tia

    @property
    def project(self):
        return self._project
