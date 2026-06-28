import json
import sys
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))

from src.capsule_preflight import run_preflight  # noqa: E402
from src.capsule_resolver import load_all_tools  # noqa: E402

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
    def packaged_capsule_names(self) -> list[str]:
        return sorted(path.stem.removesuffix(".capsule") for path in (ROOT / "capsules").glob("*.capsule.zip"))

    def load_capsule(self, name: str) -> dict:
        package_path = ROOT / "capsules" / f"{name}.capsule.zip"
        self.assertTrue(package_path.is_file(), f"missing package: {package_path}")
        with zipfile.ZipFile(package_path) as package:
            manifest = json.loads(package.read("manifest.json").decode("utf-8"))
        return manifest["capsule"]

    def test_packaged_capsules_are_exported_with_roles_schema(self):
        for name in self.packaged_capsule_names():
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

    def test_packaged_capsule_roles_preflight_clean_with_full_registered_env(self):
        tools = load_all_tools()
        env_registry = json.loads((ROOT / "lib" / "config" / "env_registry.json").read_text(encoding="utf-8"))
        available_env = {entry["key"] for entry in env_registry["env"]}

        for name in self.packaged_capsule_names():
            with self.subTest(capsule=name):
                capsule = self.load_capsule(name)
                config = capsule["config"]
                preflight = run_preflight(
                    {
                        "name": capsule["name"],
                        "roles": config.get("roles", {}),
                        "output_contract": config.get("output_contract", {}),
                    },
                    tools,
                    available_env,
                )

                self.assertEqual(
                    preflight.status,
                    "ok",
                    f"{name} should not require substitutions or blockers with all registered env available",
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
