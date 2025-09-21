from __future__ import annotations

import re
from dataclasses import dataclass
from importlib import import_module
from typing import Any, Iterable, List, Optional, Tuple

from .session import TiaSession


@dataclass
class ProgramBlockRow:
    ProjectName: str
    PLC_Name: str
    BlockName: str
    BlockType: str
    Language: str
    AttributeName: str
    AttributeValue: str
    InterfaceSection: str
    InterfaceName: str
    InterfaceDataType: str
    InitialValue: str
    Comment: str
    SourceReference: str = ""


@dataclass
class BlockSourceExport:
    plc_name: str
    block_name: str
    block_type: str
    language: str
    filename: str
    content: str


_OPENNESS_TYPES: Tuple[type[Any], type[Any]] | None = None


def _load_openness_types() -> Tuple[type[Any], type[Any]] | None:
    global _OPENNESS_TYPES
    if _OPENNESS_TYPES is not None:
        return _OPENNESS_TYPES
    try:
        engineering = import_module("Siemens.Engineering")
        hw_features = import_module("Siemens.Engineering.HW.Features")
    except ImportError:
        return None
    provider = getattr(engineering, "IEngineeringServiceProvider", None)
    software_container = getattr(hw_features, "SoftwareContainer", None)
    if provider is None or software_container is None:
        return None
    _OPENNESS_TYPES = (provider, software_container)
    return _OPENNESS_TYPES


class ProgramBlockExtractor:
    def __init__(self, tia_session: TiaSession) -> None:
        self.sess = tia_session

    def extract_blocks(
        self, plc_filter: Optional[List[str]] = None
    ) -> Tuple[List[ProgramBlockRow], List[BlockSourceExport]]:
        rows: List[ProgramBlockRow] = []
        sources: List[BlockSourceExport] = []

        project = getattr(self.sess, "project", None)
        if project is None:
            return rows, sources

        project_name = self._safe_str(getattr(project, "Name", "TIA_Project"))

        for device in self._iter_collection(getattr(project, "Devices", None)):
            plc_name = self._safe_str(getattr(device, "Name", "Device"))
            if plc_filter and plc_name not in plc_filter:
                continue

            software = self._get_plc_software(device)
            if software is None:
                continue

            block_group = getattr(software, "BlockGroup", None) or getattr(
                software, "ProgramBlocks", None
            )
            if block_group is None:
                continue

            for block in self._iter_blocks_recursive(block_group):
                block_rows, block_source = self._materialize_block(
                    project_name, plc_name, block
                )
                rows.extend(block_rows)
                if block_source:
                    sources.append(block_source)

        return rows, sources

    def _get_plc_software(self, device) -> Optional[object]:
        types = _load_openness_types()
        if types is None:
            return None
        provider_type, container_type = types

        items = getattr(device, "DeviceItems", None)
        if not items:
            return None

        entry: Any = None
        try:
            entry = items[1]
        except Exception:
            pass
        if entry is None:
            try:
                entry = next(iter(items))
            except Exception:
                entry = None
        if entry is None:
            return None

        try:
            provider = provider_type(entry)
            container = provider.GetService[container_type]()
            return getattr(container, "Software", None) if container else None
        except Exception:
            return None

    def _iter_collection(self, collection) -> Iterable[object]:
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

    def _iter_blocks_recursive(self, group) -> Iterable[object]:
        for block in self._iter_collection(getattr(group, "Blocks", None)):
            yield block
        for sub_group in self._iter_collection(getattr(group, "Groups", None)):
            yield from self._iter_blocks_recursive(sub_group)

    def _materialize_block(
        self, project_name: str, plc_name: str, block
    ) -> Tuple[List[ProgramBlockRow], Optional[BlockSourceExport]]:
        block_name = self._safe_str(getattr(block, "Name", ""))
        block_type = self._safe_str(
            getattr(block, "BlockType", getattr(block, "TypeIdentifier", ""))
        )
        language = self._safe_str(
            getattr(block, "ProgrammingLanguage", getattr(block, "Language", ""))
        )

        attributes = list(self._iter_attributes(block))
        interface_items = list(self._iter_interface_entries(block))

        block_source = self._extract_source(plc_name, block_name, block_type, language, block)
        source_reference = block_source.filename if block_source else ""

        rows: List[ProgramBlockRow] = []

        if attributes:
            for name, value in attributes:
                rows.append(
                    ProgramBlockRow(
                        ProjectName=project_name,
                        PLC_Name=plc_name,
                        BlockName=block_name,
                        BlockType=block_type,
                        Language=language,
                        AttributeName=name,
                        AttributeValue=value,
                        InterfaceSection="",
                        InterfaceName="",
                        InterfaceDataType="",
                        InitialValue="",
                        Comment="",
                        SourceReference=source_reference,
                    )
                )

        if interface_items:
            for entry in interface_items:
                rows.append(
                    ProgramBlockRow(
                        ProjectName=project_name,
                        PLC_Name=plc_name,
                        BlockName=block_name,
                        BlockType=block_type,
                        Language=language,
                        AttributeName="",
                        AttributeValue="",
                        InterfaceSection=entry["section"],
                        InterfaceName=entry["name"],
                        InterfaceDataType=entry["data_type"],
                        InitialValue=entry["initial"],
                        Comment=entry["comment"],
                        SourceReference=source_reference,
                    )
                )

        if not rows:
            rows.append(
                ProgramBlockRow(
                    ProjectName=project_name,
                    PLC_Name=plc_name,
                    BlockName=block_name,
                    BlockType=block_type,
                    Language=language,
                    AttributeName="",
                    AttributeValue="",
                    InterfaceSection="",
                    InterfaceName="",
                    InterfaceDataType="",
                    InitialValue="",
                    Comment=self._safe_str(getattr(block, "Comment", "")),
                    SourceReference=source_reference,
                )
            )

        return rows, block_source

    def _iter_attributes(self, block) -> Iterable[Tuple[str, str]]:
        attr_collection = getattr(block, "Attributes", None)
        if attr_collection is not None:
            try:
                for attr in attr_collection:
                    name = self._safe_str(getattr(attr, "Name", ""))
                    if not name:
                        continue
                    raw_value: Any = getattr(
                        attr,
                        "Value",
                        getattr(attr, "ValueString", getattr(attr, "Text", "")),
                    )
                    yield name, self._safe_str(raw_value)
            except Exception:
                pass

        attr_names = getattr(block, "AttributeNames", None)
        if attr_names is not None:
            getter = getattr(block, "GetAttribute", None)
            if callable(getter):
                for attr_name in self._iter_collection(attr_names):
                    key = self._safe_str(attr_name)
                    if not key:
                        continue
                    try:
                        value = getter(attr_name)
                    except Exception:
                        continue
                    yield key, self._safe_str(value)

        initial = getattr(block, "InitialValue", None)
        if initial is None:
            initial = getattr(block, "StartValue", None)
        if initial is not None:
            yield "InitialValue", self._safe_str(initial)

    def _iter_interface_entries(self, block) -> Iterable[dict]:
        interface = getattr(block, "Interface", None)
        if interface is None:
            return []

        sections = {
            "Inputs": ("Inputs", "Ins", "InputParameters"),
            "Outputs": ("Outputs", "Outs", "OutputParameters"),
            "InOuts": ("InOuts", "Inouts", "InOut"),
            "Statics": ("Statics", "StaticVariables"),
            "Temps": ("Temps", "TempVariables", "Temporaries"),
            "Return": ("Return",),
        }

        entries: List[dict] = []
        for label, candidates in sections.items():
            section_obj = None
            for candidate in candidates:
                section_obj = getattr(interface, candidate, None)
                if section_obj is not None:
                    break
            if section_obj is None:
                continue
            for param in self._iter_collection(section_obj):
                name = self._safe_str(getattr(param, "Name", "")) or ("Return" if label == "Return" else "")
                data_type = self._safe_str(
                    getattr(param, "DataTypeName", getattr(param, "Datatype", ""))
                )
                initial = getattr(param, "InitialValue", None)
                if initial is None:
                    initial = getattr(param, "DefaultValue", None)
                if initial is None:
                    initial = getattr(param, "StartValue", None)
                comment_obj: Any = getattr(param, "Comment", "")
                comment_text: Any = getattr(comment_obj, "Text", comment_obj)
                entries.append(
                    {
                        "section": label,
                        "name": name,
                        "data_type": data_type,
                        "initial": self._safe_str(initial),
                        "comment": self._safe_str(comment_text),
                    }
                )
        return entries

    def _extract_source(
        self,
        plc_name: str,
        block_name: str,
        block_type: str,
        language: str,
        block,
    ) -> Optional[BlockSourceExport]:
        generate = getattr(block, "GenerateSource", None)
        content: Any = None
        candidate: Any = None
        if callable(generate):
            try:
                candidate = generate()
            except TypeError:
                try:
                    candidate = generate(None)
                except Exception:
                    candidate = None
            except Exception:
                candidate = None
            if candidate is not None:
                for attr in ("Source", "SourceCode", "Text"):
                    fragment = getattr(candidate, attr, None)
                    if fragment:
                        content = fragment
                        break
                if content is None and hasattr(candidate, "ToString"):
                    try:
                        content = candidate.ToString()
                    except Exception:
                        content = None
                if content is None:
                    try:
                        content = str(candidate)
                    except Exception:
                        content = None
        if content:
            filename = self._make_source_filename(plc_name, block_name, language, block_type)
            return BlockSourceExport(
                plc_name=plc_name,
                block_name=block_name,
                block_type=block_type,
                language=language,
                filename=filename,
                content=self._safe_str(content),
            )
        return None

    def _make_source_filename(
        self, plc_name: str, block_name: str, language: str, block_type: str
    ) -> str:
        stem = f"{plc_name}_{block_name}_{block_type or 'Block'}"
        stem = self._sanitize_filename(stem)
        ext = self._guess_extension(language)
        return f"{stem}{ext}"

    def _sanitize_filename(self, name: str) -> str:
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", name)
        safe = safe.strip("._")
        return safe or "program_block"

    def _guess_extension(self, language: str) -> str:
        lang = (language or "").lower()
        if "lad" in lang:
            return ".ladder"
        if "fbd" in lang:
            return ".fbd"
        if "scl" in lang:
            return ".scl"
        if "stl" in lang or "awl" in lang:
            return ".stl"
        return ".src"

    def _safe_str(self, value) -> str:
        if value is None:
            return ""
        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        try:
            return str(value)
        except Exception:
            if hasattr(value, "ToString"):
                try:
                    return value.ToString()
                except Exception:
                    return ""
            return ""
