import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))

from src.contracts import (  # noqa: E402
    find_scene_by_id,
    get_scene_prompt,
    get_storyboard_scenes,
    scene_display_id,
    set_storyboard_scenes,
)


class StoryboardContractTest(unittest.TestCase):
    def test_reads_and_writes_canonical_storyboard(self):
        data = {"storyboard": [{"index": 1, "description": "one"}]}

        scenes = get_storyboard_scenes(data)
        self.assertEqual(scenes[0]["description"], "one")

        replacement = [{"index": 1, "description": "updated"}]
        set_storyboard_scenes(data, replacement)

        self.assertEqual(data["storyboard"], replacement)
        self.assertNotIn("scenes", data)

    def test_rejects_scenes_without_canonical_storyboard(self):
        removed_storyboard_key = "scene" + "s"
        data = {removed_storyboard_key: [{"scene_id": 0, "description": "old"}]}

        scenes = get_storyboard_scenes(data)

        self.assertEqual(scenes, [])

    def test_zero_based_scene_id_matches_user_scene_one_when_no_index_exists(self):
        scenes = [
            {
                "scene_id": 0,
                "image_prompt_chinese": "图片中文",
                "video_prompt_english": "video english",
            }
        ]

        idx, scene = find_scene_by_id(scenes, 1)

        self.assertEqual(idx, 0)
        self.assertIs(scene, scenes[0])

    def test_scene_index_takes_canonical_precedence(self):
        scenes = [{"index": 2, "scene_id": 0, "image_prompt": "canonical"}]

        idx, scene = find_scene_by_id(scenes, 2)
        wrong_idx, wrong_scene = find_scene_by_id(scenes, 1)

        self.assertEqual(idx, 0)
        self.assertIs(scene, scenes[0])
        self.assertIsNone(wrong_idx)
        self.assertIsNone(wrong_scene)


if __name__ == "__main__":
    unittest.main()
