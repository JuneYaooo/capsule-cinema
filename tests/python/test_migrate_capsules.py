import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from migrate_capsules_to_roles import (  # noqa: E402
    canon_engine,
    migrate_capsule,
)


class CanonEngineTest(unittest.TestCase):
    def test_short_names_map_to_class_names(self):
        self.assertEqual(canon_engine("seedance-fast"), "SeedanceFastVideoGeneratorTool")
        self.assertEqual(canon_engine("gemini3_pro"), "Gemini3ProImageGeneratorTool")
        self.assertEqual(canon_engine("grok"), "GrokVideoGeneratorTool")

    def test_already_canonical_passes_through(self):
        self.assertEqual(canon_engine("GptImage2Tool"), "GptImage2Tool")


class MigrateGuofengTest(unittest.TestCase):
    def setUp(self):
        self.cfg = {
            "image_engine": "GptImage2Tool",
            "video_engine": "SeedanceFastVideoGeneratorTool",
            "tts_provider": "minimax",
            "tts_voice": "Chinese_deep_voiced_male_vv1",
            "subtitle_style": "transparent_png_inkwash_gold_v7",
        }
        self.result = migrate_capsule(self.cfg, category="culture", name="guofeng_history")

    def test_roles_carry_validated_with(self):
        roles = self.result["roles"]
        self.assertEqual(roles["image"]["validated_with"], "GptImage2Tool")
        self.assertEqual(roles["video"]["validated_with"], "SeedanceFastVideoGeneratorTool")
        self.assertEqual(roles["voice"]["validated_with"], "minimax/Chinese_deep_voiced_male_vv1")
        self.assertIn("image_to_video", roles["video"]["requires"])

    def test_output_contract_matches_design(self):
        oc = self.result["output_contract"]
        self.assertEqual(oc["clip_audio"], "silent")
        self.assertEqual(oc["voice"], "unified_tts")
        self.assertEqual(oc["on_frame_text"], "none")
        self.assertEqual(oc["subtitle"], "overlay")
        self.assertEqual(oc["bgm"], "external")


class MigrateAsmrTest(unittest.TestCase):
    def setUp(self):
        self.cfg = {
            "image_engine": "gemini3_pro",
            "video_engine": "jimeng35pro",
            "has_narration": False,
            "add_subtitles": False,
            "add_background_music": False,
        }
        self.result = migrate_capsule(self.cfg, category="healing", name="healing-asmr")

    def test_native_audio_required_and_no_voice(self):
        self.assertIn("native_audio", self.result["roles"]["video"]["requires"])
        self.assertEqual(self.result["output_contract"]["clip_audio"], "native")
        self.assertEqual(self.result["output_contract"]["voice"], "none")
        self.assertEqual(self.result["output_contract"]["bgm"], "none")


class MigrateNoNarrationTest(unittest.TestCase):
    def test_tts_provider_without_narration_does_not_create_voice_role(self):
        cfg = {
            "image_engine": "seedream5",
            "video_engine": "veo3.1",
            "tts_provider": "minimax",
            "tts_voice": "some_legacy_voice",
            "has_narration": False,
            "add_subtitles": True,
            "add_background_music": True,
        }

        result = migrate_capsule(cfg, category="art_transition", name="art_motion")

        self.assertNotIn("voice", result["roles"])
        self.assertEqual(result["output_contract"]["voice"], "none")


class MigrateImageFallbackRouteTest(unittest.TestCase):
    def test_still_image_route_does_not_create_video_role(self):
        cfg = {
            "image_engine": "gpt-image-2",
            "video_engine": "none_for_default_route",
            "visual_generation_type": "still_images_with_ken_burns",
            "tts_provider": "minimax",
            "tts_voice": "Chinese_deep_voiced_male_vv1",
            "has_narration": True,
            "add_subtitles": True,
            "add_background_music": True,
        }

        result = migrate_capsule(cfg, category="douyin_story_voiceover", name="life_sim")

        self.assertEqual(result["roles"]["image"]["validated_with"], "GptImage2Tool")
        self.assertNotIn("video", result["roles"])
        self.assertEqual(result["roles"]["voice"]["validated_with"], "minimax/Chinese_deep_voiced_male_vv1")
        self.assertEqual(result["output_contract"]["voice"], "unified_tts")


if __name__ == "__main__":
    unittest.main()
