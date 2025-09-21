from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import json
import xml.etree.ElementTree as ET

from .hmi_exporter import HmiExportResult, HmiTargetInfo


def _local(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _attr_ci(element: ET.Element, *names: str) -> str:
    if not element.attrib:
        return ""
    lowered = {key.lower(): value for key, value in element.attrib.items()}
    for name in names:
        value = lowered.get(name.lower())
        if value is not None:
            return value
    return ""


def _json_dump(payload: Dict[str, str]) -> str:
    if not payload:
        return ""
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _collect_properties(element: ET.Element, exclude: Sequence[str]) -> Dict[str, str]:
    excluded = {name.lower() for name in exclude}
    props: Dict[str, str] = {}
    for key, value in element.attrib.items():
        if key.lower() in excluded:
            continue
        props[key] = value
    for child in element:
        if list(child) or child.attrib:
            continue
        text = (child.text or "").strip()
        if text:
            props[_local(child.tag)] = text
    return props


def _extract_translations(element: ET.Element) -> List[Tuple[str, str]]:
    translations: List[Tuple[str, str]] = []
    seen: set[Tuple[str, str]] = set()
    wanted = {"text", "languagetext", "multilanguagetext", "textelement", "message"}
    for child in element.iter():
        if child is element:
            continue
        name = _local(child.tag)
        if name.lower() not in wanted:
            continue
        language = (
            _attr_ci(child, "Language", "Lang", "Culture")
            or _attr_ci(element, "Language", "Lang", "Culture")
        )
        text = _attr_ci(child, "Text", "Value")
        if not text:
            text = (child.text or "").strip()
        if not text and not language:
            continue
        key = (language or "", text)
        if key in seen:
            continue
        seen.add(key)
        translations.append(key)
    return translations


def _iter_by_local(root: ET.Element, names: Iterable[str]) -> Iterable[ET.Element]:
    wanted = {name.lower() for name in names}
    for element in root.iter():
        if _local(element.tag).lower() in wanted:
            yield element


@dataclass
class _Context:
    project: str
    target: str
    device: str
    software: str


@dataclass
class TextListRow:
    project: str
    target: str
    device: str
    software: str
    text_list: str
    text_list_id: str
    text_list_guid: str
    entry_name: str
    entry_id: str
    language: str
    text: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "Project": self.project,
            "Target": self.target,
            "Device": self.device,
            "Software": self.software,
            "TextList": self.text_list,
            "TextListId": self.text_list_id,
            "TextListGuid": self.text_list_guid,
            "Entry": self.entry_name,
            "EntryId": self.entry_id,
            "Language": self.language,
            "Text": self.text,
        }


@dataclass
class ScreenElementRow:
    project: str
    target: str
    device: str
    software: str
    screen: str
    screen_id: str
    element_path: str
    element_type: str
    element_name: str
    properties_json: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "Project": self.project,
            "Target": self.target,
            "Device": self.device,
            "Software": self.software,
            "Screen": self.screen,
            "ScreenId": self.screen_id,
            "ElementPath": self.element_path,
            "ElementType": self.element_type,
            "ElementName": self.element_name,
            "Properties": self.properties_json,
        }


@dataclass
class AlarmRow:
    project: str
    target: str
    device: str
    software: str
    alarm_class: str
    alarm_class_id: str
    alarm_name: str
    alarm_id: str
    language: str
    text: str
    attributes_json: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "Project": self.project,
            "Target": self.target,
            "Device": self.device,
            "Software": self.software,
            "AlarmClass": self.alarm_class,
            "AlarmClassId": self.alarm_class_id,
            "Alarm": self.alarm_name,
            "AlarmId": self.alarm_id,
            "Language": self.language,
            "Text": self.text,
            "Attributes": self.attributes_json,
        }


@dataclass
class RecipeRow:
    project: str
    target: str
    device: str
    software: str
    recipe: str
    recipe_id: str
    item_path: str
    item_name: str
    data_type: str
    default_value: str
    min_value: str
    max_value: str
    attributes_json: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "Project": self.project,
            "Target": self.target,
            "Device": self.device,
            "Software": self.software,
            "Recipe": self.recipe,
            "RecipeId": self.recipe_id,
            "ItemPath": self.item_path,
            "ItemName": self.item_name,
            "DataType": self.data_type,
            "DefaultValue": self.default_value,
            "MinValue": self.min_value,
            "MaxValue": self.max_value,
            "Attributes": self.attributes_json,
        }


@dataclass
class FlattenedArtifacts:
    text_lists: List[TextListRow]
    screens: List[ScreenElementRow]
    alarms: List[AlarmRow]
    recipes: List[RecipeRow]

    def to_mapping(self) -> Dict[str, List[Dict[str, str]]]:
        return {
            "text_lists": [row.to_dict() for row in self.text_lists],
            "screens": [row.to_dict() for row in self.screens],
            "alarms": [row.to_dict() for row in self.alarms],
            "recipes": [row.to_dict() for row in self.recipes],
        }


def _context_from_target(target: HmiTargetInfo, project: Optional[str]) -> _Context:
    return _Context(
        project=project or "",
        target=target.identifier,
        device=target.device_name,
        software=target.software_name,
    )


def flatten_text_lists(path: Optional[Path], ctx: _Context) -> List[TextListRow]:
    if not path or not path.exists():
        return []
    root = ET.parse(path).getroot()
    rows: List[TextListRow] = []
    for text_list in _iter_by_local(root, {"TextList"}):
        list_name = _attr_ci(text_list, "Name", "DisplayName")
        list_id = _attr_ci(text_list, "ID", "Identifier")
        list_guid = _attr_ci(text_list, "Guid", "GUID")
        entries = [child for child in text_list if child is not None]
        if not entries:
            translations = _extract_translations(text_list)
            for language, text in translations:
                rows.append(
                    TextListRow(
                        ctx.project,
                        ctx.target,
                        ctx.device,
                        ctx.software,
                        list_name,
                        list_id,
                        list_guid,
                        "",
                        "",
                        language,
                        text,
                    )
                )
            continue
        for entry in entries:
            entry_name = _attr_ci(entry, "Name", "DisplayName", "Text")
            entry_id = _attr_ci(entry, "ID", "Identifier")
            translations = _extract_translations(entry)
            if translations:
                for language, text in translations:
                    rows.append(
                        TextListRow(
                            ctx.project,
                            ctx.target,
                            ctx.device,
                            ctx.software,
                            list_name,
                            list_id,
                            list_guid,
                            entry_name,
                            entry_id,
                            language,
                            text,
                        )
                    )
                continue
            text_value = _attr_ci(entry, "Text", "Value") or (entry.text or "").strip()
            if not text_value:
                continue
            rows.append(
                TextListRow(
                    ctx.project,
                    ctx.target,
                    ctx.device,
                    ctx.software,
                    list_name,
                    list_id,
                    list_guid,
                    entry_name,
                    entry_id,
                    "",
                    text_value,
                )
            )
    return rows


def flatten_screens(path: Optional[Path], ctx: _Context) -> List[ScreenElementRow]:
    if not path or not path.exists():
        return []
    root = ET.parse(path).getroot()
    rows: List[ScreenElementRow] = []

    def visit(node: ET.Element, screen_name: str, screen_id: str, trail: List[str]) -> None:
        local = _local(node.tag)
        name = _attr_ci(node, "Name", "DisplayName")
        current_name = name or local
        current_path = trail + [current_name]
        properties = _collect_properties(node, ("Name", "DisplayName", "ID"))
        should_emit = node is not None and (node is screen_root or properties or name)
        if should_emit:
            rows.append(
                ScreenElementRow(
                    ctx.project,
                    ctx.target,
                    ctx.device,
                    ctx.software,
                    screen_name,
                    screen_id,
                    "/".join([part for part in current_path if part]),
                    local,
                    name,
                    _json_dump(properties),
                )
            )
        for child in list(node):
            visit(child, screen_name, screen_id, current_path)

    for screen_root in _iter_by_local(root, {"Screen"}):
        screen_name = _attr_ci(screen_root, "Name", "DisplayName")
        screen_id = _attr_ci(screen_root, "ID", "Identifier")
        origin = screen_name or screen_id or _local(screen_root.tag)
        visit(screen_root, screen_name, screen_id, [origin])

    return rows


def flatten_alarms(path: Optional[Path], ctx: _Context) -> List[AlarmRow]:
    if not path or not path.exists():
        return []
    root = ET.parse(path).getroot()
    rows: List[AlarmRow] = []

    for alarm_class in _iter_by_local(root, {"AlarmClass", "AlarmGroup"}):
        class_name = _attr_ci(alarm_class, "Name", "DisplayName")
        class_id = _attr_ci(alarm_class, "ID", "Identifier", "Number")
        for alarm in _iter_by_local(alarm_class, {"Alarm", "AlarmMessage", "Message", "Event"}):
            alarm_name = _attr_ci(alarm, "Name", "DisplayName", "Text")
            alarm_id = _attr_ci(alarm, "ID", "Identifier", "Number")
            attributes = dict(alarm.attrib)
            translations = _extract_translations(alarm)
            if translations:
                for language, text in translations:
                    rows.append(
                        AlarmRow(
                            ctx.project,
                            ctx.target,
                            ctx.device,
                            ctx.software,
                            class_name,
                            class_id,
                            alarm_name,
                            alarm_id,
                            language,
                            text,
                            _json_dump(attributes),
                        )
                    )
                continue
            text_value = _attr_ci(alarm, "Text", "Message") or (alarm.text or "").strip()
            if not text_value:
                continue
            rows.append(
                AlarmRow(
                    ctx.project,
                    ctx.target,
                    ctx.device,
                    ctx.software,
                    class_name,
                    class_id,
                    alarm_name,
                    alarm_id,
                    "",
                    text_value,
                    _json_dump(attributes),
                )
            )
    return rows


def flatten_recipes(path: Optional[Path], ctx: _Context) -> List[RecipeRow]:
    if not path or not path.exists():
        return []
    root = ET.parse(path).getroot()
    rows: List[RecipeRow] = []

    def visit(node: ET.Element, recipe_name: str, recipe_id: str, trail: List[str]) -> None:
        for child in list(node):
            local = _local(child.tag)
            child_name = _attr_ci(child, "Name", "DisplayName")
            current_path = trail + [child_name or local]
            data_type = _attr_ci(child, "DataType", "Type", "ValueType")
            default_value = (
                _attr_ci(child, "Default", "DefaultValue", "Value")
                or (child.text or "").strip()
            )
            min_value = _attr_ci(child, "Min", "MinValue", "LowerLimit")
            max_value = _attr_ci(child, "Max", "MaxValue", "UpperLimit")
            attributes = _collect_properties(
                child,
                (
                    "Name",
                    "DisplayName",
                    "ID",
                    "DataType",
                    "Type",
                    "ValueType",
                    "Default",
                    "DefaultValue",
                    "Value",
                    "Min",
                    "MinValue",
                    "LowerLimit",
                    "Max",
                    "MaxValue",
                    "UpperLimit",
                ),
            )
            should_emit = child_name or data_type or default_value or attributes
            if should_emit:
                rows.append(
                    RecipeRow(
                        ctx.project,
                        ctx.target,
                        ctx.device,
                        ctx.software,
                        recipe_name,
                        recipe_id,
                        "/".join([part for part in current_path if part]),
                        child_name,
                        data_type,
                        default_value,
                        min_value,
                        max_value,
                        _json_dump(attributes),
                    )
                )
            visit(child, recipe_name, recipe_id, current_path)

    for recipe in _iter_by_local(root, {"Recipe"}):
        recipe_name = _attr_ci(recipe, "Name", "DisplayName")
        recipe_id = _attr_ci(recipe, "ID", "Identifier")
        origin = recipe_name or recipe_id or _local(recipe.tag)
        visit(recipe, recipe_name, recipe_id, [origin])

    return rows


def flatten_export_result(result: HmiExportResult, *, project_name: Optional[str] = None) -> FlattenedArtifacts:
    ctx = _context_from_target(result.target, project_name)
    return FlattenedArtifacts(
        text_lists=flatten_text_lists(result.text_list_path, ctx),
        screens=flatten_screens(result.screen_path, ctx),
        alarms=flatten_alarms(result.alarm_path, ctx),
        recipes=flatten_recipes(result.recipe_path, ctx),
    )


__all__ = [
    "TextListRow",
    "ScreenElementRow",
    "AlarmRow",
    "RecipeRow",
    "FlattenedArtifacts",
    "flatten_export_result",
    "flatten_text_lists",
    "flatten_screens",
    "flatten_alarms",
    "flatten_recipes",
]
