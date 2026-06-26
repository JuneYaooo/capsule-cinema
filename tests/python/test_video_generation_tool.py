import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

from custom_tools.video_generation.video_generation_tool import GenerateVideoFromImageTool  # noqa: E402


class GenerateVideoFromImageToolTest(unittest.TestCase):
    def test_omits_duration_when_not_specified(self):
        with patch("custom_tools.video_generation.video_generation_tool.Jimeng35ProVideoGeneratorTool") as tool_class:
            tool = Mock()
            tool._run.return_value = {"status": "success", "output_path": "/tmp/scene.mp4"}
            tool_class.return_value = tool

            result = GenerateVideoFromImageTool()._run(
                image_path="/tmp/scene.jpg",
                scene={"video_prompt_chinese": "羊毛毡被勺子按压回弹"},
                output_dir="/tmp/videos",
                engine="jimeng35pro",
                aspect_ratio="9:16",
            )

        self.assertEqual(result["output_path"], "/tmp/scene.mp4")
        self.assertNotIn("duration", tool._run.call_args.kwargs)


if __name__ == "__main__":
    unittest.main()
