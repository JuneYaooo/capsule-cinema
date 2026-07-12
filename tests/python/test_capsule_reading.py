from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import unittest

from src.capsules.loader import CapsuleLoadError, load_definition
from src.capsules.model import CapsuleReadOrder
from src.capsules.reading import load_stage_resources


MANIFEST = """schema_version: capsule.package.v1
name: staged
display_name: Staged Capsule
version: 1
status: active
execution_mode: local_script
category: general
primary_workflow: staged_workflow
summary: Read only the current stage.
capabilities: []
tags: []
when_to_use: []
when_not_to_use: []
read_order:
  routing: [CARD.md, contracts/input_schema.yaml]
  planning: [recipes/structure.md, recipes/copy.md]
  generation: [contracts/runtime.yaml]
  qa: [quality/rules.yaml]
  learning: []
entrypoints:
  local_script: scripts/run.py
"""


class CapsuleReadingTests(unittest.TestCase):
    def make_package(self, root: Path, *, manifest: str = MANIFEST) -> Path:
        package = root / "staged.capsule"
        for directory in ("contracts", "recipes", "quality", "scripts"):
            (package / directory).mkdir(parents=True, exist_ok=True)
        (package / "capsule.yaml").write_text(manifest, encoding="utf-8")
        (package / "CARD.md").write_text("# Route\n", encoding="utf-8")
        (package / "contracts" / "input_schema.yaml").write_text(
            "fields: {}\n", encoding="utf-8"
        )
        (package / "contracts" / "runtime.yaml").write_text(
            "runtime: local\n", encoding="utf-8"
        )
        (package / "recipes" / "structure.md").write_text(
            "# Structure\n", encoding="utf-8"
        )
        (package / "recipes" / "copy.md").write_text("# Copy\n", encoding="utf-8")
        (package / "quality" / "rules.yaml").write_text("rules: []\n", encoding="utf-8")
        (package / "scripts" / "run.py").write_text("print('ok')\n", encoding="utf-8")
        return package

    def test_v1_read_order_is_normalized_and_loaded_in_author_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package = self.make_package(Path(tmp))
            before = {path: path.read_bytes() for path in package.rglob("*") if path.is_file()}

            definition = load_definition(package)
            result = load_stage_resources(definition, "planning")

            self.assertTrue(result.ok, result.issues)
            self.assertEqual(definition.read_order.planning, ["recipes/structure.md", "recipes/copy.md"])
            resources = result.data["resources"]
            self.assertEqual(
                [item["relative_path"] for item in resources],
                ["recipes/structure.md", "recipes/copy.md"],
            )
            self.assertEqual(resources[0]["content"], "# Structure\n")
            self.assertEqual(
                resources[0]["digest"],
                hashlib.sha256(b"# Structure\n").hexdigest(),
            )
            after = {path: path.read_bytes() for path in package.rglob("*") if path.is_file()}
            self.assertEqual(before, after)

    def test_missing_read_order_defaults_to_empty_stages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package = self.make_package(
                Path(tmp), manifest=MANIFEST.split("read_order:\n", 1)[0] + "entrypoints:\n  local_script: scripts/run.py\n"
            )
            definition = load_definition(package)
            self.assertEqual(definition.read_order, CapsuleReadOrder())
            result = load_stage_resources(definition, "qa")
            self.assertTrue(result.ok)
            self.assertEqual(result.data["resources"], [])

    def test_invalid_read_order_shapes_and_duplicates_are_rejected(self) -> None:
        invalid_blocks = (
            "read_order: [CARD.md]\n",
            "read_order:\n  routing: CARD.md\n",
            "read_order:\n  routing: [CARD.md, CARD.md]\n",
            "read_order:\n  unknown: [CARD.md]\n",
        )
        for block in invalid_blocks:
            with self.subTest(block=block), tempfile.TemporaryDirectory() as tmp:
                prefix = MANIFEST.split("read_order:\n", 1)[0]
                package = self.make_package(
                    Path(tmp),
                    manifest=prefix + block + "entrypoints:\n  local_script: scripts/run.py\n",
                )
                with self.assertRaises(CapsuleLoadError) as raised:
                    load_definition(package)
                self.assertEqual(raised.exception.code, "invalid_capsule_definition")

    def test_stage_loading_fails_closed_for_unsafe_or_unreadable_resources(self) -> None:
        cases = (
            ("../outside.md", "stage_resource_outside_package"),
            ("/tmp/absolute.md", "stage_resource_outside_package"),
            ("recipes/missing.md", "stage_resource_missing"),
            ("recipes/binary.md", "stage_resource_not_utf8"),
        )
        for relative, code in cases:
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                manifest = MANIFEST.replace(
                    "planning: [recipes/structure.md, recipes/copy.md]",
                    f"planning: [{relative}]",
                )
                package = self.make_package(root, manifest=manifest)
                if relative == "recipes/binary.md":
                    (package / relative).write_bytes(b"\xff\xfe")
                definition = load_definition(package)
                result = load_stage_resources(definition, "planning")
                self.assertFalse(result.ok)
                self.assertEqual(result.status, "blocked")
                self.assertEqual(result.issues[0].code, code)
                self.assertNotIn(str(root), result.model_dump_json())

    def test_stage_loading_rejects_symlinks_and_unknown_stages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = self.make_package(root)
            outside = root / "outside.md"
            outside.write_text("outside\n", encoding="utf-8")
            link = package / "recipes" / "copy.md"
            link.unlink()
            try:
                link.symlink_to(outside)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"symlinks unavailable: {exc}")
            definition = load_definition(package)

            result = load_stage_resources(definition, "planning")
            self.assertFalse(result.ok)
            self.assertEqual(result.issues[0].code, "stage_resource_symlink_refused")

            unknown = load_stage_resources(definition, "render")
            self.assertFalse(unknown.ok)
            self.assertEqual(unknown.status, "invalid")
            self.assertEqual(unknown.issues[0].code, "stage_unknown")


if __name__ == "__main__":
    unittest.main()
