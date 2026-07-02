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

import capsule_execution_guard  # noqa: E402
import release_checkpoint  # noqa: E402
import score_video_quality  # noqa: E402
from capsule_runtime import load_capsule  # noqa: E402


class CapsuleLocalScriptBypassGuardTest(unittest.TestCase):
    def test_output_script_cannot_claim_local_script_capsule_release(self):
        manifest = {
            "capsule": "life_sim",
            "execution_script": str(ROOT / "output" / "life_sim_rich_heiress_preview" / "render_preview.py"),
        }

        issue = capsule_execution_guard.local_script_bypass_issue(manifest, capsule_name="life_sim")

        self.assertIsNotNone(issue)
        self.assertEqual(issue["id"], "local_script_capsule_bypassed")
        self.assertEqual(issue["severity"], "blocker")
        self.assertIn("output", issue["detail"])

    def test_package_local_script_is_allowed_for_local_script_capsule_release(self):
        manifest = {
            "capsule": "life_sim",
            "execution_script": str(ROOT / "capsules" / "life_sim.capsule" / "scripts" / "life_sim_executor.py"),
        }

        issue = capsule_execution_guard.local_script_bypass_issue(manifest, capsule_name="life_sim")

        self.assertIsNone(issue)

    def test_dispatcher_script_is_allowed_when_manifest_records_local_script_path(self):
        manifest = {
            "capsule": "life_sim",
            "execution_script": str(ROOT / "scripts" / "run_capsule.py"),
            "capsule_local_script_path": str(
                ROOT / "capsules" / "life_sim.capsule" / "scripts" / "life_sim_executor.py"
            ),
        }

        issue = capsule_execution_guard.local_script_bypass_issue(manifest, capsule_name="life_sim")

        self.assertIsNone(issue)

    def test_score_video_quality_adds_blocker_for_bypassed_local_script_capsule(self):
        manifest = {
            "capsule": "life_sim",
            "execution_script": str(ROOT / "output" / "life_sim_rich_heiress_preview" / "render_preview.py"),
        }
        checks, _category_scores = score_video_quality.build_check_results(
            {"categories": []},
            local_qa={},
            manifest=manifest,
            probe={},
            capsule=load_capsule("life_sim"),
            storyboard={},
            blackdetect={},
            freezedetect={},
            contact_sheet={},
            multimodal_review={},
            manual_issues=[],
        )

        blocker = next((item for item in checks if item["id"] == "local_script_capsule_bypassed"), None)
        self.assertIsNotNone(blocker)
        self.assertEqual(blocker["severity"], "blocker")

    def test_release_checkpoint_adds_blocker_for_bypassed_local_script_capsule(self):
        output_root = ROOT / "output"
        output_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=output_root) as tmpdir:
            workspace = Path(tmpdir)
            manifest_path = workspace / "artifact_manifest.json"
            manifest_path.write_text(
                """{
  "capsule": "life_sim",
  "execution_script": "output/life_sim_rich_heiress_preview/render_preview.py",
  "artifacts": []
}
""",
                encoding="utf-8",
            )

            checkpoint = release_checkpoint.build_release_checkpoint(workspace)

        check = next((item for item in checkpoint["checks"] if item["id"] == "local_script_capsule_bypassed"), None)
        self.assertIsNotNone(check)
        self.assertFalse(check["ok"])
        self.assertIn("local_script_capsule_bypassed", checkpoint["blockers"])


if __name__ == "__main__":
    unittest.main()
