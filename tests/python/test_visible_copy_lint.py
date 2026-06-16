import shutil
import sys
import unittest
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import visible_copy_lint  # noqa: E402


class VisibleCopyLintTest(unittest.TestCase):
    def setUp(self):
        self.workspace = ROOT / "output" / f"test_visible_copy_lint_{uuid4().hex}"
        self.workspace.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.workspace, ignore_errors=True)

    def write_text(self, name, text):
        path = self.workspace / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_blocks_production_version_language_in_visible_text(self):
        path = self.write_text(
            "visible.txt",
            "这是 v2 真实截图版\nsource: repo images\n按你的反馈修正\n",
        )

        hits = visible_copy_lint.lint(
            [path],
            visible_copy_lint.DEFAULT_FORBIDDEN,
            visible_copy_lint.DEFAULT_FORBIDDEN_REGEX,
            allow_policy_lines=True,
            ignore_metadata_lines=True,
        )

        terms = {hit["term"] for hit in hits}
        self.assertIn("真实截图版", terms)
        self.assertIn("source:", terms)
        self.assertTrue(any(term.startswith("regex:") for term in terms))

    def test_ignores_json_path_metadata_by_default(self):
        path = self.write_text(
            "params.json",
            '{"path": "/tmp/output/release/v3_value_hook/images/plugins.png"}\n'
            '{"visual_title": "别只让AI写文档"}\n',
        )

        hits = visible_copy_lint.lint(
            [path],
            visible_copy_lint.DEFAULT_FORBIDDEN,
            visible_copy_lint.DEFAULT_FORBIDDEN_REGEX,
            allow_policy_lines=True,
            ignore_metadata_lines=True,
        )

        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()
