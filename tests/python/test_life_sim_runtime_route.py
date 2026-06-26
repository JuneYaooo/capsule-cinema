import sys
import unittest
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

from src.runtime.general_video_crew.video_generator import VideoGenerator  # noqa: E402
from video_workflows.general_video.flow import AgnoGeneralVideoFlow  # noqa: E402


class LifeSimRuntimeRouteTest(unittest.TestCase):
    def test_flow_applies_capsule_image_engine_and_forced_fallback_route(self):
        flow = AgnoGeneralVideoFlow()
        flow.state = {
            "capsule_config": {
                "image_engine": "GptImage2Tool",
                "video_engine": "none_for_default_route",
                "visual_generation_type": "still_images_with_ken_burns",
            }
        }
        crew_result = {
            "planning_results": {
                "plan_result": {"video_elements": {}},
                "engine_result": {"video_engine": "seedance-fast"},
            },
            "storyboard": [{"duration": 1.5}],
        }

        flow._apply_capsule_overrides(crew_result)

        self.assertEqual(flow.state["manual_image_engine"], "gpt-image-2")
        self.assertEqual(flow.state["video_generation_route"], "still_images_with_ken_burns")
        self.assertTrue(flow.state["force_image_fallback_video"])
        self.assertEqual(crew_result["planning_results"]["engine_result"]["video_engine"], "image-fallback")

    def test_capsule_forced_fallback_wins_over_manual_video_engine(self):
        flow = AgnoGeneralVideoFlow()
        flow.state = {
            "manual_video_engine": "seedance-fast",
            "capsule_config": {
                "video_engine": "none_for_default_route",
                "visual_generation_type": "still_images_with_ken_burns",
            },
        }
        crew_result = {
            "planning_results": {
                "plan_result": {"video_elements": {}},
                "engine_result": {"video_engine": "seedance"},
            },
            "storyboard": [{"duration": 1.5}],
        }

        flow._apply_capsule_overrides(crew_result)
        flow.state["engine_selection"] = crew_result["planning_results"]["engine_result"]
        flow._check_manual_engine_override()

        self.assertEqual(flow.state["engine_selection"]["video_engine"], "image-fallback")

    def test_video_generator_forced_fallback_skips_external_video_engine(self):
        generator = VideoGenerator()
        generator._fallback_to_image_videos = MagicMock(return_value={0: "/tmp/scene.mp4"})
        generator._generate_video_batch = MagicMock(return_value={0: "/tmp/external.mp4"})

        result = generator.generate_videos(
            storyboard=[{"duration": 1.5}],
            image_result={"outputs": {0: "/tmp/scene.png"}},
            output_dir="/tmp/videos",
            engine="seedance-fast",
            force_image_fallback=True,
        )

        self.assertEqual(result["outputs"], {0: "/tmp/scene.mp4"})
        self.assertEqual(result["summary"]["video_route"], "image_fallback")
        generator._generate_video_batch.assert_not_called()
        generator._fallback_to_image_videos.assert_called_once()

    def test_flow_passes_runtime_route_to_generators(self):
        flow = AgnoGeneralVideoFlow()
        flow.state = {
            "storyboard": [{"duration": 1.5}],
            "workspace_dir": "/tmp/life_sim_route_workspace",
            "reference_design": {},
            "content_requirements": {
                "video_elements": {"needs_audio": False, "needs_subtitles": False, "needs_bgm": False}
            },
            "output_dirs": {
                "audios": "/tmp/audios",
                "reference_images": "/tmp/references",
                "images": "/tmp/images",
                "videos": "/tmp/videos",
                "final": "/tmp/final",
                "temp": "/tmp/temp",
                "work": "/tmp/work",
            },
            "aspect_ratio": "16:9",
            "enable_image_quality_check": False,
            "enable_video_quality_check": False,
            "user_reference_images": [],
            "reference_analysis_results": [],
            "art_style_selection": {},
            "manual_image_engine": "gpt-image-2",
            "force_image_fallback_video": True,
            "engine_selection": {"video_engine": "image-fallback"},
            "add_subtitles": False,
            "add_background_music": False,
            "generate_social_media_copywriting": False,
            "video_title": "life_sim_test",
            "voice_volume": 1.5,
        }
        flow.audio_generator.generate_audios = MagicMock()
        flow.image_generator.generate_reference_images = MagicMock(return_value={"reference_images": []})
        flow.image_generator.generate_scene_images = MagicMock(return_value={"outputs": {0: "/tmp/images/scene.png"}})
        flow.video_generator.generate_videos = MagicMock(return_value={"outputs": {0: "/tmp/videos/scene.mp4"}, "summary": {}})
        flow.image_generator.generate_cover_image = MagicMock(return_value="/tmp/final/cover.jpg")
        flow.post_processor.concatenate_videos = MagicMock(return_value="/tmp/final/base.mp4")
        flow.post_processor.add_background_music = MagicMock(return_value="/tmp/final/base.mp4")
        flow.social_media_generator = MagicMock()

        with patch("video_workflows.general_video.flow.tqdm", lambda total, desc, unit: _NoopProgress()):
            result = flow._execute_generation_phase()

        self.assertTrue(result["success"])
        flow.image_generator.generate_reference_images.assert_called_once()
        self.assertEqual(flow.image_generator.generate_reference_images.call_args.kwargs["engine"], "gpt-image-2")
        self.assertEqual(flow.image_generator.generate_scene_images.call_args.kwargs["engine"], "gpt-image-2")
        self.assertTrue(flow.video_generator.generate_videos.call_args.kwargs["force_image_fallback"])

    def test_flow_applies_execution_plan_role_selection_and_output_contract(self):
        flow = AgnoGeneralVideoFlow()
        flow.state = {
            "capsule_execution_plan": {
                "output_contract": {
                    "clip_audio": "silent",
                    "voice": "unified_tts",
                    "subtitle": "overlay",
                    "bgm": "external",
                },
                "roles": {
                    "image": {
                        "selected": "GptImage2Tool",
                        "directive": {"prompt_additions": ["ink wash"], "prompt_negatives": [], "post_steps": []},
                    },
                    "video": {
                        "selected": "Jimeng35ProVideoGeneratorTool",
                        "directive": {
                            "prompt_additions": [],
                            "prompt_negatives": ["no speech", "no dialogue"],
                            "post_steps": ["mute_audio"],
                            "notes": ["native audio muted"],
                        },
                    },
                    "voice": {"selected": "minimax/Chinese_deep_voiced_male_vv1", "directive": None},
                },
            },
            "capsule_config": {},
        }
        crew_result = {
            "planning_results": {
                "plan_result": {"video_elements": {"needs_audio": False, "needs_subtitles": False, "needs_bgm": False}},
                "voice_result": {"voice_mode": "none"},
                "music_result": {"needs_bgm": False},
                "engine_result": {"video_engine": "seedance-fast"},
            },
            "storyboard": [
                {
                    "duration": 1.5,
                    "video_prompt_chinese": "人物转身",
                    "video_prompt_english": "person turns",
                    "subtitles": [],
                }
            ],
        }

        flow._apply_capsule_overrides(crew_result)

        planning = crew_result["planning_results"]
        self.assertEqual(flow.state["manual_image_engine"], "gpt-image-2")
        self.assertEqual(planning["engine_result"]["video_engine"], "jimeng35pro")
        self.assertTrue(planning["plan_result"]["video_elements"]["needs_audio"])
        self.assertTrue(planning["plan_result"]["video_elements"]["needs_subtitles"])
        self.assertTrue(planning["plan_result"]["video_elements"]["needs_bgm"])
        self.assertEqual(planning["voice_result"]["main_voice"]["tts_provider"], "minimax")
        self.assertEqual(planning["voice_result"]["main_voice"]["voice_type"], "Chinese_deep_voiced_male_vv1")
        self.assertIn("no speech", crew_result["storyboard"][0]["video_prompt_chinese"])
        self.assertEqual(flow.state["capsule_video_directive"]["post_steps"], ["mute_audio"])

    def test_flow_keeps_execution_plan_video_role_requirements(self):
        flow = AgnoGeneralVideoFlow()
        flow.state = {
            "capsule_execution_plan": {
                "output_contract": {"clip_audio": "native", "voice": "none", "subtitle": "none"},
                "roles": {
                    "video": {
                        "selected": "Veo31VideoGeneratorTool",
                        "requires": ["image_to_video", "native_audio"],
                        "directive": {"prompt_negatives": [], "post_steps": []},
                    }
                },
            },
            "capsule_config": {},
        }
        crew_result = {
            "planning_results": {
                "plan_result": {"video_elements": {}},
                "engine_result": {"video_engine": "jimeng35pro"},
            },
            "storyboard": [{"duration": 1.5, "subtitles": ["x"]}],
        }

        flow._apply_capsule_overrides(crew_result)

        self.assertEqual(flow.state["manual_video_engine"], "veo3.1")
        self.assertEqual(flow.state["video_role_requirements"], ["image_to_video", "native_audio"])
        self.assertEqual(crew_result["planning_results"]["engine_result"]["video_engine"], "veo3.1")

    def test_flow_passes_video_directive_to_video_generator(self):
        flow = AgnoGeneralVideoFlow()
        flow.state = {
            "storyboard": [{"duration": 1.5}],
            "workspace_dir": "/tmp/capsule_plan_workspace",
            "reference_design": {},
            "content_requirements": {
                "video_elements": {"needs_audio": False, "needs_subtitles": False, "needs_bgm": False}
            },
            "output_dirs": {
                "audios": "/tmp/audios",
                "reference_images": "/tmp/references",
                "images": "/tmp/images",
                "videos": "/tmp/videos",
                "final": "/tmp/final",
                "temp": "/tmp/temp",
                "work": "/tmp/work",
            },
            "aspect_ratio": "16:9",
            "enable_image_quality_check": False,
            "enable_video_quality_check": False,
            "user_reference_images": [],
            "reference_analysis_results": [],
            "art_style_selection": {},
            "manual_image_engine": "gpt-image-2",
            "engine_selection": {"video_engine": "jimeng35pro"},
            "capsule_video_directive": {"post_steps": ["mute_audio"], "prompt_negatives": ["no speech"]},
            "add_subtitles": False,
            "add_background_music": False,
            "generate_social_media_copywriting": False,
            "video_title": "capsule_plan_test",
            "voice_volume": 1.5,
        }
        flow.audio_generator.generate_audios = MagicMock()
        flow.image_generator.generate_reference_images = MagicMock(return_value={"reference_images": []})
        flow.image_generator.generate_scene_images = MagicMock(return_value={"outputs": {0: "/tmp/images/scene.png"}})
        flow.video_generator.generate_videos = MagicMock(return_value={"outputs": {0: "/tmp/videos/scene.mp4"}, "summary": {}})
        flow.image_generator.generate_cover_image = MagicMock(return_value="/tmp/final/cover.jpg")
        flow.post_processor.concatenate_videos = MagicMock(return_value="/tmp/final/base.mp4")
        flow.post_processor.add_background_music = MagicMock(return_value="/tmp/final/base.mp4")
        flow.social_media_generator = MagicMock()

        with patch("video_workflows.general_video.flow.tqdm", lambda total, desc, unit: _NoopProgress()):
            result = flow._execute_generation_phase()

        self.assertTrue(result["success"])
        self.assertEqual(
            flow.video_generator.generate_videos.call_args.kwargs["execution_directive"],
            {"post_steps": ["mute_audio"], "prompt_negatives": ["no speech"]},
        )
        self.assertEqual(
            flow.post_processor.concatenate_videos.call_args.kwargs["execution_directive"],
            {"post_steps": ["mute_audio"], "prompt_negatives": ["no speech"]},
        )

    def test_generation_phase_stops_before_assembly_when_scene_videos_are_blocked(self):
        flow = AgnoGeneralVideoFlow()
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            output_dirs = {
                "audios": str(tmp / "audios"),
                "reference_images": str(tmp / "references"),
                "images": str(tmp / "images"),
                "videos": str(tmp / "videos"),
                "final": str(tmp / "final"),
                "temp": str(tmp / "temp"),
                "work": str(tmp / "work"),
            }
            for path in output_dirs.values():
                Path(path).mkdir(parents=True, exist_ok=True)
            storyboard_path = tmp / "storyboard.json"
            storyboard_path.write_text('{"storyboard":[{"scene_id":0}]}', encoding="utf-8")

            flow.state = {
                "storyboard": [{"scene_id": 0, "duration": 1.5, "subtitles": ["字幕"]}],
                "workspace_dir": str(tmp),
                "reference_design": {},
                "content_requirements": {
                    "video_elements": {"needs_audio": False, "needs_subtitles": True, "needs_bgm": True}
                },
                "output_dirs": output_dirs,
                "aspect_ratio": "9:16",
                "enable_image_quality_check": False,
                "enable_video_quality_check": True,
                "user_reference_images": [],
                "reference_analysis_results": [],
                "art_style_selection": {},
                "engine_selection": {"video_engine": "veo3.1"},
                "add_subtitles": True,
                "add_background_music": True,
                "generate_social_media_copywriting": False,
                "video_title": "blocked_scene_video",
                "voice_volume": 1.5,
                "storyboard_path": str(storyboard_path),
            }
            flow.audio_generator.generate_audios = MagicMock()
            flow.image_generator.generate_reference_images = MagicMock(return_value={"reference_images": []})
            flow.image_generator.generate_scene_images = MagicMock(
                return_value={"outputs": {}, "summary": {"total": 1, "successful": 0, "failed": 1}}
            )
            flow.video_generator.generate_videos = MagicMock(
                return_value={
                    "outputs": {},
                    "summary": {
                        "total": 1,
                        "generated": 0,
                        "failed": 1,
                        "video_route": "external_video_engine",
                        "fallback_blocked": True,
                        "fallback_blocked_reason": "required_flags include native_audio",
                    },
                }
            )
            flow.post_processor.add_subtitles = MagicMock(return_value={"outputs": {}})
            flow.image_generator.generate_cover_image = MagicMock(return_value=str(tmp / "final" / "cover.jpg"))
            flow.post_processor.concatenate_videos = MagicMock(return_value=str(tmp / "final" / "base.mp4"))
            flow.post_processor.add_background_music = MagicMock(return_value=str(tmp / "final" / "base.mp4"))

            with patch("video_workflows.general_video.flow.tqdm", lambda total, desc, unit: _NoopProgress()):
                result = flow._execute_generation_phase()

        self.assertFalse(result["success"])
        self.assertIn("video_fallback_blocked", result["generation_blockers"])
        self.assertIn("scene_videos_incomplete", result["generation_blockers"])
        self.assertTrue(result["artifact_manifest_path"])
        flow.post_processor.add_subtitles.assert_not_called()
        flow.image_generator.generate_cover_image.assert_not_called()
        flow.post_processor.concatenate_videos.assert_not_called()
        flow.post_processor.add_background_music.assert_not_called()

    def test_post_processor_mutes_video_segments_before_concatenation(self):
        flow = AgnoGeneralVideoFlow()
        flow.state = {}
        processor = flow.post_processor
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            scene_path = tmp / "scene.mp4"
            scene_path.write_bytes(b"fake")
            output_path = tmp / "final.mp4"
            temp_dir = tmp / "capsule-post"
            muted_path = tmp / "muted_0.mp4"

            processor.concat_tool._run = MagicMock(
                return_value={"status": "success", "output_path": str(output_path)}
            )
            processor._strip_audio_track = MagicMock(return_value=str(muted_path))

            with patch(
                "src.runtime.general_video_crew.post_processor.VideoTimeLengthManager.get_video_duration",
                return_value=1.5,
            ):
                result = processor.concatenate_videos(
                    video_result={"outputs": {0: str(scene_path)}},
                    audio_result=[],
                    storyboard=[{"duration": 1.5}],
                    cover_image="",
                    output_path=str(output_path),
                    temp_dir=temp_dir,
                    execution_directive={"post_steps": ["mute_audio"]},
                )

        self.assertEqual(result, str(output_path))
        processor._strip_audio_track.assert_called_once_with(str(scene_path), temp_dir, 0)
        self.assertEqual(processor.concat_tool._run.call_args.kwargs["video_paths"], [str(muted_path)])


class VideoGeneratorDirectiveTest(unittest.TestCase):
    def test_video_generator_applies_prompt_negatives_to_batch_scenes(self):
        generator = VideoGenerator()
        generator.video_batch_tool._run = MagicMock(
            return_value={"outputs": {0: "/tmp/out.mp4"}, "summary": {"successful": 1}}
        )
        image_path = Path("/tmp/capsule-directive-image.png")
        image_path.write_bytes(b"fake")
        try:
            generator._generate_video_batch(
                scene_list=[(0, {"video_prompt_chinese": "人物说话"})],
                image_outputs={0: str(image_path)},
                output_dir="/tmp/videos",
                engine="jimeng35pro",
                aspect_ratio="9:16",
                execution_directive={"prompt_negatives": ["no speech", "no dialogue"]},
            )
        finally:
            image_path.unlink(missing_ok=True)

        scene = generator.video_batch_tool._run.call_args.kwargs["scenes"][0]
        self.assertIn("no speech", scene["video_prompt"])
        self.assertIn("no dialogue", scene["video_prompt"])

    def test_video_generator_fallback_chain_respects_native_audio_requirement(self):
        generator = VideoGenerator()

        with patch.dict(os.environ, {"JULING_API_KEY": "x", "JULING_BASE_URL": "x"}, clear=True):
            chain = generator._fallback_engines(
                "veo3.1",
                required_flags=["image_to_video", "native_audio"],
            )

        self.assertEqual(chain[0], "veo3.1")
        self.assertIn("jimeng35pro", chain)
        self.assertNotIn("seedance-fast", chain)

    def test_video_generator_blocks_static_fallback_when_native_audio_is_required(self):
        generator = VideoGenerator()
        generator._fallback_engines = MagicMock(return_value=["veo3.1"])
        generator._generate_video_batch = MagicMock(return_value={})
        generator._fallback_to_image_videos = MagicMock(return_value={0: "/tmp/fallback.mp4"})

        result = generator.generate_videos(
            storyboard=[{"duration": 1.5}],
            image_result={"outputs": {0: "/tmp/scene.png"}},
            output_dir="/tmp/videos",
            engine="veo3.1",
            required_flags=["image_to_video", "native_audio"],
        )

        self.assertEqual(result["outputs"], {})
        self.assertEqual(result["summary"]["video_route"], "external_video_engine")
        self.assertTrue(result["summary"]["fallback_blocked"])
        self.assertIn("native_audio", result["summary"]["fallback_blocked_reason"])
        generator._fallback_to_image_videos.assert_not_called()

    def test_flow_marks_generation_failure_when_video_route_is_blocked(self):
        flow = AgnoGeneralVideoFlow()
        flow.state = {
            "storyboard": [{"duration": 1.5}],
            "workspace_dir": "/tmp/native-audio-blocked",
            "output_dirs": {},
            "final_video": "",
            "cover_image": "",
            "storyboard_path": "/tmp/native-audio-blocked/storyboard.json",
            "artifact_manifest_path": "",
            "video_title": "blocked route",
            "social_media_copywriting": None,
            "engine_selection": {"video_engine": "veo3.1"},
            "image_generation_result": {"summary": {"successful": 1, "failed": 0}},
            "video_generation_result": {
                "summary": {
                    "total": 1,
                    "generated": 0,
                    "failed": 1,
                    "video_route": "external_video_engine",
                    "fallback_blocked": True,
                    "fallback_blocked_reason": "required_flags include native_audio",
                }
            },
        }

        result = flow._build_final_result()

        self.assertFalse(result["success"])
        self.assertIn("video_fallback_blocked", result["generation_blockers"])
        self.assertEqual(result["generation_summary"]["video_route"], "external_video_engine")


class _NoopProgress:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def update(self, _amount):
        return None


if __name__ == "__main__":
    unittest.main()
