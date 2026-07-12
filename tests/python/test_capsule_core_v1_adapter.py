import tempfile
import unittest
from pathlib import Path

from src.capsules.loader import CapsuleLoadError, detect_schema, load_definition


MANIFEST = """schema_version: capsule.package.v1
profile: video.okf.capsule.v1
name: demo
display_name: Demo Capsule
version: 7
status: active
execution_mode: local_script
category: demo_video
primary_workflow: demo_workflow
summary: Produce a deterministic demo video.
capabilities: [image_to_video]
tags: [demo]
when_to_use: [demo, tutorial]
when_not_to_use: [live_stream]
entrypoints:
  preset: general_video
  local_script: scripts/run_demo.py
"""

INPUTS = """fields:
  prompt:
    type: string
    required: true
  mood:
    type: string
    required: false
    default: calm
    enum: [calm, vivid]
  target_duration:
    type: integer
    required: false
    default: 10
    minimum: 4
    maximum: 10
"""


class CapsuleCoreV1AdapterTests(unittest.TestCase):
    def make_package(self, root: Path) -> Path:
        package = root / "demo.capsule"
        (package / "contracts").mkdir(parents=True)
        (package / "scripts").mkdir()
        (package / "capsule.yaml").write_text(MANIFEST, encoding="utf-8")
        (package / "contracts" / "input_schema.yaml").write_text(INPUTS, encoding="utf-8")
        (package / "scripts" / "run_demo.py").write_text("print('demo')\n", encoding="utf-8")
        return package

    def assert_load_error(self, package: Path, code: str) -> CapsuleLoadError:
        with self.assertRaises(CapsuleLoadError) as raised:
            load_definition(package)
        self.assertEqual(raised.exception.code, code)
        self.assertTrue(raised.exception.subject.startswith(str(package.resolve())))
        self.assertIsInstance(raised.exception.details, dict)
        return raised.exception

    def test_adapts_v1_without_changing_package_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package = self.make_package(Path(tmp))
            before = {path: path.read_bytes() for path in package.rglob("*") if path.is_file()}
            capsule = load_definition("demo", search_roots=[Path(tmp)])
            after = {path: path.read_bytes() for path in package.rglob("*") if path.is_file()}
            self.assertEqual(before, after)
            self.assertEqual(capsule.metadata.version, "7")
            self.assertEqual(capsule.interface.inputs["mood"].options, ["calm", "vivid"])
            self.assertEqual(capsule.interface.inputs["target_duration"].minimum, 4)
            self.assertEqual(capsule.interface.inputs["target_duration"].maximum, 10)
            self.assertEqual(capsule.implementation.runner.kind, "local_script")
            self.assertTrue(Path(capsule.implementation.runner.entrypoint).is_absolute())

    def test_filters_only_exact_legacy_routing_markers_from_match_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package = self.make_package(Path(tmp))
            manifest = (package / "capsule.yaml").read_text(encoding="utf-8")
            manifest = manifest.replace(
                "capabilities: [image_to_video]",
                "capabilities: [local_script, runner, creator_local_script]",
            ).replace(
                "tags: [demo]",
                "tags: [local_script, entrypoint, creator_entrypoint]",
            )
            (package / "capsule.yaml").write_text(manifest, encoding="utf-8")

            capsule = load_definition(package)

            self.assertEqual(
                capsule.match.capabilities, ["runner", "creator_local_script"]
            )
            self.assertEqual(
                capsule.match.tags, ["entrypoint", "creator_entrypoint"]
            )

    def test_rejects_unknown_schema_with_stable_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package = self.make_package(Path(tmp))
            (package / "capsule.yaml").write_text(
                MANIFEST.replace("capsule.package.v1", "capsule.package.v99"),
                encoding="utf-8",
            )
            self.assert_load_error(package, "unsupported_capsule_schema")

    def test_rejects_missing_local_entrypoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package = self.make_package(Path(tmp))
            (package / "scripts" / "run_demo.py").unlink()
            self.assert_load_error(package, "runner_entrypoint_missing")

    def test_rejects_local_entrypoint_that_escapes_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = self.make_package(root)
            (root / "outside.py").write_text("print('outside')\n", encoding="utf-8")
            (package / "capsule.yaml").write_text(
                MANIFEST.replace("scripts/run_demo.py", "../outside.py"), encoding="utf-8"
            )
            self.assert_load_error(package, "runner_entrypoint_missing")

    def test_translates_circular_local_entrypoint_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package = self.make_package(Path(tmp))
            entrypoint = package / "scripts" / "loop.py"
            try:
                entrypoint.symlink_to("loop.py")
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"symlinks are unavailable: {exc}")
            (package / "capsule.yaml").write_text(
                MANIFEST.replace("scripts/run_demo.py", "scripts/loop.py"),
                encoding="utf-8",
            )
            error = self.assert_load_error(package, "runner_entrypoint_missing")
            self.assertEqual(error.subject, str(package.resolve()))

    def test_translates_malformed_and_non_object_documents(self) -> None:
        documents = {
            "capsule.yaml": "schema_version: [\n",
            "contracts/input_schema.yaml": "- prompt\n",
        }
        for relative, content in documents.items():
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as tmp:
                package = self.make_package(Path(tmp))
                (package / relative).write_text(content, encoding="utf-8")
                self.assert_load_error(package, "invalid_capsule_document")

    def test_translates_missing_input_document(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package = self.make_package(Path(tmp))
            (package / "contracts" / "input_schema.yaml").unlink()
            self.assert_load_error(package, "invalid_capsule_document")

    def test_rejects_invalid_input_field_shapes(self) -> None:
        documents = ["fields: []\n", "fields:\n  prompt: required\n", "fields:\n  prompt:\n    enum: calm\n"]
        for content in documents:
            with self.subTest(content=content), tempfile.TemporaryDirectory() as tmp:
                package = self.make_package(Path(tmp))
                (package / "contracts" / "input_schema.yaml").write_text(content, encoding="utf-8")
                self.assert_load_error(package, "invalid_input_schema")

    def test_rejects_invalid_execution_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package = self.make_package(Path(tmp))
            (package / "capsule.yaml").write_text(
                MANIFEST.replace("execution_mode: local_script", "execution_mode: remote"),
                encoding="utf-8",
            )
            self.assert_load_error(package, "invalid_runner_kind")

    def test_translates_normalized_model_validation_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package = self.make_package(Path(tmp))
            (package / "capsule.yaml").write_text(
                MANIFEST.replace("name: demo", "name: ''"), encoding="utf-8"
            )
            error = self.assert_load_error(package, "invalid_capsule_definition")
            self.assertIn("errors", error.details)

    def test_translates_invalid_manifest_collection_types(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package = self.make_package(Path(tmp))
            (package / "capsule.yaml").write_text(
                MANIFEST.replace("capabilities: [image_to_video]", "capabilities: 3"),
                encoding="utf-8",
            )
            error = self.assert_load_error(package, "invalid_capsule_definition")
            self.assertEqual(error.details, {"field": "capabilities"})

    def test_rejects_string_and_mapping_manifest_collections(self) -> None:
        cases = {
            "capabilities": "image_to_video",
            "tags": "{demo: true}",
            "when_to_use": "demo",
            "when_not_to_use": "{live_stream: true}",
        }
        for field, value in cases.items():
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                package = self.make_package(Path(tmp))
                original = next(line for line in MANIFEST.splitlines() if line.startswith(f"{field}:"))
                (package / "capsule.yaml").write_text(
                    MANIFEST.replace(original, f"{field}: {value}"),
                    encoding="utf-8",
                )
                error = self.assert_load_error(package, "invalid_capsule_definition")
                self.assertEqual(error.details, {"field": field})

    def test_detect_schema_reads_manifest_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package = self.make_package(Path(tmp))
            (package / "contracts" / "input_schema.yaml").unlink()
            self.assertEqual(detect_schema(package), "capsule.package.v1")

    def test_translates_resolution_errors_with_search_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(CapsuleLoadError) as raised:
                load_definition("missing", search_roots=[root])
            self.assertEqual(raised.exception.code, "capsule_not_found")
            self.assertEqual(raised.exception.subject, "missing")
            self.assertEqual(raised.exception.details, {"search_roots": [str(root)]})


if __name__ == "__main__":
    unittest.main()
