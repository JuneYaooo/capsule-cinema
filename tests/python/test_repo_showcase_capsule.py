import importlib.util
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
if str(TEST_DIR) not in sys.path:
    sys.path.insert(0, str(TEST_DIR))

from capsule_package_test_utils import (
    active_capsule_dir,
    load_active_capsule,
    package_file_entries,
    recipe_text,
)


ROOT = Path(__file__).resolve().parents[2]
CAPSULE_DIR = ROOT / "capsules" / "repo_showcase.capsule"


class RepoShowcaseCapsuleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tempdir = tempfile.TemporaryDirectory()
        cls.temp_root = Path(cls.tempdir.name)
        cls.manifest = {"capsule": load_active_capsule("repo_showcase")}
        script_rel = "scripts/render_repo_showcase_video.py"
        cls.renderer_source = (CAPSULE_DIR / script_rel).read_text(encoding="utf-8")
        script_target = cls.temp_root / script_rel
        script_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(CAPSULE_DIR / script_rel, script_target)

        script_path = cls.temp_root / script_rel
        spec = importlib.util.spec_from_file_location("repo_showcase_renderer", script_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cls.renderer = module

    @classmethod
    def tearDownClass(cls):
        cls.tempdir.cleanup()

    def capsule_text(self) -> str:
        capsule = self.manifest["capsule"]
        return recipe_text(capsule) + "\n" + json.dumps(capsule["quality_rules"], ensure_ascii=False)

    def quality_text(self) -> str:
        return json.dumps(self.manifest["capsule"]["quality_rules"], ensure_ascii=False)

    def test_manifest_defaults_use_taller_video_canvas(self):
        capsule = self.manifest["capsule"]
        config = capsule["config"]

        self.assertEqual(config["aspect_ratio"], "3:4")
        self.assertEqual((self.renderer.W, self.renderer.H), (1080, 1440))
        self.assertIn("3:4", capsule["description"])

    def test_manifest_public_copy_rules_capture_latest_user_feedback(self):
        capsule = self.manifest["capsule"]
        config = capsule["config"]
        rules_text = self.capsule_text() + json.dumps(config, ensure_ascii=False)

        self.assertIn("商用可用", rules_text)
        self.assertIn("不要默认", rules_text)
        self.assertIn("开源免费", rules_text)
        self.assertIn("不在视频画面写 CTA", rules_text)
        self.assertIn("价值密度总结", rules_text)
        self.assertNotIn("把项目名发给 Agent", rules_text)
        self.assertNotIn("安装这个 Skill", rules_text)
        self.assertNotIn("下条拆安装", rules_text)
        self.assertIn("怎么问", rules_text)
        self.assertIn("不要把单点反馈当成核心重做", rules_text)
        self.assertIn("不自动重渲染", rules_text)

    def test_manifest_exposes_only_short_silent_repo_showcase_route(self):
        capsule = self.manifest["capsule"]
        config = capsule["config"]
        input_schema = capsule["input_schema"]
        manifest_text = json.dumps(capsule, ensure_ascii=False)

        self.assertEqual(input_schema["fields"]["production_mode"]["default"], "short_silent_repo_showcase")
        self.assertEqual(config["output_contract"]["voice"], "none")
        self.assertEqual(config["output_contract"]["subtitle"], "none")
        self.assertEqual(config["target_duration"], 10)
        self.assertEqual(config["target_duration_max"], 10)
        self.assertNotIn("narrated_long_repo_showcase", manifest_text)

    def test_manifest_strict_silent_route_has_no_voice_tts_config(self):
        capsule = self.manifest["capsule"]
        config = capsule["config"]
        input_schema = capsule["input_schema"]

        for stale_key in (
            "tts_speed",
            "tts_volume",
            "voice_volume",
            "voiceover_required",
            "narrated_mode_requires_explicit_request",
        ):
            self.assertNotIn(stale_key, config)

        self.assertIn("Only short_silent_repo_showcase is exposed", input_schema["fields"]["production_mode"]["description"])
        self.assertEqual(config["output_contract"]["voice"], "none")
        self.assertEqual(config["output_contract"]["subtitle"], "none")
        self.assertNotIn("voiceover_required", input_schema)

    def test_manifest_silent_copy_planning_has_no_active_voiceover_outputs(self):
        capsule = self.manifest["capsule"]
        config_text = json.dumps(capsule["config"], ensure_ascii=False)
        method_text = recipe_text(capsule)

        for stale_phrase in (
            "完整旁白文案",
            "旁白级别的叙事草稿",
            "带旁白版本",
            "voiceover script",
        ):
            self.assertNotIn(stale_phrase, config_text)
            self.assertNotIn(stale_phrase, method_text)

        self.assertIn("无口播", method_text)
        self.assertIn("3-5 dense lines", method_text)
        self.assertIn("renderer_structured_cards", config_text)

    def test_renderer_has_no_tts_synthesis_path(self):
        source = self.renderer_source

        for stale_snippet in (
            "def synthesize_tts",
            "minimax_tts_tool",
            "voiceover.mp3",
            "zh_male_jieshuoxiaoming_moon_bigtts",
        ):
            self.assertNotIn(stale_snippet, source)

    def test_renderer_rejects_spoken_profile_fields(self):
        renderer = self.renderer

        for key in ("voiceover", "narration", "tts_text", "speech_text"):
            with self.subTest(key=key):
                with self.assertRaisesRegex(SystemExit, "silent-only"):
                    renderer.reject_spoken_profile_fields({key: "这段不应该进入 repo_showcase"})

    def test_manifest_quality_rules_forbid_internal_terms_in_visible_copy(self):
        rules_text = self.quality_text()

        for term in ["MIT", "商用可用", "长图按页面滚动", "页面滚动", "滚动展示", "缩放抖动"]:
            self.assertIn(term, rules_text)
        self.assertIn("公开视频", rules_text)
        self.assertIn("可见文案", rules_text)

    def test_package_file_manifest_checksums_match_zip_contents(self):
        for entry in package_file_entries("repo_showcase"):
            data = (CAPSULE_DIR / entry["package_path"]).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), entry["sha256"])
            self.assertEqual(len(data), entry["size"])

    def test_manifest_prioritizes_original_source_materials_before_readme_fallback(self):
        rules_text = self.capsule_text()

        self.assertLess(rules_text.index("仓库自带图片"), rules_text.index("README/GitHub/source"))
        self.assertLess(rules_text.index("README/GitHub/source"), rules_text.index("自制总结卡"))
        self.assertIn("README fallback 截图必须只包含 README 渲染内容区", rules_text)
        self.assertIn("不得把 GitHub 纯代码目录", rules_text)

    def test_renderer_layout_expands_middle_panel_on_taller_canvas(self):
        renderer = self.renderer

        self.assertEqual((renderer.W, renderer.H), (1080, 1440))
        x1, y1, x2, y2 = renderer.MIDDLE_PANEL_BOX
        self.assertGreaterEqual(x2 - x1, 930)
        self.assertGreaterEqual(y2 - y1, 590)
        self.assertGreaterEqual(renderer.BOTTOM_BOX_DEFAULTS[True][0], y2 + 20)

        image_box = renderer.image_boxes_for_content(470, 1)[0]
        self.assertGreaterEqual(image_box[2] - image_box[0], 860)
        self.assertGreaterEqual(image_box[3] - image_box[1], 440)
        self.assertLessEqual(image_box[3], renderer.MIDDLE_CONTENT_BOTTOM)

    def test_renderer_chooses_motion_from_source_aspect_ratio(self):
        renderer = self.renderer
        panel_box = (0, 0, 860, 460)

        tall = renderer.motion_plan_for_source((360, 1600), panel_box, requested_direction=None)
        self.assertEqual(tall["fit_mode"], "scroll_long_axis")
        self.assertEqual(tall["scale_mode"], "fit_width")
        self.assertEqual(tall["motion_direction"], "scroll_down")
        self.assertEqual(tall["motion_amount"], 0.0)

        wide = renderer.motion_plan_for_source((1800, 420), panel_box, requested_direction=None)
        self.assertEqual(wide["fit_mode"], "scroll_long_axis")
        self.assertEqual(wide["scale_mode"], "fit_height")
        self.assertEqual(wide["motion_direction"], "scroll_right")
        self.assertEqual(wide["motion_amount"], 0.0)

        similar = renderer.motion_plan_for_source((1200, 720), panel_box, requested_direction=None)
        self.assertEqual(similar["fit_mode"], "contain")
        self.assertEqual(similar["motion_direction"], "slide_in_right")
        self.assertEqual(similar["motion_amount"], 0.0)

    def test_renderer_zooms_regular_detail_images_instead_of_always_sliding(self):
        renderer = self.renderer
        panel_box = (0, 0, 860, 460)

        detail = renderer.motion_plan_for_source(
            (1200, 720),
            panel_box,
            requested_direction=None,
            requested_amount=0.08,
            content_features=["数据图表", "PPT 缩略图", "UI 面板"],
        )
        local = renderer.motion_plan_for_source(
            (1200, 720),
            panel_box,
            requested_direction="local_zoom",
            requested_amount=0.12,
            requested_focus="right",
        )

        self.assertEqual(detail["fit_mode"], "contain")
        self.assertEqual(detail["motion_direction"], "zoom_in")
        self.assertGreater(detail["motion_amount"], 0.0)
        self.assertEqual(detail["motion_focus"], "center")
        self.assertEqual(local["motion_direction"], "zoom_in")
        self.assertAlmostEqual(local["motion_amount"], 0.12)
        self.assertEqual(local["motion_focus"], "right")

    def test_renderer_supports_short_final_install_page_duration(self):
        renderer = self.renderer
        scenes = [
            {"bottom_title": "A"},
            {"bottom_title": "B"},
            {"bottom_title": "C"},
            {"bottom_title": "D"},
            {"bottom_title": "安装使用", "duration_seconds": 1.0},
        ]

        durations = renderer.compute_scene_durations({}, scenes, 10.0)

        self.assertAlmostEqual(sum(durations), 10.0, places=3)
        self.assertAlmostEqual(durations[-1], 1.0, places=3)
        for duration in durations[:-1]:
            self.assertAlmostEqual(duration, 2.25, places=3)

    def test_renderer_rejects_capsule_specific_forbidden_visible_copy(self):
        renderer = self.renderer

        violations = renderer.capsule_visible_copy_policy_violations(
            [
                "最后 1 秒写商用可用",
                "长图按页面滚动",
                "遵循 MIT 协议",
            ]
        )

        self.assertEqual(
            [item["term"] for item in violations],
            ["商用可用", "长图按页面滚动", "MIT"],
        )

    def test_manifest_defaults_capture_latest_layout_feedback(self):
        method_text = self.capsule_text()

        self.assertLess(self.renderer.top_title_y_for_profile({}), 128)
        self.assertGreaterEqual(self.renderer.top_title_line_gap_for_profile({}), 16)
        self.assertLess(self.renderer.resolve_top_subtitle({"top_subtitle": "项目 / 46k"}).count("·"), 1)
        self.assertIn("top_title_line_gap_preferred 至少 16", method_text)
        self.assertIn("中间主视觉", method_text)
        self.assertIn("middle_visual_title", self.renderer_source)

    def test_manifest_prefers_five_line_bottom_value_cards(self):
        text = self.capsule_text()

        self.assertIn("底部卡默认优先 5 行", text)
        self.assertIn("允许 4 行", text)
        self.assertIn("完整句子", text)
        self.assertIn("动态排版", text)

    def test_manifest_requires_humanized_public_self_media_copy(self):
        policy_text = self.capsule_text()

        self.assertIn("具体场景", policy_text)
        self.assertIn("目标用户", policy_text)
        self.assertIn("README 摘要", policy_text)
        self.assertIn("用户价值", policy_text)

    def test_renderer_resolves_usage_hint_subtitle_once(self):
        renderer = self.renderer

        subtitle = renderer.resolve_top_subtitle(
            {
                "top_subtitle": "Taste-Skill / 46.1k+ Stars",
                "top_subtitle_suffix": "5 张图看价值",
            }
        )
        existing = renderer.resolve_top_subtitle(
            {
                "top_subtitle": "Taste-Skill / 46.1k+ Stars · 5 张图看价值",
                "top_subtitle_suffix": "5 张图看价值",
            }
        )

        self.assertEqual(subtitle, "Taste-Skill / 46.1k+ Stars · 5 张图看价值")
        self.assertEqual(existing, "Taste-Skill / 46.1k+ Stars · 5 张图看价值")

    def test_renderer_allows_top_and_middle_title_layout_overrides(self):
        renderer = self.renderer

        self.assertEqual(renderer.top_title_y_for_profile({"top_title_y": 108}), 108)
        self.assertLess(renderer.top_title_y_for_profile({}), 128)
        self.assertGreaterEqual(renderer.top_title_line_gap_for_profile({}), 16)
        self.assertEqual(renderer.top_title_line_gap_for_profile({"top_title_line_gap": 16}), 16)
        self.assertEqual(
            renderer.middle_title_font_size(
                {"middle_visual_title_font_size": 30},
                {},
                has_value_block=False,
            ),
            30,
        )
        self.assertFalse(renderer.should_show_middle_title({}, {"show_middle_title": False}))
        self.assertTrue(renderer.should_show_middle_title({"show_middle_title": True}, {}))

    def test_renderer_adapts_bottom_body_typography_by_line_count(self):
        renderer = self.renderer

        three_line = renderer.bottom_body_typography({}, {}, line_count=3, dense=True)
        four_line = renderer.bottom_body_typography({}, {}, line_count=4, dense=True)
        five_line = renderer.bottom_body_typography({}, {}, line_count=5, dense=True)

        self.assertGreaterEqual(three_line["body_size"], 44)
        self.assertGreaterEqual(three_line["line_step"], 58)
        self.assertGreaterEqual(three_line["line_step_max"], 92)
        self.assertGreater(three_line["body_size"], four_line["body_size"])
        self.assertGreaterEqual(four_line["body_size"], five_line["body_size"])
        self.assertGreater(four_line["line_step_max"], five_line["line_step_max"])

    def test_manifest_has_consolidated_repo_showcase_playbook(self):
        rules_text = self.quality_text()
        playbook_text = self.capsule_text()

        self.assertIn("结果图", playbook_text)
        self.assertIn("机制图", playbook_text)
        self.assertIn("README 主页面", playbook_text)
        self.assertIn("5 行", playbook_text)
        self.assertIn("完整句子", playbook_text)
        self.assertIn("人味自媒体文案", playbook_text)
        self.assertIn("top_title_line_gap", playbook_text)
        self.assertIn("repo_showcase_current_playbook_required", rules_text)
        self.assertIn("show_copy_before_render_when_requested", rules_text)

    def test_manifest_includes_self_media_copy_hook_patterns(self):
        quality_rules = self.quality_text()
        patterns_text = self.capsule_text()

        for hook_id in [
            "result_first",
            "stop_old_way",
            "proof_number",
            "paid_or_heavy_replacement",
            "wrong_expectation_reframe",
        ]:
            self.assertIn(hook_id, patterns_text)

        self.assertIn("具体用户场景", patterns_text)
        self.assertIn("数字锚点", patterns_text)
        self.assertIn("痛点", patterns_text)
        self.assertIn("评论张力", patterns_text)
        self.assertIn("3-5 dense lines", patterns_text)
        self.assertIn("proof", patterns_text)
        self.assertIn("copy_hook_patterns_required", quality_rules)

    def test_manifest_includes_short_silent_open_source_skills_flash_hooks(self):
        capsule = self.manifest["capsule"]
        config = capsule["config"]
        flash_text = self.capsule_text()

        self.assertEqual(config["target_duration"], 10)
        self.assertEqual(config["output_contract"]["voice"], "none")
        self.assertEqual(config["output_contract"]["subtitle"], "none")
        self.assertIn("4-5页", flash_text)
        self.assertIn("价值密度总结", flash_text)
        self.assertEqual(config["output_contract"]["on_frame_text"], "renderer_structured_cards")
        self.assertIn("result_first", flash_text)
        self.assertIn("stop_old_way", flash_text)
        self.assertIn("proof_number", flash_text)
        self.assertIn("wrong_expectation_reframe", flash_text)
        self.assertIn("不能直接套公式", flash_text)
        self.assertIn("不在视频画面写 CTA", flash_text)
        self.assertIn("不写评论、关注、收藏、下条", flash_text)
        self.assertNotIn("评论 skill", flash_text)
        self.assertNotIn("收藏这套流程", flash_text)
        self.assertNotIn("下条拆安装", flash_text)

    def test_manifest_includes_content_aware_motion_policy(self):
        policy_text = self.capsule_text()
        rules_text = self.quality_text()

        self.assertIn("content_aware_motion_policy", policy_text)
        self.assertIn("中心放大", policy_text)
        self.assertIn("局部放大", policy_text)
        self.assertIn("从左往右", policy_text)
        self.assertIn("上下滑", policy_text)
        self.assertIn("图片比例", policy_text)
        self.assertIn("内容特征", policy_text)
        self.assertIn("content_aware_motion_policy_required", rules_text)


if __name__ == "__main__":
    unittest.main()
