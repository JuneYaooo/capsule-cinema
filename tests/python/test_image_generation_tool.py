import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

from custom_tools.image_generation.image_generation_tool import resolve_reference_engine  # noqa: E402
from custom_tools.image_generation.seedream5_image_generator_tool import Seedream5ImageGenerator  # noqa: E402
from src.runtime.general_video_crew.image_generator import ImageGenerator  # noqa: E402


class ImageGenerationEngineSelectionTest(unittest.TestCase):
    def test_reference_image_keeps_gpt_image_2_because_edits_api_is_supported(self):
        engine, used_fallback = resolve_reference_engine("gpt-image-2", "/tmp/reference.png")

        self.assertEqual(engine, "gpt-image-2")
        self.assertFalse(used_fallback)

    def test_non_reference_keeps_requested_engine(self):
        engine, used_fallback = resolve_reference_engine("gpt-image-2", None)

        self.assertEqual(engine, "gpt-image-2")
        self.assertFalse(used_fallback)


class Seedream5TimeoutTest(unittest.TestCase):
    def test_stream_request_uses_finite_read_timeout(self):
        captured = {}

        class FakeStream:
            status_code = 200
            text = ""

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def iter_lines(self):
                return ["data: [DONE]"]

        class FakeClient:
            def __init__(self, timeout):
                captured["timeout"] = timeout

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def stream(self, *_args, **_kwargs):
                return FakeStream()

        generator = Seedream5ImageGenerator.__new__(Seedream5ImageGenerator)
        generator.base_url = "https://api.example.test"
        generator.headers = {}

        from unittest.mock import patch

        with patch("custom_tools.image_generation.seedream5_image_generator_tool.httpx.Client", FakeClient):
            generator._stream_request({"messages": []})

        self.assertIsNotNone(captured["timeout"].read)

    def test_reference_image_encoding_compresses_hd_portrait_image(self):
        generator = Seedream5ImageGenerator.__new__(Seedream5ImageGenerator)

        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "reference.jpg"
            Image.new("RGB", (1080, 1920), (240, 230, 220)).save(image_path, "JPEG", quality=92)

            with patch.object(generator, "_compress_image", return_value=str(image_path)) as compress:
                generator._encode_image_to_base64(str(image_path))

        compress.assert_called_once()

    def test_remote_image_download_streams_with_timeout_and_redacts_signed_url(self):
        generator = Seedream5ImageGenerator.__new__(Seedream5ImageGenerator)
        captured = {}

        class FakeResponse:
            status_code = 200
            content = b"fake image"

            def raise_for_status(self):
                return None

            def iter_content(self, chunk_size=8192):
                captured["chunk_size"] = chunk_size
                yield b"fake "
                yield b"image"

        def fake_get(url, **kwargs):
            captured["url"] = url
            captured["kwargs"] = kwargs
            return FakeResponse()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "out.jpg"
            with patch("custom_tools.image_generation.seedream5_image_generator_tool.requests.get", fake_get), \
                 patch("builtins.print") as fake_print:
                generator._save_image(
                    "https://signed.example.test/image.jpg?token=secret-value",
                    str(output_path),
                )

            printed = " ".join(str(call.args[0]) for call in fake_print.call_args_list if call.args)
            downloaded = output_path.read_bytes()

        self.assertEqual(downloaded, b"fake image")
        self.assertTrue(captured["kwargs"]["stream"])
        self.assertIsInstance(captured["kwargs"]["timeout"], tuple)
        self.assertIn("chunk_size", captured)
        self.assertNotIn("token=secret-value", printed)


class RuntimeImageQualityGateTest(unittest.TestCase):
    def test_quality_check_unavailable_fails_checked_scene_image(self):
        generator = ImageGenerator()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            image_path = output_dir / "scene.jpg"
            image_path.write_bytes(b"fake image")
            generator.scene_image_tool._run = MagicMock(
                return_value={"status": "success", "output_path": str(image_path)}
            )
            fake_checker = MagicMock()
            fake_checker._run.return_value = {
                "success": False,
                "error": "model_not_found: no distributor",
            }

            with patch("custom_tools.quality_check.ImageQualityCheckerTool", return_value=fake_checker):
                result = generator._generate_single_scene(
                    0,
                    {"scene_id": 0, "image_prompt_chinese": "蓝莓芝士毛毡小方"},
                    {"char_id_to_image": {}},
                    str(output_dir),
                    "9:16",
                    max_retries=1,
                    enable_moderation=False,
                    enable_quality_check=True,
                    engine="seedream5",
                )

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error"], "image_quality_check_unavailable")
        self.assertIn("model_not_found", result["quality_check_error"])


class RuntimeImageBatchTimeoutTest(unittest.TestCase):
    def test_scene_image_batch_marks_pending_futures_failed_after_timeout(self):
        generator = ImageGenerator()

        def slow_scene(*_args, **_kwargs):
            time.sleep(0.2)
            return {
                "scene_id": 0,
                "image_path": "/tmp/late.jpg",
                "generation_mode": "text2image",
                "status": "success",
                "index": 0,
            }

        generator._generate_single_scene = MagicMock(side_effect=slow_scene)

        with tempfile.TemporaryDirectory() as tmpdir:
            started = time.monotonic()
            result = generator.generate_scene_images(
                storyboard=[{"scene_id": 0, "image_prompt_chinese": "草莓毛毡小方"}],
                references_result={"reference_images": []},
                output_dir=tmpdir,
                max_workers=1,
                enable_quality_check=False,
                scene_timeout_seconds=0.01,
            )
            elapsed = time.monotonic() - started

        self.assertLess(elapsed, 0.15)
        self.assertEqual(result["summary"]["failed"], 1)
        self.assertEqual(result["summary"]["timed_out"], 1)
        self.assertEqual(result["details"][0]["status"], "failed")
        self.assertEqual(result["details"][0]["error"], "scene_image_generation_timeout")


if __name__ == "__main__":
    unittest.main()
