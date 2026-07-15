import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))

from src.capsule_resolver import (  # noqa: E402
    load_tool_capabilities,
    load_all_tools,
    resolve_role,
    resolve_video_fallback,
)


PUBLIC_VIDEO_ROLE = {
    "modality": "video",
    "requires": ["image_to_video"],
    "prefers_enums": {"emotion_expressiveness": "high"},
    "validated_with": "Seedance20VideoGeneratorTool",
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

    def test_env_alternatives_accept_any_complete_group(self):
        tools = {
            "ImageTool": {
                "modality": "image",
                "provides": {"flags": {"text_to_image": True}},
                "requires_env_any": [["PRIMARY_KEY", "PRIMARY_BASE"], ["COMPAT_KEY", "COMPAT_BASE"]],
            },
            "OtherTool": {
                "modality": "image",
                "provides": {"flags": {"text_to_image": True}},
                "requires_env": ["OTHER_KEY"],
            },
        }
        role = {"modality": "image", "requires": ["text_to_image"], "validated_with": "ImageTool"}

        incomplete = resolve_role(role, tools, available_env={"COMPAT_KEY"})
        result = resolve_role(role, tools, available_env={"COMPAT_KEY", "COMPAT_BASE"})

        self.assertIsNone(incomplete.selected)
        self.assertEqual(incomplete.status, "blocked")
        self.assertEqual(result.selected, "ImageTool")
        self.assertEqual(result.status, "ok")

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
        self.tools = load_tool_capabilities(ROOT / "lib" / "config" / "tool_capabilities.yaml")

    def test_picks_validated_tool_when_its_env_is_available(self):
        env = {"ARK_API_KEY", "ARK_SEEDANCE_MODEL"}

        result = resolve_role(PUBLIC_VIDEO_ROLE, self.tools, available_env=env)

        self.assertEqual(result.selected, "Seedance20VideoGeneratorTool")
        self.assertEqual(result.status, "ok")

    def test_blocked_when_no_video_env_available(self):
        result = resolve_role(PUBLIC_VIDEO_ROLE, self.tools, available_env=set())

        self.assertIsNone(result.selected)
        self.assertEqual(result.status, "blocked")
        self.assertIn("image_to_video", result.missing)

    def test_official_image_env_keeps_validated_image_tool(self):
        role = {"modality": "image", "requires": [], "validated_with": "VolcengineImageGeneratorTool"}
        env = {"ARK_API_KEY", "ARK_SEEDREAM_MODEL"}

        result = resolve_role(role, self.tools, available_env=env)

        self.assertEqual(result.selected, "VolcengineImageGeneratorTool")
        self.assertEqual(result.status, "ok")


class VideoFallbackBridgeTest(unittest.TestCase):
    """运行时回退链：用 Resolver 按本地可用性动态算，替代全局静态 FALLBACK_ORDER。"""

    def setUp(self):
        self.tools = dict(load_tool_capabilities(ROOT / "lib" / "config" / "tool_capabilities.yaml"))

    def test_chain_is_local_availability_driven(self):
        chain = resolve_video_fallback(
            "seedance2.0", {"ARK_API_KEY", "ARK_SEEDANCE_MODEL"}, self.tools
        )

        self.assertEqual(chain, ["seedance2.0"])

    def test_chain_defaults_to_engine_when_no_env(self):
        chain = resolve_video_fallback("seedance2.0", set(), self.tools)

        self.assertEqual(chain, ["seedance2.0"])


class ToolCapabilityVocabularyTest(unittest.TestCase):
    def test_tool_capabilities_only_use_l1_vocabulary(self):
        capabilities = yaml.safe_load((ROOT / "lib" / "config" / "capabilities.yaml").read_text(encoding="utf-8"))
        tools = yaml.safe_load((ROOT / "lib" / "config" / "tool_capabilities.yaml").read_text(encoding="utf-8"))["tools"]
        modalities = capabilities["modalities"]

        errors = []
        for tool_name, tool in tools.items():
            modality = tool.get("modality")
            vocab = modalities.get(modality)
            if not vocab:
                errors.append(f"{tool_name}: unknown modality {modality}")
                continue

            valid_flags = set((vocab.get("flags") or {}).keys())
            valid_enums = set((vocab.get("enums") or {}).keys())
            valid_limits = set((vocab.get("limits") or {}).keys())
            valid_tags = set(vocab.get("tags") or [])
            provides = tool.get("provides") or {}

            for flag in (provides.get("flags") or {}):
                if flag not in valid_flags:
                    errors.append(f"{tool_name}: unknown {modality} flag {flag}")
            for enum in (provides.get("enums") or {}):
                if enum not in valid_enums:
                    errors.append(f"{tool_name}: unknown {modality} enum {enum}")
            for limit in (provides.get("limits") or {}):
                if limit not in valid_limits:
                    errors.append(f"{tool_name}: unknown {modality} limit {limit}")
            for tag in tool.get("tags") or []:
                if tag not in valid_tags:
                    errors.append(f"{tool_name}: unknown {modality} tag {tag}")

        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
