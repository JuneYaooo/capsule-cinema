from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.capsules.preservation import (
    PreservationError,
    _write_json_atomic,
    assert_package_unchanged,
    sha256_file,
    snapshot_package,
    write_baseline,
)


class CapsulePreservationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.package = self.root / "fixture.capsule"
        (self.package / "recipes").mkdir(parents=True)
        (self.package / "scripts").mkdir()
        (self.package / "assets").mkdir()
        (self.package / "__pycache__").mkdir()
        (self.package / "capsule.yaml").write_text("name: fixture\n", encoding="utf-8")
        (self.package / "recipes" / "copy.md").write_text("# Copy\nOriginal\n", encoding="utf-8")
        (self.package / "scripts" / "render.py").write_text("print('fixture')\n", encoding="utf-8")
        (self.package / "assets" / "logo.bin").write_bytes(b"\x00\x01fixture")
        (self.package / "__pycache__" / "x.pyc").write_bytes(b"cache")

    def test_snapshot_is_deterministic_and_excludes_only_ephemeral_bytes(self) -> None:
        before = snapshot_package(self.package)
        repeated = snapshot_package(self.package)

        self.assertEqual(before, repeated)
        self.assertEqual(
            [record.relative_path for record in before.files],
            sorted(record.relative_path for record in before.files),
        )
        self.assertEqual(before.schema_version, "capsule.preservation/v1")
        self.assertEqual(len(before.package_digest), 64)

        (self.package / "__pycache__" / "x.pyc").write_bytes(b"changed cache")
        after_cache = snapshot_package(self.package)
        self.assertEqual(before.package_digest, after_cache.package_digest)
        self.assertTrue(
            any(
                record.relative_path == "__pycache__/x.pyc"
                and record.classification == "excluded_ephemeral"
                for record in after_cache.files
            )
        )

        (self.package / "recipes" / "copy.md").write_text(
            "# Copy\nchanged\n", encoding="utf-8"
        )
        after_source = snapshot_package(self.package)
        self.assertNotEqual(before.package_digest, after_source.package_digest)

    def test_file_and_package_digests_include_relative_paths(self) -> None:
        snapshot = snapshot_package(self.package)
        source = self.package / "capsule.yaml"
        expected_file_digest = hashlib.sha256(b"capsule.yaml\0" + source.read_bytes()).hexdigest()
        record = next(item for item in snapshot.files if item.relative_path == "capsule.yaml")

        self.assertEqual(record.digest, expected_file_digest)
        self.assertEqual(sha256_file(source), hashlib.sha256(source.read_bytes()).hexdigest())

        package_hasher = hashlib.sha256()
        for item in snapshot.files:
            if item.classification != "excluded_ephemeral":
                package_hasher.update(item.relative_path.encode("utf-8"))
                package_hasher.update(b"\0")
                package_hasher.update(item.digest.encode("ascii"))
        self.assertEqual(snapshot.package_digest, package_hasher.hexdigest())

    def test_only_documented_ephemeral_files_are_excluded(self) -> None:
        (self.package / ".DS_Store").write_bytes(b"finder")
        (self.package / "recipes" / ".copy.md.swp").write_bytes(b"swap")
        (self.package / "recipes" / "authored.tmp").write_bytes(b"authored")

        snapshot = snapshot_package(self.package)
        classifications = {item.relative_path: item.classification for item in snapshot.files}

        self.assertEqual(classifications[".DS_Store"], "excluded_ephemeral")
        self.assertEqual(classifications["recipes/.copy.md.swp"], "excluded_ephemeral")
        self.assertEqual(classifications["recipes/authored.tmp"], "authored")

    def test_snapshot_rejects_file_symlink_that_resolves_outside_package(self) -> None:
        external = self.root / "external-secret.txt"
        external.write_text("outside package\n", encoding="utf-8")
        (self.package / "recipes" / "external.md").symlink_to(external)

        with self.assertRaisesRegex(
            PreservationError, "source_path_outside_package"
        ) as caught:
            snapshot_package(self.package)

        self.assertEqual(caught.exception.code, "source_path_outside_package")
        self.assertEqual(
            caught.exception.details["relative_path"], "recipes/external.md"
        )

    def test_write_baseline_is_atomic_structured_and_does_not_capture_environment(self) -> None:
        snapshot = snapshot_package(self.package)
        output = self.root / "migration" / "baseline"
        secret = "must-not-be-serialized"

        with patch.dict(os.environ, {"CAPSULE_TEST_SECRET": secret}):
            baseline_path = write_baseline(
                snapshot,
                output,
                git_head="abc123",
                dirty_paths=["capsules/repo_showcase.capsule/capsule.yaml"],
                python_version="3.12.9",
                ffmpeg_version="7.1",
            )

        self.assertEqual(baseline_path, output / "baseline.json")
        self.assertEqual(
            sorted(path.name for path in output.iterdir()),
            ["baseline.json", "package-digest.json", "source-inventory.json"],
        )
        self.assertFalse(any(path.name.endswith(".tmp") for path in output.iterdir()))
        serialized = "\n".join(path.read_text(encoding="utf-8") for path in output.iterdir())
        self.assertNotIn(secret, serialized)

        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        self.assertEqual(baseline["schema_version"], "capsule.preservation/v1")
        self.assertEqual(baseline["package_digest"], snapshot.package_digest)
        self.assertEqual(baseline["git_head"], "abc123")
        self.assertEqual(baseline["python_version"], "3.12.9")
        self.assertEqual(baseline["ffmpeg_version"], "7.1")
        self.assertNotIn("environment", baseline)

    def test_atomic_write_preserves_existing_target_when_replace_fails(self) -> None:
        output = self.root / "migration" / "baseline"
        output.mkdir(parents=True)
        target = output / "baseline.json"
        sentinel = b"existing baseline sentinel\n"
        target.write_bytes(sentinel)

        with patch.object(
            Path,
            "replace",
            autospec=True,
            side_effect=OSError("replace failed"),
        ) as replace:
            with self.assertRaisesRegex(OSError, "replace failed"):
                _write_json_atomic(target, {"replacement": True})

        self.assertEqual(target.read_bytes(), sentinel)
        temporary, replacement_target = replace.call_args.args
        self.assertEqual(replacement_target, target)
        self.assertEqual(temporary.parent, target.parent)
        self.assertFalse(temporary.exists())

    def test_baseline_cannot_write_inside_or_at_source(self) -> None:
        snapshot = snapshot_package(self.package)
        for output in (self.package, self.package / "baseline"):
            with self.subTest(output=output):
                with self.assertRaisesRegex(PreservationError, "output_inside_source") as caught:
                    write_baseline(
                        snapshot,
                        output,
                        git_head="abc",
                        dirty_paths=[],
                        python_version="3.12",
                        ffmpeg_version="6.1",
                    )
                self.assertEqual(caught.exception.code, "output_inside_source")

    def test_assert_package_unchanged_detects_authored_mutation(self) -> None:
        before = snapshot_package(self.package)
        (self.package / "scripts" / "render.py").write_text("print('changed')\n", encoding="utf-8")

        with self.assertRaisesRegex(PreservationError, "source_mutated") as caught:
            assert_package_unchanged(before, self.package)

        self.assertEqual(caught.exception.code, "source_mutated")
        self.assertEqual(caught.exception.details["before_digest"], before.package_digest)


if __name__ == "__main__":
    unittest.main()
