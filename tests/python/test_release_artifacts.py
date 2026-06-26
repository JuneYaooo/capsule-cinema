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

    def test_plan_repairs_falls_back_to_local_qa_when_score_missing(self):
        local_qa = {
            "ok": False,
            "checks": [
                {"id": "prompt_index_exists", "ok": False, "severity": "error", "message": "missing prompt index"},
                {"id": "manifest_copywriting", "ok": False, "severity": "warning", "message": "missing copy"},
                {"id": "ffprobe", "ok": False, "severity": "error", "message": "bad video"},
            ],
        }
        self.write_json(self.workspace / "qa" / "local_video_qa.json", local_qa)

        output = plan_repairs.write_repair_plan(self.workspace)
        payload = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(payload["source_status"], "local_qa_failed")
        self.assertTrue(payload["blocking"])
        self.assertEqual([item["type"] for item in payload["actions"]], ["refresh_release_package", "reassemble_or_rerender"])
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

    def test_release_checkpoint_blocks_specialized_promise_without_specialized_output(self):
        final_video = self.workspace / "release" / "final_video.mp4"
        final_video.write_text("video")
        self.write_json(
            self.workspace / "artifact_manifest.json",
            {
                "workflow": "general_video",
                "delivery_promise": {
                    "schema": "capsule_cinema.delivery_promise.v1",
                    "promise_type": "specialized_route",
                    "route": "action_transfer",
                    "approved_fallback": "",
                },
                "artifacts": [
                    {"category": "final_video", "path": str(final_video)},
                ],
            },
        )
        self.write_json(self.workspace / "qa" / "local_video_qa.json", {"ok": True})
        self.write_json(
            self.workspace / "qa" / "video_quality_score.json",
            {"status": "pass", "score": 91, "score_max": 100, "blockers": [], "warnings": []},
        )
        self.write_json(self.workspace / "qa" / "repair_plan.json", {"blocking": False})

        output = release_checkpoint.write_release_checkpoint(self.workspace)
        payload = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(payload["status"], "blocked")
        self.assertFalse(payload["release_ready"])
        self.assertIn("delivery_promise:specialized_route_requires_specialized_output", payload["blockers"])
        checks = {item["id"]: item for item in payload["checks"]}
        self.assertFalse(checks["delivery_promise_honored"]["ok"])

    def test_release_checkpoint_blocks_source_led_without_source_review(self):
        final_video = self.workspace / "release" / "final_video.mp4"
        final_video.write_text("video")
        self.write_json(
            self.workspace / "artifact_manifest.json",
            {
                "workflow": "general_video",
                "delivery_promise": {
                    "schema": "capsule_cinema.delivery_promise.v1",
                    "promise_type": "source_led",
                    "route": "source_edit",
                },
                "artifacts": [
                    {"category": "final_video", "path": str(final_video)},
                ],
            },
        )
        self.write_json(self.workspace / "qa" / "local_video_qa.json", {"ok": True})
        self.write_json(
            self.workspace / "qa" / "video_quality_score.json",
            {"status": "pass", "score": 91, "score_max": 100, "blockers": [], "warnings": []},
        )
        self.write_json(self.workspace / "qa" / "repair_plan.json", {"blocking": False})

        output = release_checkpoint.write_release_checkpoint(self.workspace)
        payload = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(payload["status"], "blocked")
        self.assertIn("delivery_promise:source_led_missing_source_review", payload["blockers"])


if __name__ == "__main__":
    unittest.main()
