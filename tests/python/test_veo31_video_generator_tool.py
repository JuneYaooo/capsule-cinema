import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import requests


ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

from custom_tools.video_generation.veo31_video_generator_tool import Veo31VideoClient  # noqa: E402


class FakeResponse:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} Server Error")

    def json(self):
        return self._payload


class Veo31VideoClientRetryTest(unittest.TestCase):
    def test_create_task_retries_transient_server_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            client = Veo31VideoClient(
                api_key="test-key",
                base_url="https://api.example.test",
                output_dir=tmpdir,
            )

            responses = [
                FakeResponse(500, text="temporary server error"),
                FakeResponse(200, {"id": "task_123"}),
            ]

            with patch("custom_tools.video_generation.veo31_video_generator_tool.time.sleep"), patch(
                "custom_tools.video_generation.veo31_video_generator_tool.requests.post",
                side_effect=responses,
            ) as post:
                task_id = client.create_task({"model": "veo3.1_fast", "prompt": "test"})

        self.assertEqual(task_id, "task_123")
        self.assertEqual(post.call_count, 2)


if __name__ == "__main__":
    unittest.main()
