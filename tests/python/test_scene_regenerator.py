import json
import shutil
import sys
import unittest
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))

from src.runtime.general_video_crew import scene_regenerator  # noqa: E402


class SceneRegeneratorTest(unittest.TestCase):
    def setUp(self):
        self.workspace = ROOT / "output" / f"test_scene_regenerator_{uuid4().hex}"
        (self.workspace / "work" / "images").mkdir(parents=True)
        (self.workspace / "work" / "videos").mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.workspace, ignore_errors=True)

    def write_storyboard(self, scene):
        with (self.workspace / "storyboard.json").open("w", encoding="utf-8") as file:
            json.dump({"storyboard": [scene]}, file, ensure_ascii=False)

    def read_storyboard_scene(self):
        with (self.workspace / "storyboard.json").open("r", encoding="utf-8") as file:
            return json.load(file)["storyboard"][0]

    def patch_generators(self):
        old_generate_image = scene_regenerator.generate_image
        old_generate_video = scene_regenerator.generate_video
        captured = {}

        def fake_generate_image(**kwargs):
            output_path = Path(kwargs["output_path"])
            output_path.write_text("image", encoding="utf-8")
            return str(output_path)

        def fake_generate_video(**kwargs):
            captured["video_kwargs"] = kwargs
            output_path = Path(kwargs["output_dir"]) / "provider_result.mp4"
            output_path.write_text("video", encoding="utf-8")
            return str(output_path)

        scene_regenerator.generate_image = fake_generate_image
        scene_regenerator.generate_video = fake_generate_video
        return old_generate_image, old_generate_video, captured

    def restore_generators(self, old_generate_image, old_generate_video):
        scene_regenerator.generate_image = old_generate_image
        scene_regenerator.generate_video = old_generate_video

    def test_regenerates_scene_and_updates_storyboard(self):
        self.write_storyboard(
            {
                "index": 1,
                "image_prompt": "old image",
                "video_prompt": "old video",
            }
        )
        old_image, old_video, _ = self.patch_generators()
        try:
            result = scene_regenerator.regenerate_scene(
                workspace_dir=self.workspace,
                scene_id=1,
                image_prompt="new image",
                video_prompt="new video",
                image_engine="seedream5",
                video_engine="seedance-fast",
            )
        finally:
            self.restore_generators(old_image, old_video)

        self.assertEqual(result["status"], "success")
        self.assertTrue(result["image_path"].endswith("/work/images/scene_01_v1.jpg"))
        self.assertTrue(result["video_path"].endswith("/work/videos/scene_01_v1.mp4"))
        self.assertTrue(Path(result["image_path"]).exists())
        self.assertTrue(Path(result["video_path"]).exists())

        scene = self.read_storyboard_scene()
        self.assertEqual(scene["image_prompt"], "new image")
        self.assertEqual(scene["video_prompt"], "new video")
        self.assertEqual(scene["image_path"], result["image_path"])
        self.assertEqual(scene["video_path"], result["video_path"])
        self.assertEqual(scene["regen_version"], 1)
        self.assertEqual(scene["regen_image_engine"], "seedream5")
        self.assertEqual(scene["regen_engine"], "seedance-fast")

    def test_skip_image_reuses_storyboard_image_when_present(self):
        existing_image = self.workspace / "work" / "images" / "existing.jpg"
        existing_image.write_text("image", encoding="utf-8")
        self.write_storyboard(
            {
                "index": 1,
                "image_path": "work/images/existing.jpg",
                "video_prompt": "motion",
            }
        )
        old_image, old_video, captured = self.patch_generators()
        try:
            result = scene_regenerator.regenerate_scene(
                workspace_dir=self.workspace,
                scene_id=1,
                skip_image=True,
                video_engine="seedance",
            )
        finally:
            self.restore_generators(old_image, old_video)

        self.assertNotIn("image_path", result)
        self.assertEqual(captured["video_kwargs"]["image_path"], str(existing_image.resolve()))
        scene = self.read_storyboard_scene()
        self.assertEqual(scene["image_path"], "work/images/existing.jpg")
        self.assertEqual(scene["video_path"], result["video_path"])
        self.assertEqual(scene["regen_engine"], "seedance")


if __name__ == "__main__":
    unittest.main()
