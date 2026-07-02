import importlib.util
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
EXECUTOR_PATH = ROOT / "capsules" / "life_sim.capsule" / "scripts" / "life_sim_executor.py"


def load_executor():
    spec = importlib.util.spec_from_file_location("life_sim_executor", EXECUTOR_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


class LifeSimOpeningBodyAudioContractTest(unittest.TestCase):
    def test_life_shaker_opening_identity_pattern_names_the_life(self):
        runtime_text = (ROOT / "capsules" / "life_sim.capsule" / "contracts" / "runtime.yaml").read_text(
            encoding="utf-8"
        )

        self.assertIn("每天一个模拟人生，今天你抽到的是<主题短名>的一生。", runtime_text)
        self.assertIn("今天你抽到的是<主题短名>的一生", runtime_text)
        self.assertNotIn("每天一个模拟人生，今天你抽到的是<主题短名>。", runtime_text)

    def test_strips_opening_tts_from_body_script_prefix(self):
        executor = load_executor()

        body, changed = executor.strip_opening_tts_from_body_script(
            "每天一个模拟人生，今天你抽到孙悟空。\n\n你不是被生下来的，你是被天地炸醒的。",
            "每天一个模拟人生，今天你抽到孙悟空。",
        )

        self.assertTrue(changed)
        self.assertEqual(body, "你不是被生下来的，你是被天地炸醒的。")

    def test_opening_strip_tolerates_spacing_and_punctuation(self):
        executor = load_executor()

        body, changed = executor.strip_opening_tts_from_body_script(
            " 每天一个模拟人生，今天你抽到孙悟空！\n\n你听见石头裂开。",
            "每天一个模拟人生 今天你抽到孙悟空。",
        )

        self.assertTrue(changed)
        self.assertEqual(body, "你听见石头裂开。")

    def test_opening_strip_keeps_body_when_opening_tts_is_empty_or_not_prefix(self):
        executor = load_executor()

        empty_opening_body, empty_opening_changed = executor.strip_opening_tts_from_body_script(
            "你从石头里醒来。",
            "",
        )
        unmatched_body, unmatched_changed = executor.strip_opening_tts_from_body_script(
            "你从石头里醒来。",
            "每天一个模拟人生，今天你抽到孙悟空。",
        )

        self.assertFalse(empty_opening_changed)
        self.assertEqual(empty_opening_body, "你从石头里醒来。")
        self.assertFalse(unmatched_changed)
        self.assertEqual(unmatched_body, "你从石头里醒来。")

    def test_validate_contract_blocks_repeated_opening_tts_in_body(self):
        executor = load_executor()
        params = {
            "storyboard": {
                "opening": {"tts": "每天一个模拟人生，今天你抽到孙悟空。"},
                "narration_script": "每天一个模拟人生，今天你抽到孙悟空。\n\n你不是被生下来的。",
            }
        }

        checks = executor.validate_contract("孙悟空的一生", params, self._minimal_config())

        check = self._check_by_id(checks, "opening_tts_not_repeated_in_body")
        self.assertFalse(check["ok"])
        self.assertEqual(check["severity"], "blocker")

    def test_validate_contract_allows_body_script_after_identity_lock(self):
        executor = load_executor()
        params = {
            "opening": {"tts": "每天一个模拟人生，今天你抽到孙悟空。"},
            "narration_script": "你不是被生下来的，你是被天地炸醒的。",
        }

        checks = executor.validate_contract("孙悟空的一生", params, self._minimal_config())

        self.assertTrue(self._check_by_id(checks, "opening_tts_not_repeated_in_body")["ok"])

    def test_dry_run_report_records_opening_body_audio_check(self):
        executor = load_executor()
        params = {
            "config": self._minimal_config(),
            "storyboard": {
                "opening": {"tts": "每天一个模拟人生，今天你抽到孙悟空。"},
                "narration_script": "每天一个模拟人生，今天你抽到孙悟空。\n\n你从石头里醒来。",
            },
        }

        with TemporaryDirectory() as tmp:
            params_path = Path(tmp) / "params.json"
            output_dir = Path(tmp) / "out"
            params_path.write_text(json.dumps(params, ensure_ascii=False), encoding="utf-8")

            with patch.object(
                sys,
                "argv",
                [
                    "life_sim_executor.py",
                    "--topic",
                    "孙悟空的一生",
                    "--params",
                    str(params_path),
                    "--output-dir",
                    str(output_dir),
                    "--dry-run",
                ],
            ):
                exit_code = executor.main()

            notes = json.loads((output_dir / "reports" / "run_notes.json").read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 2)
            self.assertFalse(notes["ok"])
            self.assertFalse(self._check_by_id(notes["checks"], "opening_tts_not_repeated_in_body")["ok"])

    def test_validate_contract_requires_paced_one_to_five_micro_cuts_and_visual_continuity(self):
        executor = load_executor()

        checks = executor.validate_contract("孙悟空的一生", {}, self._minimal_config())

        self.assertTrue(self._check_by_id(checks, "micro_cut_seconds_range")["ok"])
        self.assertTrue(self._check_by_id(checks, "micro_cut_average_target")["ok"])
        self.assertTrue(self._check_by_id(checks, "visual_storyline_continuity_required")["ok"])
        self.assertTrue(self._check_by_id(checks, "voice_sentence_boundary_pacing_required")["ok"])
        self.assertTrue(self._check_by_id(checks, "image2_budget_notice_before_generation")["ok"])

    def test_validate_contract_requires_settled_motion_character_lock_and_hook_review(self):
        executor = load_executor()

        checks = executor.validate_contract("孙悟空的一生", {}, self._minimal_config())

        self.assertTrue(self._check_by_id(checks, "settled_body_motion_required")["ok"])
        self.assertTrue(self._check_by_id(checks, "character_lock_required")["ok"])
        self.assertTrue(self._check_by_id(checks, "viral_script_review_required")["ok"])
        self.assertTrue(self._check_by_id(checks, "reference_style_ingestion_supported")["ok"])
        self.assertTrue(self._check_by_id(checks, "visual_mini_sequence_required")["ok"])

    def test_dry_run_budget_notice_uses_average_pacing_to_estimate_image_count(self):
        executor = load_executor()
        params = {
            "config": self._minimal_config(),
            "target_duration_seconds": 64,
        }

        with TemporaryDirectory() as tmp:
            params_path = Path(tmp) / "params.json"
            output_dir = Path(tmp) / "out"
            params_path.write_text(json.dumps(params, ensure_ascii=False), encoding="utf-8")

            with patch.object(
                sys,
                "argv",
                [
                    "life_sim_executor.py",
                    "--topic",
                    "孙悟空的一生",
                    "--params",
                    str(params_path),
                    "--output-dir",
                    str(output_dir),
                    "--dry-run",
                ],
            ):
                exit_code = executor.main()

            notes = json.loads((output_dir / "reports" / "run_notes.json").read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 0)
            self.assertEqual(notes["estimated_unique_body_images"], 22)
            self.assertIn("1-5 秒", notes["budget_notice"])
            self.assertIn("平均 2.6-3.0 秒", notes["budget_notice"])
            self.assertIn("约 22 张独立 Image2 图片", notes["budget_notice"])

    def test_non_dry_run_requires_generation_budget_ack_before_backend(self):
        executor = load_executor()
        params = {
            "config": self._minimal_config(),
            "target_duration_seconds": 64,
        }

        with TemporaryDirectory() as tmp:
            params_path = Path(tmp) / "params.json"
            output_dir = Path(tmp) / "out"
            params_path.write_text(json.dumps(params, ensure_ascii=False), encoding="utf-8")

            with patch.object(
                sys,
                "argv",
                [
                    "life_sim_executor.py",
                    "--topic",
                    "孙悟空的一生",
                    "--params",
                    str(params_path),
                    "--output-dir",
                    str(output_dir),
                ],
            ):
                exit_code = executor.main()

            notes = json.loads((output_dir / "reports" / "run_notes.json").read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 2)
            self.assertFalse(notes["ok"])
            self.assertEqual(notes["error"], "generation_budget_ack_required")
            self.assertIn("约 22 张独立 Image2 图片", notes["budget_notice"])
            self.assertFalse(self._check_by_id(notes["checks"], "generation_budget_ack_required")["ok"])

    def _minimal_config(self):
        return {
            "opening_style_default": "life_shaker",
            "opening_style_options": ["life_shaker", "title_card", "cold_open", "none"],
            "opening_template": {
                "tts_required_lines": ["series_title", "episode_topic"],
                "duration_seconds": {"default": 4.0},
            },
            "output_contract": {"subtitle": "none"},
            "body_subtitles_default": False,
            "visual_generation_type": "unique_image2_keyframes_with_micro_cuts",
            "micro_cut_visual_source": "unique_image2_keyframe_per_cut",
            "distinct_body_image_per_micro_cut_required": True,
            "body_image_content_hash_unique_required": True,
            "micro_cut_seconds": {
                "min": 1.0,
                "max": 5.0,
                "ideal": [2.7, 3.0],
                "target_average": {"min": 2.6, "max": 3.0},
            },
            "visual_continuity_required": True,
            "visual_storyline_required": True,
            "visual_mini_sequence_required": True,
            "visual_mini_sequence_size": {"min": 3, "max": 5},
            "continuity_anchor_required_per_micro_cut": True,
            "voice_visual_relation_required_per_micro_cut": True,
            "voice_visual_relation_allowed": ["direct", "parallel", "foreshadow"],
            "keyword_illustration_storyboard_forbidden": True,
            "voice_sentence_boundary_pacing_required": True,
            "visual_cut_sentence_policy": {
                "min_complete_sentences_per_cut": 1,
                "preferred_complete_sentences_per_cut": [1, 2],
                "forbid_mid_sentence_cut": True,
                "merge_short_sentences": True,
                "long_sentence_policy": "allow_multiple_visuals_at_semantic_clause_boundaries",
                "long_sentence_multiple_visuals_allowed": True,
                "require_same_sentence_visual_continuity": True,
            },
            "image2_budget_notice_required": True,
            "motion_policy": {
                "body_motion_style": "settled_hold",
                "default_body_frame_motion": "static_hold",
                "allow_subtle_displacement": True,
                "subtle_displacement_scale_range": [0.008, 0.018],
                "continuous_shake_forbidden": True,
                "opening_shake_scope": "opening_only",
                "punctuation_shake_max_seconds": 0.25,
                "body_motion_qa_required": True,
            },
            "character_lock": {
                "character_bible_required": True,
                "character_reference_image_required": True,
                "character_anchor_required_per_prompt": True,
                "actor_state_required_per_micro_cut": True,
                "reference_identity_not_pose_lock": True,
                "contact_sheet_drift_review_required": True,
            },
            "script_quality_policy": {
                "hook_variants_required": 3,
                "content_force_card_required": True,
                "true_first_line_audit_required": True,
                "enemy_or_pressure_source_required": True,
                "ban_generic_advice": True,
                "reference_style_brief_required_when_reference_path": True,
            },
            "reference_account_ingestion": {
                "reference_account_analysis_path_supported": True,
                "distill_patterns_only": True,
            },
        }

    def _check_by_id(self, checks, check_id):
        for check in checks:
            if check.get("id") == check_id:
                return check
        raise AssertionError(f"missing check {check_id}")


if __name__ == "__main__":
    unittest.main()
