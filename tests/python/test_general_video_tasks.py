import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

from video_workflows.general_video.tasks import AgnoVideoTasks  # noqa: E402
from video_workflows.general_video.crew import (  # noqa: E402
    AgnoGeneralVideoCrew,
    enforce_capsule_storyboard_scene_range,
)


class GeneralVideoTasksParseTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tasks = AgnoVideoTasks(MagicMock())

    def test_create_storyboard_accepts_storyboard_key(self):
        parsed = self.tasks._parse_json_response(
            '{"storyboard":[{"scene_id":1,"description":"first"}]}',
            "create_storyboard",
        )

        self.assertIn("scenes", parsed)
        self.assertEqual(len(parsed["scenes"]), 1)
        self.assertEqual(parsed["scenes"][0]["scene_id"], 1)

    def test_create_storyboard_accepts_raw_scene_list(self):
        parsed = self.tasks._parse_json_response(
            '[{"scene_id":1,"description":"first"},{"scene_id":2,"description":"second"}]',
            "create_storyboard",
        )

        self.assertIn("scenes", parsed)
        self.assertEqual(len(parsed["scenes"]), 2)
        self.assertEqual(parsed["scenes"][1]["description"], "second")


class OptionalPlanningTaskShortCircuitTest(unittest.TestCase):
    def setUp(self) -> None:
        self.agents = MagicMock()
        self.tasks = AgnoVideoTasks(self.agents)

    def test_select_voice_skips_agent_when_audio_not_needed(self):
        result = self.tasks.select_voice("不要旁白", {"scenes": [{}]}, needs_audio=False)

        self.assertEqual(result["voice_mode"], "none")
        self.agents.get_voice_selector.assert_not_called()

    def test_generate_narration_skips_agent_when_audio_not_needed(self):
        result = self.tasks.generate_narration(
            "不要旁白",
            {"scenes": [{"scene_id": 0}, {"scene_id": 1}]},
            needs_audio=False,
        )

        self.assertEqual(
            result["narrations"],
            [
                {"scene_index": 0, "narration": "", "voice_character_tag": "", "speed_ratio": 1.0, "video_generation_type": "image_to_video"},
                {"scene_index": 1, "narration": "", "voice_character_tag": "", "speed_ratio": 1.0, "video_generation_type": "image_to_video"},
            ],
        )
        self.agents.get_script_writer.assert_not_called()

    def test_generate_subtitles_skips_agent_when_subtitles_not_needed(self):
        result = self.tasks.generate_subtitles(
            "不要字幕",
            {"scenes": [{"scene_id": 0}, {"scene_id": 1}]},
            {"narrations": []},
            needs_subtitles=False,
        )

        self.assertEqual(
            result["scene_subtitles"],
            [
                {"scene_index": 0, "subtitles": []},
                {"scene_index": 1, "subtitles": []},
            ],
        )
        self.agents.get_script_writer.assert_not_called()

    def test_select_music_skips_agent_when_bgm_not_needed(self):
        result = self.tasks.select_music("不要背景音乐", {"scenes": [{}]}, needs_bgm=False)

        self.assertFalse(result["needs_bgm"])
        self.assertEqual(result["music_volume"], 0)
        self.agents.get_music_selector.assert_not_called()

    def test_select_music_uses_capsule_defaults_without_agent(self):
        result = self.tasks.select_music(
            "羊毛毡 ASMR",
            {"scenes": [{}]},
            needs_bgm=True,
            music_defaults={"bgm_volume": 0.04, "bgm_mood": "soft healing kitchen instrumental"},
        )

        self.assertTrue(result["needs_bgm"])
        self.assertEqual(result["music_source"], "online")
        self.assertEqual(result["music_volume"], 0.04)
        self.assertIn("soft healing kitchen instrumental", result["music_query"])
        self.agents.get_music_selector.assert_not_called()

    def test_select_sound_effects_skips_agent_when_library_is_empty(self):
        with patch(
            "src.utils.sound_effects_utils.SoundEffectsManager.get_available_sound_effects",
            return_value=[],
        ):
            result = self.tasks.select_sound_effects(
                "保留原生 ASMR 触感声",
                {"scenes": [{"scene_id": 0}]},
                {"narrations": []},
            )

        self.assertFalse(result["needs_sound_effects"])
        self.assertEqual(result["sound_effects"], {})
        self.assertEqual(result["reason"], "sound_effect_library_empty")
        self.agents.get_content_requirements_analyzer.assert_not_called()

    def test_select_video_engine_uses_forced_engine_without_agent(self):
        result = self.tasks.select_video_engine(
            "胶囊要求",
            {"scenes": [{}]},
            "pure_image_to_video",
            forced_engine="seedance2.0",
        )

        self.assertEqual(result["video_engine"], "seedance2.0")
        self.assertTrue(result["user_specified"])
        self.assertEqual(result["override_reason"], "runtime_or_capsule_forced_engine")
        self.agents.get_video_engine_selector.assert_not_called()


class PlanningPhaseContractOverrideTest(unittest.TestCase):
    def test_run_planning_phase_fails_fast_when_storyboard_has_no_scenes(self):
        crew = AgnoGeneralVideoCrew.__new__(AgnoGeneralVideoCrew)
        crew.tasks_manager = MagicMock()
        crew.tasks_manager.plan_video_production.return_value = {
            "video_generation_mode": "pure_image_to_video",
            "video_elements": {"needs_audio": True, "needs_subtitles": True, "needs_bgm": True},
        }
        crew.tasks_manager.create_story.return_value = {"title": "test"}
        crew.tasks_manager.create_storyboard.return_value = {"scenes": []}
        crew.tasks_manager.select_voice.return_value = {"voice_mode": "none"}
        crew.tasks_manager.generate_narration.return_value = {"narrations": []}
        crew.tasks_manager.generate_subtitles.return_value = {"scene_subtitles": []}
        crew.tasks_manager.select_music.return_value = {"needs_bgm": False}
        crew.tasks_manager.select_sound_effects.return_value = {"needs_sound_effects": False, "sound_effects": {}}
        crew.tasks_manager.select_video_engine.return_value = {"video_engine": "seedance2.0"}
        crew.tasks_manager.select_art_style.return_value = {"visual_style": {}}
        crew.tasks_manager.design_reference.return_value = {}

        with self.assertRaisesRegex(ValueError, "分镜为空"):
            crew.run_planning_phase("便利店夜班店长", 12, state={})

        crew.tasks_manager.select_voice.assert_not_called()
        crew.tasks_manager.generate_narration.assert_not_called()
        crew.tasks_manager.generate_subtitles.assert_not_called()
        crew.tasks_manager.select_music.assert_not_called()
        crew.tasks_manager.select_sound_effects.assert_not_called()
        crew.tasks_manager.select_video_engine.assert_not_called()
        crew.tasks_manager.select_art_style.assert_not_called()
        crew.tasks_manager.design_reference.assert_not_called()

    def test_run_planning_phase_fails_fast_when_required_planning_task_is_cancelled(self):
        crew = AgnoGeneralVideoCrew.__new__(AgnoGeneralVideoCrew)
        crew.tasks_manager = MagicMock()
        crew.tasks_manager.plan_video_production.return_value = {
            "video_generation_mode": "pure_image_to_video",
            "video_elements": {"needs_audio": True, "needs_subtitles": True, "needs_bgm": True},
        }
        crew.tasks_manager.create_story.return_value = {"title": "test"}
        crew.tasks_manager.create_storyboard.return_value = {"scenes": [{"scene_id": 0}]}
        crew.tasks_manager.select_voice.return_value = {"voice_mode": "single"}
        crew.tasks_manager.generate_narration.return_value = {"raw_output": "Operation cancelled by user"}
        crew.tasks_manager.generate_subtitles.return_value = {"scene_subtitles": []}
        crew.tasks_manager.select_music.return_value = {"needs_bgm": True}
        crew.tasks_manager.select_sound_effects.return_value = {"needs_sound_effects": False, "sound_effects": {}}
        crew.tasks_manager.select_video_engine.return_value = {"video_engine": "seedance2.0"}
        crew.tasks_manager.select_art_style.return_value = {"visual_style": {}}
        crew.tasks_manager.design_reference.return_value = {}

        with self.assertRaisesRegex(ValueError, "generate_narration"):
            crew.run_planning_phase("杨震暮夜却金", 15, state={})

        crew.tasks_manager.generate_subtitles.assert_not_called()
        crew.tasks_manager.select_music.assert_not_called()
        crew.tasks_manager.select_sound_effects.assert_not_called()
        crew.tasks_manager.select_video_engine.assert_not_called()
        crew.tasks_manager.select_art_style.assert_not_called()
        crew.tasks_manager.design_reference.assert_not_called()

    def test_run_planning_phase_applies_state_output_contract_before_optional_tasks(self):
        crew = AgnoGeneralVideoCrew.__new__(AgnoGeneralVideoCrew)
        crew.tasks_manager = MagicMock()
        crew.tasks_manager.plan_video_production.return_value = {
            "video_generation_mode": "pure_image_to_video",
            "video_elements": {"needs_audio": True, "needs_subtitles": True, "needs_bgm": True},
        }
        crew.tasks_manager.create_story.return_value = {"title": "test"}
        crew.tasks_manager.create_storyboard.return_value = {"scenes": [{"scene_id": 0}]}
        crew.tasks_manager.select_voice.return_value = {"voice_mode": "none"}
        crew.tasks_manager.generate_narration.return_value = {"narrations": []}
        crew.tasks_manager.generate_subtitles.return_value = {"scene_subtitles": []}
        crew.tasks_manager.select_music.return_value = {"needs_bgm": False}
        crew.tasks_manager.select_sound_effects.return_value = {"needs_sound_effects": False, "sound_effects": {}}
        crew.tasks_manager.select_video_engine.return_value = {"video_engine": "seedance2.0"}
        crew.tasks_manager.select_art_style.return_value = {"visual_style": {}}
        crew.tasks_manager.design_reference.return_value = {}

        result = crew.run_planning_phase(
            "不要旁白，不要字幕，不要背景音乐",
            12,
            state={
                "add_subtitles": False,
                "add_background_music": False,
                "capsule_config": {
                    "has_narration": False,
                    "output_contract": {"voice": "none", "subtitle": "none", "bgm": "none"},
                },
            },
        )

        video_elements = result["plan_result"]["video_elements"]
        self.assertFalse(video_elements["needs_audio"])
        self.assertFalse(video_elements["needs_subtitles"])
        self.assertFalse(video_elements["needs_bgm"])
        crew.tasks_manager.select_voice.assert_called_once_with(
            "不要旁白，不要字幕，不要背景音乐",
            {"scenes": [{"scene_id": 0}]},
            False,
        )
        crew.tasks_manager.generate_subtitles.assert_called_once()
        self.assertFalse(crew.tasks_manager.generate_subtitles.call_args.args[3])
        crew.tasks_manager.select_music.assert_called_once()
        self.assertFalse(crew.tasks_manager.select_music.call_args.kwargs["needs_bgm"])

    def test_run_planning_phase_uses_declared_capsule_style_without_art_style_agent(self):
        crew = AgnoGeneralVideoCrew.__new__(AgnoGeneralVideoCrew)
        crew.tasks_manager = MagicMock()
        crew.tasks_manager.plan_video_production.return_value = {
            "video_generation_mode": "pure_image_to_video",
            "video_elements": {"needs_audio": False, "needs_subtitles": False, "needs_bgm": True},
        }
        crew.tasks_manager.create_story.return_value = {"title": "test"}
        crew.tasks_manager.create_storyboard.return_value = {"scenes": [{"scene_id": 0}]}
        crew.tasks_manager.select_voice.return_value = {"voice_mode": "none"}
        crew.tasks_manager.generate_narration.return_value = {"narrations": []}
        crew.tasks_manager.generate_subtitles.return_value = {"scene_subtitles": []}
        crew.tasks_manager.select_music.return_value = {"needs_bgm": True}
        crew.tasks_manager.select_sound_effects.return_value = {"needs_sound_effects": False, "sound_effects": {}}
        crew.tasks_manager.select_video_engine.return_value = {"video_engine": "seedance2.0"}
        crew.tasks_manager.design_reference.return_value = {}

        result = crew.run_planning_phase(
            "羊毛毡 ASMR",
            8,
            state={
                "capsule_name": "demo_style",
                "manual_video_engine": "seedance2.0",
                "capsule_config": {
                    "visual_style": {
                        "特效": {"质感": "干燥纤维手作质感"},
                        "构图": {"类型": "极近微距"},
                    }
                },
            },
        )

        crew.tasks_manager.select_art_style.assert_not_called()
        self.assertEqual(result["engine_result"]["video_engine"], "seedance2.0")
        self.assertEqual(result["art_style_result"]["style_code"], "capsule_visual_style")
        self.assertIn("纤维", result["art_style_result"]["visual_style"]["特效"]["质感"])


class CapsuleStoryboardSceneRangeTest(unittest.TestCase):
    def test_merges_micro_shots_to_capsule_generated_scene_range(self):
        planning_results = {
            "storyboard_result": {
                "scenes": [
                    {
                        "scene_id": i,
                        "description": f"微镜头 {i}",
                        "duration": 2.0,
                        "video_prompt_chinese": f"动作 {i}",
                        "character_ids": ["hands"] if i % 2 == 0 else ["tool"],
                    }
                    for i in range(18)
                ]
            },
            "narration_result": {"narrations": [{"narration": ""} for _ in range(18)]},
            "subtitles_result": {"scene_subtitles": [{"subtitles": []} for _ in range(18)]},
        }

        enforce_capsule_storyboard_scene_range(
            planning_results,
            {"generated_scene_count_range": [6, 8]},
        )

        scenes = planning_results["storyboard_result"]["scenes"]
        self.assertEqual(len(scenes), 8)
        self.assertEqual(sum(scene["duration"] for scene in scenes), 36.0)
        self.assertIn("微镜头 0", scenes[0]["description"])
        self.assertIn("微镜头 1", scenes[0]["description"])
        self.assertIn("动作 0", scenes[0]["video_prompt_chinese"])
        self.assertEqual(scenes[0]["character_ids"], ["hands", "tool"])
        self.assertEqual(len(planning_results["narration_result"]["narrations"]), 8)
        self.assertEqual(len(planning_results["subtitles_result"]["scene_subtitles"]), 8)
        self.assertEqual(
            planning_results["storyboard_result"]["capsule_scene_count_normalized"],
            {"original_count": 18, "target_count": 8},
        )


if __name__ == "__main__":
    unittest.main()
