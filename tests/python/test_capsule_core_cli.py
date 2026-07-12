from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import capsule
from src.capsules.dispatch import DispatchPlan

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "capsule.py"


def write_preset(root: Path, name: str) -> Path:
    package = root / f"{name}.capsule"
    (package / "contracts").mkdir(parents=True)
    (package / "capsule.yaml").write_text(
        f"""schema_version: capsule.package.v1
name: {name}
display_name: {name.title()}
version: 1
status: active
execution_mode: preset
summary: test package
category: test
primary_workflow: test
capabilities: []
tags: []
when_to_use: []
when_not_to_use: []
entrypoints: {{preset: general_video}}
""",
        encoding="utf-8",
    )
    (package / "contracts" / "input_schema.yaml").write_text(
        "fields: {}\n", encoding="utf-8"
    )
    (package / "contracts" / "runtime.yaml").write_text(
        "roles: {}\n", encoding="utf-8"
    )
    return package


def write_creator_contract_package(root: Path) -> Path:
    package = write_preset(root, "creator_contract")
    (package / "capsule.yaml").write_text(
        (package / "capsule.yaml").read_text(encoding="utf-8").replace(
            "capabilities: []\ntags: []",
            "capabilities: [runner, local_script, creator_runner]\n"
            "tags: [entrypoint, local_script, creator_entrypoint]",
        ),
        encoding="utf-8",
    )
    (package / "contracts" / "input_schema.yaml").write_text(
        """fields:
  runner:
    type: string
    required: true
    description: Choose the story runner, not an implementation runner.
    enum: [runner, entrypoint, local_script]
  entrypoint:
    type: string
    description: Creator-defined narrative entrypoint.
  local_script:
    type: string
    description: Creator copy may say local_script verbatim.
""",
        encoding="utf-8",
    )
    return package


class CapsuleCoreCliTests(unittest.TestCase):
    def invoke(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join(
            [str(ROOT / "lib"), str(ROOT / "scripts")]
        )
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
        )

    def assert_one_envelope(self, result: subprocess.CompletedProcess[str]) -> dict:
        decoder = json.JSONDecoder()
        payload, end = decoder.raw_decode(result.stdout)
        self.assertEqual(result.stdout[end:].strip(), "")
        self.assertEqual(set(payload), {"ok", "status", "data", "issues"})
        return payload

    def assert_no_implementation_structure(self, capsule: dict) -> None:
        self.assertNotIn("implementation", capsule)

    def test_list_discovers_real_capsules(self) -> None:
        result = self.invoke("list")
        payload = self.assert_one_envelope(result)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(payload["ok"])
        names = {item["name"] for item in payload["data"]["capsules"]}
        self.assertIn("art_motion", names)
        self.assertIn("felt_asmr", names)

    def test_show_does_not_expose_runner_choice(self) -> None:
        listed = self.invoke("list")
        catalog = self.assert_one_envelope(listed)
        self.assertEqual(listed.returncode, 0, listed.stderr)
        names = [item["name"] for item in catalog["data"]["capsules"]]
        self.assertTrue(names)
        for item in catalog["data"]["capsules"]:
            self.assert_no_implementation_structure(item)
            self.assertNotIn("local_script", item["capabilities"])
            self.assertNotIn("local_script", item["tags"])

        for name in names:
            with self.subTest(capsule=name):
                result = self.invoke("show", name)
                payload = self.assert_one_envelope(result)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assert_no_implementation_structure(payload["data"]["capsule"])

    def test_doctor_does_not_expose_nested_runner_choice(self) -> None:
        listed = self.invoke("list")
        catalog = self.assert_one_envelope(listed)
        self.assertEqual(listed.returncode, 0, listed.stderr)
        names = [item["name"] for item in catalog["data"]["capsules"]]
        self.assertTrue(names)

        for name in names:
            with self.subTest(capsule=name):
                result = self.invoke("doctor", name)
                payload = self.assert_one_envelope(result)
                self.assertIn(result.returncode, (0, 1), result.stderr)
                self.assert_no_implementation_structure(payload["data"]["capsule"])

    def test_creator_owned_runner_named_inputs_and_copy_are_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package = write_creator_contract_package(Path(tmp))
            result = self.invoke("show", str(package))
            payload = self.assert_one_envelope(result)

            self.assertEqual(result.returncode, 0, result.stderr)
            capsule = payload["data"]["capsule"]
            self.assertEqual(
                set(capsule["inputs"]), {"runner", "entrypoint", "local_script"}
            )
            self.assertEqual(
                capsule["inputs"]["runner"]["options"],
                ["runner", "entrypoint", "local_script"],
            )
            self.assertEqual(
                capsule["inputs"]["entrypoint"]["description"],
                "Creator-defined narrative entrypoint.",
            )
            self.assertIn(
                "local_script verbatim",
                capsule["inputs"]["local_script"]["description"],
            )
            self.assertEqual(capsule["capabilities"], ["runner", "creator_runner"])
            self.assertEqual(capsule["tags"], ["entrypoint", "creator_entrypoint"])

    def test_plan_uses_same_surface_for_both_runner_families(self) -> None:
        for capsule in ("art_motion", "felt_asmr"):
            with self.subTest(capsule=capsule):
                result = self.invoke(
                    "plan",
                    capsule,
                    "--topic",
                    "A small test",
                    "--params-json",
                    "{}",
                    "--output-dir",
                    str(ROOT / "output" / "capsule-core-cli-test" / capsule),
                )
                payload = self.assert_one_envelope(result)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(payload["status"], "dispatch_ready")
                self.assertEqual(payload["data"]["action"], "plan")
                serialized = json.dumps(payload, ensure_ascii=False)
                self.assertNotIn("runner", serialized)
                self.assertNotIn("command", serialized)
                self.assertNotIn("entrypoint", serialized)

    def test_missing_capsule_returns_json_failure(self) -> None:
        result = self.invoke("show", "does-not-exist")
        payload = self.assert_one_envelope(result)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["issues"][0]["code"], "capsule_not_found")

    def test_root_routes_list_show_and_doctor_to_custom_packages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_preset(root, "custom")
            for args, expected_status in (
                (("list", "--root", str(root)), "catalog_ready"),
                (("show", "custom", "--root", str(root)), "capsule_ready"),
                (("doctor", "custom", "--root", str(root)), "ready"),
            ):
                with self.subTest(command=args[0]):
                    result = self.invoke(*args)
                    payload = self.assert_one_envelope(result)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(payload["status"], expected_status)

    def test_invalid_params_json_is_sanitized_json_failure(self) -> None:
        secret = "super-secret-value"
        for raw in (f'{{"token":"{secret}"', f'"{secret}"'):
            with self.subTest(raw=raw):
                result = self.invoke(
                    "plan",
                    "art_motion",
                    "--topic",
                    "test",
                    "--params-json",
                    raw,
                    "--output-dir",
                    str(ROOT / "output" / "capsule-core-cli-invalid"),
                )
                payload = self.assert_one_envelope(result)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(payload["status"], "invalid_request")
                self.assertEqual(payload["issues"][0]["code"], "invalid_params_json")
                self.assertNotIn(secret, result.stdout)
                self.assertNotIn(raw, result.stdout)

    def test_dispatch_error_becomes_stable_json_failure(self) -> None:
        result = self.invoke(
            "plan",
            "felt_asmr",
            "--topic",
            "test",
            "--params-json",
            '{"secret_parameter":"do-not-echo"}',
            "--output-dir",
            str(ROOT / "output" / "capsule-core-cli-dispatch-error"),
        )
        payload = self.assert_one_envelope(result)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(payload["issues"][0]["code"], "unsupported_preset_parameter")
        self.assertNotIn("do-not-echo", result.stdout)

    def test_plan_load_error_becomes_stable_json_failure(self) -> None:
        result = self.invoke(
            "plan",
            "does-not-exist",
            "--topic",
            "test",
            "--output-dir",
            str(ROOT / "output" / "capsule-core-cli-missing"),
        )
        payload = self.assert_one_envelope(result)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(payload["status"], "not_found")
        self.assertEqual(payload["issues"][0]["code"], "capsule_not_found")

    def test_argument_errors_remain_argparse_exit_two(self) -> None:
        result = self.invoke("plan", "art_motion")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("usage:", result.stderr)

    def test_reference_documents_json_and_exit_contract(self) -> None:
        reference = (ROOT / "references" / "capsule-core-cli.md").read_text(
            encoding="utf-8"
        )
        reference = reference.lower()

        self.assertIn("after argument parsing succeeds", reference)
        self.assertIn("exit code `0`", reference)
        self.assertIn("exit code `1`", reference)
        self.assertIn("exit code `2`", reference)
        self.assertIn("stdout remains empty", reference)
        self.assertIn("stderr", reference)

    def test_run_start_failure_prints_one_safe_json_envelope(self) -> None:
        secret = "TOP_SECRET_TOKEN"
        plan = DispatchPlan(
            capsule="demo",
            action="run",
            command=[f"/private/{secret}/runner"],
            cwd=f"/private/{secret}",
            environment={"SECRET": secret},
            output_dir="output/demo",
        )
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch("capsule.build_dispatch_plan", return_value=plan),
            patch(
                "src.capsules.dispatch.subprocess.run",
                side_effect=OSError(f"cannot start /private/{secret}"),
            ),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            return_code = capsule.main(
                [
                    "run",
                    "demo",
                    "--topic",
                    "test",
                    "--output-dir",
                    "output/demo",
                ]
            )

        payload, end = json.JSONDecoder().raw_decode(stdout.getvalue())
        self.assertEqual(stdout.getvalue()[end:].strip(), "")
        self.assertEqual(return_code, 1)
        self.assertEqual(payload["issues"][0]["code"], "runner_start_failed")
        self.assertEqual(stderr.getvalue(), "")
        self.assertNotIn(secret, stdout.getvalue())

    def test_run_null_parameter_value_error_prints_one_safe_json_envelope(self) -> None:
        secret = "TOP_SECRET_TOKEN"
        stdout = io.StringIO()
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            with (
                patch(
                    "src.capsules.dispatch.subprocess.run",
                    side_effect=ValueError(f"embedded null byte {secret}"),
                ) as run,
                redirect_stdout(stdout),
                redirect_stderr(stderr),
            ):
                return_code = capsule.main(
                    [
                        "run",
                        "felt_asmr",
                        "--topic",
                        "test",
                        "--params-json",
                        json.dumps({"platform": f"bad\0{secret}"}),
                        "--output-dir",
                        str(Path(tmp) / "output"),
                    ]
                )

        payload, end = json.JSONDecoder().raw_decode(stdout.getvalue())
        self.assertEqual(stdout.getvalue()[end:].strip(), "")
        self.assertEqual(return_code, 1)
        self.assertEqual(payload["status"], "run_failed")
        self.assertEqual(payload["issues"][0]["code"], "runner_start_failed")
        self.assertEqual(stderr.getvalue(), "")
        self.assertNotIn(secret, stdout.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())
        run.assert_called_once()

    def test_loader_failures_are_safe_across_all_cli_operations(self) -> None:
        with tempfile.TemporaryDirectory(prefix="TOP_SECRET_ROOT_") as tmp:
            root = Path(tmp)
            malformed = write_preset(root, "malformed")
            (malformed / "capsule.yaml").write_text(
                "schema_version: [\n", encoding="utf-8"
            )
            unsupported = write_preset(root, "unsupported")
            (unsupported / "capsule.yaml").write_text(
                (unsupported / "capsule.yaml")
                .read_text(encoding="utf-8")
                .replace("capsule.package.v1", "capsule.package.v99"),
                encoding="utf-8",
            )
            missing_entrypoint = write_preset(root, "missing_entrypoint")
            (missing_entrypoint / "capsule.yaml").write_text(
                (missing_entrypoint / "capsule.yaml")
                .read_text(encoding="utf-8")
                .replace("execution_mode: preset", "execution_mode: local_script")
                .replace(
                    "entrypoints: {preset: general_video}",
                    "entrypoints: {local_script: scripts/missing.py}",
                ),
                encoding="utf-8",
            )
            missing_runtime = write_preset(root, "missing_runtime")
            (missing_runtime / "contracts" / "runtime.yaml").unlink()
            cases = [
                (
                    ("list", "--root", str(root)),
                    {
                        "invalid_capsule_document",
                        "unsupported_capsule_schema",
                        "runner_entrypoint_missing",
                    },
                ),
                (("show", str(malformed)), {"invalid_capsule_document"}),
                (("doctor", str(missing_runtime)), {"invalid_capsule_document"}),
                (
                    (
                        "plan",
                        str(unsupported),
                        "--topic",
                        "test",
                        "--output-dir",
                        "output/test",
                    ),
                    {"unsupported_capsule_schema"},
                ),
                (
                    (
                        "run",
                        str(missing_entrypoint),
                        "--topic",
                        "test",
                        "--output-dir",
                        "output/test",
                    ),
                    {"runner_entrypoint_missing"},
                ),
            ]

            for args, expected_codes in cases:
                with self.subTest(operation=args[0]):
                    result = self.invoke(*args)
                    payload = self.assert_one_envelope(result)
                    codes = {issue["code"] for issue in payload["issues"]}
                    self.assertEqual(codes, expected_codes)
                    self.assertNotIn(str(root), result.stdout)
                    self.assertNotIn("TOP_SECRET_ROOT_", result.stdout)
                    self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
