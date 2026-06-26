import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

from custom_tools.utilities.social_media_copywriting_tool import SocialMediaCopywritingTool  # noqa: E402


class SocialMediaCopywritingSecretLoggingTest(unittest.TestCase):
    def test_gemini_call_does_not_log_api_key_preview(self):
        class FakeResponse:
            status_code = 200
            text = ""

            def json(self):
                return {
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {
                                        "text": json.dumps(
                                            {"copywriting": [], "comments": []},
                                            ensure_ascii=False,
                                        )
                                    }
                                ]
                            }
                        }
                    ]
                }

        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = Path(tmpdir) / "sample.mp4"
            video_path.write_bytes(b"fake video")
            fake_api_key = "sk-" + "test_" + "SECRET_PREVIEW_" + "1234567890"
            env = {
                "VIDEO_ANALYSIS_BASE_URL": "https://gemini.example.test",
                "VIDEO_ANALYSIS_API_KEY": fake_api_key,
                "VIDEO_ANALYSIS_MODEL_NAME": "gemini-test",
            }

            with patch.dict(os.environ, env, clear=False), patch(
                "custom_tools.utilities.social_media_copywriting_tool.requests.post",
                return_value=FakeResponse(),
            ):
                with self.assertLogs("social_media_copywriting", level="INFO") as captured:
                    result = SocialMediaCopywritingTool()._call_gemini_native_api(
                        str(video_path),
                        "return json",
                        "douyin",
                        max_retries=1,
                    )

        logs = "\n".join(captured.output)
        self.assertTrue(result["success"])
        self.assertNotIn("sk-test", logs)
        self.assertNotIn("7890", logs)
        self.assertNotIn("SECRET_PREVIEW", logs)
        self.assertIn("VIDEO_ANALYSIS_API_KEY", logs)


if __name__ == "__main__":
    unittest.main()
