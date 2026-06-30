import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "run_video.py"


def load_run_video():
    spec = importlib.util.spec_from_file_location("run_video", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RunVideoPreflightTest(unittest.TestCase):
    def _write_capsule_db(self, db_path: Path) -> None:
        self._write_capsule_db_with_config(
            db_path,
            {
                "roles": {
                    "image": {"requires": [], "validated_with": "GptImage2Tool"},
                    "video": {"requires": ["image_to_video"], "validated_with": "Jimeng35ProVideoGeneratorTool"},
                    "voice": {"validated_with": "minimax/Chinese_deep_voiced_male_vv1"},
                },
                "output_contract": {
                    "clip_audio": "silent",
                    "voice": "unified_tts",
                    "on_frame_text": "none",
                    "subtitle": "overlay",
                    "bgm": "external",
                },
                "aspect_ratio": "9:16",
                "target_duration": 12,
            },
        )

    def _write_capsule_db_with_config(self, db_path: Path, config: dict) -> None:
        if "aspect_ratio" not in config:
            config["aspect_ratio"] = "9:16"
        if "target_duration" not in config:
            config["target_duration"] = 12
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                CREATE TABLE capsules (
                    name TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    execution_mode TEXT NOT NULL,
                    description TEXT NOT NULL,
                    category TEXT NOT NULL,
                    tags_json TEXT NOT NULL,
                    config_json TEXT NOT NULL,
                    method_json TEXT NOT NULL,
                    input_schema_json TEXT NOT NULL,
                    quality_rules_json TEXT NOT NULL,
                    local_assets_json TEXT NOT NULL,
                    local_script_path TEXT NOT NULL,
                    version INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                """
                INSERT INTO capsules (
                    name, display_name, status, execution_mode, description,
                    category, tags_json, config_json, method_json, input_schema_json,
                    quality_rules_json, local_assets_json, local_script_path, version
                )
                VALUES (?, ?, 'active', 'preset', 'test', 'general', '[]', ?, '{}', '{}', '[]', '[]', '', 1)
                """,
                ("preflight_capsule", "Preflight Capsule", json.dumps(config, ensure_ascii=False)),
            )
            conn.commit()

    def _substituted_config(self) -> dict:
        return {
            "roles": {
                "video": {
                    "requires": ["image_to_video"],
                    "validated_with": "UnavailablePreferredVideoTool",
                }
            },
            "output_contract": {
                "clip_audio": "silent",
                "on_frame_text": "none",
                "subtitle": "none",
                "bgm": "none",
            },
            "aspect_ratio": "9:16",
            "target_duration": 12,
        }

    def test_capsule_roles_run_preflight_and_pass_execution_plan_to_flow(self):
        old_env = {
            key: os.environ.get(key)
            for key in (
                "DOTENV_PATH",
                "KRILL_GPT_IMAGE2_API_KEY",
                "KRILL_GPT_IMAGE2_BASE_URL",
                "JULING_API_KEY",
                "JULING_BASE_URL",
                "MINIMAX_API_KEY",
            )
        }
        old_argv = sys.argv[:]
        try:
            with tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                db_path = tmp_path / "capsules.sqlite"
                workspace = tmp_path / "workspace"
                workspace.mkdir()
                self._write_capsule_db(db_path)
                os.environ["DOTENV_PATH"] = str(tmp_path / "missing.env")
                os.environ["KRILL_GPT_IMAGE2_API_KEY"] = "test"
                os.environ["KRILL_GPT_IMAGE2_BASE_URL"] = "https://api.krill-ai.com/v1"
                os.environ["JULING_API_KEY"] = "test"
                os.environ["JULING_BASE_URL"] = "https://example.test"
                os.environ["MINIMAX_API_KEY"] = "test"

                run_video = load_run_video()
                captured = {}

                def fake_flow(user_requirements, target_duration, **kwargs):
                    captured["user_requirements"] = user_requirements
                    captured["target_duration"] = target_duration
                    captured["kwargs"] = kwargs
                    return {
                        "success": True,
                        "workspace_dir": str(workspace),
                        "generation_summary": {},
                        "video_title": "test",
                    }

                sys.argv = [
                    "run_video.py",
                    "--user_requirements",
                    "做一个测试视频",
                    "--capsule",
                    "preflight_capsule",
                    "--capsule_db",
                    str(db_path),
                    "--storyboard_only",
                ]

                with patch("video_workflows.general_video.flow.run_general_video_flow", fake_flow):
                    run_video.main()

                kwargs = captured["kwargs"]
                self.assertEqual(kwargs["capsule_execution_plan"]["roles"]["video"]["selected"], "Jimeng35ProVideoGeneratorTool")
                self.assertIn("mute_audio", kwargs["capsule_execution_plan"]["roles"]["video"]["directive"]["post_steps"])
                self.assertEqual(kwargs["capsule_preflight_report"]["status"], "ok")
                self.assertTrue((workspace / "preflight_report.json").exists())
                self.assertTrue((workspace / "execution_plan.json").exists())
                manifest = json.loads((workspace / "artifact_manifest.json").read_text(encoding="utf-8"))
                categories = {item["category"] for item in manifest["artifacts"]}
                self.assertIn("preflight_report", categories)
                self.assertIn("execution_plan", categories)
        finally:
            sys.argv = old_argv
            for key, value in old_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_substituted_preflight_blocks_generation_without_acceptance(self):
        old_env = {key: os.environ.get(key) for key in ("DOTENV_PATH", "JULING_API_KEY", "JULING_BASE_URL", "VEO3_API_KEY", "VEO3_BASE_URL")}
        old_argv = sys.argv[:]
        try:
            with tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                db_path = tmp_path / "capsules.sqlite"
                self._write_capsule_db_with_config(db_path, self._substituted_config())
                os.environ["DOTENV_PATH"] = str(tmp_path / "missing.env")
                os.environ.pop("JULING_API_KEY", None)
                os.environ.pop("JULING_BASE_URL", None)
                os.environ["VEO3_API_KEY"] = "test"
                os.environ["VEO3_BASE_URL"] = "https://example.test"

                run_video = load_run_video()
                sys.argv = [
                    "run_video.py",
                    "--user_requirements",
                    "做一个测试视频",
                    "--capsule",
                    "preflight_capsule",
                    "--capsule_db",
                    str(db_path),
                ]

                with self.assertRaises(SystemExit) as ctx:
                    run_video.main()

                self.assertIn("--accept_preflight_changes", str(ctx.exception))
        finally:
            sys.argv = old_argv
            for key, value in old_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_acceptance_allows_substituted_preflight_to_reach_flow(self):
        old_env = {key: os.environ.get(key) for key in ("DOTENV_PATH", "JULING_API_KEY", "JULING_BASE_URL", "VEO3_API_KEY", "VEO3_BASE_URL")}
        old_argv = sys.argv[:]
        try:
            with tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                db_path = tmp_path / "capsules.sqlite"
                workspace = tmp_path / "workspace"
                workspace.mkdir()
                self._write_capsule_db_with_config(db_path, self._substituted_config())
                os.environ["DOTENV_PATH"] = str(tmp_path / "missing.env")
                os.environ.pop("JULING_API_KEY", None)
                os.environ.pop("JULING_BASE_URL", None)
                os.environ["VEO3_API_KEY"] = "test"
                os.environ["VEO3_BASE_URL"] = "https://example.test"

                run_video = load_run_video()
                captured = {}

                def fake_flow(user_requirements, target_duration, **kwargs):
                    captured["kwargs"] = kwargs
                    return {
                        "success": True,
                        "workspace_dir": str(workspace),
                        "generation_summary": {},
                        "video_title": "test",
                    }

                sys.argv = [
                    "run_video.py",
                    "--user_requirements",
                    "做一个测试视频",
                    "--capsule",
                    "preflight_capsule",
                    "--capsule_db",
                    str(db_path),
                    "--accept_preflight_changes",
                ]

                with patch("video_workflows.general_video.flow.run_general_video_flow", fake_flow):
                    run_video.main()

                kwargs = captured["kwargs"]
                self.assertEqual(kwargs["capsule_preflight_report"]["status"], "needs_confirmation")
                self.assertEqual(kwargs["capsule_execution_plan"]["roles"]["video"]["status"], "substituted")
                self.assertNotEqual(kwargs["capsule_execution_plan"]["roles"]["video"]["selected"], "UnavailablePreferredVideoTool")
        finally:
            sys.argv = old_argv
            for key, value in old_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_post_run_status_separates_generation_success_from_deliverable(self):
        run_video = load_run_video()
        result = {
            "success": True,
            "final_video": "/tmp/final.mp4",
            "edit_plan_validation_ok": False,
            "local_video_qa_ok": True,
            "post_run_warnings": ["edit plan validation did not pass; see qa/edit_plan_validation.json"],
        }

        run_video.apply_post_run_delivery_status(result, storyboarding_only=False)

        self.assertTrue(result["success"])
        self.assertFalse(result["deliverable"])
        self.assertEqual("generated_but_failed_qa", result["run_status"])
        self.assertIn("edit_plan_validation_failed", result["qa_blockers"])

    def test_post_run_status_marks_fully_checked_video_deliverable(self):
        run_video = load_run_video()
        result = {
            "success": True,
            "final_video": "/tmp/final.mp4",
            "edit_plan_validation_ok": True,
            "local_video_qa_ok": True,
            "post_run_warnings": [],
        }

        run_video.apply_post_run_delivery_status(result, storyboarding_only=False)

        self.assertTrue(result["deliverable"])
        self.assertEqual("deliverable", result["run_status"])


if __name__ == "__main__":
    unittest.main()
