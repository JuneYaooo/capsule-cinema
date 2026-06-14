import json
import shutil
import sys
import unittest
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "lib"))

import build_edit_plan  # noqa: E402
import plan_repairs  # noqa: E402
import release_checkpoint  # noqa: E402


class ReleaseArtifactsTest(unittest.TestCase):
    def setUp(self):
        self.workspace = ROOT / "output" / f"test_release_artifacts_{uuid4().hex}"
        (self.workspace / "work" / "videos" / "subtitled").mkdir(parents=True)
        (self.workspace / "work" / "audios").mkdir(parents=True)
        (self.workspace / "release").mkdir(parents=True)
        (self.workspace / "qa").mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.workspace, ignore_errors=True)

    def write_json(self, path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def test_build_edit_plan_scans_standard_workspace_media(self):
        self.write_json(
            self.workspace / "storyboard.json",
            {
                "storyboard": [
                    {"index": 1, "description": "opening", "duration": 4, "subtitle_text": "hello"},
                    {"index": 2, "description": "payoff", "duration": 3, "narration": "done"},
                ]
            },
        )
        (self.workspace / "work" / "videos" / "subtitled" / "scene_00_with_subtitles.mp4").write_text("video")
        (self.workspace / "work" / "videos" / "scene_01_v1.mp4").write_text("video")
        (self.workspace / "work" / "audios" / "scene_00.mp3").write_text("audio")

        output = build_edit_plan.write_edit_plan(self.workspace)
        payload = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(payload["schema"], "capsule_cinema.edit_plan.v1")
        self.assertEqual(payload["timeline"]["duration"], 7.0)
        self.assertEqual(len(payload["timeline"]["tracks"][0]["clips"]), 2)
        self.assertTrue(payload["scene_map"][0]["video_path"].endswith("scene_00_with_subtitles.mp4"))
        self.assertTrue(payload["scene_map"][1]["video_path"].endswith("scene_01_v1.mp4"))
        self.assertEqual(len(payload["timeline"]["tracks"][2]["clips"]), 2)

    def test_plan_repairs_maps_blockers_to_actions(self):
        score = {
            "status": "fail",
            "blockers": [
                {"id": "subtitle_text_layout", "severity": "manual_blocker", "description": "bad captions"},
                {"id": "no_black_frames", "severity": "blocker", "description": "black frame"},
            ],
            "warnings": [{"id": "copywriting_present", "severity": "warning"}],
        }
        self.write_json(self.workspace / "qa" / "video_quality_score.json", score)

        output = plan_repairs.write_repair_plan(self.workspace)
        payload = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(payload["status"], "needs_repair")
        self.assertTrue(payload["blocking"])
        self.assertEqual([item["type"] for item in payload["actions"]], ["rerender_subtitles", "regenerate_or_replace_scene"])
        self.assertEqual(payload["warning_count"], 1)

    def test_release_checkpoint_summarizes_package_status(self):
        final_video = self.workspace / "release" / "final_video.mp4"
        cover = self.workspace / "release" / "cover.jpg"
        final_video.write_text("video")
        cover.write_text("cover")
        self.write_json(
            self.workspace / "artifact_manifest.json",
            {
                "artifacts": [
                    {"category": "final_video", "path": str(final_video)},
                    {"category": "cover_image", "path": str(cover)},
                ]
            },
        )
        self.write_json(self.workspace / "work" / "edit_plan.json", {"schema": "capsule_cinema.edit_plan.v1"})
        self.write_json(self.workspace / "qa" / "local_video_qa.json", {"ok": True})
        self.write_json(
            self.workspace / "qa" / "video_quality_score.json",
            {"status": "pass", "score": 91, "score_max": 100, "blockers": [], "warnings": []},
        )
        self.write_json(self.workspace / "qa" / "repair_plan.json", {"blocking": False})

        output = release_checkpoint.write_release_checkpoint(self.workspace)
        payload = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(payload["schema"], "capsule_cinema.release_checkpoint.v1")
        self.assertEqual(payload["status"], "pass")
        self.assertTrue(payload["release_ready"])
        categories = {item["category"] for item in payload["artifacts"]}
        self.assertIn("final_video", categories)
        self.assertIn("edit_plan", categories)
        self.assertTrue(output.as_posix().endswith("/release/release_checkpoint.json"))


if __name__ == "__main__":
    unittest.main()
