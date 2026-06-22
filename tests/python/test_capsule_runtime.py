import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CAPSULE_RUNTIME_PATH = ROOT / "scripts" / "capsule_runtime.py"


def load_capsule_runtime():
    spec = importlib.util.spec_from_file_location("capsule_runtime", CAPSULE_RUNTIME_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CapsuleRuntimeAssetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = load_capsule_runtime()

    def test_runtime_defaults_use_packaged_default_bgm_asset(self):
        with tempfile.TemporaryDirectory() as tmp:
            bgm_path = Path(tmp) / "manten_diloty.mp3"
            bgm_path.write_bytes(b"fake mp3")
            capsule = {
                "config": {
                    "add_background_music": True,
                    "default_bgm_asset": bgm_path.name,
                    "bgm_volume": 0.42,
                },
                "local_assets": [
                    {
                        "key": "manten_diloty_bgm",
                        "role": "bgm",
                        "path": str(bgm_path),
                        "tags": ["default"],
                    }
                ],
            }

            defaults = self.runtime.capsule_runtime_defaults(capsule)

            self.assertEqual(defaults["background_music_path"], str(bgm_path))
            self.assertEqual(defaults["background_music_asset_key"], "manten_diloty_bgm")
            self.assertEqual(defaults["bgm_volume"], 0.42)

    def test_capsule_prompt_includes_local_asset_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            asset_path = Path(tmp) / "reference.png"
            asset_path.write_bytes(b"png")
            capsule = {
                "name": "asset_capsule",
                "display_name": "Asset Capsule",
                "category": "repo_showcase",
                "description": "test capsule",
                "config": {"add_background_music": True},
                "method": {},
                "quality_rules": [],
                "local_assets": [
                    {
                        "key": "reference_image",
                        "role": "reference_image",
                        "path": str(asset_path),
                        "description": "Reference frame",
                        "tags": ["default"],
                    }
                ],
            }

            prompt = self.runtime.build_capsule_prompt(capsule, "make a short video")

            self.assertIn('"local_assets"', prompt)
            self.assertIn('"reference_image"', prompt)
            self.assertIn('"exists": true', prompt)

    def _write_capsule_row(self, db_path: Path, name: str, display_name: str = "Test Capsule") -> None:
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS capsules (
                    name TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    execution_mode TEXT NOT NULL,
                    description TEXT NOT NULL,
                    category TEXT NOT NULL,
                    tags_json TEXT NOT NULL,
                    config_json TEXT NOT NULL,
                    method_json TEXT NOT NULL,
                    input_schema_json TEXT NOT NULL,
                    quality_rules_json TEXT NOT NULL,
                    local_assets_json TEXT NOT NULL,
                    local_script_path TEXT NOT NULL,
                    version INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                """
                INSERT INTO capsules (
                    name, display_name, status, execution_mode, description,
                    category, tags_json, config_json, method_json, input_schema_json,
                    quality_rules_json, local_assets_json, local_script_path, version
                )
                VALUES (?, ?, 'active', 'preset', 'test', 'test', '[]', '{}', '{}', '{}', '[]', '[]', '', 1)
                """,
                (name, display_name),
            )
            conn.commit()

    def test_load_capsule_accepts_public_short_name_alias(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "capsules.sqlite"
            self._write_capsule_row(db_path, "digital_human_presenter_v1", "Legacy Digital Human")

            capsule = self.runtime.load_capsule("digital_human", str(db_path))

        self.assertEqual(capsule["name"], "digital_human_presenter_v1")
        self.assertEqual(capsule["display_name"], "Legacy Digital Human")

    def test_load_capsule_direct_short_name_wins_over_alias(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "capsules.sqlite"
            self._write_capsule_row(db_path, "digital_human_presenter_v1", "Legacy Digital Human")
            self._write_capsule_row(db_path, "digital_human", "Short Digital Human")

            capsule = self.runtime.load_capsule("digital_human", str(db_path))

        self.assertEqual(capsule["name"], "digital_human")
        self.assertEqual(capsule["display_name"], "Short Digital Human")

    def test_load_capsule_short_name_can_try_multiple_legacy_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "capsules.sqlite"
            self._write_capsule_row(db_path, "healing_asmr_food_daily_v1", "Healing ASMR")

            capsule = self.runtime.load_capsule("felt_asmr", str(db_path))

        self.assertEqual(capsule["name"], "healing_asmr_food_daily_v1")

    def test_load_capsule_accepts_general_healing_asmr_short_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "capsules.sqlite"
            self._write_capsule_row(db_path, "healing_asmr_food_daily_v1", "Healing ASMR")

            capsule = self.runtime.load_capsule("healing_asmr", str(db_path))

        self.assertEqual(capsule["name"], "healing_asmr_food_daily_v1")


if __name__ == "__main__":
    unittest.main()
