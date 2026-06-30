import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from capsule_v3_validate import main, validate_capsule_dir  # noqa: E402


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_valid_capsule(root: Path) -> Path:
    cap = root / "valid.capsule"
    write(
        cap / "capsule.yaml",
        """
schema_version: capsule.v3
name: valid
display_name: Valid
version: 1
status: active
execution_mode: preset
category: test
summary: Valid capsule.
when_to_use: []
when_not_to_use: []
read_order:
  routing: [CARD.md, contracts/runtime.yaml]
  planning: [recipes/structure.md]
  generation: [contracts/runtime.yaml, assets/index.yaml]
  qa: [quality/rules.yaml]
  learning: [learning/promoted_lessons.yaml]
entrypoints:
  preset: general_video
""".strip()
        + "\n",
    )
    write(cap / "CARD.md", "# Valid\n")
    write(cap / "contracts" / "runtime.yaml", "roles: {}\noutput_contract: {}\ndefaults: {}\n")
    write(cap / "contracts" / "input_schema.yaml", "fields: {}\n")
    write(cap / "recipes" / "structure.md", "# Structure\n")
    write(cap / "quality" / "rules.yaml", "rules:\n  - id: final_video_required\n    type: artifact_required\n")
    write(cap / "quality" / "release_gates.yaml", "gates:\n  - final_video_required\n")
    write(cap / "assets" / "index.yaml", "assets: []\n")
    write(cap / "learning" / "promoted_lessons.yaml", "lessons: []\n")
    return cap


class CapsuleV3ValidateTest(unittest.TestCase):
    def test_main_returns_zero_and_formats_success_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            cap = make_valid_capsule(Path(tmp))
            stdout = io.StringIO()
            with mock.patch.object(sys, "argv", ["capsule_v3_validate.py", str(cap), "--warnings-ok"]):
                with contextlib.redirect_stdout(stdout):
                    with self.assertRaises(SystemExit) as exc:
                        main()
        self.assertEqual(exc.exception.code, 0)
        self.assertEqual(stdout.getvalue(), "capsule v3 validation: ok\n")

    def test_main_returns_one_and_formats_error_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            cap = make_valid_capsule(Path(tmp))
            write(cap / "recipes" / "structure.md", "# Structure\n\nUse /Users/me/output/run/final.mp4\n")
            stdout = io.StringIO()
            with mock.patch.object(sys, "argv", ["capsule_v3_validate.py", str(cap), "--warnings-ok"]):
                with contextlib.redirect_stdout(stdout):
                    with self.assertRaises(SystemExit) as exc:
                        main()
        recipe_path = (cap / "recipes" / "structure.md").resolve()
        self.assertEqual(exc.exception.code, 1)
        self.assertEqual(
            stdout.getvalue(),
            "capsule v3 validation: failed\n"
            f"- error: output path found in recipe/package file: {recipe_path}\n",
        )

    def test_main_json_output_includes_failed_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            cap = make_valid_capsule(Path(tmp))
            write(cap / "recipes" / "structure.md", "# Structure\n\nUse /Users/me/output/run/final.mp4\n")
            stdout = io.StringIO()
            with mock.patch.object(sys, "argv", ["capsule_v3_validate.py", str(cap), "--warnings-ok", "--json"]):
                with contextlib.redirect_stdout(stdout):
                    with self.assertRaises(SystemExit) as exc:
                        main()
        self.assertEqual(exc.exception.code, 1)
        self.assertIn('"ok": false', stdout.getvalue())
        self.assertIn('"capsule_dir":', stdout.getvalue())

    def test_valid_capsule_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            cap = make_valid_capsule(Path(tmp))
            report = validate_capsule_dir(cap, warnings_ok=True)
        self.assertTrue(report["ok"])
        self.assertEqual(report["errors"], [])

    def test_missing_read_order_file_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            cap = make_valid_capsule(Path(tmp))
            (cap / "recipes" / "structure.md").unlink()
            report = validate_capsule_dir(cap, warnings_ok=True)
        self.assertFalse(report["ok"])
        self.assertTrue(any("read_order" in item for item in report["errors"]))

    def test_output_path_in_recipe_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            cap = make_valid_capsule(Path(tmp))
            write(cap / "recipes" / "structure.md", "# Structure\n\nUse /Users/me/output/run/final.mp4\n")
            report = validate_capsule_dir(cap, warnings_ok=True)
        self.assertFalse(report["ok"])
        self.assertTrue(any("output path" in item for item in report["errors"]))

    def test_local_script_entrypoint_must_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            cap = make_valid_capsule(Path(tmp))
            text = (cap / "capsule.yaml").read_text(encoding="utf-8")
            text = text.replace("execution_mode: preset", "execution_mode: local_script")
            text = text.replace("preset: general_video", "preset: general_video\n  local_script: scripts/run.py")
            write(cap / "capsule.yaml", text)
            report = validate_capsule_dir(cap, warnings_ok=True)
        self.assertFalse(report["ok"])
        self.assertTrue(any("local_script" in item for item in report["errors"]))

    def test_secret_or_remote_looking_values_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            cap = make_valid_capsule(Path(tmp))
            write(cap / "CARD.md", "# Valid\n\nUse https://example.com and sk-secret-token-value-here\n")
            report = validate_capsule_dir(cap, warnings_ok=True)
        self.assertFalse(report["ok"])
        self.assertTrue(any("secret or remote-looking value" in item for item in report["errors"]))

    def test_unsupported_asset_role_and_reuse_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            cap = make_valid_capsule(Path(tmp))
            write(
                cap / "assets" / "index.yaml",
                """
assets:
  - key: bad
    role: qa_report
    reuse: deliverable
    path: refs/report.txt
""".strip()
                + "\n",
            )
            report = validate_capsule_dir(cap, warnings_ok=True)
        self.assertFalse(report["ok"])
        self.assertTrue(any("unsupported role" in item for item in report["errors"]))
        self.assertTrue(any("unsupported reuse" in item for item in report["errors"]))

    def test_explicit_asset_output_path_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            cap = make_valid_capsule(Path(tmp))
            write(
                cap / "assets" / "index.yaml",
                """
assets:
  - key: final_video
    role: source_media
    reuse: reference_only
    path: output/final.mp4
""".strip()
                + "\n",
            )
            report = validate_capsule_dir(cap, warnings_ok=True)
        self.assertFalse(report["ok"])
        self.assertTrue(any("output path" in item for item in report["errors"]))

    def test_task_2_style_sanitized_asset_without_source_path_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            cap = make_valid_capsule(Path(tmp))
            write(
                cap / "assets" / "index.yaml",
                """
assets:
  - key: style_frame
    role: style_reference
    reuse: reference_only
    path: references/style/frame-01.png
""".strip()
                + "\n",
            )
            report = validate_capsule_dir(cap, warnings_ok=True)
        self.assertTrue(report["ok"])
        self.assertEqual(report["errors"], [])


if __name__ == "__main__":
    unittest.main()
