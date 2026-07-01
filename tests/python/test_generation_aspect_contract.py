import base64
from io import BytesIO
import shutil
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from uuid import uuid4

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))

from custom_tools.image_generation import seedream5_image_generator_tool  # noqa: E402
from custom_tools.image_generation.seedream5_image_generator_tool import GptImage2Tool  # noqa: E402
from custom_tools.video_generation.seedance_video_generator_tool import (  # noqa: E402
    SeedanceFastVideoGeneratorTool,
    _SeedanceClient,
)


class GenerationAspectContractTest(unittest.TestCase):
    def setUp(self):
        self.workspace = ROOT / "output" / f"test_generation_aspect_{uuid4().hex}"
        self.workspace.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_gpt_image2_uses_prompt_ratio_and_no_pixel_size_for_images_api(self):
        captured = {}

        class FakeResponse:
            status_code = 200
            text = ""

            def json(self):
                return {"data": [{"b64_json": base64.b64encode(b"png").decode("ascii")}]}

        class FakeClient:
            def __init__(self, *args, **kwargs):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def post(self, url, json, headers):
                captured["url"] = url
                captured["payload"] = json
                captured["headers"] = headers
                return FakeResponse()

        with patch.dict(
            "os.environ",
            {
                "GPT_IMAGE2_BASE_URL": "https://example.test",
                "GPT_IMAGE2_API_KEY": "secret",
            },
            clear=True,
        ), patch(
            "custom_tools.image_generation.seedream5_image_generator_tool.httpx.Client",
            FakeClient,
        ):
            GptImage2Tool()._generate_with_images_api(
                prompt="水墨秦始皇背影",
                aspect_ratio="9:16",
                quality="hd",
            )

        payload = captured["payload"]
        self.assertEqual(payload["size"], "auto")
        self.assertIn("9:16", payload["prompt"])
        self.assertNotRegex(payload["prompt"], r"\d+x\d+")
        self.assertNotRegex(payload["size"], r"\d+x\d+")

    def test_gpt_image2_can_use_krill_channel_env(self):
        captured = {}

        class FakeResponse:
            status_code = 200
            text = ""

            def json(self):
                return {"data": [{"b64_json": base64.b64encode(b"png").decode("ascii")}]}

        class FakeClient:
            def __init__(self, *args, **kwargs):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def post(self, url, json, headers):
                captured["url"] = url
                captured["payload"] = json
                captured["headers"] = headers
                return FakeResponse()

        with patch.dict(
            "os.environ",
            {
                "KRILL_GPT_IMAGE2_BASE_URL": "https://api.krill-ai.com/v1",
                "KRILL_GPT_IMAGE2_API_KEY": "krill-secret",
            },
            clear=True,
        ), patch(
            "custom_tools.image_generation.seedream5_image_generator_tool.httpx.Client",
            FakeClient,
        ):
            GptImage2Tool()._generate_with_images_api(
                prompt="A children's book drawing of a baby otter",
                aspect_ratio="1:1",
                quality="high",
            )

        self.assertEqual(captured["url"], "https://api.krill-ai.com/v1/images/generations")
        self.assertEqual(captured["payload"]["model"], "gpt-image-2")
        self.assertEqual(captured["payload"]["size"], "1024x1024")
        self.assertEqual(captured["payload"]["quality"], "high")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer krill-secret")

    def test_zeakai_gpt_image2_pro_uses_zeakai_env_and_model(self):
        captured = {}

        class FakeResponse:
            status_code = 200
            text = ""

            def json(self):
                return {"data": [{"b64_json": base64.b64encode(b"png").decode("ascii")}]}

        class FakeClient:
            def __init__(self, *args, **kwargs):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def post(self, url, json, headers):
                captured["url"] = url
                captured["payload"] = json
                captured["headers"] = headers
                return FakeResponse()

        with patch.dict(
            "os.environ",
            {
                "ZEAKAI_GPT_IMAGE2_PRO_BASE_URL": "https://zeakai.example.test",
                "ZEAKAI_GPT_IMAGE2_PRO_API_KEY": "zeakai-secret",
            },
            clear=True,
        ), patch(
            "custom_tools.image_generation.seedream5_image_generator_tool.httpx.Client",
            FakeClient,
        ):
            tool_class = getattr(seedream5_image_generator_tool, "GptImage2ProTool", None)
            self.assertIsNotNone(tool_class)
            tool_class()._generate_with_images_api(
                prompt="水墨秦始皇背影",
                aspect_ratio="9:16",
                quality="hd",
            )

        self.assertEqual(captured["url"], "https://zeakai.example.test/v1/images/generations")
        self.assertEqual(captured["payload"]["model"], "gpt-image-2-pro")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer zeakai-secret")

    def test_zeakai_gpt_image2_pro_supports_video_workflow_chat_endpoint(self):
        image_buffer = BytesIO()
        Image.new("RGB", (1024, 1792), "white").save(image_buffer, "PNG")
        image_data = "data:image/png;base64," + base64.b64encode(image_buffer.getvalue()).decode("ascii")
        captured = {}

        class FakeStreamResponse:
            status_code = 200
            text = ""

            def iter_lines(self, decode_unicode=True):
                payload = {"choices": [{"delta": {"content": image_data}}]}
                yield "data: " + __import__("json").dumps(payload)
                yield "data: [DONE]"

            def close(self):
                return None

        def fake_post(url, **kwargs):
            captured["url"] = url
            captured["kwargs"] = kwargs
            return FakeStreamResponse()

        class ImagesClientShouldNotBeUsed:
            def __init__(self, *args, **kwargs):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def post(self, *_args, **_kwargs):
                raise AssertionError("images endpoint should not be used when ZeakAI endpoint is chat")

        with patch.dict(
            "os.environ",
            {
                "ZEAKAI_BASE_URL": "https://zeakai.example.test",
                "ZEAKAI_API_KEY": "zeakai-secret",
                "ZEAKAI_GPT_IMAGE2_PRO_ENDPOINT": "chat",
            },
            clear=True,
        ), patch(
            "custom_tools.image_generation.seedream5_image_generator_tool.requests.post",
            fake_post,
        ), patch(
            "custom_tools.image_generation.seedream5_image_generator_tool.httpx.Client",
            ImagesClientShouldNotBeUsed,
        ):
            tool_class = getattr(seedream5_image_generator_tool, "GptImage2ProTool", None)
            result = tool_class()._run(
                prompt="水墨秦始皇背影",
                output_path=str(self.workspace / "zeakai_chat.png"),
                aspect_ratio="9:16",
            )

        self.assertIn("成功", result)
        self.assertEqual(captured["url"], "https://zeakai.example.test/v1/chat/completions")
        self.assertEqual(captured["kwargs"]["timeout"], 240)
        self.assertTrue((self.workspace / "zeakai_chat.png").exists())

    def test_gpt_image2_rejects_saved_image_when_actual_aspect_ratio_drifts(self):
        bad_image = self.workspace / "bad_ratio.png"
        Image.new("RGB", (1024, 1536), "white").save(bad_image)
        data_uri = "data:image/png;base64," + base64.b64encode(bad_image.read_bytes()).decode("ascii")

        with patch.object(GptImage2Tool, "_generate_with_images_api", return_value=data_uri):
            result = GptImage2Tool()._run(
                prompt="水墨秦始皇背影",
                output_path=str(self.workspace / "out.png"),
                aspect_ratio="9:16",
            )

        self.assertIn("失败", result)
        self.assertIn("9:16", result)
        self.assertIn("比例", result)

    def test_seedance_uses_output_path_parent_as_default_client_dir(self):
        target = self.workspace / "videos" / "seedance.mp4"
        captured = {}
        fake_client = Mock()
        fake_client.text_to_video.return_value = {"output_path": str(target)}

        def make_client(*args, **kwargs):
            captured["output_dir"] = kwargs["output_dir"]
            return fake_client

        with patch(
            "custom_tools.video_generation.seedance_video_generator_tool._SeedanceClient",
            side_effect=make_client,
        ), patch(
            "custom_tools.video_generation.seedance_video_generator_tool.validate_video_aspect_ratio"
        ):
            result = SeedanceFastVideoGeneratorTool()._run(
                prompt="ink moves",
                output_path=str(target),
                aspect_ratio="9:16",
                duration="10s",
            )

        self.assertEqual(result["output_path"], str(target))
        self.assertEqual(Path(captured["output_dir"]), target.parent)
        fake_client.text_to_video.assert_called_once()

    def test_seedance_default_client_dir_lives_under_output_root(self):
        captured = {}
        fake_client = Mock()

        def make_client(*args, **kwargs):
            captured["output_dir"] = kwargs["output_dir"]
            fake_client.text_to_video.return_value = {
                "output_path": str(Path(kwargs["output_dir"]) / "seedance.mp4")
            }
            return fake_client

        with patch(
            "custom_tools.video_generation.seedance_video_generator_tool._SeedanceClient",
            side_effect=make_client,
        ), patch(
            "custom_tools.video_generation.seedance_video_generator_tool.validate_video_aspect_ratio"
        ):
            SeedanceFastVideoGeneratorTool()._run(
                prompt="ink moves",
                aspect_ratio="9:16",
                duration="10s",
            )

        self.assertEqual(
            Path(captured["output_dir"]),
            ROOT / "output" / "manual_tool" / "work" / "videos" / "seedance",
        )

    def test_seedance_client_keeps_explicit_output_dir_under_output_root(self):
        output_dir = self.workspace / "seedance_videos"
        with patch.dict(
            "os.environ",
            {
                "JULING_BASE_URL": "https://example.test",
                "JULING_API_KEY": "secret",
            },
            clear=False,
        ):
            client = _SeedanceClient(output_dir=str(output_dir))

        self.assertEqual(client.output_dir, output_dir)

    def test_seedance_rejects_downloaded_video_when_actual_aspect_ratio_drifts(self):
        fake_video = self.workspace / "provider.mp4"
        fake_video.write_bytes(b"not a real mp4; dimensions are mocked")
        fake_client = Mock()
        fake_client.image_to_video.return_value = {"output_path": str(fake_video)}

        with patch(
            "custom_tools.video_generation.seedance_video_generator_tool._SeedanceClient",
            return_value=fake_client,
        ), patch(
            "custom_tools.video_generation.seedance_video_generator_tool.probe_video_dimensions",
            return_value=(832, 1120),
            create=True,
        ):
            result = SeedanceFastVideoGeneratorTool()._run(
                prompt="ink moves",
                generation_type="image_to_video",
                image_path=str(self.workspace / "first_frame.png"),
                aspect_ratio="9:16",
                output_path=str(fake_video),
                duration="10s",
            )

        self.assertIn("error", result)
        self.assertIn("9:16", result["error"])
        self.assertIn("832x1120", result["error"])
        fake_client.image_to_video.assert_called_once()


if __name__ == "__main__":
    unittest.main()
