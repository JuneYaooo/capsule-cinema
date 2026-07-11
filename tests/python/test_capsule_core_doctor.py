import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from src.capsules.doctor import doctor_capsule


def write_package(root: Path, runtime: str) -> Path:
    package = root / "demo.capsule"
    (package / "contracts").mkdir(parents=True)
    (package / "capsule.yaml").write_text(
        """schema_version: capsule.package.v1
name: demo
display_name: Demo
version: 1
status: active
execution_mode: preset
summary: Demo
category: demo
primary_workflow: demo
capabilities: []
tags: []
when_to_use: []
when_not_to_use: []
entrypoints: {preset: general_video}
""",
        encoding="utf-8",
    )
    (package / "contracts" / "input_schema.yaml").write_text(
        "fields: {}\n", encoding="utf-8"
    )
    (package / "contracts" / "runtime.yaml").write_text(runtime, encoding="utf-8")
    return package


class CapsuleCoreDoctorTests(unittest.TestCase):
    def test_no_declared_roles_is_structurally_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package = write_package(Path(tmp), "roles: {}\noutput_contract: {}\n")
            with (
                patch("src.capsules.doctor.load_all_tools") as load_tools,
                patch("src.capsules.doctor.scan_available_env") as scan_env,
                patch("src.capsules.doctor.run_preflight") as run_preflight,
            ):
                result = doctor_capsule(package)
            self.assertTrue(result.ok)
            self.assertEqual(result.status, "ready")
            self.assertIsNone(result.data["preflight"])
            self.assertEqual(result.issues[0].code, "preflight_not_declared")
            self.assertEqual(result.issues[0].severity, "info")
            load_tools.assert_not_called()
            scan_env.assert_not_called()
            run_preflight.assert_not_called()

    def test_missing_capability_blocks_with_preflight_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package = write_package(
                Path(tmp),
                """roles:
  image:
    modality: image
    requires: [transparent_background]
output_contract: {}
""",
            )
            result = doctor_capsule(package, environ={}, tools={})
            self.assertFalse(result.ok)
            self.assertEqual(result.status, "blocked")
            self.assertEqual(result.issues[0].code, "local_capability_blocked")
            self.assertEqual(result.data["preflight"]["blocked"], ["image"])

    def test_substitution_requires_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package = write_package(
                Path(tmp),
                """roles:
  image:
    modality: image
    validated_with: preferred
output_contract: {}
""",
            )
            tools = {
                "available": {
                    "modality": "image",
                    "provides": {"flags": {}},
                    "requires_env": ["LOCAL_IMAGE_KEY"],
                }
            }
            result = doctor_capsule(
                package,
                environ={"LOCAL_IMAGE_KEY": "present"},
                tools=tools,
            )
            self.assertTrue(result.ok)
            self.assertEqual(result.status, "needs_confirmation")
            self.assertEqual(
                result.issues[0].code, "local_substitution_requires_confirmation"
            )
            self.assertEqual(result.issues[0].severity, "warning")
            self.assertEqual(
                result.data["preflight"]["roles"]["image"]["selected"], "available"
            )

    def test_exact_declared_tool_is_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package = write_package(
                Path(tmp),
                """roles:
  image:
    modality: image
    validated_with: preferred
output_contract: {}
""",
            )
            tools = {
                "preferred": {
                    "modality": "image",
                    "provides": {"flags": {}},
                    "requires_env": ["LOCAL_IMAGE_KEY"],
                }
            }
            result = doctor_capsule(
                package,
                environ={"LOCAL_IMAGE_KEY": "present"},
                tools=tools,
            )
            self.assertTrue(result.ok)
            self.assertEqual(result.status, "ready")
            self.assertEqual(result.issues, [])
            self.assertEqual(result.data["preflight"]["status"], "ok")

    def test_loader_error_becomes_invalid_capsule_envelope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = doctor_capsule("missing", search_roots=[Path(tmp)])
            self.assertFalse(result.ok)
            self.assertEqual(result.status, "invalid_capsule")
            self.assertEqual(result.issues[0].code, "capsule_not_found")

    def test_runtime_document_error_does_not_leak_loader_exception(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package = write_package(Path(tmp), "roles: [\n")
            result = doctor_capsule(package, environ={}, tools={})
            self.assertFalse(result.ok)
            self.assertEqual(result.status, "invalid_capsule")
            self.assertEqual(result.issues[0].code, "invalid_capsule_document")
            self.assertEqual(
                result.issues[0].message,
                "Could not read capsule runtime contract.",
            )
            self.assertNotIn("YAML", result.issues[0].message)

    def test_runtime_read_and_decode_errors_return_stable_envelopes(self) -> None:
        failures = [OSError("simulated secret"), UnicodeError("simulated secret")]
        for failure in failures:
            with (
                self.subTest(error_type=type(failure).__name__),
                tempfile.TemporaryDirectory() as tmp,
            ):
                package = write_package(Path(tmp), "roles: {}\n")
                with patch(
                    "src.capsules.doctor.load_runtime_contract",
                    side_effect=failure,
                ):
                    result = doctor_capsule(package)

                self.assertFalse(result.ok)
                self.assertEqual(result.status, "invalid_capsule")
                self.assertEqual(result.issues[0].code, "invalid_capsule_document")
                self.assertEqual(
                    result.issues[0].message,
                    "Could not read capsule runtime contract.",
                )
                self.assertNotIn("simulated secret", result.model_dump_json())

    def test_default_tool_catalog_errors_return_stable_blocked_envelopes(self) -> None:
        failures = [OSError("simulated secret"), yaml.YAMLError("simulated secret")]
        runtime = "roles: {image: {modality: image}}\n"
        for failure in failures:
            with (
                self.subTest(error_type=type(failure).__name__),
                tempfile.TemporaryDirectory() as tmp,
            ):
                package = write_package(Path(tmp), runtime)
                with patch(
                    "src.capsules.doctor.load_all_tools",
                    side_effect=failure,
                ):
                    result = doctor_capsule(package, environ={})

                self.assertFalse(result.ok)
                self.assertEqual(result.status, "blocked")
                self.assertEqual(
                    result.issues[0].code, "local_tool_catalog_unavailable"
                )
                self.assertEqual(
                    result.issues[0].message,
                    "Could not read local tool capability catalog.",
                )
                self.assertEqual(result.issues[0].details, {})
                self.assertNotIn("simulated secret", result.model_dump_json())

    def test_invalid_role_shape_becomes_invalid_capsule_envelope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package = write_package(Path(tmp), "roles: {image: invalid}\n")
            result = doctor_capsule(package, environ={}, tools={})
            self.assertFalse(result.ok)
            self.assertEqual(result.status, "invalid_capsule")
            self.assertEqual(result.issues[0].code, "invalid_runtime_contract")

    def test_invalid_nested_role_shapes_become_stable_envelopes(self) -> None:
        roles = [
            "depends_on: 3",
            "requires: 3",
            "requires_enums: []",
        ]
        for role in roles:
            with self.subTest(role=role), tempfile.TemporaryDirectory() as tmp:
                package = write_package(
                    Path(tmp),
                    f"roles:\n  image:\n    modality: image\n    {role}\n",
                )
                result = doctor_capsule(package, environ={}, tools={})

                self.assertFalse(result.ok)
                self.assertEqual(result.status, "invalid_capsule")
                self.assertEqual(result.issues[0].code, "invalid_runtime_contract")
                self.assertEqual(
                    result.issues[0].message,
                    "Capsule runtime role fields have invalid types.",
                )
                self.assertEqual(result.issues[0].details, {})


if __name__ == "__main__":
    unittest.main()
