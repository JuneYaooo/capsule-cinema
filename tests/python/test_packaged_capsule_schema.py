import json
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
README_EXAMPLE_CAPSULES = [
    "repo_showcase",
    "art_motion",
    "felt_asmr",
    "life_sim",
    "guofeng_history",
]
LEGACY_CONFIG_KEYS = {
    "image_engine",
    "video_engine",
    "action_engine",
    "lip_sync_engine",
    "tts_provider",
    "tts_voice",
    "has_narration",
    "has_subtitle",
    "has_bgm",
    "add_subtitles",
    "add_background_music",
    "add_bgm",
    "bgm",
    "mode",
}


class PackagedCapsuleSchemaTest(unittest.TestCase):
    def load_capsule(self, name: str) -> dict:
        package_path = ROOT / "capsules" / f"{name}.capsule.zip"
        self.assertTrue(package_path.is_file(), f"missing package: {package_path}")
        with zipfile.ZipFile(package_path) as package:
            manifest = json.loads(package.read("manifest.json").decode("utf-8"))
        return manifest["capsule"]

    def test_readme_example_capsules_are_exported_with_roles_schema(self):
        for name in README_EXAMPLE_CAPSULES:
            with self.subTest(capsule=name):
                capsule = self.load_capsule(name)
                config = capsule["config"]

                self.assertIn("roles", config)
                self.assertIsInstance(config["roles"], dict)
                self.assertIn("output_contract", config)
                self.assertIsInstance(config["output_contract"], dict)
                self.assertFalse(
                    LEGACY_CONFIG_KEYS & set(config),
                    f"{name} still has legacy config keys: {LEGACY_CONFIG_KEYS & set(config)}",
                )

    def test_life_sim_schema_uses_image_fallback_without_invalid_video_role(self):
        capsule = self.load_capsule("life_sim")
        config = capsule["config"]

        self.assertEqual(config["visual_generation_type"], "still_images_with_ken_burns")
        self.assertNotIn("video", config["roles"])
        self.assertEqual(config["roles"]["image"]["validated_with"], "GptImage2Tool")
        self.assertEqual(config["output_contract"]["voice"], "unified_tts")

    def test_guofeng_packaged_run_history_uses_success_status(self):
        capsule = self.load_capsule("guofeng_history")
        statuses = {item.get("status") for item in capsule.get("run_history", [])}

        self.assertNotIn("pass", statuses)
        self.assertIn("success", statuses)


if __name__ == "__main__":
    unittest.main()
