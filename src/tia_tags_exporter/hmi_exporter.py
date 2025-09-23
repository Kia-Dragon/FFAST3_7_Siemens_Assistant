from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple, cast

import re


@dataclass
class HmiTargetInfo:
    device_name: str
    software_name: str
    identifier: str


@dataclass
class HmiExportResult:
    target: HmiTargetInfo
    text_list_path: Optional[Path] = None
    screen_path: Optional[Path] = None
    alarm_path: Optional[Path] = None
    recipe_path: Optional[Path] = None
    extras: Dict[str, Path] = field(default_factory=dict)


class HmiExporter:
    """Drive Siemens Openness exports for HMI assets.

    This module keeps the raw Openness calls isolated from the Qt layer so that we can
    mock and test the logic without a running TIA Portal instance. The exporter focuses
    on producing the native AML/XML payloads that Siemens generates for each HMI
    feature area (text lists, screens, alarms, and recipes). Flattening those XML
    payloads into tabular data is handled elsewhere.
    """

    def __init__(self, session: Any) -> None:
        self._session = session
        self._svc_provider_type: Optional[type[Any]] = None
        self._software_container_type: Optional[type[Any]] = None
        self._export_options = None
        self._file_info_type: Optional[type[Any]] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def list_targets(self) -> List[HmiTargetInfo]:
        provider, container = self._load_openness_types()
        project = getattr(self._session, "project", None)
        if not project:
            return []
        raw_devices = getattr(project, "Devices", None)
        devices = list(raw_devices) if raw_devices else []
        if not devices:
            return []

        targets: List[HmiTargetInfo] = []
        for device in devices:
            device_name = _safe_string(getattr(device, "Name", ""))
            raw_items = getattr(device, "DeviceItems", None)
            device_items = list(raw_items) if raw_items else []
            for item in device_items:
                try:
                    container_inst = provider(item).GetService[container]()
                except Exception:
                    continue
                if not container_inst:
                    continue
                software = getattr(container_inst, "Software", None)
                if not software:
                    continue
                if not self._is_hmi_software(software):
                    continue
                software_name = _safe_string(getattr(software, "Name", "")) or device_name
                identifier = self._make_target_identifier(device_name, software)
                targets.append(HmiTargetInfo(device_name, software_name, identifier))
        return targets

    def export_targets(
        self,
        out_dir: Path,
        target_filter: Optional[Iterable[str]] = None,
        progress: Optional[Callable[[str], None]] = None,
    ) -> List[HmiExportResult]:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        targets = self.list_targets()
        if target_filter:
            accepted = {ident.lower() for ident in target_filter}
            targets = [t for t in targets if t.identifier.lower() in accepted]
        if not targets:
            return []

        provider, container = self._load_openness_types()
        export_options = self._load_export_options()
        file_info_type = self._load_file_info()
        project = getattr(self._session, "project", None)
        raw_devices = getattr(project, "Devices", None) if project else None

        devices = list(raw_devices) if raw_devices else []

        targets_by_identifier = {t.identifier: t for t in targets}
        results: List[HmiExportResult] = []
        seen: Dict[str, HmiExportResult] = {}

        for device in devices:
            device_name = _safe_string(getattr(device, "Name", ""))
            raw_items = getattr(device, "DeviceItems", None)
            device_items = list(raw_items) if raw_items else []
            for item in device_items:
                try:
                    container_inst = provider(item).GetService[container]()
                except Exception:
                    continue
                if not container_inst:
                    continue
                software = getattr(container_inst, "Software", None)
                if not software:
                    continue
                if not self._is_hmi_software(software):
                    continue
                identifier = self._make_target_identifier(device_name, software)
                info = targets_by_identifier.get(identifier)
                if not info:
                    continue
                if progress and identifier not in seen:
                    progress(f"Exporting HMI target {info.software_name} ...")
                result = seen.get(identifier)
                if not result:
                    result = HmiExportResult(target=info)
                    seen[identifier] = result
                    results.append(result)
                self._export_bundle(software, info, out_dir, file_info_type, export_options, result, progress)

        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _load_openness_types(self) -> Tuple[type[Any], type[Any]]:
        if self._svc_provider_type and self._software_container_type:
            return self._svc_provider_type, self._software_container_type
        engineering = import_module("Siemens.Engineering")
        hw_features = import_module("Siemens.Engineering.HW.Features")
        provider = getattr(engineering, "IEngineeringServiceProvider")
        container = getattr(hw_features, "SoftwareContainer")
        self._svc_provider_type = provider
        self._software_container_type = container
        return provider, container

    def _load_export_options(self):
        if self._export_options is None:
            engineering = import_module("Siemens.Engineering")
            self._export_options = getattr(engineering, "ExportOptions")
        return self._export_options

    def _load_file_info(self) -> type[Any]:
        if self._file_info_type is None:
            system_io = import_module("System.IO")
            self._file_info_type = getattr(system_io, "FileInfo")
        return cast(type[Any], self._file_info_type)

    def _is_hmi_software(self, software: Any) -> bool:
        name = _get_type_name(software)
        if not name:
            return False
        return ".Hmi" in name or name.endswith("HmiTarget")

    def _make_target_identifier(self, device_name: str, software: Any | None) -> str:
        if software is None:
            return device_name
        sw_name = _safe_string(getattr(software, "Name", ""))
        type_name = _get_type_name(software) or ""
        base = f"{device_name}::{sw_name}" if sw_name else device_name
        if type_name:
            return f"{base}::{type_name}"
        return base



    def _export_bundle(
        self,
        software: Any,
        info: HmiTargetInfo,
        out_dir: Path,
        file_info_type: type[Any],
        export_options,
        result: HmiExportResult,
        progress: Optional[Callable[[str], None]],
    ) -> None:
        target_dir = out_dir / _sanitize_filename(info.identifier)
        target_dir.mkdir(parents=True, exist_ok=True)

        exports: List[Tuple[str, str]] = [
            ("TextListFolder", "text_lists"),
            ("ScreenFolder", "screens"),
            ("AlarmClasses", "alarms"),
            ("RecipeManagement", "recipes"),
        ]

        for attr_name, stem in exports:
            node = _get_attribute(software, attr_name)
            if not node:
                continue
            export_method = getattr(node, "Export", None)
            if not callable(export_method):
                continue
            out_path = target_dir / f"{stem}.aml"
            try:
                file_info = file_info_type(str(out_path))
                export_method(file_info, export_options.WithDefaults)
            except Exception as exc:
                if progress:
                    progress(f"Failed exporting {stem} for {info.software_name}: {exc}")
                continue
            if stem == "text_lists":
                result.text_list_path = out_path
            elif stem == "screens":
                result.screen_path = out_path
            elif stem == "alarms":
                result.alarm_path = out_path
            elif stem == "recipes":
                result.recipe_path = out_path
            else:
                result.extras[stem] = out_path
            if progress:
                progress(f"Exported {stem} for {info.software_name} -> {out_path}")


# ----------------------------------------------------------------------
# Helper utilities
# ----------------------------------------------------------------------

def _safe_string(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _get_type_name(obj: Any) -> str:
    try:
        typ = obj.GetType()
    except Exception:
        return ""
    return _safe_string(getattr(typ, "FullName", ""))


def _sanitize_filename(name: str) -> str:
    if not name:
        return "tia-hmi"
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", name)
    return cleaned.strip("._") or "tia-hmi"


def _get_attribute(obj: Any, attr_name: str) -> Any | None:
    direct = getattr(obj, attr_name, None)
    if direct is not None:
        return direct
    # fall back to case-insensitive reflection search
    try:
        typ = obj.GetType()
        props = typ.GetProperties()
    except Exception:
        return None
    attr_lower = attr_name.lower()
    for prop in props:
        name = _safe_string(getattr(prop, "Name", ""))
        if not name:
            continue
        if name.lower() != attr_lower:
            continue
        try:
            return prop.GetValue(obj, None)
        except Exception:
            continue
    return None


__all__ = [
    "HmiExporter",
    "HmiExportResult",
    "HmiTargetInfo",
]





