import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))

from src.capsule_resolver import (  # noqa: E402
    load_tool_capabilities,
    load_all_tools,
    resolve_role,
    resolve_video_fallback,
)


# guofeng_history 的视频角色（见设计文档 §3 L3）
GUOFENG_VIDEO_ROLE = {
    "modality": "video",
    "requires": ["image_to_video"],
    "prefers_enums": {"emotion_expressiveness": "high"},
    "validated_with": "SeedanceFastVideoGeneratorTool",
}


class ResolveRoleTest(unittest.TestCase):
    def test_requires_flag_filters_out_tools_without_capability(self):
        tools = {
            "ImgVidTool": {
                "modality": "video",
                "provides": {"flags": {"image_to_video": True}},
                "requires_env": ["K1"],
            },
            "TextVidTool": {
                "modality": "video",
                "provides": {"flags": {"image_to_video": False, "text_to_video": True}},
                "requires_env": ["K1"],
            },
        }
        role = {"modality": "video", "requires": ["image_to_video"]}

        result = resolve_role(role, tools, available_env={"K1"})

        self.assertEqual(result.selected, "ImgVidTool")
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.fallback, [])

    def test_prefers_hits_rank_candidates(self):
        tools = {
            "Plain": {
                "modality": "video",
                "provides": {"flags": {"image_to_video": True}},
                "tags": [],
                "requires_env": ["K1"],
            },
            "Rich": {
                "modality": "video",
                "provides": {"flags": {"image_to_video": True}},
                "tags": ["cinematic", "fast_iteration"],
                "requires_env": ["K1"],
            },
        }
        role = {
            "modality": "video",
            "requires": ["image_to_video"],
            "prefers": ["cinematic", "fast_iteration"],
        }

        result = resolve_role(role, tools, available_env={"K1"})

        self.assertEqual(result.selected, "Rich")
        self.assertEqual(result.fallback, ["Plain"])

    def test_status_substituted_when_selected_differs_from_validated_with(self):
        tools = {
            "Alt": {
                "modality": "video",
                "provides": {"flags": {"image_to_video": True}},
                "requires_env": ["K1"],
            },
        }
        role = {
            "modality": "video",
            "requires": ["image_to_video"],
            "validated_with": "Original",
        }

        result = resolve_role(role, tools, available_env={"K1"})

        self.assertEqual(result.selected, "Alt")
        self.assertEqual(result.status, "substituted")

    def test_cost_tier_breaks_ties_lower_first(self):
        tools = {
            "Pricey": {
                "modality": "video",
                "provides": {"flags": {"image_to_video": True}},
                "requires_env": ["K1"],
                "cost_tier": "high",
            },
            "Cheap": {
                "modality": "video",
                "provides": {"flags": {"image_to_video": True}},
                "requires_env": ["K1"],
                "cost_tier": "low",
            },
        }
        role = {"modality": "video", "requires": ["image_to_video"]}

        result = resolve_role(role, tools, available_env={"K1"})

        self.assertEqual(result.selected, "Cheap")
        self.assertEqual(result.fallback, ["Pricey"])

    def test_validated_tool_wins_tie_over_cheaper(self):
        tools = {
            "Cheap": {
                "modality": "image",
                "provides": {"flags": {"text_to_image": True}},
                "requires_env": ["K1"],
                "cost_tier": "low",
            },
            "Validated": {
                "modality": "image",
                "provides": {"flags": {"text_to_image": True}},
                "requires_env": ["K1"],
                "cost_tier": "medium",
            },
        }
        role = {
            "modality": "image",
            "requires": ["text_to_image"],
            "validated_with": "Validated",
        }

        result = resolve_role(role, tools, available_env={"K1"})

        self.assertEqual(result.selected, "Validated")
        self.assertEqual(result.status, "ok")

    def test_prefers_still_beats_validated(self):
        tools = {
            "Better": {
                "modality": "image",
                "provides": {"flags": {"text_to_image": True}},
                "tags": ["high_quality"],
                "requires_env": ["K1"],
            },
            "Validated": {
                "modality": "image",
                "provides": {"flags": {"text_to_image": True}},
                "tags": [],
                "requires_env": ["K1"],
            },
        }
        role = {
            "modality": "image",
            "requires": ["text_to_image"],
            "prefers": ["high_quality"],
            "validated_with": "Validated",
        }

        result = resolve_role(role, tools, available_env={"K1"})

        self.assertEqual(result.selected, "Better")
        self.assertEqual(result.status, "substituted")

    def test_requires_enums_filters_mismatched_value(self):
        tools = {
            "Zh": {
                "modality": "voice",
                "provides": {"enums": {"lang": "zh-CN"}},
                "requires_env": ["K1"],
            },
            "En": {
                "modality": "voice",
                "provides": {"enums": {"lang": "en-US"}},
                "requires_env": ["K1"],
            },
        }
        role = {"modality": "voice", "requires_enums": {"lang": "zh-CN"}}

        result = resolve_role(role, tools, available_env={"K1"})

        self.assertEqual(result.selected, "Zh")
        self.assertEqual(result.fallback, [])

    def test_requires_limits_member_check_filters_out(self):
        tools = {
            "Wide": {
                "modality": "video",
                "provides": {
                    "flags": {"image_to_video": True},
                    "limits": {"aspect_ratios": ["16:9"]},
                },
                "requires_env": ["K1"],
            },
            "Vertical": {
                "modality": "video",
                "provides": {
                    "flags": {"image_to_video": True},
                    "limits": {"aspect_ratios": ["16:9", "9:16"]},
                },
                "requires_env": ["K1"],
            },
        }
        role = {
            "modality": "video",
            "requires": ["image_to_video"],
            "requires_limits": {"aspect_ratios": "9:16"},
        }

        result = resolve_role(role, tools, available_env={"K1"})

        self.assertEqual(result.selected, "Vertical")
        self.assertEqual(result.fallback, [])

    def test_forbids_tag_excludes_tool(self):
        tools = {
            "Realistic": {
                "modality": "image",
                "provides": {"flags": {"text_to_image": True}},
                "tags": ["realistic_photo"],
                "requires_env": ["K1"],
            },
            "Ink": {
                "modality": "image",
                "provides": {"flags": {"text_to_image": True}},
                "tags": ["ink_wash_friendly"],
                "requires_env": ["K1"],
            },
        }
        role = {
            "modality": "image",
            "requires": ["text_to_image"],
            "forbids": ["realistic_photo"],
        }

        result = resolve_role(role, tools, available_env={"K1"})

        self.assertEqual(result.selected, "Ink")
        self.assertEqual(result.fallback, [])

    def test_blocked_reports_unmet_requires(self):
        tools = {
            "NoAudio": {
                "modality": "video",
                "provides": {"flags": {"image_to_video": True, "native_audio": False}},
                "requires_env": ["K1"],
            },
        }
        role = {"modality": "video", "requires": ["native_audio"]}

        result = resolve_role(role, tools, available_env={"K1"})

        self.assertEqual(result.selected, None)
        self.assertEqual(result.status, "blocked")
        self.assertIn("native_audio", result.missing)


class AcceptanceTest(unittest.TestCase):
    """端到端：加载真实 L2，验证胶囊角色在不同本地环境下的撮合与自动替代。"""

    def setUp(self):
        self.tools = load_tool_capabilities()

    def test_picks_validated_tool_when_its_env_is_available(self):
        env = {"JULING_API_KEY", "JULING_BASE_URL", "VEO3_API_KEY", "VEO3_BASE_URL"}

        result = resolve_role(GUOFENG_VIDEO_ROLE, self.tools, available_env=env)

        self.assertEqual(result.selected, "SeedanceFastVideoGeneratorTool")
        self.assertEqual(result.status, "ok")

    def test_auto_substitutes_when_validated_tool_env_missing(self):
        # 清掉 JULING（即梦/seedance/veo3.1 共用此凭证），只剩 VEO3 凭证
        env = {"VEO3_API_KEY", "VEO3_BASE_URL"}

        result = resolve_role(GUOFENG_VIDEO_ROLE, self.tools, available_env=env)

        self.assertEqual(result.selected, "Veo3VideoGeneratorTool")
        self.assertEqual(result.status, "substituted")

    def test_blocked_when_no_video_env_available(self):
        result = resolve_role(GUOFENG_VIDEO_ROLE, self.tools, available_env=set())

        self.assertIsNone(result.selected)
        self.assertEqual(result.status, "blocked")
        self.assertIn("image_to_video", result.missing)


class VideoFallbackBridgeTest(unittest.TestCase):
    """运行时回退链：用 Resolver 按本地可用性动态算，替代全局静态 FALLBACK_ORDER。"""

    def setUp(self):
        self.tools = load_all_tools()

    def test_chain_is_local_availability_driven(self):
        chain = resolve_video_fallback(
            "seedance-fast", {"JULING_API_KEY", "JULING_BASE_URL"}, self.tools
        )

        self.assertEqual(chain[0], "seedance-fast")
        self.assertIn("jimeng35pro", chain)
        self.assertNotIn("veo3", chain)  # veo3 需要 VEO3 凭证，本地无

    def test_chain_includes_veo3_when_env_present(self):
        chain = resolve_video_fallback(
            "seedance-fast",
            {"JULING_API_KEY", "JULING_BASE_URL", "VEO3_API_KEY", "VEO3_BASE_URL"},
            self.tools,
        )

        self.assertIn("veo3", chain)

    def test_chain_defaults_to_engine_when_no_env(self):
        chain = resolve_video_fallback("seedance-fast", set(), self.tools)

        self.assertEqual(chain, ["seedance-fast"])


if __name__ == "__main__":
    unittest.main()
