import os
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "lib"
sys.path.insert(0, str(LIB))

from custom_tools.lip_sync import ltx23_lip_sync_tool as module


class LTX23LipSyncToolTest(unittest.TestCase):
    def test_submit_task_uses_current_runninghub_audio_inputs(self):
        os.environ["RUNNINGHUB_API_KEY"] = "test-key"
        captured = {}

        class FakeResponse:
            status_code = 200

            def json(self):
                return {"taskId": "task-current"}

        def fake_post(url, json, headers, timeout):
            captured["json"] = json
            return FakeResponse()

        original_post = module.requests.post
        module.requests.post = fake_post
        try:
            api = module.LTX23LipSyncAPI()
            task_id = api.submit_task(
                image_file_name="api/cat.png",
                audio_file_name="api/voice.wav",
                duration_seconds=0,
                action_prompt="固定镜头自然说话",
                resolution=1280,
                frame_rate=30,
                instance_type="plus",
            )
        finally:
            module.requests.post = original_post

        self.assertEqual(task_id, "task-current")
        node_info = captured["json"]["nodeInfoList"]
        self.assertIn(
            {
                "nodeId": "1755",
                "fieldName": "audio",
                "fieldValue": "api/voice.wav",
                "description": "Upload song or audio",
            },
            node_info,
        )
        self.assertIn(
            {
                "nodeId": "1776",
                "fieldName": "value",
                "fieldValue": "0",
                "description": "Audio start offset seconds",
            },
            node_info,
        )
        self.assertNotIn("1594", {item["nodeId"] for item in node_info})


if __name__ == "__main__":
    unittest.main()
