import importlib.util
import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CAPSULE_PATH = ROOT / "capsules" / "github_skills_showcase.capsule.zip"


class GithubSkillsShowcaseCapsuleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tempdir = tempfile.TemporaryDirectory()
        cls.temp_root = Path(cls.tempdir.name)
        with zipfile.ZipFile(CAPSULE_PATH) as package:
            cls.manifest = json.loads(package.read("manifest.json").decode("utf-8"))
            package.extract("script/render_repo_showcase_video.py", cls.temp_root)

        script_path = cls.temp_root / "script" / "render_repo_showcase_video.py"
        spec = importlib.util.spec_from_file_location("github_skills_showcase_renderer", script_path)
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
        self.assertIn("把项目名发给 Agent", rules_text)
        self.assertIn("安装这个 Skill", rules_text)
        self.assertIn("怎么问", rules_text)
        self.assertIn("不要把单点反馈当成核心重做", rules_text)
        self.assertIn("不自动重渲染", rules_text)

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
            priority.index("github_repo_provided_visual_assets"),
            priority.index("web_original_visual_assets"),
        )
        self.assertLess(
            priority.index("web_original_visual_assets"),
            priority.index("readme_content_screenshot_fallback"),
        )
        self.assertLess(
            priority.index("readme_content_screenshot_fallback"),
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
        self.assertLess(config["top_subtitle_min_y_preferred"], 286)
        self.assertEqual(config["top_subtitle_suffix_default"], "结尾有安装命令")
        self.assertLessEqual(config["middle_visual_title_font_size_preferred"], 32)
        self.assertTrue(config["middle_visual_title_optional"])
        self.assertIn("中间素材标题", method_text)
        self.assertIn("可省略", method_text)

    def test_renderer_resolves_usage_hint_subtitle_once(self):
        renderer = self.renderer

        subtitle = renderer.resolve_top_subtitle(
            {
                "top_subtitle": "Taste-Skill / 46.1k+ Stars",
                "top_subtitle_suffix": "结尾有安装命令",
            }
        )
        existing = renderer.resolve_top_subtitle(
            {
                "top_subtitle": "Taste-Skill / 46.1k+ Stars · 结尾有安装命令",
                "top_subtitle_suffix": "结尾有安装命令",
            }
        )

        self.assertEqual(subtitle, "Taste-Skill / 46.1k+ Stars · 结尾有安装命令")
        self.assertEqual(existing, "Taste-Skill / 46.1k+ Stars · 结尾有安装命令")

    def test_renderer_allows_top_and_middle_title_layout_overrides(self):
        renderer = self.renderer

        self.assertEqual(renderer.top_title_y_for_profile({"top_title_y": 108}), 108)
        self.assertLess(renderer.top_title_y_for_profile({}), 128)
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


if __name__ == "__main__":
    unittest.main()
