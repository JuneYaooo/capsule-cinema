import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = ROOT / "scripts"
LIB = ROOT / "lib"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

from score_video_quality import (  # noqa: E402
    build_check_results,
    edit_plan_validation_issues,
    load_rubric,
    multimodal_review_issues,
    normalize_multimodal_review,
    report_is_release_ready,
    requires_speech_visual_sync,
    requires_voice_character_review,
    run_multimodal_review,
)


class ScoreVideoQualityRoutingTest(unittest.TestCase):
    def test_voice_none_capsule_skips_speech_and_character_review(self):
        capsule = {
            "name": "repo_showcase",
            "category": "repo_showcase",
            "config": {
                "output_contract": {
                    "voice": "none",
                }
            },
        }

        self.assertFalse(requires_speech_visual_sync(capsule, {}, {}))
        self.assertFalse(requires_voice_character_review(capsule, {}, {}))

    def test_missing_scene_video_is_warning_when_generated_count_matches_capsule_range(self):
        capsule = {
            "name": "felt_asmr",
            "config": {
                "generated_scene_count_range": [6, 8],
            },
        }
        validation = {
            "checks": [
                {"id": "clip_source_exists", "ok": True, "clip_id": f"scene_{idx:02d}_video"}
                for idx in range(1, 8)
            ],
            "blockers": [
                {
                    "id": "no_missing_scene_video_warnings",
                    "message": "edit plan has no missing scene video warnings",
                    "missing_count": 1,
                }
            ],
            "warnings": [],
        }

        blockers, warnings = edit_plan_validation_issues(validation, capsule=capsule)

        self.assertEqual([], blockers)
        self.assertEqual(1, len(warnings))
        self.assertEqual("no_missing_scene_video_warnings", warnings[0]["id"])
        self.assertIn("within capsule generated_scene_count_range", warnings[0]["detail"])

    def test_missing_scene_video_remains_blocker_below_capsule_range(self):
        capsule = {
            "name": "felt_asmr",
            "config": {
                "generated_scene_count_range": [6, 8],
            },
        }
        validation = {
            "checks": [
                {"id": "clip_source_exists", "ok": True, "clip_id": f"scene_{idx:02d}_video"}
                for idx in range(1, 6)
            ],
            "blockers": [
                {
                    "id": "no_missing_scene_video_warnings",
                    "message": "edit plan has no missing scene video warnings",
                    "missing_count": 3,
                }
            ],
            "warnings": [],
        }

        blockers, warnings = edit_plan_validation_issues(validation, capsule=capsule)

        self.assertEqual(1, len(blockers))
        self.assertEqual([], warnings)

    def test_capsule_scoped_visual_artifact_warning_promotes_to_blocker(self):
        capsule = {
            "name": "felt_asmr",
            "quality_rules": [
                {
                    "id": "visible_process_grammar_gate",
                    "severity": "blocker",
                    "type": "manual_or_gemini_gate",
                }
            ],
        }
        raw = {
            "success": True,
            "has_issues": True,
            "needs_regeneration": False,
            "quality_score": 4,
            "issues": [
                {
                    "id": "main_subject_not_deformed",
                    "severity": "warning",
                    "timestamp": "00:08",
                    "description": "玻璃盒一压，里面的东西直接穿过玻璃边界，物理因果不成立。",
                }
            ],
        }

        review = normalize_multimodal_review(
            raw,
            "gemini3",
            ROOT / "fake.mp4",
            False,
            False,
            False,
            capsule=capsule,
        )
        blockers, warnings = multimodal_review_issues(review)

        self.assertEqual("failed", review["status"])
        self.assertEqual(1, len(blockers))
        self.assertEqual([], warnings)
        self.assertEqual("main_subject_not_deformed", blockers[0]["id"])
        self.assertIn("visible_process_grammar_gate", blockers[0]["detail"])

    def test_visual_artifact_warning_is_not_global_without_capsule_gate(self):
        capsule = {
            "name": "repo_showcase",
            "quality_rules": [],
        }
        raw = {
            "success": True,
            "has_issues": True,
            "needs_regeneration": False,
            "quality_score": 4,
            "issues": [
                {
                    "id": "main_subject_not_deformed",
                    "severity": "warning",
                    "timestamp": "00:08",
                    "description": "玻璃盒一压，里面的东西直接穿过玻璃边界，物理因果不成立。",
                }
            ],
        }

        review = normalize_multimodal_review(
            raw,
            "gemini3",
            ROOT / "fake.mp4",
            False,
            False,
            False,
            capsule=capsule,
        )
        blockers, warnings = multimodal_review_issues(review)

        self.assertEqual("needs_review", review["status"])
        self.assertEqual([], blockers)
        self.assertEqual(1, len(warnings))

    def test_skipped_multimodal_review_preserves_existing_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            existing_path = output_dir / "multimodal_video_review.json"
            existing_path.write_text(
                '{"enabled": true, "status": "needs_review", "success": true, "issues": [{"id": "main_subject_not_deformed", "severity": "warning"}]}\n',
                encoding="utf-8",
            )
            args = Namespace(
                multimodal_review=False,
                multimodal_provider="gemini3",
                multimodal_review_output="",
            )

            report = run_multimodal_review(args, None, output_dir, False, False, False, None)

            self.assertTrue(report["enabled"])
            self.assertEqual("needs_review", report["status"])
            self.assertEqual("warning", report["issues"][0]["severity"])
            self.assertIn("needs_review", existing_path.read_text(encoding="utf-8"))

    def test_existing_multimodal_report_is_renormalized_for_capsule_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            existing_path = output_dir / "multimodal_video_review.json"
            existing_path.write_text(
                '{"enabled": true, "provider": "gemini3", "status": "needs_review", "success": true, "video_path": "fake.mp4", "raw": {"success": true, "has_issues": true, "quality_score": 4, "issues": [{"id": "main_subject_not_deformed", "severity": "warning", "description": "容器边界被穿透"}]}}\n',
                encoding="utf-8",
            )
            args = Namespace(
                multimodal_review=False,
                multimodal_provider="gemini3",
                multimodal_review_output="",
            )
            capsule = {
                "name": "felt_asmr",
                "quality_rules": [{"id": "visible_process_grammar_gate"}],
            }

            report = run_multimodal_review(args, ROOT / "fake.mp4", output_dir, False, False, False, capsule)

            self.assertEqual("failed", report["status"])
            self.assertEqual("blocker", report["issues"][0]["severity"])

    def test_score_needs_review_is_not_release_ready(self):
        rubric = {"score_bands": {"pass": 85, "needs_review": 70}}

        self.assertFalse(report_is_release_ready(76, [], rubric))
        self.assertTrue(report_is_release_ready(86, [], rubric))

    def test_enabled_unavailable_multimodal_review_is_blocker(self):
        review = {
            "enabled": True,
            "success": False,
            "status": "unavailable",
            "error": "Gemini3 timed out",
            "issues": [],
        }

        blockers, warnings = multimodal_review_issues(review)

        self.assertEqual([], warnings)
        self.assertEqual(1, len(blockers))
        self.assertEqual("multimodal_review_unavailable", blockers[0]["id"])

    def test_static_fallback_is_blocker_for_real_motion_capsule(self):
        capsule = {
            "name": "guofeng_history",
            "category": "history_culture",
            "config": {
                "require_real_motion_video_segments": True,
                "static_fallback_can_pass_release": False,
                "static_zoompan_fallback_preview_only": True,
            },
        }
        manifest = {
            "generation_summary": {
                "video_route": "image_fallback",
                "video_engine": "image-fallback",
            },
            "artifacts": [
                {"category": "scene_video", "path": "work/videos/fallback_videos/scene_00_fallback.mp4"}
            ],
        }

        checks, _scores = build_check_results(
            load_rubric(),
            local_qa={"final_video": str(ROOT / "fake.mp4"), "checks": [{"id": "aspect_ratio", "ok": True}]},
            manifest=manifest,
            probe={"ok": True, "duration": 30.0, "width": 1080, "height": 1920, "has_audio": True},
            capsule=capsule,
            storyboard={"storyboard": [{"description": "first"}]},
            blackdetect={"available": True, "events": []},
            freezedetect={"available": True, "events": []},
            contact_sheet={"ok": True},
            multimodal_review={"success": True, "checks": {}, "issues": []},
            manual_issues=[],
        )

        route_check = next(item for item in checks if item["id"] == "route_truthful")
        self.assertFalse(route_check["ok"])
        self.assertIn("image_fallback", route_check["detail"])


if __name__ == "__main__":
    unittest.main()
