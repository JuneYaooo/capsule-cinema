from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


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

    def test_list_discovers_real_capsules(self) -> None:
        result = self.invoke("list")
        payload = self.assert_one_envelope(result)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(payload["ok"])
        names = {item["name"] for item in payload["data"]["capsules"]}
        self.assertIn("art_motion", names)
        self.assertIn("felt_asmr", names)

    def test_show_does_not_expose_runner_choice(self) -> None:
        result = self.invoke("show", "art_motion")
        payload = self.assert_one_envelope(result)
        self.assertEqual(result.returncode, 0, result.stderr)
        serialized = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("local_script", serialized)
        self.assertNotIn("entrypoint", serialized)

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


if __name__ == "__main__":
    unittest.main()
