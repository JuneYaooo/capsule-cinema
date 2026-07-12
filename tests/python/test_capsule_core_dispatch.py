from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import traceback
import unittest
from pathlib import Path
from unittest.mock import patch

from src.capsules.dispatch import (
    DispatchError,
    DispatchPlan,
    build_dispatch_plan,
    execute_dispatch_plan,
)


def write_package(root: Path, name: str, mode: str) -> Path:
    package = root / f"{name}.capsule"
    (package / "contracts").mkdir(parents=True)
    (package / "scripts").mkdir()
    local = "\n  local_script: scripts/run.py" if mode == "local_script" else ""
    (package / "capsule.yaml").write_text(
        f"""schema_version: capsule.package.v1
name: {name}
display_name: {name}
version: 1
status: active
execution_mode: {mode}
summary: demo
category: demo
primary_workflow: demo
capabilities: []
tags: []
when_to_use: []
when_not_to_use: []
entrypoints:
  preset: general_video{local}
""",
        encoding="utf-8",
    )
    (package / "contracts" / "input_schema.yaml").write_text(
        "fields: {}\n", encoding="utf-8"
    )
    (package / "scripts" / "run.py").write_text(
        "print('run')\n", encoding="utf-8"
    )
    return package


class CapsuleCoreDispatchTests(unittest.TestCase):
    def test_plan_hides_local_runner_behind_common_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = write_package(root, "local", "local_script")
            output = root / "out"
            params = {"mood": "calm"}

            plan = build_dispatch_plan(package, "topic", params, output, "plan")

            self.assertEqual(plan.capsule, "local")
            self.assertEqual(plan.command[0], sys.executable)
            self.assertTrue(plan.command[1].endswith("scripts/run_capsule.py"))
            self.assertEqual(plan.cwd, str(Path(__file__).resolve().parents[2]))
            self.assertEqual(plan.environment, {})
            self.assertIn("--dry-run", plan.command)
            self.assertIn("--params", plan.command)
            params_path = output / "inputs" / "params.requested.json"
            self.assertEqual(json.loads(params_path.read_text()), params)
            self.assertTrue(params_path.read_text(encoding="utf-8").endswith("\n"))

    def test_plan_maps_preset_params_and_output_environment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = write_package(root, "preset", "preset")
            output = root / "out"
            params = {
                "target_duration": 18,
                "aspect_ratio": "9:16",
                "platform": "douyin",
                "add_subtitles": False,
                "add_background_music": True,
                "background_music_path": "/tmp/music.mp3",
                "bgm_volume": 0.25,
                "voice_volume": 2,
                "image_engine": "image",
                "video_engine": "video",
                "user_reference_images": ["a.png", "b.png"],
                "accept_preflight_changes": True,
            }

            plan = build_dispatch_plan(package, "topic", params, output, "plan")

            self.assertTrue(plan.command[1].endswith("scripts/run_video.py"))
            self.assertIn("--storyboard_only", plan.command)
            self.assertEqual(
                plan.environment,
                {"OPENCLAW_OUTPUT_DIR": str(output.resolve())},
            )
            expected_pairs = {
                "--target_duration": "18",
                "--aspect_ratio": "9:16",
                "--platform": "douyin",
                "--add_subtitles": "false",
                "--add_background_music": "true",
                "--background_music_path": "/tmp/music.mp3",
                "--bgm_volume": "0.25",
                "--voice_volume": "2.0",
                "--image_engine": "image",
                "--video_engine": "video",
                "--user_reference_images": '["a.png","b.png"]',
            }
            for flag, value in expected_pairs.items():
                self.assertEqual(plan.command[plan.command.index(flag) + 1], value)
            self.assertIn("--accept_preflight_changes", plan.command)
            self.assertEqual(
                json.loads(
                    (output / "inputs" / "params.requested.json").read_text()
                ),
                params,
            )

    def test_preset_unknown_parameters_raise_stable_dispatch_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package = write_package(Path(tmp), "preset", "preset")
            with self.assertRaises(DispatchError) as raised:
                build_dispatch_plan(
                    package,
                    "topic",
                    {"z_unknown": 1, "a_unknown": 2},
                    Path(tmp) / "out",
                    "run",
                )

            self.assertEqual(raised.exception.code, "unsupported_preset_parameter")
            self.assertEqual(
                raised.exception.details,
                {"parameters": ["a_unknown", "z_unknown"]},
            )
            self.assertTrue(
                (Path(tmp) / "out" / "inputs" / "params.requested.json").is_file()
            )

    def test_preset_parameter_types_are_strict(self) -> None:
        invalid_params = [
            {"target_duration": True},
            {"aspect_ratio": 916},
            {"add_subtitles": "false"},
            {"bgm_volume": "0.2"},
            {"user_reference_images": "a.png"},
            {"accept_preflight_changes": 1},
        ]
        for params in invalid_params:
            with self.subTest(params=params), tempfile.TemporaryDirectory() as tmp:
                package = write_package(Path(tmp), "preset", "preset")
                with self.assertRaises(DispatchError) as raised:
                    build_dispatch_plan(
                        package, "topic", params, Path(tmp) / "out", "run"
                    )
                self.assertEqual(
                    raised.exception.code, "invalid_preset_parameter"
                )
                self.assertEqual(
                    raised.exception.details["parameter"], next(iter(params))
                )

    def test_snapshot_serialization_failure_is_a_stable_dispatch_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package = write_package(Path(tmp), "local", "local_script")
            with self.assertRaises(DispatchError) as raised:
                build_dispatch_plan(
                    package,
                    "topic",
                    {"not_json": {1, 2}},
                    Path(tmp) / "out",
                    "run",
                )

            self.assertEqual(raised.exception.code, "output_snapshot_failed")
            self.assertEqual(
                raised.exception.details,
                {"output_dir": str((Path(tmp) / "out").resolve())},
            )

    def test_snapshot_write_failure_is_a_stable_dispatch_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package = write_package(Path(tmp), "local", "local_script")
            with (
                patch("pathlib.Path.write_text", side_effect=OSError("secret")),
                self.assertRaises(DispatchError) as raised,
            ):
                build_dispatch_plan(
                    package,
                    "topic",
                    {},
                    Path(tmp) / "out",
                    "run",
                )

            self.assertEqual(raised.exception.code, "output_snapshot_failed")
            self.assertNotIn("secret", str(raised.exception))

    def test_snapshot_boundary_hides_underlying_exception_context(self) -> None:
        failures = [
            ("src.capsules.dispatch.json.dumps", TypeError("TOP_SECRET_TOKEN")),
            ("pathlib.Path.write_text", OSError("TOP_SECRET_TOKEN")),
        ]
        for target, failure in failures:
            with (
                self.subTest(error_type=type(failure).__name__),
                tempfile.TemporaryDirectory() as tmp,
            ):
                package = write_package(Path(tmp), "local", "local_script")
                with (
                    patch(target, side_effect=failure),
                    self.assertRaises(DispatchError) as raised,
                ):
                    build_dispatch_plan(
                        package,
                        "topic",
                        {},
                        Path(tmp) / "out",
                        "run",
                    )

                self.assertEqual(
                    raised.exception.code, "output_snapshot_failed"
                )
                self.assertEqual(
                    raised.exception.details,
                    {"output_dir": str((Path(tmp) / "out").resolve())},
                )
                self.assert_sanitized_exception(raised.exception)

    def assert_sanitized_exception(self, exception: DispatchError) -> None:
        visible = "".join(traceback.format_exception(exception))
        self.assertNotIn("TOP_SECRET_TOKEN", visible)
        self.assertIsNone(exception.__cause__)
        self.assertIsNone(exception.__context__)

    @patch("src.capsules.dispatch.subprocess.run")
    def test_executor_merges_override_and_forwards_logs_to_stderr(self, run) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package = write_package(Path(tmp), "preset", "preset")
            plan = build_dispatch_plan(package, "topic", {}, Path(tmp) / "out", "run")
            run.return_value.returncode = 0
            run.return_value.stdout = "legacy stdout\n"
            run.return_value.stderr = "legacy stderr\n"

            with (
                patch.dict(
                    os.environ,
                    {"KEEP_ME": "yes", "OPENCLAW_OUTPUT_DIR": "old"},
                    clear=True,
                ),
                patch("sys.stderr.write") as stderr_write,
            ):
                result = execute_dispatch_plan(plan)

            self.assertTrue(result.ok)
            self.assertEqual(result.status, "completed")
            self.assertEqual(result.data["return_code"], 0)
            run.assert_called_once_with(
                plan.command,
                cwd=plan.cwd,
                env={
                    "KEEP_ME": "yes",
                    "OPENCLAW_OUTPUT_DIR": plan.output_dir,
                },
                text=True,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
            )
            self.assertEqual(
                [call.args[0] for call in stderr_write.call_args_list],
                ["legacy stdout\n", "legacy stderr\n"],
            )

    @patch("src.capsules.dispatch.subprocess.run")
    def test_executor_returns_child_exit_evidence(self, run) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package = write_package(Path(tmp), "preset", "preset")
            plan = build_dispatch_plan(package, "topic", {}, Path(tmp) / "out", "run")
            run.return_value.returncode = 7
            run.return_value.stdout = ""
            run.return_value.stderr = ""

            result = execute_dispatch_plan(plan)

            self.assertFalse(result.ok)
            self.assertEqual(result.status, "run_failed")
            self.assertEqual(result.data["return_code"], 7)
            self.assertEqual(result.issues[0].code, "runner_failed")
            self.assertEqual(result.issues[0].details, {"return_code": 7})

    @patch("src.capsules.dispatch.subprocess.run")
    def test_executor_maps_start_errors_without_exception_evidence(self, run) -> None:
        run.side_effect = OSError("TOP_SECRET_TOKEN /private/runner.py")
        plan = self.safe_plan()

        result = execute_dispatch_plan(plan)

        self.assertFalse(result.ok)
        self.assertEqual(result.status, "run_failed")
        self.assertEqual(result.issues[0].code, "runner_start_failed")
        self.assertEqual(
            result.data,
            {"capsule": "demo", "action": "run", "output_dir": "output/demo"},
        )
        serialized = result.model_dump_json()
        self.assertNotIn("TOP_SECRET_TOKEN", serialized)
        self.assertNotIn("runner.py", serialized)

    @patch("src.capsules.dispatch.subprocess.run")
    def test_executor_maps_value_error_as_a_safe_start_failure(self, run) -> None:
        run.side_effect = ValueError("embedded null byte TOP_SECRET_TOKEN")

        result = execute_dispatch_plan(self.safe_plan())

        self.assertFalse(result.ok)
        self.assertEqual(result.status, "run_failed")
        self.assertEqual(result.issues[0].code, "runner_start_failed")
        self.assertEqual(
            result.data,
            {"capsule": "demo", "action": "run", "output_dir": "output/demo"},
        )
        serialized = result.model_dump_json()
        self.assertNotIn("TOP_SECRET_TOKEN", serialized)
        self.assertNotIn("embedded null byte", serialized)
        self.assertNotIn("/private/", serialized)

    @patch("src.capsules.dispatch.subprocess.run")
    def test_executor_maps_communication_and_unicode_errors(self, run) -> None:
        failures = [
            subprocess.SubprocessError("TOP_SECRET_TOKEN"),
            UnicodeError("TOP_SECRET_TOKEN"),
        ]
        for failure in failures:
            with self.subTest(error_type=type(failure).__name__):
                run.side_effect = failure

                result = execute_dispatch_plan(self.safe_plan())

                self.assertFalse(result.ok)
                self.assertEqual(result.status, "run_failed")
                self.assertEqual(
                    result.issues[0].code, "runner_communication_failed"
                )
                self.assertNotIn("TOP_SECRET_TOKEN", result.model_dump_json())

    @patch("src.capsules.dispatch.subprocess.run")
    def test_executor_requests_replacement_decoding_for_invalid_bytes(self, run) -> None:
        run.return_value = subprocess.CompletedProcess(
            args=["hidden"], returncode=0, stdout="invalid: �\n", stderr=""
        )

        with patch("sys.stderr.write") as stderr_write:
            result = execute_dispatch_plan(self.safe_plan())

        self.assertTrue(result.ok)
        self.assertEqual(run.call_args.kwargs["encoding"], "utf-8")
        self.assertEqual(run.call_args.kwargs["errors"], "replace")
        stderr_write.assert_called_once_with("invalid: �\n")

    @patch("src.capsules.dispatch.subprocess.run")
    def test_executor_maps_log_forwarding_unicode_errors(self, run) -> None:
        run.return_value = subprocess.CompletedProcess(
            args=["hidden"], returncode=0, stdout="legacy output", stderr=""
        )

        with patch("sys.stderr.write", side_effect=UnicodeError("TOP_SECRET_TOKEN")):
            result = execute_dispatch_plan(self.safe_plan())

        self.assertFalse(result.ok)
        self.assertEqual(result.issues[0].code, "runner_communication_failed")
        self.assertNotIn("TOP_SECRET_TOKEN", result.model_dump_json())

    def safe_plan(self) -> DispatchPlan:
        return DispatchPlan(
            capsule="demo",
            action="run",
            command=["/private/TOP_SECRET_TOKEN/runner"],
            cwd="/private/TOP_SECRET_TOKEN",
            environment={"SECRET": "TOP_SECRET_TOKEN"},
            output_dir="output/demo",
        )


if __name__ == "__main__":
    unittest.main()
