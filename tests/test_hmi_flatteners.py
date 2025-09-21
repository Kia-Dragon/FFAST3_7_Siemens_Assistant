import tempfile
import unittest
from pathlib import Path

from tia_tags_exporter.hmi_exporter import HmiExportResult, HmiTargetInfo
from tia_tags_exporter.hmi_flatteners import flatten_export_result

TEXT_LIST_AML = """<?xml version=\"1.0\" encoding=\"utf-8\"?>
<Document xmlns=\"urn:dummy\" xmlns:Text=\"urn:dummy:text\">
  <Text:TextList Name=\"StatusMessages\" ID=\"42\" Guid=\"{ABC}\">
    <Text:TextItem Name=\"Running\" ID=\"1\">
      <Text:LanguageText Language=\"en-US\">Running</Text:LanguageText>
      <Text:LanguageText Language=\"de-DE\" Text=\"Laeuft\" />
    </Text:TextItem>
    <Text:TextItem Name=\"Stopped\" ID=\"2\">
      <Text:LanguageText Language=\"en-US\" Text=\"Stopped\" />
    </Text:TextItem>
  </Text:TextList>
</Document>
"""

SCREEN_AML = """<?xml version=\"1.0\" encoding=\"utf-8\"?>
<Document xmlns=\"urn:dummy\" xmlns:Screen=\"urn:dummy:screen\">
  <Screen:Screen Name=\"MainScreen\" ID=\"100\">
    <Screen:Button Name=\"StartButton\" Left=\"10\" Top=\"20\">
      <Screen:Text>Start</Screen:Text>
    </Screen:Button>
    <Screen:IOField Name=\"SpeedField\" Tag=\"MotorSpeed\" Left=\"50\" Top=\"100\" />
  </Screen:Screen>
</Document>
"""

ALARM_AML = """<?xml version=\"1.0\" encoding=\"utf-8\"?>
<Document xmlns=\"urn:dummy\" xmlns:Alarm=\"urn:dummy:alarm\">
  <Alarm:AlarmClass Name=\"Process\" Number=\"5\">
    <Alarm:Alarm Name=\"Overheat\" Number=\"200\" Severity=\"Error\">
      <Alarm:Text Language=\"en-US\">Temperature high</Alarm:Text>
      <Alarm:Text Language=\"fr-FR\" Text=\"Temperature elevee\" />
    </Alarm:Alarm>
  </Alarm:AlarmClass>
</Document>
"""

RECIPE_AML = """<?xml version=\"1.0\" encoding=\"utf-8\"?>
<Document xmlns=\"urn:dummy\" xmlns:Recipe=\"urn:dummy:recipe\">
  <Recipe:Recipe Name=\"Mix1\" ID=\"7\">
    <Recipe:Parameter Name=\"Duration\" DataType=\"Int\" DefaultValue=\"10\" Min=\"0\" Max=\"120\" />
    <Recipe:Member Name=\"Speed\">
      <Recipe:Value DataType=\"Real\" Default=\"12.5\" LowerLimit=\"0\" UpperLimit=\"25\" />
    </Recipe:Member>
  </Recipe:Recipe>
</Document>
"""


def write_aml(directory: Path, name: str, content: str) -> Path:
    path = directory / name
    path.write_text(content, encoding="utf-8")
    return path


class HmiFlattenersTests(unittest.TestCase):
    def test_flatten_export_result(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hmi-flatten-test-") as tmp:
            tmp_path = Path(tmp)
            text_path = write_aml(tmp_path, "text_lists.aml", TEXT_LIST_AML)
            screen_path = write_aml(tmp_path, "screens.aml", SCREEN_AML)
            alarm_path = write_aml(tmp_path, "alarms.aml", ALARM_AML)
            recipe_path = write_aml(tmp_path, "recipes.aml", RECIPE_AML)

            target = HmiTargetInfo(
                device_name="HMI1",
                software_name="HMI_RT",
                identifier="HMI1::HMI_RT::Siemens.Engineering.Hmi.HmiTarget",
            )
            result = HmiExportResult(
                target=target,
                text_list_path=text_path,
                screen_path=screen_path,
                alarm_path=alarm_path,
                recipe_path=recipe_path,
            )

            flattened = flatten_export_result(result, project_name="ProjectX")

        running_en = next(
            row for row in flattened.text_lists if row.entry_name == "Running" and row.language == "en-US"
        )
        self.assertEqual(running_en.text, "Running")
        running_de = next(
            row for row in flattened.text_lists if row.entry_name == "Running" and row.language == "de-DE"
        )
        self.assertEqual(running_de.text, "Laeuft")

        screen_elements = {row.element_name for row in flattened.screens if row.element_name}
        self.assertTrue({"MainScreen", "StartButton", "SpeedField"}.issubset(screen_elements))

        alarm_languages = sorted(row.language for row in flattened.alarms)
        self.assertEqual(alarm_languages, ["en-US", "fr-FR"])
        overheat_en = next(row for row in flattened.alarms if row.language == "en-US")
        self.assertIn("Temperature", overheat_en.text)

        duration_row = next(row for row in flattened.recipes if row.item_name == "Duration")
        self.assertEqual(duration_row.data_type, "Int")
        self.assertEqual(duration_row.default_value, "10")

        value_row = next(row for row in flattened.recipes if row.item_path.endswith("Speed/Value"))
        self.assertEqual(value_row.min_value, "0")
        self.assertEqual(value_row.max_value, "25")


if __name__ == "__main__":
    unittest.main()
