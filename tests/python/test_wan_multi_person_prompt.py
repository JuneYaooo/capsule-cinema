import importlib.util
import os
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "lib"
sys.path.insert(0, str(LIB))


def load_client_module():
    module_path = LIB / "custom_tools" / "action_animation" / "wan_multi_person_api_client.py"
    spec = importlib.util.spec_from_file_location("wan_multi_person_api_client_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class WanMultiPersonPromptTest(unittest.TestCase):
    def test_run_workflow_overrides_positive_prompt_and_disables_metadata(self):
        module = load_client_module()
        os.environ["RUNNINGHUB_API_KEY"] = "test-key"
        captured = {}

        class FakeResponse:
            status_code = 200

            def json(self):
                return {"taskId": "task-123", "status": "RUNNING"}

        def fake_post(url, json, headers):
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers
            return FakeResponse()

        module.requests.post = fake_post

        client = module.WanMultiPersonApiClient(output_dir="/tmp/wan-multi-person-test")
        task_id = client.run_workflow(
            image_file_name="api/image.png",
            video_file_name="api/video.mp4",
            instance_type="plus",
            width=576,
            height=1024,
            positive_prompt="四个中年秃顶大叔在樱花林里跳舞",
            add_metadata=False,
        )

        self.assertEqual(task_id, "task-123")
        self.assertFalse(captured["json"]["addMetadata"])
        self.assertIn(
            {
                "nodeId": "368",
                "fieldName": "positive_prompt",
                "fieldValue": "四个中年秃顶大叔在樱花林里跳舞",
            },
            captured["json"]["nodeInfoList"],
        )


if __name__ == "__main__":
    unittest.main()
