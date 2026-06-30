import json
import sys
import unittest
from pathlib import Path


TEST_DIR = Path(__file__).resolve().parent
if str(TEST_DIR) not in sys.path:
    sys.path.insert(0, str(TEST_DIR))

from capsule_package_test_utils import load_active_capsule, recipe_text


class GuofengHistoricalExplainerCapsuleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.capsule = load_active_capsule("guofeng_history")

    def test_capsule_uses_public_unversioned_name(self):
        self.assertEqual(self.capsule["name"], "guofeng_history")
        self.assertEqual(self.capsule["display_name"], "国风历史人物讲解")
        self.assertEqual(self.capsule["version"], 5)

    def test_capsule_forbids_voiceover_padding_and_requires_continuous_narration(self):
        config = self.capsule["config"]
        quality_rules = self.capsule["quality_rules"]
        rules_text = recipe_text(self.capsule) + json.dumps(quality_rules, ensure_ascii=False)

        self.assertEqual(config["output_contract"]["voice"], "unified_tts")
        self.assertIn("continuous_voiceover_no_padding", {item["id"] for item in quality_rules})
        self.assertIn("no per-scene audio padding", rules_text)
        self.assertIn("Cut visuals to narration", rules_text)

    def test_capsule_requires_distinct_first_frames_for_story_beats(self):
        quality_rules = self.capsule["quality_rules"]
        rules_text = recipe_text(self.capsule) + json.dumps(quality_rules, ensure_ascii=False)

        self.assertIn("distinct_first_frame_per_scene", {item["id"] for item in quality_rules})
        self.assertIn("one distinct generated first frame", rules_text)
        self.assertIn("Do not split one source image or source clip into multiple story beats", rules_text)

    def test_capsule_requires_segment_first_frame_review_artifact(self):
        quality_rules = self.capsule["quality_rules"]
        rule_ids = {item["id"] for item in quality_rules}
        rules_text = recipe_text(self.capsule) + json.dumps(quality_rules, ensure_ascii=False)

        self.assertIn("segment_first_frame_contact_sheet_required", rule_ids)
        self.assertIn("segment_first_frames_contact_sheet", rules_text)

    def test_capsule_requires_real_motion_video_not_static_zoompan_final(self):
        config = self.capsule["config"]
        quality_rules = self.capsule["quality_rules"]
        rule_ids = {item["id"] for item in quality_rules}
        rules_text = recipe_text(self.capsule) + json.dumps(quality_rules, ensure_ascii=False)

        self.assertEqual(config["roles"]["video"]["requires"], ["image_to_video"])
        self.assertTrue(config["static_zoompan_fallback_preview_only"])
        self.assertTrue(config["require_real_motion_video_segments"])
        self.assertIn("real_motion_video_segments_required", rule_ids)
        self.assertIn("Static zoompan fallback is preview-only", rules_text)
        self.assertIn("must not be marked pass", rules_text)

    def test_capsule_requires_semantic_visual_timeline_not_equal_scene_splits(self):
        quality_rules = self.capsule["quality_rules"]
        rule_ids = {item["id"] for item in quality_rules}
        rules_text = recipe_text(self.capsule) + json.dumps(quality_rules, ensure_ascii=False)

        self.assertIn("semantic_visual_timeline_required", rule_ids)
        self.assertIn("Equal-duration visual splitting is preview-only", rules_text)
        self.assertIn("derive scene start/end times from narration meaning units", rules_text)

    def test_capsule_requires_character_bible_and_reference_sheet_before_storyboard_images(self):
        quality_rules = self.capsule["quality_rules"]
        rule_ids = {item["id"] for item in quality_rules}
        rules_text = recipe_text(self.capsule) + json.dumps(quality_rules, ensure_ascii=False)

        self.assertIn("character_bible_required", rule_ids)
        self.assertIn("character_consistency_required", rule_ids)
        self.assertIn("Before storyboard image generation, provide a character bible", rules_text)
        self.assertIn("Yang Zhen", rules_text)
        self.assertIn("Wang Mi", rules_text)
        self.assertIn("canonical character reference sheet", rules_text)

    def test_character_reference_locks_identity_not_pose_or_layout(self):
        quality_rules = self.capsule["quality_rules"]
        rule_ids = {item["id"] for item in quality_rules}
        rules_text = recipe_text(self.capsule) + json.dumps(quality_rules, ensure_ascii=False)

        self.assertIn("reference_identity_not_pose_lock", rule_ids)
        self.assertIn("scene_appropriate_character_variation_required", rule_ids)
        self.assertIn("lock identity", rules_text)
        self.assertIn("exact pose, action, camera angle, layout, location", rules_text)
        self.assertIn("side, back, three-quarter, distant, silhouette", rules_text.lower())
        self.assertIn("full front-facing", rules_text)


if __name__ == "__main__":
    unittest.main()
