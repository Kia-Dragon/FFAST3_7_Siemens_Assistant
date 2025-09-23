from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, List, Optional
from importlib import import_module

from .session import TiaSession


ADDRESS_ATTRIBUTE = "Address"
CONNECTED_SUBNET_ATTRIBUTE = "ConnectedSubnet"
NAME_ATTRIBUTE = "Name"
IO_SYSTEM_ATTRIBUTE = "IoSystem"


@dataclass
class DevicesNetworksRow:
    ProjectName: str = ""
    DeviceName: str = ""
    DeviceType: str = ""
    NetworkInterface: str = ""
    NodeAddress: str = ""
    SubnetName: str = ""
    IoSystemName: str = ""


class DevicesNetworksExporter:
    def __init__(self, tia_session: TiaSession) -> None:
        self.sess = tia_session
        self._network_interface_type = None

    def _load_openness_types(self):
        if self._network_interface_type is None:
            try:
                engineering = import_module("Siemens.Engineering")
                self._network_interface_type = getattr(engineering.HW.Features, "NetworkInterface")
            except (ImportError, AttributeError):
                # Handle case where Openness is not available
                pass
        return self._network_interface_type

    def extract_devices_networks(
        self, plc_filter: Optional[List[str]] = None
    ) -> List[DevicesNetworksRow]:
        rows: List[DevicesNetworksRow] = []
        self._load_openness_types()

        project = getattr(self.sess, "project", None)
        if project is None:
            return rows

        project_name = self._safe_str(getattr(project, NAME_ATTRIBUTE, "TIA_Project"))

        for device in self._iter_collection(getattr(project, "Devices", None)):
            device_name = self._safe_str(getattr(device, NAME_ATTRIBUTE, "Device"))
            if plc_filter and device_name not in plc_filter:
                continue

            device_type = self._safe_str(getattr(device, "TypeIdentifier", ""))

            for device_item in self._iter_collection(getattr(device, "DeviceItems", None)):
                # Recursive search for NetworkInterface
                rows.extend(self._extract_network_info(project_name, device_name, device_type, device_item))

        return rows

    def _extract_network_info(self, project_name: str, device_name: str, device_type: str, device_item: Any) -> List[DevicesNetworksRow]:
        rows = []
        if self._network_interface_type:
            try:
                network_interface = device_item.GetService[self._network_interface_type]()
                if network_interface:
                    for node in self._iter_collection(getattr(network_interface, "Nodes", None)):
                        address = self._safe_str(node.GetAttribute(ADDRESS_ATTRIBUTE))
                        subnet = getattr(node, CONNECTED_SUBNET_ATTRIBUTE, None)
                        subnet_name = self._safe_str(getattr(subnet, NAME_ATTRIBUTE, ""))
                        io_system = getattr(node, IO_SYSTEM_ATTRIBUTE, None)
                        io_system_name = self._safe_str(getattr(io_system, NAME_ATTRIBUTE, ""))
                        
                        rows.append(
                            DevicesNetworksRow(
                                ProjectName=project_name,
                                DeviceName=device_name,
                                DeviceType=device_type,
                                NetworkInterface=self._safe_str(getattr(device_item, NAME_ATTRIBUTE, "")),
                                NodeAddress=address,
                                SubnetName=subnet_name,
                                IoSystemName=io_system_name,
                            )
                        )
            except (AttributeError, TypeError):
                # Ignore exceptions during service retrieval
                pass

        # Recursive call for sub-items
        for sub_item in self._iter_collection(getattr(device_item, "DeviceItems", None)):
            rows.extend(self._extract_network_info(project_name, device_name, device_type, sub_item))
        
        return rows


    def _iter_collection(self, collection: Any) -> Iterable[Any]:
        if collection is None:
            return []
        try:
            return list(collection)
        except TypeError:
            count = getattr(collection, "Count", 0)
            items = []
            for idx in range(count):
                try:
                    items.append(collection[idx])
                except Exception:
                    continue
            return items

    def _safe_str(self, value) -> str:
        if value is None:
            return ""
        try:
            return str(value)
        except Exception:
            return ""
