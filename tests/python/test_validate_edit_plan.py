import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from release_checkpoint import build_release_checkpoint  # noqa: E402
from validate_edit_plan import validate_edit_plan, write_edit_plan_validation  # noqa: E402


class ValidateEditPlanTest(unittest.TestCase):
    def make_workspace(self):
        output_root = ROOT / "output"
        output_root.mkdir(exist_ok=True)
        tmp = tempfile.TemporaryDirectory(prefix="test_edit_plan_", dir=output_root)
        workspace = Path(tmp.name)
        (workspace / "work").mkdir()
        (workspace / "qa").mkdir()
        (workspace / "release").mkdir()
        return tmp, workspace

    def write_plan(self, workspace: Path, source_path: str) -> Path:
        plan = {
            "schema": "capsule_cinema.edit_plan.v1",
            "workspace": str(workspace),
            "timeline": {
                "duration": 2.0,
                "tracks": [
                    {
                        "id": "video_main",
                        "type": "video",
                        "clips": [
                            {
                                "id": "scene_01_video",
                                "scene_id": 1,
                                "source_path": source_path,
                                "start": 0,
                                "duration": 2.0,
                                "source_duration": 0,
                            }
                        ],
                    }
                ],
            },
            "scene_map": [
                {
                    "scene_id": 1,
                    "clip_id": "scene_01",
                    "start": 0,
                    "duration": 2.0,
                    "video_path": source_path,
                }
            ],
            "warnings": [],
        }
        path = workspace / "work" / "edit_plan.json"
        path.write_text(json.dumps(plan), encoding="utf-8")
        return path

    def test_valid_edit_plan_passes_contract(self):
        tmp, workspace = self.make_workspace()
        with tmp:
            media = workspace / "work" / "scene_01.mp4"
            media.write_bytes(b"placeholder")
            self.write_plan(workspace, str(media))

            report = validate_edit_plan(workspace)

            self.assertTrue(report["ok"], report["blockers"])
            self.assertEqual(report["status"], "pass")

    def test_external_clip_path_is_blocker(self):
        tmp, workspace = self.make_workspace()
        with tmp:
            self.write_plan(workspace, "/tmp/outside.mp4")

            report = validate_edit_plan(workspace)

            self.assertFalse(report["ok"])
            self.assertTrue(any(item["id"] == "clip_source_exists" for item in report["blockers"]))

    def test_release_checkpoint_blocks_on_edit_plan_validation(self):
        tmp, workspace = self.make_workspace()
        with tmp:
            final_video = workspace / "release" / "final.mp4"
            final_video.write_bytes(b"placeholder")
            manifest = {
                "artifacts": [
                    {"category": "final_video", "path": str(final_video)},
                ]
            }
            (workspace / "artifact_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            self.write_plan(workspace, "/tmp/outside.mp4")
            validation_path = write_edit_plan_validation(workspace)

            checkpoint = build_release_checkpoint(
                workspace,
                edit_plan_validation_path=validation_path,
            )

            self.assertEqual(checkpoint["status"], "blocked")
            self.assertFalse(checkpoint["release_ready"])
            self.assertTrue(checkpoint["blockers"])


if __name__ == "__main__":
    unittest.main()
