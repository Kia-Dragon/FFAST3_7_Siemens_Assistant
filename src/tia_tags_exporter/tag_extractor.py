
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, List, Optional

@dataclass
class TagRow:
    ProjectName: str
    PLC_Name: str
    TagTable: str
    TagName: str
    DataType: str
    Address: str
    Comment: str
    Retentive: bool
    Scope: str
    TagId: str

class TagExtractor:
    def __init__(self, tia_session) -> None:
        self.sess = tia_session

    def list_plcs(self) -> List[str]:
        # Enumerate devices and return those with PlcSoftware
        import Siemens.Engineering as tia
        devices = list(self.sess.project.Devices)
        plcs: List[str] = []
        for dev in devices:
            try:
                # Access software container service
                from Siemens.Engineering.HW.Features import SoftwareContainer
                from Siemens.Engineering import IEngineeringServiceProvider
                sc = IEngineeringServiceProvider(dev.DeviceItems[1]).GetService[SoftwareContainer]()
                if sc is not None:
                    sw = sc.Software
                    if hasattr(sw, 'TagTableGroup'):
                        plcs.append(dev.Name)
            except Exception:
                continue
        return plcs

    def extract_tags(self, plc_filter: Optional[List[str]] = None) -> Iterable[TagRow]:
        import Siemens.Engineering as tia
        from Siemens.Engineering.HW.Features import SoftwareContainer
        from Siemens.Engineering import IEngineeringServiceProvider

        project_name = self.sess.project.Name if hasattr(self.sess.project, 'Name') else 'TIA_Project'

        for dev in self.sess.project.Devices:
            if plc_filter and dev.Name not in plc_filter:
                continue
            try:
                sc = IEngineeringServiceProvider(dev.DeviceItems[1]).GetService[SoftwareContainer]()
                if sc is None:
                    continue
                sw = sc.Software
                if not hasattr(sw, 'TagTableGroup'):
                    continue
                ttg = sw.TagTableGroup
                for ttab in ttg.TagTables:
                    table_name = ttab.Name
                    for tag in ttab.Tags:
                        name = getattr(tag, 'Name', '')
                        dtype = getattr(tag, 'DataType', None)
                        dtype_str = str(dtype) if dtype is not None else ''
                        addr = getattr(tag, 'LogicalAddress', None)
                        addr_str = str(addr) if addr is not None else ''
                        comm = getattr(tag, 'Comment', None)
                        comm_str = str(comm) if comm is not None else ''
                        ret = getattr(tag, 'Retain', False) or getattr(tag, 'Retentive', False)
                        scope = 'Global'
                        tag_id = f"{dev.Name}:{table_name}:{name}"
                        yield TagRow(project_name, dev.Name, table_name, name, dtype_str, addr_str, comm_str, bool(ret), scope, tag_id)
            except Exception:
                continue
