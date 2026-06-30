import json
import sys
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
if str(TEST_DIR) not in sys.path:
    sys.path.insert(0, str(TEST_DIR))

from capsule_package_test_utils import (
    active_capsule_dir,
    load_active_capsule,
    package_files,
    package_relative_path,
    read_package_text,
    recipe_text,
)


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
        return sorted(path.name.removesuffix(".capsule") for path in (ROOT / "capsules").glob("*.capsule"))

    def load_capsule(self, name: str) -> dict:
        capsule_dir = active_capsule_dir(name)
        self.assertTrue((capsule_dir / "capsule.yaml").is_file(), f"missing package: {capsule_dir}")
        return load_active_capsule(name)

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

        self.assertEqual(config["visual_generation_type"], "unique_image2_keyframes_with_micro_cuts")
        self.assertNotIn("video", config["roles"])
        self.assertEqual(config["roles"]["image"]["validated_with"], "GptImage2Tool")
        self.assertEqual(config["output_contract"]["voice"], "unified_tts")

    def test_life_sim_is_execution_capsule_with_local_script(self):
        capsule = self.load_capsule("life_sim")
        files = package_files("life_sim")
        local_script = package_relative_path("life_sim", capsule["local_script_path"])

        self.assertEqual(capsule["execution_mode"], "local_script")
        self.assertTrue(capsule["local_script_path"])
        self.assertIn(local_script, files)

        source = read_package_text("life_sim", local_script)
        self.assertIn("--topic", source)
        self.assertIn("--params", source)
        self.assertIn("--output-dir", source)
        self.assertIn("unique_image2_keyframes", source)

    def test_life_sim_opening_template_is_asset_backed_and_tts_adaptive(self):
        capsule = self.load_capsule("life_sim")
        files = package_files("life_sim")
        config = capsule["config"]
        method_text = recipe_text(capsule)
        local_assets = {item["key"]: item for item in capsule["local_assets"]}
        opening_template = config.get("opening_template", {})

        self.assertEqual(opening_template.get("style"), "life_object_shaker")
        self.assertEqual(opening_template.get("tts_policy"), "use_unified_story_tts_or_supplied_opening_tts_audio")
        self.assertIn("series_title", opening_template.get("tts_required_lines", []))
        self.assertIn("episode_topic", opening_template.get("tts_required_lines", []))
        self.assertGreaterEqual(opening_template.get("readability", {}).get("result_title_min_font_px", 0), 72)
        self.assertNotIn("fixed_tts_text", opening_template)
        self.assertEqual(opening_template.get("background_assets", {}).get("9:16"), "life_shaker_background_9x16")
        self.assertEqual(opening_template.get("background_assets", {}).get("16:9"), "life_shaker_background_16x9")
        self.assertEqual(opening_template.get("renderer_asset"), "life_shaker_opening_renderer")

        self.assertNotIn("story_formula", method_text)
        self.assertNotIn("scene_pool", method_text)

        for key in (
            "life_shaker_background_9x16",
            "life_shaker_background_16x9",
            "life_shaker_sfx",
            "life_shaker_opening_renderer",
        ):
            self.assertIn(key, local_assets)
            self.assertIn(package_relative_path("life_sim", local_assets[key]["path"]), files)

        renderer_path = package_relative_path("life_sim", local_assets["life_shaker_opening_renderer"]["path"])
        renderer_source = read_package_text("life_sim", renderer_path)
        self.assertIn("--tts-audio", renderer_source)
        self.assertIn("--result-title", renderer_source)
        self.assertIn("--candidate-terms", renderer_source)
        self.assertNotIn("出租屋风水大师", renderer_source)

    def test_life_sim_body_subtitles_micro_cuts_and_voice_contract(self):
        capsule = self.load_capsule("life_sim")
        config = capsule["config"]
        method_text = recipe_text(capsule)
        rule_ids = {item.get("id") for item in capsule["quality_rules"]}

        self.assertEqual(config["output_contract"]["subtitle"], "none")
        self.assertFalse(config["body_subtitles_default"])
        self.assertGreaterEqual(config["micro_cut_seconds"]["min"], 1.0)
        self.assertLessEqual(config["micro_cut_seconds"]["max"], 3.0)
        self.assertEqual(config["micro_cut_visual_source"], "unique_image2_keyframe_per_cut")
        self.assertTrue(config["distinct_body_image_per_micro_cut_required"])
        self.assertTrue(config["body_image_content_hash_unique_required"])
        serialized_capsule = json.dumps(capsule, ensure_ascii=False)
        self.assertEqual(config["roles"]["voice"]["provider"], "minimax")
        self.assertEqual(config["roles"]["voice"]["validated_with"], "minimax/male_narrator")
        self.assertEqual(config["roles"]["voice"]["default_voice_type"], "male_narrator")
        self.assertFalse(config["roles"]["voice"]["allow_silent_fallback"])
        self.assertEqual(config["tts_provider_default"], "minimax")
        self.assertEqual(config["tts_default_voice_type"], "male_narrator")
        self.assertEqual(config["tts_speed"], 1.18)
        self.assertEqual(config["tts_speed_range"], [1.18, 1.18])
        self.assertFalse(config["tts_voice_preflight_required"])
        self.assertIn("MiniMax male_narrator", method_text)
        self.assertNotIn("zh_male_qingxian", serialized_capsule)
        self.assertNotIn("Chinese (Mandarin)_Radio_Host", serialized_capsule)
        self.assertIn("不要说教", method_text)
        self.assertIn("短剧", method_text)
        self.assertIn("荒诞", method_text)
        self.assertIn("正文无底部字幕", method_text)
        self.assertIn("独立 Image2", method_text)
        self.assertIn("内容哈希", method_text)
        self.assertIn("opening_series_tts_required", rule_ids)
        self.assertIn("opening_duration_guard", rule_ids)
        self.assertIn("body_subtitles_disabled_by_default", rule_ids)
        self.assertIn("micro_cut_density_enforced", rule_ids)
        self.assertIn("energetic_tts_required", rule_ids)
        self.assertIn("no_moralizing_voiceover", rule_ids)
        self.assertIn("short_drama_absurdity_required", rule_ids)
        self.assertNotIn("tts_voice_grant_preflight_required", rule_ids)
        self.assertIn("distinct_image2_keyframe_per_micro_cut", rule_ids)
        self.assertIn("distinct_image2_content_per_micro_cut", rule_ids)
        self.assertEqual(
            config["opening_template"]["duration_seconds"]["max_rendered_seconds_without_user_override"],
            4.5,
        )
        self.assertLessEqual(config["opening_template"]["opening_tts_max_chars"], 24)
        self.assertIn("opening_manifest.duration", method_text)

    def test_life_sim_story_and_visual_rules_are_flexible(self):
        capsule = self.load_capsule("life_sim")
        method_text = recipe_text(capsule)

        self.assertIn("story_principles", method_text)
        self.assertIn("flexible_arc_policy", method_text)
        self.assertNotIn("story_formula", method_text)
        self.assertNotIn("scene_pool", method_text)

        self.assertIn("剧情跌宕", method_text)
        self.assertIn("适配完整故事", method_text)

    def test_active_packages_do_not_carry_run_history_evidence(self):
        capsule = self.load_capsule("guofeng_history")

        self.assertNotIn("run_history", capsule)
        self.assertNotIn("feedback", capsule)
        self.assertNotIn("changelog", capsule)


if __name__ == "__main__":
    unittest.main()
