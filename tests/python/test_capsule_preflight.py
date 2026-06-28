import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))

from src.capsule_resolver import load_all_tools  # noqa: E402
from src.capsule_preflight import (  # noqa: E402
    raise_if_blocked,
    run_preflight,
    scan_available_env,
    to_execution_plan,
    to_report,
)


GUOFENG = {
    "name": "guofeng_history",
    "roles": {
        "image": {"requires": [], "validated_with": "GptImage2Tool"},
        "video": {"requires": ["image_to_video"], "validated_with": "SeedanceFastVideoGeneratorTool"},
        "voice": {"validated_with": "minimax/Chinese_deep_voiced_male_vv1"},
    },
    "output_contract": {
        "clip_audio": "silent",
        "voice": "unified_tts",
        "on_frame_text": "none",
        "subtitle": "overlay",
        "bgm": "external",
    },
}


class ScanEnvTest(unittest.TestCase):
    def test_only_keys_with_values_are_available(self):
        env = scan_available_env({"A": "x", "B": "", "C": None, "D": "y"})
        self.assertEqual(env, {"A", "D"})


class PreflightTest(unittest.TestCase):
    def setUp(self):
        self.tools = load_all_tools()

    def test_full_env_resolves_all_roles_ok(self):
        env = {"GPT_IMAGE2_API_KEY", "JULING_API_KEY", "JULING_BASE_URL", "MINIMAX_API_KEY"}

        pf = run_preflight(GUOFENG, self.tools, env)

        self.assertEqual(pf.status, "ok")
        self.assertEqual(pf.roles["image"].selected, "GptImage2Tool")
        self.assertEqual(pf.roles["video"].selected, "SeedanceFastVideoGeneratorTool")
        self.assertEqual(pf.roles["voice"].selected, "minimax/Chinese_deep_voiced_male_vv1")
        self.assertEqual(pf.blocked, [])

    def test_blocked_role_makes_preflight_blocked(self):
        env = {"MINIMAX_API_KEY"}  # 没有任何视频/图像凭证

        pf = run_preflight(GUOFENG, self.tools, env)

        self.assertEqual(pf.status, "blocked")
        self.assertIn("video", pf.blocked)
        self.assertIn("image_to_video", pf.roles["video"].missing)

    def test_substitution_requires_confirmation(self):
        capsule = {
            "name": "vid_only",
            "roles": {
                "video": {
                    "requires": ["image_to_video"],
                    "validated_with": "SeedanceFastVideoGeneratorTool",
                }
            },
            "output_contract": {"clip_audio": "silent"},
        }
        env = {"VEO3_API_KEY", "VEO3_BASE_URL"}  # 仅 veo3，替代发生

        pf = run_preflight(capsule, self.tools, env)

        self.assertEqual(pf.roles["video"].status, "substituted")
        self.assertEqual(pf.roles["video"].selected, "Veo3VideoGeneratorTool")
        self.assertEqual(pf.status, "needs_confirmation")

    def test_adapter_directive_is_bound_for_silent_contract_on_audio_tool(self):
        capsule = {
            "name": "silent_on_audio",
            "roles": {
                "video": {
                    "requires": ["image_to_video"],
                    "validated_with": "Jimeng35ProVideoGeneratorTool",
                }
            },
            "output_contract": {"clip_audio": "silent"},
        }
        env = {"JULING_API_KEY", "JULING_BASE_URL"}

        pf = run_preflight(capsule, self.tools, env)

        self.assertEqual(pf.roles["video"].selected, "Jimeng35ProVideoGeneratorTool")
        self.assertIn("mute_audio", pf.roles["video"].directive.post_steps)

    def test_adapter_blocked_contract_makes_preflight_blocked(self):
        capsule = {
            "name": "sfx_only_requires_voice_strip",
            "roles": {
                "video": {
                    "requires": ["image_to_video", "native_audio"],
                    "validated_with": "Jimeng35ProVideoGeneratorTool",
                }
            },
            "output_contract": {"clip_audio": "sfx_only"},
        }
        env = {"JULING_API_KEY", "JULING_BASE_URL"}

        pf = run_preflight(capsule, self.tools, env)

        self.assertEqual(pf.status, "blocked")
        self.assertIn("video", pf.blocked)
        self.assertIn("strip_voice_post_processor", pf.roles["video"].missing)

    def test_unapproved_on_frame_text_degradation_blocks(self):
        capsule = {
            "name": "text_requires_reliable_rendering",
            "roles": {
                "image": {
                    "requires": ["text_to_image"],
                    "validated_with": "Seedream5ImageGeneratorTool",
                }
            },
            "output_contract": {"on_frame_text": "required", "on_frame_text_fallback": "fail"},
        }
        env = {"JULING_API_KEY", "JULING_BASE_URL"}

        pf = run_preflight(capsule, self.tools, env)

        self.assertEqual(pf.status, "blocked")
        self.assertIn("image", pf.blocked)
        self.assertIn("on_frame_text", pf.roles["image"].missing)

    def test_audio_contract_only_applies_to_video_role(self):
        capsule = {
            "name": "asmr_native_audio",
            "roles": {
                "image": {
                    "requires": [],
                    "validated_with": "Gemini3ProImageGeneratorTool",
                },
                "video": {
                    "requires": ["image_to_video", "native_audio"],
                    "validated_with": "Jimeng35ProVideoGeneratorTool",
                },
            },
            "output_contract": {
                "clip_audio": "native",
                "voice": "none",
                "on_frame_text": "none",
                "subtitle": "none",
                "bgm": "none",
            },
        }
        env = {"GEMINI3_PRO_API_KEY", "GEMINI3_PRO_BASE_URL", "JULING_API_KEY", "JULING_BASE_URL"}

        pf = run_preflight(capsule, self.tools, env)

        self.assertEqual(pf.status, "ok")
        self.assertEqual(pf.roles["image"].status, "ok")
        self.assertEqual(pf.roles["video"].status, "ok")

    def test_felt_asmr_validated_veo31_satisfies_native_audio_role(self):
        capsule = {
            "name": "felt_asmr",
            "roles": {
                "video": {
                    "requires": ["image_to_video", "native_audio"],
                    "validated_with": "Veo31VideoGeneratorTool",
                }
            },
            "output_contract": {"clip_audio": "native", "voice": "none", "subtitle": "none"},
        }
        env = {"JULING_API_KEY", "JULING_BASE_URL"}

        pf = run_preflight(capsule, self.tools, env)

        self.assertEqual(pf.status, "ok")
        self.assertEqual(pf.roles["video"].selected, "Veo31VideoGeneratorTool")
        self.assertEqual(pf.roles["video"].status, "ok")


class PreflightArtifactTest(unittest.TestCase):
    def setUp(self):
        self.tools = load_all_tools()
        env = {"GPT_IMAGE2_API_KEY", "JULING_API_KEY", "JULING_BASE_URL", "MINIMAX_API_KEY"}
        self.pf = run_preflight(GUOFENG, self.tools, env)

    def test_report_lists_roles_and_status(self):
        report = to_report(self.pf)

        self.assertEqual(report["capsule"], "guofeng_history")
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["roles"]["video"]["selected"], "SeedanceFastVideoGeneratorTool")
        self.assertEqual(report["roles"]["video"]["status"], "ok")

    def test_execution_plan_binds_directive(self):
        capsule = {
            "name": "silent_on_audio",
            "roles": {
                "video": {
                    "requires": ["image_to_video"],
                    "validated_with": "Jimeng35ProVideoGeneratorTool",
                }
            },
            "output_contract": {"clip_audio": "silent"},
        }
        env = {"JULING_API_KEY", "JULING_BASE_URL"}
        pf = run_preflight(capsule, self.tools, env)

        plan = to_execution_plan(pf, capsule)

        self.assertEqual(plan["capsule"], "silent_on_audio")
        self.assertEqual(plan["output_contract"], {"clip_audio": "silent"})
        self.assertEqual(plan["roles"]["video"]["selected"], "Jimeng35ProVideoGeneratorTool")
        self.assertEqual(plan["roles"]["video"]["requires"], ["image_to_video"])
        self.assertIn("mute_audio", plan["roles"]["video"]["directive"]["post_steps"])


class RaiseIfBlockedTest(unittest.TestCase):
    def setUp(self):
        self.tools = load_all_tools()

    def test_blocked_raises_with_actionable_suggestion(self):
        pf = run_preflight(GUOFENG, self.tools, {"MINIMAX_API_KEY"})

        with self.assertRaises(ValueError) as ctx:
            raise_if_blocked(pf, self.tools)

        message = str(ctx.exception)
        self.assertIn("video", message)
        self.assertIn("image_to_video", message)
        self.assertIn("JULING_API_KEY", message)

    def test_runnable_preflight_does_not_raise(self):
        pf = run_preflight(GUOFENG, self.tools, {"JULING_API_KEY", "JULING_BASE_URL", "MINIMAX_API_KEY"})

        raise_if_blocked(pf, self.tools)  # 不抛即通过


if __name__ == "__main__":
    unittest.main()
