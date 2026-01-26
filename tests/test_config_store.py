
import tempfile
import unittest
from pathlib import Path

from tia_tags_exporter.config_store import ProfileStore
from tia_tags_exporter.settings import DllProfile


class TestConfigStore(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = ProfileStore(Path(self.temp_dir.name))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_save_and_load_v17_profile(self):
        profile = DllProfile(
            tia_version="V17",
            public_api_dir=Path("C:/TIA/V17"),
            file_version="17.0.0.0",
            public_key_token="1234567890abcdef",
        )
        self.store.set_profile(profile)

        loaded_profile = self.store.get_profile("V17")
        self.assertIsNotNone(loaded_profile)
        self.assertEqual(profile.tia_version, loaded_profile.tia_version)
        self.assertEqual(str(profile.public_api_dir), str(loaded_profile.public_api_dir))
        self.assertEqual(profile.file_version, loaded_profile.file_version)
        self.assertEqual(profile.public_key_token, loaded_profile.public_key_token)

    def test_save_and_load_v18_profile(self):
        profile = DllProfile(
            tia_version="V18",
            public_api_dir=Path("C:/TIA/V18"),
            file_version="18.0.0.0",
            public_key_token="fedcba0987654321",
        )
        self.store.set_profile(profile)

        loaded_profile = self.store.get_profile("V18")
        self.assertIsNotNone(loaded_profile)
        self.assertEqual(profile.tia_version, loaded_profile.tia_version)
        self.assertEqual(str(profile.public_api_dir), str(loaded_profile.public_api_dir))
        self.assertEqual(profile.file_version, loaded_profile.file_version)
        self.assertEqual(profile.public_key_token, loaded_profile.public_key_token)

    def test_load_non_existent_profile(self):
        loaded_profile = self.store.get_profile("V19")
        self.assertIsNone(loaded_profile)

if __name__ == "__main__":
    unittest.main()
