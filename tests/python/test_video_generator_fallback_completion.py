import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

from src.runtime.general_video_crew.video_generator import VideoGenerator  # noqa: E402


def make_storyboard(count=3):
    return [
        {"index": idx + 1, "video_prompt": f"scene {idx + 1}"}
        for idx in range(count)
    ]


def make_image_result(tmpdir, count=3):
    outputs = {}
    for idx in range(count):
        path = Path(tmpdir) / f"scene_{idx + 1}.png"
        path.write_bytes(b"fake image")
        outputs[idx] = str(path)
    return {"outputs": outputs}


class VideoFallbackCompletionTest(unittest.TestCase):
    def test_fallback_engine_fills_only_missing_scenes(self):
        calls = []
        generator = VideoGenerator()

        def fake_fallback_engines(_engine, required_flags=None):
            return ["engine_a", "engine_b"]

        def fake_generate(scene_list, image_outputs, output_dir, engine, aspect_ratio, execution_directive=None):
            original_indices = [original for original, _scene in scene_list]
            calls.append((engine, original_indices))
            if engine == "engine_a":
                return {0: str(Path(output_dir) / "scene_1.mp4")}
            return {idx: str(Path(output_dir) / f"scene_{idx + 1}.mp4") for idx in original_indices}

        with tempfile.TemporaryDirectory() as tmpdir, \
             patch.object(generator, "_fallback_engines", fake_fallback_engines), \
             patch.object(generator, "_generate_video_batch", fake_generate), \
             patch.object(generator, "_analyze_and_regenerate_videos", side_effect=lambda video_outputs, **_kwargs: video_outputs):
            result = generator.generate_videos(
                storyboard=make_storyboard(3),
                image_result=make_image_result(tmpdir, 3),
                output_dir=tmpdir,
                engine="engine_a",
                enable_quality_check=True,
            )

        self.assertEqual(calls, [("engine_a", [0, 1, 2]), ("engine_b", [1, 2])])
        self.assertEqual(result["summary"]["generated"], 3)
        self.assertEqual(result["summary"]["failed"], 0)
        self.assertEqual(set(result["outputs"]), {0, 1, 2})

    def test_static_fallback_only_fills_missing_scenes(self):
        calls = []
        generator = VideoGenerator()

        def fake_fallback_engines(_engine, required_flags=None):
            return ["engine_a"]

        def fake_generate(scene_list, image_outputs, output_dir, engine, aspect_ratio, execution_directive=None):
            return {0: str(Path(output_dir) / "scene_1.mp4")}

        def fake_fallback(storyboard, image_outputs, output_dir, animation_type="auto"):
            calls.append([scene.get("index") for scene in storyboard])
            return {
                idx: str(Path(output_dir) / f"fallback_{idx + 1}.mp4")
                for idx in range(len(storyboard))
            }

        with tempfile.TemporaryDirectory() as tmpdir, \
             patch.object(generator, "_fallback_engines", fake_fallback_engines), \
             patch.object(generator, "_generate_video_batch", fake_generate), \
             patch.object(generator, "_fallback_to_image_videos", fake_fallback):
            result = generator.generate_videos(
                storyboard=make_storyboard(3),
                image_result=make_image_result(tmpdir, 3),
                output_dir=tmpdir,
                engine="engine_a",
                enable_quality_check=False,
                allow_static_fallback=True,
            )

        self.assertEqual(calls, [[2, 3]])
        self.assertEqual(result["summary"]["generated"], 3)
        self.assertEqual(result["summary"]["failed"], 0)


if __name__ == "__main__":
    unittest.main()
