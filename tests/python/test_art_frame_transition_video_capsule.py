import importlib.util
import json
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "capsules" / "art_frame_transition_video" / "run_art_frame_transition_video.py"


def load_capsule_script():
    spec = importlib.util.spec_from_file_location("art_frame_transition_video", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ArtFrameDecisionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = load_capsule_script()

    def test_single_complete_reference_becomes_end_anchor(self):
        refs = self.script.normalize_reference_images(
            [{"path": "/tmp/full_bloom_finished.jpg", "description": "finished full bloom artwork"}]
        )

        plan = self.script.decide_frame_plan(
            "让这幅花瓶画慢慢长出花草，整体舒适高级",
            refs,
            mood="auto",
        )

        self.assertEqual(plan["anchor_frame"], "end")
        self.assertEqual(plan["start_frame_strategy"], "derive_from_reference")
        self.assertEqual(plan["end_frame_strategy"], "use_reference")
        self.assertEqual(plan["motion_route"], "comfortable_immersive")
        self.assertIn("derive_consistent_start_frame", plan["image_processing_actions"])

    def test_two_references_are_ordered_by_simple_and_rich_state(self):
        refs = self.script.normalize_reference_images(
            [
                {"path": "/tmp/empty_vase_start.jpg", "description": "empty quiet initial state"},
                {"path": "/tmp/full_flowers_end.jpg", "description": "full flowering finished state"},
            ]
        )

        plan = self.script.decide_frame_plan("从空瓶到盛放", refs, mood="auto")

        self.assertEqual(plan["anchor_frame"], "both")
        self.assertEqual(plan["start_frame_strategy"], "select_from_inputs")
        self.assertEqual(plan["end_frame_strategy"], "select_from_inputs")
        self.assertEqual(plan["selected_start_image"], "/tmp/empty_vase_start.jpg")
        self.assertEqual(plan["selected_end_image"], "/tmp/full_flowers_end.jpg")

    def test_modern_surreal_prompt_uses_novel_route(self):
        refs = self.script.normalize_reference_images([])

        plan = self.script.decide_frame_plan(
            "现代艺术装置，画里的几何体从画布里浮出来，要新奇吸引人",
            refs,
            mood="auto",
            style_hint="现代艺术",
        )

        self.assertEqual(plan["motion_route"], "novel_attention")
        self.assertEqual(plan["start_frame_strategy"], "generate_from_text")
        self.assertEqual(plan["end_frame_strategy"], "generate_from_text")
