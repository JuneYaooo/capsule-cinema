import importlib.util
import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CAPSULE_PATH = ROOT / "capsules" / "repo_showcase.capsule.zip"


class RepoShowcaseCapsuleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tempdir = tempfile.TemporaryDirectory()
        cls.temp_root = Path(cls.tempdir.name)
        with zipfile.ZipFile(CAPSULE_PATH) as package:
            cls.manifest = json.loads(package.read("manifest.json").decode("utf-8"))
            cls.renderer_source = package.read("script/render_repo_showcase_video.py").decode("utf-8")
            package.extract("script/render_repo_showcase_video.py", cls.temp_root)

        script_path = cls.temp_root / "script" / "render_repo_showcase_video.py"
        spec = importlib.util.spec_from_file_location("repo_showcase_renderer", script_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cls.renderer = module

    @classmethod
    def tearDownClass(cls):
        cls.tempdir.cleanup()

    def test_manifest_defaults_use_taller_video_canvas(self):
        capsule = self.manifest["capsule"]
        config = capsule["config"]

        self.assertEqual(config["aspect_ratio"], "3:4")
        self.assertEqual(config["width"], 1080)
        self.assertEqual(config["height"], 1440)
        self.assertIn("3:4", capsule["description"])

    def test_manifest_public_copy_rules_capture_latest_user_feedback(self):
        capsule = self.manifest["capsule"]
        method = capsule["method"]
        config = capsule["config"]
        rules_text = json.dumps(method, ensure_ascii=False) + json.dumps(config, ensure_ascii=False)

        self.assertIn("商用可用", rules_text)
        self.assertIn("不要默认", rules_text)
        self.assertIn("开源免费", rules_text)
        self.assertIn("不在视频画面写 CTA", rules_text)
        self.assertIn("每一页都有丰富的价值点", rules_text)
        self.assertNotIn("把项目名发给 Agent", rules_text)
        self.assertNotIn("安装这个 Skill", rules_text)
        self.assertNotIn("下条拆安装", rules_text)
        self.assertIn("怎么问", rules_text)
        self.assertIn("不要把单点反馈当成核心重做", rules_text)
        self.assertIn("不自动重渲染", rules_text)

    def test_manifest_exposes_only_short_silent_repo_showcase_route(self):
        capsule = self.manifest["capsule"]
        config = capsule["config"]
        manifest_text = json.dumps(capsule, ensure_ascii=False)

        self.assertEqual(config["default_route"], "short_silent_repo_showcase")
        self.assertEqual(config["production_mode"], "short_silent_repo_showcase")
        self.assertEqual(config["output_contract"]["voice"], "none")
        self.assertEqual(config["output_contract"]["subtitle"], "none")
        self.assertEqual(config.get("optional_routes", []), [])
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

        self.assertEqual(config["route_conflict_policy"], "config.default_route wins; repo_showcase exposes only short_silent_repo_showcase: no voiceover route, no subtitles, 4-5 pages, <=10 seconds, with BGM.")
        self.assertEqual(config["output_contract"]["voice"], "none")
        self.assertEqual(config["output_contract"]["subtitle"], "none")
        self.assertNotIn("voiceover_required", input_schema)

    def test_manifest_silent_copy_planning_has_no_active_voiceover_outputs(self):
        capsule = self.manifest["capsule"]
        config_text = json.dumps(capsule["config"], ensure_ascii=False)
        method_text = json.dumps(capsule["method"], ensure_ascii=False)

        for stale_phrase in (
            "完整旁白文案",
            "旁白级别的叙事草稿",
            "带旁白版本",
            "voiceover script",
        ):
            self.assertNotIn(stale_phrase, config_text)
            self.assertNotIn(stale_phrase, method_text)

        self.assertIn("静音卡片叙事稿", config_text)
        self.assertIn("卡片级叙事草稿", method_text)

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
        method = self.manifest["capsule"]["method"]
        quality_rules = method["quality_rules"]
        rules_text = json.dumps(quality_rules, ensure_ascii=False)

        for term in ["MIT", "商用可用", "长图按页面滚动", "页面滚动", "滚动展示", "缩放抖动"]:
            self.assertIn(term, rules_text)
        self.assertIn("公开视频", rules_text)
        self.assertIn("可见文案", rules_text)

    def test_package_file_manifest_checksums_match_zip_contents(self):
        with zipfile.ZipFile(CAPSULE_PATH) as package:
            names = set(package.namelist())
            for entry in self.manifest["files"]:
                package_path = entry["package_path"]
                self.assertIn(package_path, names)
                data = package.read(package_path)
                self.assertEqual(hashlib.sha256(data).hexdigest(), entry["sha256"])
                self.assertEqual(len(data), entry["size"])

    def test_manifest_prioritizes_original_source_materials_before_readme_fallback(self):
        config = self.manifest["capsule"]["config"]
        priority = config["middle_visual_source_priority"]

        self.assertLess(
            priority.index("github_repo_result_or_output_images"),
            priority.index("github_mechanism_diagrams_architecture_charts_or_process_visuals"),
        )
        self.assertLess(
            priority.index("github_mechanism_diagrams_architecture_charts_or_process_visuals"),
            priority.index("github_demo_ui_output_screenshots_gifs_videos_or_galleries"),
        )
        self.assertLess(
            priority.index("github_demo_ui_output_screenshots_gifs_videos_or_galleries"),
            priority.index("github_readme_embedded_rich_visuals"),
        )
        self.assertLess(
            priority.index("github_readme_embedded_rich_visuals"),
            priority.index("web_primary_original_result_or_mechanism_visuals"),
        )
        self.assertLess(
            priority.index("web_primary_original_result_or_mechanism_visuals"),
            priority.index("readme_main_page_rendered_content_screenshot_fallback"),
        )
        self.assertLess(
            priority.index("readme_main_page_rendered_content_screenshot_fallback"),
            priority.index("github_source_file_command_or_manifest_screenshot_specific_proof_only"),
        )
        self.assertLess(
            priority.index("github_source_file_command_or_manifest_screenshot_specific_proof_only"),
            priority.index("generated_summary_cards_documented_fallback"),
        )
        scope_policy = config["readme_screenshot_scope_policy"]
        self.assertIn("README", scope_policy)
        self.assertIn("must not include code directory", scope_policy)

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
        config = self.manifest["capsule"]["config"]
        method_text = json.dumps(self.manifest["capsule"]["method"], ensure_ascii=False)

        self.assertLess(config["top_title_y_preferred"], 128)
        self.assertGreaterEqual(config["top_title_line_gap_preferred"], 16)
        self.assertGreaterEqual(config["top_title_max_h"], 150)
        self.assertLess(config["top_subtitle_min_y_preferred"], 286)
        self.assertEqual(config["top_subtitle_suffix_default"], "")
        self.assertIn("顶部元信息行", config["top_subtitle_contract_note"])
        self.assertIn("不是字幕", config["top_subtitle_contract_note"])
        self.assertLessEqual(config["middle_visual_title_font_size_preferred"], 32)
        self.assertTrue(config["middle_visual_title_optional"])
        self.assertIn("top_title_spacing_policy", method_text)
        self.assertIn("中间素材标题", method_text)
        self.assertIn("可省略", method_text)

    def test_manifest_prefers_five_line_bottom_value_cards(self):
        method = self.manifest["capsule"]["method"]
        policy = method["five_line_bottom_cards_policy"]

        self.assertTrue(policy["required"])
        self.assertIn("优先 5 行", policy["default"])
        self.assertIn("允许 4 行", policy["fallback"])
        self.assertIn("完整短句", json.dumps(policy["line_rules"], ensure_ascii=False))
        self.assertIn("adaptive_bottom_layout_policy", policy["layout_pairing"])

    def test_manifest_requires_humanized_public_self_media_copy(self):
        method = self.manifest["capsule"]["method"]
        policy = method["public_self_media_copy_policy"]
        policy_text = json.dumps(policy, ensure_ascii=False)

        self.assertTrue(policy["required"])
        self.assertIn("具体场景", policy_text)
        self.assertIn("真人判断", policy_text)
        self.assertIn("README 摘要", policy_text)
        self.assertIn("信息点排列", policy_text)

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
        capsule = self.manifest["capsule"]
        playbook = capsule["method"]["repo_showcase_current_playbook"]
        rules_text = json.dumps(capsule["quality_rules"], ensure_ascii=False)
        playbook_text = json.dumps(playbook, ensure_ascii=False)

        self.assertEqual(playbook["version"], "2026-06-27-feedback-rollup")
        self.assertIn("结果图", playbook_text)
        self.assertIn("机制图", playbook_text)
        self.assertIn("README 主页面", playbook_text)
        self.assertIn("5 行", playbook_text)
        self.assertIn("完整句子", playbook_text)
        self.assertIn("AI 味", playbook_text)
        self.assertIn("top_title_line_gap", playbook_text)
        self.assertIn("repo_showcase_current_playbook_required", rules_text)
        self.assertIn("show_copy_before_render_when_requested", rules_text)

    def test_manifest_includes_self_media_copy_hook_patterns(self):
        capsule = self.manifest["capsule"]
        patterns = capsule["method"]["copy_hook_patterns"]
        quality_rules = json.dumps(capsule["quality_rules"], ensure_ascii=False)
        patterns_text = json.dumps(patterns, ensure_ascii=False)

        self.assertTrue(patterns["required"])
        for hook_id in [
            "counterintuitive_opening",
            "must_know",
            "surprising_use",
            "contrast_suspense",
            "free_or_low_cost_surprise",
        ]:
            self.assertIn(hook_id, patterns["title_hook_formulas"])

        self.assertIn("极度具象化", patterns_text)
        self.assertIn("数字锚定", patterns_text)
        self.assertIn("以前{时间/成本}", patterns_text)
        self.assertIn("现在{时间/成本}", patterns_text)
        self.assertIn("焦虑", patterns_text)
        self.assertIn("好奇", patterns_text)
        self.assertIn("静音卡片叙事稿", patterns_text)
        self.assertIn("徽章时间表", patterns_text)
        self.assertIn("copy_hook_patterns_required", quality_rules)

    def test_manifest_includes_short_silent_open_source_skills_flash_hooks(self):
        capsule = self.manifest["capsule"]
        config = capsule["config"]
        patterns = capsule["method"]["copy_hook_patterns"]
        flash = patterns["short_silent_open_source_skills_flash"]
        flash_text = json.dumps(flash, ensure_ascii=False)

        self.assertTrue(config["open_source_skills_flash_hooks_enabled"])
        self.assertEqual(config["open_source_skills_flash_hooks_version"], "2026-06-29")
        self.assertTrue(flash["required"])
        self.assertEqual(flash["format"]["duration_seconds"], 10)
        self.assertEqual(flash["format"]["image_count"], 5)
        self.assertFalse(flash["format"]["tts"])
        self.assertEqual(flash["format"]["sequence"][-1], "value_density_summary")
        self.assertEqual(flash["five_card_flash_structure"][-1]["role"], "value_density_summary")
        self.assertEqual(config["output_contract"]["on_frame_text"], "renderer_structured_cards")
        self.assertTrue(config["renderer_owned_card_text"])
        self.assertIn("结果公式", flash["title_hook_library"])
        self.assertIn("去痛替代", flash["title_hook_library"])
        self.assertIn("数字证明", flash["title_hook_library"])
        self.assertIn("GitHub热榜", flash["title_hook_library"])
        self.assertIn("身份锁定", flash["title_hook_library"])
        self.assertIn("反常识", flash["title_hook_library"])
        self.assertIn("自动出脚本", flash_text)
        self.assertIn("别再手写提示词", flash_text)
        self.assertIn("10秒看懂这个 repo", flash_text)
        self.assertIn("每一页都有丰富的价值点", flash_text)
        self.assertIn("不能直接套模板", flash_text)
        self.assertNotIn("CTA", flash_text)
        self.assertNotIn("cta", flash_text)
        self.assertNotIn("评论 skill", flash_text)
        self.assertNotIn("收藏这套流程", flash_text)
        self.assertNotIn("下条拆安装", flash_text)
        self.assertNotIn("必备", json.dumps(flash["title_hook_library"]["身份锁定"], ensure_ascii=False))
        self.assertEqual(config["output_contract"]["voice"], "none")
        self.assertEqual(config["output_contract"]["subtitle"], "none")

    def test_manifest_includes_content_aware_motion_policy(self):
        capsule = self.manifest["capsule"]
        policy = capsule["method"]["content_aware_motion_policy"]
        policy_text = json.dumps(policy, ensure_ascii=False)
        rules_text = json.dumps(capsule["quality_rules"], ensure_ascii=False)

        self.assertTrue(policy["required"])
        self.assertIn("中心放大", policy_text)
        self.assertIn("局部放大", policy_text)
        self.assertIn("从左往右", policy_text)
        self.assertIn("上下滑", policy_text)
        self.assertIn("根据图片比例", policy_text)
        self.assertIn("根据内容特征", policy_text)
        self.assertIn("content_aware_motion_policy_required", rules_text)


if __name__ == "__main__":
    unittest.main()
