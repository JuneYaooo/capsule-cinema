import sys
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from capsule_package_convert import convert_capsule  # noqa: E402


class CapsulePackageConvertCanonicalRecipesTest(unittest.TestCase):
    def test_converter_routes_legacy_method_keys_to_canonical_recipe_files(self):
        payload = {
            "name": "sample",
            "display_name": "Sample",
            "status": "active",
            "execution_mode": "preset",
            "description": "Sample capsule",
            "category": "test",
            "tags": [],
            "version": 1,
            "config": {
                "roles": {"image": {"validated_with": "GptImage2Tool"}},
                "output_contract": {"voice": "none", "subtitle": "none"},
                "body_subtitles_default": False,
                "micro_cut_seconds": {"min": 1.0, "max": 3.0},
                "micro_cut_visual_source": "unique_image2_keyframe_per_cut",
                "distinct_body_image_per_micro_cut_required": True,
                "body_image_content_hash_unique_required": True,
                "opening_template": {"renderer_asset": "life_shaker_opening_renderer"},
            },
            "method": {
                "story_principles": ["剧情跌宕优先"],
                "flexible_arc_policy": ["适配完整故事"],
                "copy_hook_patterns": {"required": True},
                "repo_showcase_current_playbook": {"required": True},
                "five_line_bottom_cards_policy": {"required": True},
            },
            "input_schema": {},
            "quality_rules": [{"id": "final_video_required", "type": "artifact_required"}],
            "local_assets": [],
            "examples": [],
            "source": {"type": "zip", "legacy_version": 1},
        }

        with tempfile.TemporaryDirectory() as tmp:
            capsule_dir = convert_capsule(payload, Path(tmp), overwrite=True)

            runtime = yaml.safe_load((capsule_dir / "contracts" / "runtime.yaml").read_text(encoding="utf-8"))
            structure = (capsule_dir / "recipes" / "structure.md").read_text(encoding="utf-8")
            copy = (capsule_dir / "recipes" / "copy.md").read_text(encoding="utf-8")

            self.assertFalse((capsule_dir / "recipes" / "legacy_notes.md").exists())
            self.assertFalse((capsule_dir / "recipes" / "subtitle.md").exists())
            self.assertIn("story_principles", structure)
            self.assertIn("flexible_arc_policy", structure)
            self.assertIn("copy_hook_patterns", copy)
            self.assertIn("repo_showcase_current_playbook", copy)
            self.assertIn("five_line_bottom_cards_policy", copy)
            self.assertEqual(runtime["defaults"]["micro_cut_visual_source"], "unique_image2_keyframe_per_cut")
            self.assertEqual(runtime["defaults"]["opening_template"]["renderer_asset"], "life_shaker_opening_renderer")


if __name__ == "__main__":
    unittest.main()
