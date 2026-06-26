import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

from custom_tools.video_processing.video_subtitle_tool import VideoSubtitleTool  # noqa: E402


class VideoSubtitleToolWrapTest(unittest.TestCase):
    def test_long_chinese_srt_line_is_wrapped_in_ass(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            srt_path = tmp_path / "captions.srt"
            srt_path.write_text(
                "1\n"
                "00:00:00,200 --> 00:00:02,000\n"
                "它描绘的不是热闹，而是玻璃瓶里的赛博微型花园，从空瓶到夜色中发光的机械。\n",
                encoding="utf-8",
            )

            tool = VideoSubtitleTool()
            ass_path = tool._convert_srt_to_ass(
                srt_path=srt_path,
                font_name="PingFang SC",
                font_size=46,
                font_color="&H00F2E8D8",
                outline_color="&H802A241D",
                outline_width=2,
                shadow_color="&H00000000",
                shadow_offset=1,
                margin_v=95,
                alignment=2,
                bold=True,
                play_res_x=720,
                play_res_y=1280,
            )

            ass_text = ass_path.read_text(encoding="utf-8")
            self.assertIn("\\N", ass_text)
            self.assertIn("玻璃瓶里的赛博微型花园", ass_text)


if __name__ == "__main__":
    unittest.main()
