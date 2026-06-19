import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from custom_tools.video_generation.video_generation_tool import UniversalVideoGenerationTool
from src.video_generation_config import normalize_video_engine_name


class Veo31VideoGeneratorTests(unittest.TestCase):
    def test_normalizes_veo31_aliases(self):
        self.assertEqual(normalize_video_engine_name("veo31"), "veo3.1")
        self.assertEqual(normalize_video_engine_name("veo3_1"), "veo3.1")
        self.assertEqual(normalize_video_engine_name("veo3.1_fast"), "veo3.1")

    def test_client_builds_first_last_frame_payload(self):
        from custom_tools.video_generation.veo31_video_generator_tool import (
            Veo31VideoClient,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(
                os.environ,
                {
                    "JULING_BASE_URL": "https://example.test",
                    "JULING_API_KEY": "secret",
                    "JULING_VEO31_MODEL": "veo3.1_fast",
                },
            ):
                client = Veo31VideoClient(output_dir=tmpdir)
                payload = client.build_payload(
                    prompt="flowers grow",
                    generation_type="first_last_frame",
                    aspect_ratio="9:16",
                    images=[
                        "https://example.test/start.jpg",
                        "https://example.test/end.jpg",
                    ],
                )

        self.assertEqual(payload["model"], "veo3.1_fast")
        self.assertEqual(payload["prompt"], "flowers grow")
        self.assertEqual(payload["type"], 2)
        self.assertEqual(payload["aspect_ratio"], "9:16")
        self.assertEqual(
            payload["images"],
            ["https://example.test/start.jpg", "https://example.test/end.jpg"],
        )

    def test_universal_tool_routes_first_last_frame(self):
        with patch(
            "custom_tools.video_generation.video_generation_tool.Veo31VideoGeneratorTool"
        ) as tool_class:
            tool = Mock()
            tool._run.return_value = {
                "status": "success",
                "output_path": "output/test.mp4",
            }
            tool_class.return_value = tool

            result = UniversalVideoGenerationTool()._run(
                prompt="flowers grow",
                output_dir="output/test_veo31",
                generation_type="first_last_frame",
                engine="veo3.1",
                start_image_path="start.png",
                end_image_path="end.png",
                aspect_ratio="9:16",
            )

        self.assertEqual(result["output_path"], "output/test.mp4")
        tool._run.assert_called_once()
        self.assertEqual(
            tool._run.call_args.kwargs["generation_type"],
            "first_last_frame",
        )
        self.assertEqual(tool._run.call_args.kwargs["start_image_path"], "start.png")
        self.assertEqual(tool._run.call_args.kwargs["end_image_path"], "end.png")


if __name__ == "__main__":
    unittest.main()
