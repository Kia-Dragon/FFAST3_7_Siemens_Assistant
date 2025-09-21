
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tia_tags_exporter.hmi_exporter import HmiExporter, _sanitize_filename


class FakeFileInfo:
    def __init__(self, path: str) -> None:
        self.path = path


class FakeExportNode:
    def __init__(self, key: str) -> None:
        self.key = key
        self.calls: list[tuple[str, str]] = []

    def Export(self, file_info: FakeFileInfo, options) -> None:  # noqa: N802 - mimic .NET API
        out_path = Path(file_info.path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(f"export:{self.key}:{options}", encoding="utf-8")
        self.calls.append((file_info.path, str(options)))


class FakeGetService:
    def __init__(self, container) -> None:
        self._container = container

    def __getitem__(self, item):  # noqa: D401 - mimic .NET indexer
        return lambda: self._container


class FakeProviderInstance:
    def __init__(self, container) -> None:
        self._container = container
        self.GetService = FakeGetService(container)


def fake_provider(item):
    return FakeProviderInstance(item._container)


class FakeSoftwareContainer:
    def __init__(self, software) -> None:
        self.Software = software


class FakeDeviceItem:
    def __init__(self, software) -> None:
        self._container = FakeSoftwareContainer(software)


class FakeHmiSoftware:
    def __init__(self, name: str) -> None:
        self.Name = name
        self.TextListFolder = FakeExportNode("text_lists")
        self.ScreenFolder = FakeExportNode("screens")
        self.AlarmClasses = FakeExportNode("alarms")
        self.RecipeManagement = FakeExportNode("recipes")

    def GetType(self):  # noqa: N802 - mimic .NET API
        return SimpleNamespace(FullName="Siemens.Engineering.Hmi.FakeTarget")


class FakeDevice:
    def __init__(self, name: str, software: FakeHmiSoftware) -> None:
        self.Name = name
        self.DeviceItems = [FakeDeviceItem(software)]


class FakeProject:
    def __init__(self, devices) -> None:
        self.Devices = devices


class FakeSession:
    def __init__(self, devices) -> None:
        self.project = FakeProject(devices)
        self.project_name = "TestProject"


def fake_import(name: str):
    if name == "Siemens.Engineering":
        return SimpleNamespace(
            IEngineeringServiceProvider=fake_provider,
            ExportOptions=SimpleNamespace(WithDefaults="defaults"),
        )
    if name == "Siemens.Engineering.HW.Features":
        return SimpleNamespace(SoftwareContainer=FakeSoftwareContainer)
    if name == "System.IO":
        return SimpleNamespace(FileInfo=FakeFileInfo)
    raise ImportError(name)


class HmiExporterTests(unittest.TestCase):
    def test_exports_expected_files(self) -> None:
        software = FakeHmiSoftware("HMI Target")
        device = FakeDevice("HMI Panel", software)
        session = FakeSession([device])

        with patch("tia_tags_exporter.hmi_exporter.import_module", side_effect=fake_import):
            exporter = HmiExporter(session)
            targets = exporter.list_targets()
            self.assertEqual(len(targets), 1)
            identifier = targets[0].identifier
            self.assertIn("HMI Panel", identifier)
            self.assertIn("HMI Target", identifier)

            with tempfile.TemporaryDirectory() as tmp_dir:
                out_dir = Path(tmp_dir)
                results = exporter.export_targets(out_dir)

                self.assertEqual(len(results), 1)
                result = results[0]
                target_root = out_dir / _sanitize_filename(identifier)

                self.assertEqual(result.text_list_path, target_root / "text_lists.aml")
                self.assertEqual(result.screen_path, target_root / "screens.aml")
                self.assertEqual(result.alarm_path, target_root / "alarms.aml")
                self.assertEqual(result.recipe_path, target_root / "recipes.aml")

                for expected in (
                    result.text_list_path,
                    result.screen_path,
                    result.alarm_path,
                    result.recipe_path,
                ):
                    self.assertIsNotNone(expected)
                    assert expected is not None
                    self.assertTrue(expected.exists())
                    self.assertTrue(expected.read_text(encoding="utf-8").startswith("export:"))


if __name__ == "__main__":
    unittest.main()



