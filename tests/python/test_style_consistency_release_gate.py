import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
LIB = ROOT / "lib"
for path in (str(SCRIPTS), str(LIB)):
    if path not in sys.path:
        sys.path.insert(0, path)

import release_checkpoint  # noqa: E402
import score_video_quality  # noqa: E402
from capsule_runtime import load_capsule  # noqa: E402


class StyleConsistencyReleaseGateTest(unittest.TestCase):
    def test_score_video_quality_blocks_failed_style_consistency_report(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "style_consistency_report.json"
            report_path.write_text(
                json.dumps(
                    {
                        "schema": "capsule_cinema.style_consistency_report.v1",
                        "ok": False,
                        "blockers": ["prompt_style_hash_drift"],
                        "warnings": [],
                    }
                ),
                encoding="utf-8",
            )
            manifest = {
                "artifacts": [
                    {
                        "category": "style_consistency_report",
                        "path": str(report_path),
                    }
                ]
            }

            checks, _category_scores = score_video_quality.build_check_results(
                {"categories": []},
                local_qa={},
                manifest=manifest,
                probe={},
                capsule=None,
                storyboard={},
                blackdetect={},
                freezedetect={},
                contact_sheet={},
                multimodal_review={},
                manual_issues=[],
            )

            blocker = next((item for item in checks if item["id"] == "style_consistency_failed"), None)
            self.assertIsNotNone(blocker)
            self.assertEqual(blocker["severity"], "blocker")
            self.assertIn("prompt_style_hash_drift", blocker["detail"])

    def test_score_video_quality_blocks_missing_required_style_consistency_report(self):
        checks, _category_scores = score_video_quality.build_check_results(
            {"categories": []},
            local_qa={},
            manifest={"capsule": "life_sim", "artifacts": []},
            probe={},
            capsule=load_capsule("life_sim"),
            storyboard={},
            blackdetect={},
            freezedetect={},
            contact_sheet={},
            multimodal_review={},
            manual_issues=[],
        )

        blocker = next((item for item in checks if item["id"] == "style_consistency_report_missing"), None)
        self.assertIsNotNone(blocker)
        self.assertEqual(blocker["severity"], "blocker")

    def test_score_video_quality_infers_required_style_report_from_manifest_capsule(self):
        checks, _category_scores = score_video_quality.build_check_results(
            {"categories": []},
            local_qa={},
            manifest={"capsule": "life_sim", "artifacts": []},
            probe={},
            capsule=None,
            storyboard={},
            blackdetect={},
            freezedetect={},
            contact_sheet={},
            multimodal_review={},
            manual_issues=[],
        )

        blocker = next((item for item in checks if item["id"] == "style_consistency_report_missing"), None)
        self.assertIsNotNone(blocker)
        self.assertEqual(blocker["severity"], "blocker")

    def test_release_checkpoint_blocks_failed_style_consistency_report(self):
        output_root = ROOT / "output"
        output_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=output_root) as tmpdir:
            workspace = Path(tmpdir)
            (workspace / "qa").mkdir(parents=True, exist_ok=True)
            (workspace / "artifact_manifest.json").write_text(
                json.dumps(
                    {
                        "artifacts": [
                            {
                                "category": "style_consistency_report",
                                "path": str(workspace / "qa" / "style_consistency_report.json"),
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            (workspace / "qa" / "style_consistency_report.json").write_text(
                json.dumps(
                    {
                        "schema": "capsule_cinema.style_consistency_report.v1",
                        "ok": False,
                        "blockers": ["strict_reference_downgraded_without_ack"],
                        "warnings": [],
                    }
                ),
                encoding="utf-8",
            )

            checkpoint = release_checkpoint.build_release_checkpoint(workspace)

        check = next((item for item in checkpoint["checks"] if item["id"] == "style_consistency_failed"), None)
        self.assertIsNotNone(check)
        self.assertFalse(check["ok"])
        self.assertIn("style_consistency_failed", checkpoint["blockers"])

    def test_release_checkpoint_blocks_missing_required_style_consistency_report(self):
        output_root = ROOT / "output"
        output_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=output_root) as tmpdir:
            workspace = Path(tmpdir)
            (workspace / "artifact_manifest.json").write_text(
                json.dumps({"capsule": "life_sim", "artifacts": []}),
                encoding="utf-8",
            )

            checkpoint = release_checkpoint.build_release_checkpoint(workspace)

        check = next((item for item in checkpoint["checks"] if item["id"] == "style_consistency_report_missing"), None)
        self.assertIsNotNone(check)
        self.assertFalse(check["ok"])
        self.assertIn("style_consistency_report_missing", checkpoint["blockers"])


if __name__ == "__main__":
    unittest.main()
