import argparse
import json
import shutil
import sys
import unittest
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import local_video_qa  # noqa: E402


class LocalVideoQATest(unittest.TestCase):
    def setUp(self):
        self.workspace = ROOT / "output" / f"test_local_video_qa_{uuid4().hex}"
        (self.workspace / "release").mkdir(parents=True)
        (self.workspace / "qa").mkdir()
        self.final_video = self.workspace / "release" / "final.mp4"
        self.final_video.write_bytes(b"video")
        self._original_probe = local_video_qa.probe_video
        local_video_qa.probe_video = lambda _path: {
            "ok": True,
            "duration": 8.0,
            "width": 720,
            "height": 1280,
            "has_audio": True,
            "format": {},
        }

    def tearDown(self):
        local_video_qa.probe_video = self._original_probe
        shutil.rmtree(self.workspace, ignore_errors=True)

    def write_manifest(self, artifacts):
        (self.workspace / "artifact_manifest.json").write_text(
            json.dumps({"artifacts": artifacts}, ensure_ascii=False),
            encoding="utf-8",
        )

    def qa_args(self):
        return argparse.Namespace(
            run_dir=str(self.workspace),
            manifest="",
            final_video=str(self.final_video),
            aspect_ratio="9:16",
            min_duration=6.0,
            aspect_tolerance=0.08,
            expect_audio=True,
            require_prompts=True,
        )

    def test_require_prompts_fails_when_manifest_has_no_prompt_snapshots(self):
        self.write_manifest(
            [
                {"category": "final_video", "path": str(self.final_video)},
                {"category": "copywriting", "path": str(self.workspace / "release" / "copy.md")},
            ]
        )

        report = local_video_qa.run_qa(self.qa_args())

        self.assertFalse(report["ok"])
        checks = {item["id"]: item for item in report["checks"]}
        self.assertFalse(checks["manifest_prompt_artifacts"]["ok"])
        self.assertFalse(checks["prompt_index_exists"]["ok"])

    def test_require_prompts_passes_when_prompt_snapshots_exist(self):
        prompt_index = self.workspace / "prompts" / "prompt_index.json"
        image_prompt = self.workspace / "prompts" / "image" / "scene_v001.json"
        prompt_index.parent.mkdir(parents=True)
        image_prompt.parent.mkdir(parents=True)
        prompt_index.write_text("{}", encoding="utf-8")
        image_prompt.write_text("{}", encoding="utf-8")
        self.write_manifest(
            [
                {"category": "final_video", "path": str(self.final_video)},
                {"category": "copywriting", "path": str(self.workspace / "release" / "copy.md")},
                {"category": "storyboard_prompt", "path": str(prompt_index)},
                {"category": "storyboard_prompt", "path": str(image_prompt)},
            ]
        )

        report = local_video_qa.run_qa(self.qa_args())

        self.assertTrue(report["ok"])
        checks = {item["id"]: item for item in report["checks"]}
        self.assertTrue(checks["manifest_prompt_artifacts"]["ok"])
        self.assertTrue(checks["prompt_index_exists"]["ok"])
        self.assertTrue(checks["manifest_prompt_paths_exist"]["ok"])


if __name__ == "__main__":
    unittest.main()
