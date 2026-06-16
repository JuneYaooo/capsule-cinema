import importlib.util
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


if __name__ == "__main__":
    unittest.main()
