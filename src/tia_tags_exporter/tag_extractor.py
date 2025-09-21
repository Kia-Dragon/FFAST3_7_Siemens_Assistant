from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Any, Iterator, List, Optional, Tuple, cast


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


_OP_TYPES: Tuple[type[Any], type[Any]] | None = None


def _load_openness_types() -> Tuple[type[Any], type[Any]]:
    """Import Siemens Openness types lazily so Pyright can run without CLR."""
    global _OP_TYPES
    if _OP_TYPES is not None:
        return _OP_TYPES

    try:
        engineering = import_module("Siemens.Engineering")
        hw_features = import_module("Siemens.Engineering.HW.Features")
    except ImportError as exc:  # pragma: no cover - requires TIA Portal runtime
        raise RuntimeError(
            "Siemens Openness assemblies are not available. Call ensure_clr_and_load " +
            "before using TagExtractor."
        ) from exc

    service_provider = cast(type[Any], getattr(engineering, "IEngineeringServiceProvider"))
    software_container = cast(type[Any], getattr(hw_features, "SoftwareContainer"))
    _OP_TYPES = (service_provider, software_container)
    return _OP_TYPES


class TagExtractor:
    def __init__(self, tia_session: Any) -> None:
        self.sess = tia_session

    def list_plcs(self) -> List[str]:
        service_provider, software_container = _load_openness_types()

        devices = list(getattr(self.sess.project, "Devices", []))
        plcs: List[str] = []
        for dev in devices:
            device_items = getattr(dev, "DeviceItems", None)
            if not device_items:
                continue
            try:
                container = service_provider(device_items[1]).GetService[software_container]()
            except Exception:
                continue
            software = getattr(container, "Software", None)
            if software and hasattr(software, "TagTableGroup"):
                name = getattr(dev, "Name", None)
                if name:
                    plcs.append(str(name))
        return plcs

    def extract_tags(self, plc_filter: Optional[List[str]] = None) -> Iterator[TagRow]:
        service_provider, software_container = _load_openness_types()

        project = getattr(self.sess, "project", None)
        project_name = getattr(project, "Name", "TIA_Project")
        devices = getattr(project, "Devices", []) if project else []

        for dev in devices:
            plc_name = getattr(dev, "Name", "")
            if plc_filter and plc_name not in plc_filter:
                continue

            device_items = getattr(dev, "DeviceItems", None)
            if not device_items:
                continue
            try:
                container = service_provider(device_items[1]).GetService[software_container]()
            except Exception:
                continue
            if container is None:
                continue
            software = getattr(container, "Software", None)
            tag_group = getattr(software, "TagTableGroup", None)
            if not tag_group:
                continue

            for table in getattr(tag_group, "TagTables", []):
                table_name = getattr(table, "Name", "")
                for tag in getattr(table, "Tags", []):
                    name = getattr(tag, "Name", "")
                    data_type = getattr(tag, "DataType", None)
                    address = getattr(tag, "LogicalAddress", None)
                    comment = getattr(tag, "Comment", None)
                    retain = getattr(tag, "Retain", None)
                    retentive = getattr(tag, "Retentive", None)
                    yield TagRow(
                        str(project_name),
                        str(plc_name),
                        str(table_name),
                        str(name),
                        "" if data_type is None else str(data_type),
                        "" if address is None else str(address),
                        "" if comment is None else str(comment),
                        bool(retain or retentive),
                        "Global",
                        f"{plc_name}:{table_name}:{name}",
                    )
