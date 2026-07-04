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


class CapsuleProductionContractReleaseGateTest(unittest.TestCase):
    def test_release_checkpoint_blocks_missing_required_contract_outputs(self):
        output_root = ROOT / "output"
        output_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=output_root) as tmpdir:
            workspace = Path(tmpdir)
            final_video = workspace / "release" / "final_video.mp4"
            final_video.parent.mkdir(parents=True)
            final_video.write_bytes(b"video")
            (workspace / "artifact_manifest.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "production_contract": {
                            "schema_version": "capsule.production_contract.v1",
                            "minimum_evidence_for_release": "L2_multimodal_probe",
                            "required_outputs": {
                                "final_video": "required",
                                "cover": "required",
                                "voice": "required",
                                "bgm": "required",
                                "contact_sheet": "required",
                                "qa_report": "required",
                                "publishing_package": "required",
                            },
                        },
                        "artifacts": [
                            {
                                "category": "final_video",
                                "path": str(final_video),
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            checkpoint = release_checkpoint.build_release_checkpoint(workspace)

        self.assertEqual("blocked", checkpoint["status"])
        self.assertIn("production_contract:cover_missing", checkpoint["blockers"])
        self.assertIn("production_contract:voice_missing", checkpoint["blockers"])
        self.assertIn("production_contract:bgm_missing", checkpoint["blockers"])
        self.assertIn("production_contract:contact_sheet_missing", checkpoint["blockers"])
        self.assertIn("production_contract:qa_report_missing", checkpoint["blockers"])
        self.assertIn("production_contract:publishing_package_missing", checkpoint["blockers"])
        check_ids = {item["id"] for item in checkpoint["checks"]}
        self.assertIn("production_contract_required_outputs", check_ids)

    def test_release_checkpoint_passes_contract_output_gate_when_required_artifacts_exist(self):
        output_root = ROOT / "output"
        output_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=output_root) as tmpdir:
            workspace = Path(tmpdir)
            paths = {
                "final_video": workspace / "release" / "final_video.mp4",
                "cover_image": workspace / "release" / "cover.png",
                "voice": workspace / "audio" / "voice.wav",
                "bgm": workspace / "audio" / "bgm.mp3",
                "contact_sheet": workspace / "qa" / "review_contact_sheet.jpg",
                "qa_report": workspace / "qa" / "local_video_qa.json",
                "publishing_package": workspace / "publish" / "publishing_package.md",
            }
            for path in paths.values():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"x")
            (workspace / "artifact_manifest.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "production_contract": {
                            "schema_version": "capsule.production_contract.v1",
                            "required_outputs": {
                                "final_video": "required",
                                "cover": "required",
                                "voice": "required",
                                "bgm": "required",
                                "contact_sheet": "required",
                                "qa_report": "required",
                                "publishing_package": "required",
                            },
                        },
                        "artifacts": [
                            {"category": category, "path": str(path)}
                            for category, path in paths.items()
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            checkpoint = release_checkpoint.build_release_checkpoint(workspace)

        self.assertNotIn("production_contract:cover_missing", checkpoint["blockers"])
        self.assertNotIn("production_contract:voice_missing", checkpoint["blockers"])
        contract_check = next(
            item for item in checkpoint["checks"] if item["id"] == "production_contract_required_outputs"
        )
        self.assertTrue(contract_check["ok"])


if __name__ == "__main__":
    unittest.main()
