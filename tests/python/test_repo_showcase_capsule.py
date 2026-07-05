import importlib.util
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

TEST_DIR = Path(__file__).resolve().parent
if str(TEST_DIR) not in sys.path:
    sys.path.insert(0, str(TEST_DIR))

from capsule_package_test_utils import (
    active_capsule_dir,
    load_active_capsule,
    package_file_entries,
    read_package_text,
    recipe_text,
)


ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))
CAPSULE_DIR = ROOT / "capsules" / "repo_showcase.capsule"

from src.capsule_gate_runner import run_capsule_gates  # noqa: E402


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
        video_elements = config["video_elements"]

        self.assertNotIn("aspect_ratio", config)
        self.assertEqual(video_elements["fixed"]["aspect_ratio"], "3:4")
        self.assertEqual((self.renderer.W, self.renderer.H), (1080, 1440))
        self.assertIn("3:4", capsule["description"])
        self.assertEqual(video_elements["fixed"]["visible_bottom_title"], False)
        self.assertIn("reconstructed_source_cards", video_elements["forbidden"])
        self.assertNotIn("preflight_contract", yaml.safe_load((CAPSULE_DIR / "contracts" / "runtime.yaml").read_text(encoding="utf-8")))

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
        self.assertEqual(capsule["execution_mode"], "local_script")
        self.assertTrue(capsule["local_script_path"].endswith("scripts/render_repo_showcase_video.py"))
        self.assertEqual(config["output_contract"]["voice"], "none")
        self.assertEqual(config["output_contract"]["subtitle"], "none")
        self.assertEqual(config["output_contract"]["clip_audio"], "none")
        self.assertEqual(config["roles"], {})
        self.assertNotIn("target_duration", config)
        self.assertEqual(config["video_elements"]["defaults"]["target_duration"], 10)
        self.assertEqual(config["video_elements"]["defaults"]["target_duration_max"], 10)
        self.assertNotIn("preset: general_video", (CAPSULE_DIR / "capsule.yaml").read_text(encoding="utf-8"))
        self.assertNotIn("Jimeng35ProVideoGeneratorTool", manifest_text)
        self.assertNotIn("GptImage2Tool", manifest_text)
        self.assertNotIn("narrated_long_repo_showcase", manifest_text)

    def test_manifest_bgm_default_matches_packaged_asset(self):
        capsule = self.manifest["capsule"]
        input_schema = capsule["input_schema"]
        bgm_asset = next(asset for asset in capsule["local_assets"] if asset["key"] == "manten_diloty_bgm")

        self.assertEqual(
            input_schema["fields"]["bgm_asset_filename"]["default"],
            Path(bgm_asset["path"]).name,
        )
        self.assertEqual(bgm_asset["reuse"], "always")

    def test_manifest_keeps_source_asset_manifest_as_generated_artifact_not_user_required(self):
        input_schema = self.manifest["capsule"]["input_schema"]

        self.assertFalse(input_schema["fields"]["source_asset_manifest"]["required"])
        self.assertFalse(input_schema["fields"]["source_asset_manifest_path"]["required"])

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
        self.assertIn("4-5 visible complete readable lines", method_text)
        self.assertNotIn("4-5 visible short complete lines", method_text)
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

    def _real_source_profile(self, *, bottom_title="", bottom_lines=None, source_item=None):
        image_path = self.temp_root / "real-source.png"
        image_path.write_bytes(b"fake image bytes; validation only checks source provenance")
        source_item = source_item or {
            "asset_id": "real_source_1",
            "path": str(image_path),
            "asset_type": "documentation_screenshot",
            "source_kind": "github_readme_content",
            "source_url_or_repo_path": "owner/repo README content area",
            "capture_method": "browser_content_area_screenshot",
            "actual_source": True,
            "reconstructed_card": False,
        }
        if bottom_lines is None:
            bottom_lines = [
                "把这个仓库交给 Agent 前，先看 README 里有没有真实可跑的入口。",
                "如果它只能展示概念说明，就先当资料库而不是生产工具。",
                "有 demo、模板或输出截图时，再判断它能替你省掉哪一步。",
                "最后用一个真实办公任务试问，确认结果还能继续编辑。",
            ]
        return {
            "top_title": "真实素材 preflight",
            "top_subtitle": "owner/repo / source gate",
            "show_top_tag": False,
            "source_asset_manifest": [source_item],
            "scenes": [
                {
                    "asset_id": "real_source_1",
                    "image_paths": [str(image_path)],
                    "bottom_title": bottom_title,
                    "bottom_lines": bottom_lines,
                    "footer": "README 内容区",
                }
            ],
        }

    def test_renderer_preflight_rejects_reconstructed_middle_cards(self):
        renderer = self.renderer
        profile = self._real_source_profile(
            source_item={
                "asset_id": "real_source_1",
                "path": str(self.temp_root / "real-source.png"),
                "asset_type": "source_grounded_card",
                "source_kind": "topic_table_and_readme",
                "capture_method": "pil_generated_text_card",
                "actual_source": False,
                "reconstructed_card": True,
            }
        )

        with self.assertRaisesRegex(SystemExit, "reconstructed_card|actual_source"):
            renderer.validate_repo_showcase_profile(profile)

    def test_renderer_preflight_rejects_visible_bottom_title(self):
        renderer = self.renderer
        profile = self._real_source_profile(bottom_title="底部标题不该出现")

        with self.assertRaisesRegex(SystemExit, "bottom_title"):
            renderer.validate_repo_showcase_profile(profile)

    def test_renderer_preflight_rejects_short_fragment_bottom_lines(self):
        renderer = self.renderer
        profile = self._real_source_profile(
            bottom_lines=["README 原文", "看星标", "安装使用", "最后判断"]
        )

        with self.assertRaisesRegex(SystemExit, "bottom_lines"):
            renderer.validate_repo_showcase_profile(profile)

    def test_renderer_preflight_rejects_source_assets_outside_allowed_types(self):
        renderer = self.renderer
        profile = self._real_source_profile(
            source_item={
                "asset_id": "real_source_1",
                "path": str(self.temp_root / "real-source.png"),
                "asset_type": "source_grounded_card",
                "source_kind": "github_readme_content",
                "source_url_or_repo_path": "owner/repo README content area",
                "capture_method": "browser_content_area_screenshot",
                "actual_source": True,
                "reconstructed_card": False,
            }
        )

        with self.assertRaisesRegex(SystemExit, "asset_type"):
            renderer.validate_repo_showcase_profile(profile)

    def test_renderer_preflight_accepts_real_sources_without_bottom_title(self):
        renderer = self.renderer
        profile = self._real_source_profile()

        renderer.validate_repo_showcase_profile(profile)

    def test_release_gates_bind_repeated_failures_to_shared_checkers(self):
        release_gates = yaml.safe_load((CAPSULE_DIR / "quality" / "release_gates.yaml").read_text(encoding="utf-8"))
        structured = {
            item["id"]: item
            for item in release_gates["gates"]
            if isinstance(item, dict)
        }

        self.assertEqual(
            structured["bottom_title_not_visible_required"]["checker"],
            "forbidden_profile_fields",
        )
        self.assertEqual(
            structured["reconstructed_cards_not_real_sources"]["checker"],
            "manifest_item_flags",
        )
        self.assertEqual(
            structured["bottom_card_4_to_5_lines"]["checker"],
            "list_length_between",
        )
        self.assertEqual(
            structured["fallback_generated_card_preview_only"]["checker"],
            "fallback_blocks_approved_release",
        )

    def test_manifest_uses_positive_real_source_contract_without_generated_loophole(self):
        visual_text = read_package_text("repo_showcase", "recipes/visual.md")
        runtime = yaml.safe_load((CAPSULE_DIR / "contracts" / "runtime.yaml").read_text(encoding="utf-8"))
        rules_text = self.quality_text()

        for phrase in [
            "Approved middle visual contract",
            "Allowed source asset types",
            "Fallback order when no rich media exists",
            "repository_image",
            "readme_embedded_image",
            "documentation_screenshot",
            "source_file_screenshot",
            "demo_output_screenshot",
            "video_or_gif_frame",
            "README content screenshot",
            "source/example/config file screenshot",
            "fail the approved render",
        ]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, visual_text)

        for stale_phrase in [
            "third use image-2",
            "fourth use HTML/PIL",
            "Generated visuals must change representation",
            "When generated diagrams or summary cards are unavoidable",
            "generated support visuals",
            "HTML/PIL/代码生成图",
        ]:
            with self.subTest(stale_phrase=stale_phrase):
                self.assertNotIn(stale_phrase, visual_text)

        source_contract = runtime["source_material_contract"]
        self.assertEqual(
            source_contract["approved_middle_visual_source"],
            "actual_source_manifest_only",
        )
        self.assertEqual(
            source_contract["allowed_source_asset_types"],
            [
                "repository_image",
                "readme_embedded_image",
                "documentation_screenshot",
                "source_file_screenshot",
                "demo_output_screenshot",
                "video_or_gif_frame",
            ],
        )
        self.assertEqual(source_contract["fallback_policy"]["on_no_real_source"], "fail_approved_render")
        self.assertIn("approved_middle_visual_positive_contract", rules_text)
        self.assertIn("real_source_fallback_order_required", rules_text)

    def test_shared_gate_runner_catches_repo_showcase_bad_profile(self):
        profile = self._real_source_profile(bottom_title="底部标题不该出现")

        report = run_capsule_gates(CAPSULE_DIR, "pre_render", profile=profile)

        self.assertFalse(report["ok"])
        self.assertIn("bottom_title_not_visible_required", report["blockers"])

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
        self.assertLess(rules_text.index("README/GitHub/source"), rules_text.index("真实素材不足"))
        self.assertIn("README fallback 截图必须只包含 README 渲染内容区", rules_text)
        self.assertIn("不得把 GitHub 纯代码目录", rules_text)

    def test_manifest_requires_clear_skill_identity_and_v2_visual_copy_rules(self):
        full_text = self.capsule_text()
        rules_text = self.quality_text()
        release_gates = read_package_text("repo_showcase", "quality/release_gates.yaml")
        lessons_text = read_package_text("repo_showcase", "learning/promoted_lessons.yaml")

        required_gate_ids = [
            "project_identity_badge_required",
            "multi_skill_subject_list_when_needed",
            "top_subtitle_readability_and_spacing",
            "middle_visual_material_ladder_v2",
            "approved_middle_visual_positive_contract",
            "allowed_source_asset_types_required",
            "real_source_fallback_order_required",
            "bottom_card_4_to_5_lines",
            "middle_visual_no_repeated_title_stronger",
            "public_copy_only_viewer_language",
            "plain_language_for_office_audience",
            "qa_visible_subject_identity_required",
        ]
        for gate_id in required_gate_ids:
            with self.subTest(gate_id=gate_id):
                self.assertIn(gate_id, rules_text)
                self.assertIn(gate_id, release_gates)

        for phrase in [
            "owner/repo",
            "Skill path",
            "subject_paths",
            "3-5 个代表短路径",
            "34-38px",
            "推荐 36px",
            "真实结果/产品素材",
            "primary-source",
            "Allowed source asset types",
            "source_file_screenshot",
            "Fallback order when no rich media exists",
            "4-5 行",
            "完整、通顺、可独立读懂的句子",
            "可以比 20 个中文字更长",
            "5.1k stars",
            "不把 bottom_title 当成创作必填项",
            "公开视频文案只使用观众语言",
            "deck",
            "普通办公用户",
        ]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, full_text)

        for lesson_id in [
            "project_identity_badge_required",
            "middle_visual_material_ladder_v2",
            "bottom_card_4_to_5_lines",
            "approved_middle_visual_positive_contract",
        ]:
            self.assertIn(lesson_id, lessons_text)

    def test_renderer_layout_expands_middle_panel_on_taller_canvas(self):
        renderer = self.renderer

        self.assertEqual((renderer.W, renderer.H), (1080, 1440))
        x1, y1, x2, y2 = renderer.MIDDLE_PANEL_BOX
        self.assertGreaterEqual(x2 - x1, 930)
        self.assertGreaterEqual(y2 - y1, 570)
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

    def test_renderer_keeps_middle_panel_clear_of_top_subtitle_pixels(self):
        renderer = self.renderer
        profile = {
            "top_title": "飞书资料到企微通知\n先串成一条会后流程",
            "top_subtitle": "daymade Skills 里最适合中国办公的用法",
        }
        image = renderer.Image.new("RGBA", (renderer.W, renderer.H))
        draw = renderer.ImageDraw.Draw(image)
        title_gap = renderer.top_title_line_gap_for_profile(profile)
        title_font = renderer.fit_font_size(
            draw,
            profile["top_title"],
            start=int(profile.get("top_title_font_size", 68)),
            minimum=42,
            max_w=940,
            max_h=int(profile.get("top_title_max_h", 158)),
            bold=True,
            line_gap=title_gap,
        )
        title_end = renderer.draw_centered(
            draw,
            profile["top_title"],
            renderer.top_title_y_for_profile(profile),
            title_font,
            "#FFFFFF",
            line_gap=title_gap,
            stroke_width=2,
            stroke_fill="#000000",
        )
        subtitle = renderer.resolve_top_subtitle(profile)
        subtitle_font = renderer.fit_font_size(
            draw,
            subtitle,
            start=int(profile.get("top_subtitle_font_size", 30)),
            minimum=20,
            max_w=920,
            max_h=40,
        )
        subtitle_y = max(renderer.top_subtitle_min_y_for_profile(profile), title_end + 16)
        subtitle_bottom = draw.textbbox((0, subtitle_y), subtitle, font=subtitle_font)[3]

        self.assertGreaterEqual(renderer.MIDDLE_PANEL_BOX[1] - subtitle_bottom, 36)

    def test_manifest_prefers_five_line_bottom_value_cards(self):
        text = self.capsule_text()

        self.assertIn("底部卡默认优先 5 行", text)
        self.assertIn("允许 4 行", text)
        self.assertIn("完整句子", text)
        self.assertIn("可以比 20 个中文字更长", text)
        self.assertIn("动态排版", text)
        self.assertNotIn("每行约 8-20 个中文字", text)
        self.assertNotIn("4-5 visible short complete lines", text)

    def test_manifest_uses_github_native_star_proof_wording(self):
        text = self.capsule_text()

        self.assertIn("5.1k stars", text)
        self.assertIn("GitHub 原生表达", text)
        self.assertNotIn("让你点进来", text)
        self.assertNotIn("点进去才发现", text)
        self.assertNotIn("已经够显眼", text)
        self.assertNotIn("更值得看", text)
        self.assertNotIn("真正值得看", text)
        self.assertNotIn("证明关注度", text)
        self.assertNotRegex(text, r"\d+(?:\.\d+)?k\s*星")
        self.assertNotRegex(text, r"\d{4,}\s*星")

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
        self.assertFalse(renderer.should_show_middle_title({}, {}))
        self.assertFalse(renderer.should_show_middle_title({"show_middle_title": False}, {}))
        self.assertTrue(renderer.should_show_middle_title({}, {"show_middle_title": True}))
        self.assertTrue(renderer.should_show_middle_title({"show_middle_title": True}, {}))

    def test_renderer_collects_no_middle_visual_title_by_default(self):
        renderer = self.renderer

        visible = renderer.collect_visible_text(
            {
                "top_title": "顶部标题",
                "top_subtitle": "顶部副标题",
                "show_top_tag": False,
                "scenes": [
                    {
                        "visual_title": "中间标题不要出现",
                        "bottom_title": "底部标题",
                        "bottom_lines": ["底部正文"],
                    }
                ],
            }
        )

        self.assertNotIn("中间标题不要出现", visible)
        self.assertNotIn("底部标题", visible)
        self.assertIn("底部正文", visible)

    def test_renderer_collects_no_image_labels_by_default(self):
        renderer = self.renderer
        image_path = self.temp_root / "sample-source.png"
        image_path.write_bytes(b"not opened by collect_visible_text")

        visible = renderer.collect_visible_text(
            {
                "top_title": "顶部标题",
                "show_top_tag": False,
                "scenes": [
                    {
                        "image_paths": [str(image_path)],
                        "image_labels": ["资料标签不要出现"],
                        "bottom_title": "底部标题",
                    }
                ],
            }
        )
        explicit = renderer.collect_visible_text(
            {
                "top_title": "顶部标题",
                "show_top_tag": False,
                "show_image_labels": True,
                "scenes": [
                    {
                        "image_paths": [str(image_path)],
                        "image_labels": ["资料标签可以出现"],
                        "bottom_title": "底部标题",
                    }
                ],
            }
        )

        self.assertNotIn("资料标签不要出现", visible)
        self.assertIn("资料标签可以出现", explicit)

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
        self.assertIn("4-5 visible complete readable lines", patterns_text)
        self.assertIn("proof", patterns_text)
        self.assertIn("copy_hook_patterns_required", quality_rules)

    def test_manifest_captures_category_difference_result_title_logic(self):
        patterns_text = self.capsule_text()
        copy_text = read_package_text("repo_showcase", "recipes/copy.md")
        start = copy_text.index('"category_difference_result_title_logic"')
        end = copy_text.index('"avoid"', start)
        title_logic_block = copy_text[start:end]

        for phrase in [
            "熟悉品类 + 反常识新能力 + 具体结果",
            "品类入口",
            "差异动词",
            "用户已有认知",
            "默认期待",
            "标题不负责讲完，副标题负责补清楚",
            "3 秒测试",
            "替换测试",
            "复述测试",
        ]:
            self.assertIn(phrase, patterns_text)

        self.assertNotIn("old_world", title_logic_block)
        self.assertNotIn("旧世界", title_logic_block)

        for case_specific_marker in [
            "example_for_",
            "strong_public_titles",
            "subtitle_examples",
            "why_it_works",
        ]:
            self.assertNotIn(case_specific_marker, title_logic_block)
        self.assertIn("单条视频的项目名、行业、文件类型、动作词或输出格式写进胶囊示例", title_logic_block)

    def test_manifest_requires_editorial_analysis_copy_logic(self):
        patterns_text = self.capsule_text()
        rules_text = self.quality_text()
        copy_text = read_package_text("repo_showcase", "recipes/copy.md")
        release_gates = read_package_text("repo_showcase", "quality/release_gates.yaml")
        lessons_text = read_package_text("repo_showcase", "learning/promoted_lessons.yaml")
        start = copy_text.index('"editorial_analysis_copy_logic"')
        end = copy_text.index('"first_screen_formulas"', start)
        copy_logic_block = copy_text[start:end]

        for phrase in [
            "不要只复述 README",
            "自己的分析和切入点",
            "用户已有认知",
            "默认期待",
            "同类默认印象",
            "非显而易见差异",
            "为什么现在值得看",
            "适用边界",
            "取舍",
            "每页底部卡至少推进一个判断",
        ]:
            self.assertIn(phrase, patterns_text)

        self.assertIn("copy_editorial_analysis_required", rules_text)
        self.assertIn("copy_editorial_analysis_required", release_gates)
        self.assertIn("editorial_analysis_copy_logic", lessons_text)

        for case_specific_marker in [
            "gpt-image2-ppt-skills",
            "gpt_image2_ppt_skills",
            "旧 PPT",
            "PNG",
            "PPTX",
            "抄模板",
        ]:
            self.assertNotIn(case_specific_marker, copy_logic_block)

        self.assertNotIn("旧工作流", copy_logic_block)
        self.assertNotIn("old_workflow", copy_logic_block)

    def test_manifest_requires_self_media_label_user_readability_gate(self):
        patterns_text = self.capsule_text()
        rules_text = self.quality_text()
        copy_text = read_package_text("repo_showcase", "recipes/copy.md")
        release_gates = read_package_text("repo_showcase", "quality/release_gates.yaml")
        lessons_text = read_package_text("repo_showcase", "learning/promoted_lessons.yaml")
        start = copy_text.index('"self_media_label_user_readability_gate"')
        end = copy_text.index('"first_screen_formulas"', start)
        label_gate_block = copy_text[start:end]

        for phrase in [
            "自媒体标签",
            "标签不是 hashtag",
            "用户视角",
            "一眼能看懂",
            "一眼想点",
            "给谁看",
            "什么场景",
            "能拿到什么",
            "陌生用户测试",
            "3 秒复述",
        ]:
            self.assertIn(phrase, patterns_text)

        self.assertIn("self_media_label_user_angle_required", rules_text)
        self.assertIn("self_media_label_user_angle_required", release_gates)
        self.assertIn("self_media_label_user_readability_gate", lessons_text)

        for case_specific_marker in [
            "gpt-image2-ppt-skills",
            "gpt_image2_ppt_skills",
            "旧 PPT",
            "PNG",
            "PPTX",
            "抄模板",
        ]:
            self.assertNotIn(case_specific_marker, label_gate_block)

    def test_manifest_does_not_promote_current_project_specific_examples(self):
        patterns_text = self.capsule_text()

        for case_specific_marker in [
            "仿出整套新PPT",
            "旧 PPT",
            "PNG + PPTX",
            "gpt-image2-ppt-skills",
            "gpt_image2_ppt_skills",
            "抄模板",
        ]:
            self.assertNotIn(case_specific_marker, patterns_text)

    def test_manifest_includes_short_silent_open_source_skills_flash_hooks(self):
        capsule = self.manifest["capsule"]
        config = capsule["config"]
        flash_text = self.capsule_text()

        self.assertEqual(config["video_elements"]["defaults"]["target_duration"], 10)
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

    def test_manifest_removes_template_recipe_placeholders(self):
        self.assertNotIn("No capsule-specific structure rules", read_package_text("repo_showcase", "recipes/structure.md"))
        self.assertNotIn("No capsule-specific visual rules", read_package_text("repo_showcase", "recipes/visual.md"))
        self.assertNotIn("No capsule-specific audio rules", read_package_text("repo_showcase", "recipes/audio.md"))

    def test_manifest_does_not_require_ai_flavored_negative_parallelism(self):
        policy_text = self.capsule_text()

        self.assertNotIn("至少 1 个标题使用“别再/不用/先停一下/不是...是...”结构", policy_text)
        self.assertNotIn("不是提示词，是触发链", policy_text)
        self.assertNotIn("高星标火的不是省钱", policy_text)
        self.assertNotIn("除非用户明确要求授权细节", policy_text)


if __name__ == "__main__":
    unittest.main()
