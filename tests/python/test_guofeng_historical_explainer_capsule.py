import json
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CAPSULE_PATH = ROOT / "capsules" / "guofeng_history_explainer.capsule.zip"


class GuofengHistoricalExplainerCapsuleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with zipfile.ZipFile(CAPSULE_PATH) as package:
            manifest = json.loads(package.read("manifest.json").decode("utf-8"))
        cls.capsule = manifest["capsule"]

    def test_capsule_uses_public_unversioned_name(self):
        self.assertEqual(self.capsule["name"], "guofeng_history_explainer")
        self.assertEqual(self.capsule["display_name"], "国风历史人物讲解")
        self.assertEqual(self.capsule["version"], 5)

    def test_capsule_forbids_voiceover_padding_and_requires_continuous_narration(self):
        config = self.capsule["config"]
        method = self.capsule["method"]
        quality_rules = self.capsule["quality_rules"]
        rules_text = json.dumps(method, ensure_ascii=False) + json.dumps(quality_rules, ensure_ascii=False)

        self.assertEqual(config["audio_assembly_policy"], "continuous_full_track")
        self.assertTrue(config["forbid_segmented_tts_padding"])
        self.assertIn("continuous_voiceover_no_padding", {item["id"] for item in quality_rules})
        self.assertIn("no per-scene audio padding", rules_text)
        self.assertIn("Cut visuals to narration", rules_text)

    def test_capsule_requires_distinct_first_frames_for_story_beats(self):
        config = self.capsule["config"]
        method = self.capsule["method"]
        quality_rules = self.capsule["quality_rules"]
        rules_text = json.dumps(method, ensure_ascii=False) + json.dumps(quality_rules, ensure_ascii=False)

        self.assertTrue(config["scene_visual_uniqueness_required"])
        self.assertIn("distinct_first_frame_per_scene", {item["id"] for item in quality_rules})
        self.assertIn("one distinct generated first frame", rules_text)
        self.assertIn("Do not split one source image or source clip into multiple story beats", rules_text)

    def test_capsule_requires_segment_first_frame_review_artifact(self):
        config = self.capsule["config"]
        method = self.capsule["method"]
        quality_rules = self.capsule["quality_rules"]
        rule_ids = {item["id"] for item in quality_rules}
        rules_text = json.dumps(method, ensure_ascii=False) + json.dumps(quality_rules, ensure_ascii=False)

        self.assertTrue(config["segment_first_frame_contact_sheet_required"])
        self.assertIn("segment_first_frame_contact_sheet_required", rule_ids)
        self.assertIn("segment_first_frames_contact_sheet", rules_text)

    def test_capsule_requires_real_motion_video_not_static_zoompan_final(self):
        config = self.capsule["config"]
        method = self.capsule["method"]
        quality_rules = self.capsule["quality_rules"]
        rule_ids = {item["id"] for item in quality_rules}
        rules_text = json.dumps(method, ensure_ascii=False) + json.dumps(quality_rules, ensure_ascii=False)

        self.assertEqual(config["visual_motion_policy"], "image_to_video_per_scene")
        self.assertTrue(config["static_zoompan_fallback_preview_only"])
        self.assertTrue(config["require_real_motion_video_segments"])
        self.assertIn("real_motion_video_segments_required", rule_ids)
        self.assertIn("static zoompan fallback is preview-only", rules_text)
        self.assertIn("must not be marked pass", rules_text)

    def test_capsule_requires_semantic_visual_timeline_not_equal_scene_splits(self):
        config = self.capsule["config"]
        method = self.capsule["method"]
        quality_rules = self.capsule["quality_rules"]
        rule_ids = {item["id"] for item in quality_rules}
        rules_text = json.dumps(method, ensure_ascii=False) + json.dumps(quality_rules, ensure_ascii=False)

        self.assertEqual(config["visual_narration_alignment_policy"], "semantic_beat_timeline")
        self.assertTrue(config["forbid_equal_duration_scene_splitting"])
        self.assertIn("semantic_visual_timeline_required", rule_ids)
        self.assertIn("Do not split visual segments into equal durations", rules_text)
        self.assertIn("derive scene start and end times from narration meaning units", rules_text)

    def test_capsule_requires_character_bible_and_reference_sheet_before_storyboard_images(self):
        config = self.capsule["config"]
        method = self.capsule["method"]
        quality_rules = self.capsule["quality_rules"]
        rule_ids = {item["id"] for item in quality_rules}
        rules_text = json.dumps(method, ensure_ascii=False) + json.dumps(quality_rules, ensure_ascii=False)

        self.assertTrue(config["character_bible_required"])
        self.assertTrue(config["character_reference_sheet_required"])
        self.assertTrue(config["canonical_character_reference_before_storyboard"])
        self.assertIn("character_bible_required", rule_ids)
        self.assertIn("character_consistency_required", rule_ids)
        self.assertIn("Design a character bible before generating storyboard images", rules_text)
        self.assertIn("Yang Zhen", rules_text)
        self.assertIn("Wang Mi", rules_text)
        self.assertIn("canonical character reference sheet", rules_text)

    def test_character_reference_locks_identity_not_pose_or_layout(self):
        config = self.capsule["config"]
        method = self.capsule["method"]
        quality_rules = self.capsule["quality_rules"]
        rule_ids = {item["id"] for item in quality_rules}
        rules_text = json.dumps(method, ensure_ascii=False) + json.dumps(quality_rules, ensure_ascii=False)

        self.assertEqual(config["character_reference_usage_policy"], "identity_anchor_not_pose_lock")
        self.assertTrue(config["allow_scene_appropriate_character_variation"])
        self.assertTrue(config["allow_side_back_silhouette_distant_views"])
        self.assertTrue(config["forbid_reference_sheet_pose_or_layout_copying"])
        self.assertIn("reference_identity_not_pose_lock", rule_ids)
        self.assertIn("scene_appropriate_character_variation_required", rule_ids)
        self.assertIn("locks identity, not exact pose, action, camera angle, layout, or location", rules_text)
        self.assertIn("side, back, three-quarter, distant, and silhouette views are allowed", rules_text.lower())
        self.assertIn("Do not force full front-facing character views into every storyboard image", rules_text)


if __name__ == "__main__":
    unittest.main()
