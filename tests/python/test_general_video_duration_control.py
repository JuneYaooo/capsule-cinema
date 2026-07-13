import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "lib"

if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

from video_workflows.general_video.crew import AgnoGeneralVideoCrew  # noqa: E402
from video_workflows.general_video.tasks import AgnoVideoTasks  # noqa: E402


class FakeScriptWriter:
    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts = []

    def run(self, prompt):
        self.prompts.append(prompt)
        return SimpleNamespace(content=json.dumps(self.responses.pop(0), ensure_ascii=False))


class FakeAgents:
    def __init__(self, script_writer):
        self.script_writer = script_writer

    def get_script_writer(self):
        return self.script_writer


def narration(text, scene_index=0, speed_ratio=1.0):
    return {
        "scene_index": scene_index,
        "narration": text,
        "voice_character_tag": "main",
        "speed_ratio": speed_ratio,
        "video_generation_type": "image_to_video",
    }


class GeneralVideoDurationControlTest(unittest.TestCase):
    def setUp(self):
        self.storyboard = {
            "scenes": [
                {"description": "scene one", "duration": 5},
                {"description": "scene two", "duration": 5},
            ]
        }

    def test_overlong_narration_is_rewritten_to_target_duration(self):
        writer = FakeScriptWriter([
            {"narrations": [narration("甲" * 40), narration("乙" * 20, 1)]},
            {"narrations": [narration("甲" * 10), narration("乙" * 10, 1)]},
        ])
        tasks = AgnoVideoTasks(FakeAgents(writer))

        result = tasks.generate_narration(
            "做一个十秒视频",
            self.storyboard,
            needs_audio=True,
            target_duration=10,
        )

        self.assertEqual(len(writer.prompts), 2)
        self.assertIn("目标成片总时长：10.0秒", writer.prompts[0])
        self.assertIn("旁白总字符预算：不超过40个有效字符", writer.prompts[0])
        self.assertEqual(result["narrations"][0]["narration"], "甲" * 10)

    def test_narration_fails_closed_when_rewrite_is_still_too_long(self):
        overlong = {"narrations": [narration("甲" * 40), narration("乙" * 20, 1)]}
        writer = FakeScriptWriter([overlong, overlong])
        tasks = AgnoVideoTasks(FakeAgents(writer))

        with self.assertRaisesRegex(ValueError, "自动压缩后仍无法满足目标时长"):
            tasks.generate_narration(
                "做一个十秒视频",
                self.storyboard,
                needs_audio=True,
                target_duration=10,
            )

    def test_split_scenes_allocate_duration_instead_of_copying_parent_duration(self):
        crew = AgnoGeneralVideoCrew.__new__(AgnoGeneralVideoCrew)
        scene = {
            "scene_id": 0,
            "description": "long narration",
            "duration": 8,
            "speed_ratio": 1.0,
            "narration": "|".join(["甲" * 12, "乙" * 12, "丙" * 12, "丁" * 12]),
        }

        result = crew._split_long_narration_scenes([scene])

        self.assertEqual(len(result), 4)
        self.assertAlmostEqual(sum(item["duration"] for item in result), 12.0)
        self.assertEqual([item["duration"] for item in result], [3.0, 3.0, 3.0, 3.0])

    def test_unsplit_scene_duration_is_aligned_to_narration(self):
        crew = AgnoGeneralVideoCrew.__new__(AgnoGeneralVideoCrew)
        scene = {
            "scene_id": 0,
            "duration": 2,
            "speed_ratio": 1.0,
            "narration": "甲" * 12,
        }

        result = crew._split_long_narration_scenes([scene])

        self.assertEqual(result[0]["duration"], 3.0)

    def test_storyboard_duration_gate_rejects_large_overrun(self):
        crew = AgnoGeneralVideoCrew.__new__(AgnoGeneralVideoCrew)

        with self.assertRaisesRegex(ValueError, "分镜总时长超过目标时长"):
            crew._validate_storyboard_duration(
                [{"duration": 30}, {"duration": 30}],
                target_duration=45,
            )


if __name__ == "__main__":
    unittest.main()
