import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

from custom_tools.quality_check.gemini3_video_analyzer import Gemini3VideoAnalyzer  # noqa: E402


class Gemini3VideoAnalyzerTimeoutTest(unittest.TestCase):
    def test_openai_client_uses_video_analysis_timeout(self):
        captured = {}

        class FakeCompletions:
            def create(self, **_kwargs):
                class Message:
                    content = '{"has_issues": false, "needs_regeneration": false, "quality_score": 9, "issues": [], "summary": "ok"}'

                class Choice:
                    message = Message()

                class Response:
                    choices = [Choice()]

                return Response()

        class FakeChat:
            completions = FakeCompletions()

        class FakeOpenAI:
            chat = FakeChat()

            def __init__(self, **kwargs):
                captured.update(kwargs)

        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = Path(tmpdir) / "sample.mp4"
            video_path.write_bytes(b"fake video")

            with patch.dict(
                "os.environ",
                {
                    "GEMINI3_API_KEY": "test-key",
                    "GEMINI3_BASE_URL": "https://api.example.test/v1",
                    "GEMINI3_MODEL_NAME": "gemini-test",
                    "VIDEO_ANALYSIS_TIMEOUT_SECONDS": "12.5",
                },
            ), patch("custom_tools.quality_check.gemini3_video_analyzer.OpenAI", FakeOpenAI):
                result = Gemini3VideoAnalyzer().analyze_video(str(video_path))

        self.assertTrue(result["success"])
        self.assertEqual(12.5, captured.get("timeout"))

    def test_analysis_failure_is_not_reported_as_good_quality(self):
        class FakeCompletions:
            def create(self, **_kwargs):
                raise TimeoutError("request timed out")

        class FakeChat:
            completions = FakeCompletions()

        class FakeOpenAI:
            chat = FakeChat()

            def __init__(self, **_kwargs):
                pass

        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = Path(tmpdir) / "sample.mp4"
            video_path.write_bytes(b"fake video")

            with patch.dict(
                "os.environ",
                {
                    "GEMINI3_API_KEY": "test-key",
                    "GEMINI3_BASE_URL": "https://api.example.test/v1",
                    "GEMINI3_MODEL_NAME": "gemini-test",
                },
            ), patch("custom_tools.quality_check.gemini3_video_analyzer.OpenAI", FakeOpenAI):
                result = Gemini3VideoAnalyzer().analyze_video(str(video_path))

        self.assertFalse(result["success"])
        self.assertTrue(result["has_issues"])
        self.assertTrue(result["needs_review"])
        self.assertEqual(0, result["quality_score"])


if __name__ == "__main__":
    unittest.main()
