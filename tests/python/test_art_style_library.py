import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))

from custom_tools.utilities.art_style_manager_tool import ArtStyleManagerTool  # noqa: E402


ART_STYLES_DIR = ROOT / "lib" / "art_styles"
REQUIRED_VISUAL_STYLE_KEYS = {
    "颜色": {"主色调", "辅助色", "氛围特征"},
    "排版": {"元素布局", "层次关系"},
    "构图": {"类型", "特征", "视角"},
    "特效": {"元素", "质感"},
}


class ArtStyleLibraryTest(unittest.TestCase):
    def test_art_style_library_contains_only_yaml_presets_at_top_level(self):
        nested_library = ART_STYLES_DIR / "art_styles"

        self.assertFalse(
            nested_library.exists() or nested_library.is_symlink(),
            "lib/art_styles/art_styles is a dead nested library link; presets should live directly in lib/art_styles",
        )

    def test_all_tracked_art_style_presets_match_runtime_schema(self):
        yaml_files = sorted(ART_STYLES_DIR.glob("*.yaml"))

        self.assertGreater(len(yaml_files), 0)
        for path in yaml_files:
            with self.subTest(path=path.name):
                data = yaml.safe_load(path.read_text(encoding="utf-8"))
                self.assertEqual(data.get("style_code"), path.stem)
                self.assertTrue(data.get("style_name"))

                visual_style = data.get("visual_style")
                self.assertIsInstance(visual_style, dict)
                for section, required_keys in REQUIRED_VISUAL_STYLE_KEYS.items():
                    self.assertIn(section, visual_style)
                    self.assertTrue(required_keys.issubset(visual_style[section].keys()))

    def test_create_style_writes_to_temporary_directory_by_default(self):
        style_config = {
            "style_name": "测试临时风格",
            "style_description": "用于验证运行时创建风格不会写入内置预设目录",
            "visual_style": {
                "颜色": {
                    "主色调": ["测试蓝"],
                    "辅助色": ["测试白"],
                    "氛围特征": "干净明确",
                },
                "排版": {
                    "元素布局": "中心布局",
                    "层次关系": "主体清晰",
                },
                "构图": {
                    "类型": "测试构图",
                    "特征": "稳定",
                    "视角": "平视",
                },
                "特效": {
                    "元素": ["测试纹理"],
                    "质感": "轻量",
                },
            },
        }

        with tempfile.TemporaryDirectory() as tmp:
            styles_dir = Path(tmp)
            tool = ArtStyleManagerTool()

            with patch.object(tool, "_get_art_styles_dir", return_value=styles_dir):
                result = tool._run(
                    action="create",
                    style_code="runtime_test_style",
                    style_config=style_config,
                )

            self.assertTrue(result["success"])
            self.assertFalse((styles_dir / "runtime_test_style.yaml").exists())
            self.assertTrue((styles_dir / "tmp" / "runtime_test_style.yaml").exists())
            self.assertTrue(result["is_temporary"])

    def test_create_style_can_explicitly_write_permanent_preset(self):
        style_config = {
            "style_name": "测试永久风格",
            "style_description": "用于验证显式永久写入仍然可用",
            "visual_style": {
                "颜色": {
                    "主色调": ["测试金"],
                    "辅助色": ["测试灰"],
                    "氛围特征": "稳定",
                },
                "排版": {
                    "元素布局": "对称布局",
                    "层次关系": "前后分明",
                },
                "构图": {
                    "类型": "永久构图",
                    "特征": "清晰",
                    "视角": "平视",
                },
                "特效": {
                    "元素": ["柔和光效"],
                    "质感": "干净",
                },
            },
        }

        with tempfile.TemporaryDirectory() as tmp:
            styles_dir = Path(tmp)
            tool = ArtStyleManagerTool()

            with patch.object(tool, "_get_art_styles_dir", return_value=styles_dir):
                result = tool._run(
                    action="create",
                    style_code="permanent_test_style",
                    style_config=style_config,
                    temporary=False,
                )

            self.assertTrue(result["success"])
            self.assertTrue((styles_dir / "permanent_test_style.yaml").exists())
            self.assertFalse((styles_dir / "tmp" / "permanent_test_style.yaml").exists())
            self.assertFalse(result["is_temporary"])


if __name__ == "__main__":
    unittest.main()
