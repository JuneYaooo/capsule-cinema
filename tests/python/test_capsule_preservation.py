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
    build_preservation_manifest,
    inventory_sections,
    _write_json_atomic,
    assert_package_unchanged,
    sha256_file,
    snapshot_package,
    validate_preservation_manifest,
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

    def test_section_inventory_is_complete_and_uses_stable_distinct_ids(self) -> None:
        (self.package / "capsule.yaml").write_text(
            "identity:\n  name: fixture\nmatch:\n  tags: [same, same]\ninterface:\n  input: text\n",
            encoding="utf-8",
        )
        (self.package / "recipes" / "copy.md").write_text(
            "---\ntitle: Copy\n---\nIntro before headings.\n\n# First\nBody.\n\n## Second\nMore.\n",
            encoding="utf-8",
        )
        (self.package / "scripts" / "render.py").write_text(
            '"""Module docs."""\nSETTING = 1\n\ndef render():\n    return SETTING\n\nclass Runner:\n    pass\n',
            encoding="utf-8",
        )

        sections = inventory_sections(self.package)
        ids = [section.section_id for section in sections]

        self.assertEqual(ids, [section.section_id for section in inventory_sections(self.package)])
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("capsule.yaml#yaml:/match/tags/0", ids)
        self.assertIn("capsule.yaml#yaml:/match/tags/1", ids)
        self.assertTrue(any(item.relative_path == "recipes/copy.md" and item.kind == "markdown_frontmatter" for item in sections))
        self.assertTrue(any(item.relative_path == "recipes/copy.md" and item.kind == "markdown_preamble" for item in sections))
        python_ids = {
            item.section_id for item in sections if item.relative_path == "scripts/render.py"
        }
        self.assertTrue(
            {
                "scripts/render.py#python:module-preamble",
                "scripts/render.py#python:function:render",
                "scripts/render.py#python:class:Runner",
            }.issubset(python_ids)
        )
        self.assertTrue(all(
            item in {
                "scripts/render.py#python:module-preamble",
                "scripts/render.py#python:function:render",
                "scripts/render.py#python:class:Runner",
            } or "#python:module-region:" in item
            for item in python_ids
        ))
        for section in sections:
            self.assertEqual(len(section.source_digest), 64)
            self.assertIsNotNone(section.byte_start)
            self.assertIsNotNone(section.byte_end)
            self.assertIsNotNone(section.line_start)
            self.assertIsNotNone(section.line_end)

    def test_python_inventory_partitions_all_authored_content_with_unique_stable_symbols(self) -> None:
        source = (
            '"""Module docs."""\n'
            "SETTING = 1\n\n"
            "@decorate\n"
            "def repeated():\n"
            "    return SETTING\n\n"
            "BETWEEN = 2\n\n"
            "async def repeated():\n"
            "    return BETWEEN\n\n"
            "class Runner:\n"
            "    pass\n\n"
            "AFTER = Runner()\n"
        )
        path = self.package / "scripts" / "render.py"
        path.write_text(source, encoding="utf-8")

        python_sections = [
            item for item in inventory_sections(self.package)
            if item.relative_path == "scripts/render.py"
        ]
        ids = [item.section_id for item in python_sections]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("scripts/render.py#python:function:repeated", ids)
        self.assertIn("scripts/render.py#python:async-function:repeated", ids)
        self.assertIn("scripts/render.py#python:class:Runner", ids)
        self.assertGreaterEqual(sum("module-region:" in item for item in ids), 2)

        ordered = sorted(python_sections, key=lambda item: item.byte_start)
        self.assertEqual(ordered[0].byte_start, 0)
        self.assertEqual(ordered[-1].byte_end, len(source.encode("utf-8")))
        self.assertEqual(
            [(left.byte_end, right.byte_start) for left, right in zip(ordered, ordered[1:])],
            [(item.byte_end, item.byte_end) for item in ordered[:-1]],
        )
        reconstructed = b"".join(
            path.read_bytes()[item.byte_start:item.byte_end] for item in ordered
        )
        self.assertEqual(reconstructed, path.read_bytes())
        decorated = next(item for item in python_sections if item.section_id.endswith("function:repeated"))
        self.assertEqual(decorated.line_start, 4)
        self.assertEqual(
            path.read_bytes()[decorated.byte_start:decorated.byte_end].decode("utf-8"),
            "@decorate\ndef repeated():\n    return SETTING",
        )

        shifted = "# leading comment\n" + source
        path.write_text(shifted, encoding="utf-8")
        shifted_ids = {
            item.section_id for item in inventory_sections(self.package)
            if item.relative_path == "scripts/render.py" and ":function:" in item.section_id
        }
        self.assertIn("scripts/render.py#python:function:repeated", shifted_ids)

    def test_python_duplicate_symbols_receive_deterministic_occurrence_ids(self) -> None:
        path = self.package / "scripts" / "render.py"
        path.write_text(
            "def same():\n    return 1\n\ndef same():\n    return 2\n",
            encoding="utf-8",
        )
        ids = [
            item.section_id for item in inventory_sections(self.package)
            if item.relative_path == "scripts/render.py"
        ]
        self.assertIn("scripts/render.py#python:function:same", ids)
        self.assertIn("scripts/render.py#python:function:same~2", ids)
        self.assertEqual(ids, [
            item.section_id for item in inventory_sections(self.package)
            if item.relative_path == "scripts/render.py"
        ])

    def test_markdown_inventory_supports_crlf_setext_fences_and_stable_duplicate_ids(self) -> None:
        source = (
            "---\r\ntitle: Copy\r\n---\r\n"
            "Intro.\r\n\r\n"
            "Same\r\n====\r\n"
            "First body.\r\n\r\n"
            "```md\r\n# Not a heading\r\nFake\r\n----\r\n```\r\n\r\n"
            "Same\r\n----\r\n"
            "Second body.\r\n"
        )
        path = self.package / "recipes" / "copy.md"
        path.write_bytes(source.encode("utf-8"))

        markdown = [
            item for item in inventory_sections(self.package)
            if item.relative_path == "recipes/copy.md"
        ]
        ids = [item.section_id for item in markdown]
        self.assertEqual(
            ids,
            [
                "recipes/copy.md#markdown_frontmatter:frontmatter",
                "recipes/copy.md#markdown_preamble:preamble",
                "recipes/copy.md#markdown_heading:same",
                "recipes/copy.md#markdown_heading:same~2",
            ],
        )
        self.assertEqual([(item.line_start, item.line_end) for item in markdown], [(1, 3), (4, 5), (6, 15), (16, 18)])
        self.assertEqual(len(ids), len(set(ids)))
        self.assertNotIn("Not a heading", "\n".join(ids))
        self.assertNotIn("Fake", "\n".join(ids))
        ordered = sorted(markdown, key=lambda item: item.byte_start)
        self.assertEqual(
            b"".join(path.read_bytes()[item.byte_start:item.byte_end] for item in ordered),
            path.read_bytes(),
        )

        path.write_bytes(source.replace("Intro.\r\n", "Intro.\r\n\r\n").encode("utf-8"))
        shifted_heading_ids = [
            item.section_id for item in inventory_sections(self.package)
            if item.relative_path == "recipes/copy.md" and item.kind == "markdown_heading"
        ]
        self.assertEqual(
            shifted_heading_ids,
            [
                "recipes/copy.md#markdown_heading:same",
                "recipes/copy.md#markdown_heading:same~2",
            ],
        )

    def test_text_inventory_keeps_whitespace_gaps_and_empty_python_file_addressable(self) -> None:
        markdown_path = self.package / "recipes" / "copy.md"
        markdown_path.write_text("---\ntitle: Copy\n---\n\n\n# Heading\nBody\n", encoding="utf-8")
        python_path = self.package / "scripts" / "render.py"
        python_path.write_text("", encoding="utf-8")

        sections = inventory_sections(self.package)
        markdown = [item for item in sections if item.relative_path == "recipes/copy.md"]
        self.assertEqual([item.kind for item in markdown], [
            "markdown_frontmatter", "markdown_preamble", "markdown_heading"
        ])
        self.assertEqual(
            b"".join(
                markdown_path.read_bytes()[item.byte_start:item.byte_end]
                for item in sorted(markdown, key=lambda section: section.byte_start)
            ),
            markdown_path.read_bytes(),
        )
        python = [item for item in sections if item.relative_path == "scripts/render.py"]
        self.assertEqual([item.section_id for item in python], [
            "scripts/render.py#python:module-preamble"
        ])
        self.assertEqual((python[0].byte_start, python[0].byte_end), (0, 0))

    def test_nested_yaml_pointers_are_escaped_distinct_and_precisely_routed(self) -> None:
        for directory in ("quality",):
            (self.package / directory).mkdir(exist_ok=True)
        (self.package / "quality" / "release_gates.yaml").write_text(
            "gates:\n"
            "  - id: structured\n"
            "    checker:\n"
            "      command: verify\n"
            "  - human review\n"
            "a/b:\n"
            "  ~key:\n"
            "    - same\n"
            "    - same\n",
            encoding="utf-8",
        )
        sections = inventory_sections(self.package)
        gates = [item for item in sections if item.relative_path == "quality/release_gates.yaml"]
        by_id = {item.section_id: item for item in gates}
        self.assertIn("quality/release_gates.yaml#yaml:/a~1b/~0key/0", by_id)
        self.assertIn("quality/release_gates.yaml#yaml:/a~1b/~0key/1", by_id)
        manifest = build_preservation_manifest(snapshot_package(self.package), sections)
        routes = {item.section_id: item.disposition for item in manifest.dispositions}
        self.assertEqual(routes["quality/release_gates.yaml#yaml:/gates/1"], "converted_to_rubric")
        for section_id in (
            "quality/release_gates.yaml#yaml:/gates/0",
            "quality/release_gates.yaml#yaml:/gates/0/checker",
            "quality/release_gates.yaml#yaml:/gates/0/checker/command",
        ):
            self.assertEqual(routes[section_id], "converted_to_checker")

    def test_classifier_only_uses_exact_supported_paths_and_does_not_hide_authored_views(self) -> None:
        (self.package / "recipes" / "raw.txt").write_text("authored recipe", encoding="utf-8")
        (self.package / "scripts" / "notes.md").write_text("authored script notes", encoding="utf-8")
        (self.package / "assets" / "notes.md").write_text("authored asset notes", encoding="utf-8")
        (self.package / "CARD.md").write_text(
            "---\ntitle: Fixture\n---\n# Metadata\nDuplicated.\n\n# Editorial\nUnique authored guidance.\n",
            encoding="utf-8",
        )
        (self.package / "index.md").write_text("# Navigation\nDuplicated links.\n\n# Notes\nUnique notes.\n", encoding="utf-8")
        sections = inventory_sections(self.package)
        manifest = build_preservation_manifest(snapshot_package(self.package), sections)
        routes = {item.section_id: item.disposition for item in manifest.dispositions}

        self.assertEqual(routes["recipes/raw.txt#binary:whole-file"], "preserved_in_definition")
        self.assertEqual(routes["scripts/notes.md#markdown_preamble:preamble"], "preserved_in_definition")
        self.assertEqual(routes["assets/notes.md#markdown_preamble:preamble"], "preserved_in_definition")
        self.assertEqual(routes["CARD.md#markdown_frontmatter:frontmatter"], "generated_view")
        self.assertEqual(routes["CARD.md#markdown_heading:metadata"], "generated_view")
        self.assertEqual(routes["CARD.md#markdown_heading:editorial"], "moved_to_guidance")
        self.assertEqual(routes["index.md#markdown_heading:navigation"], "generated_view")
        self.assertEqual(routes["index.md#markdown_heading:notes"], "moved_to_guidance")

    def test_repo_showcase_routing_and_manifest_validation_require_exact_coverage(self) -> None:
        for directory in ("contracts", "quality", "learning", "examples"):
            (self.package / directory).mkdir(exist_ok=True)
        (self.package / "capsule.yaml").write_text(
            "identity:\n  name: fixture\nmatch:\n  tags: [repo]\ninterface:\n  input: text\n",
            encoding="utf-8",
        )
        (self.package / "contracts" / "input_schema.yaml").write_text("type: object\n", encoding="utf-8")
        (self.package / "contracts" / "runtime.yaml").write_text("timeout: 30\n", encoding="utf-8")
        (self.package / "quality" / "rules.yaml").write_text("rules:\n  framing:\n    weight: 2\n", encoding="utf-8")
        (self.package / "quality" / "release_gates.yaml").write_text(
            "gates:\n  - id: has_readme\n    checker: file_exists\n  - human review\n",
            encoding="utf-8",
        )
        (self.package / "learning" / "promoted_lessons.yaml").write_text("lessons:\n  - show proof\n", encoding="utf-8")
        (self.package / "assets" / "index.yaml").write_text("assets:\n  - logo.bin\n", encoding="utf-8")
        (self.package / "examples" / "sample.txt").write_text("example\n", encoding="utf-8")
        (self.package / "CARD.md").write_text("# Fixture\nMetadata\n", encoding="utf-8")
        (self.package / "index.md").write_text("# Navigation\nLinks\n", encoding="utf-8")

        snapshot = snapshot_package(self.package)
        sections = inventory_sections(self.package)
        manifest = build_preservation_manifest(snapshot, sections)
        dispositions = {item.section_id: item.disposition for item in manifest.dispositions}

        expected_by_path = {
            "contracts/input_schema.yaml": "preserved_in_definition",
            "contracts/runtime.yaml": "preserved_in_definition",
            "recipes/copy.md": "moved_to_guidance",
            "learning/promoted_lessons.yaml": "moved_to_guidance",
            "assets/index.yaml": "preserved_in_definition",
            "assets/logo.bin": "moved_to_asset",
            "examples/sample.txt": "moved_to_example",
            "scripts/render.py": "moved_to_runner",
            "__pycache__/x.pyc": "excluded_ephemeral",
        }
        for path, disposition in expected_by_path.items():
            routed = [dispositions[item.section_id] for item in sections if item.relative_path == path]
            self.assertTrue(routed, path)
            self.assertEqual(set(routed), {disposition}, path)
        self.assertEqual(
            {dispositions[item.section_id] for item in sections if item.relative_path == "CARD.md"},
            {"moved_to_guidance"},
        )
        self.assertEqual(
            {dispositions[item.section_id] for item in sections if item.relative_path == "index.md"},
            {"generated_view"},
        )
        self.assertEqual(
            {dispositions[item.section_id] for item in sections if item.relative_path == "capsule.yaml"},
            {"preserved_in_definition"},
        )
        rules = [item for item in sections if item.relative_path == "quality/rules.yaml"]
        self.assertEqual({dispositions[item.section_id] for item in rules}, {"converted_to_rubric"})
        gates = [item for item in sections if item.relative_path == "quality/release_gates.yaml"]
        self.assertIn("converted_to_checker", {dispositions[item.section_id] for item in gates})
        self.assertIn("converted_to_rubric", {dispositions[item.section_id] for item in gates})

        result = validate_preservation_manifest(manifest)
        self.assertTrue(result.ok)
        self.assertEqual(result.status, "complete")
        self.assertEqual(result.data["coverage_percent"], 100.0)
        self.assertEqual(result.data["unclassified"], [])
        self.assertEqual(result.data["silent_deletions"], [])

        tampered_cases = [
            ("coverage_percent", 99.0),
            ("unclassified", [manifest.sections[0].section_id]),
            ("silent_deletions", [manifest.sections[0].section_id]),
        ]
        for field, value in tampered_cases:
            with self.subTest(tampered=field):
                tampered = manifest.model_copy(update={field: value})
                validation = validate_preservation_manifest(tampered)
                self.assertFalse(validation.ok)
                self.assertEqual(validation.status, "incomplete")
                issue = next(
                    item for item in validation.issues
                    if item.code == "preservation_manifest_summary_mismatch"
                )
                self.assertEqual(issue.details["field"], field)

        for index, missing in enumerate(manifest.dispositions):
            incomplete = manifest.model_copy(
                update={"dispositions": manifest.dispositions[:index] + manifest.dispositions[index + 1:]}
            )
            failure = validate_preservation_manifest(incomplete)
            self.assertFalse(failure.ok)
            self.assertEqual(failure.status, "incomplete")
            issue = next(item for item in failure.issues if item.code == "preservation_unclassified")
            self.assertEqual(issue.details["section_ids"], [missing.section_id])

        duplicate = manifest.model_copy(
            update={"dispositions": manifest.dispositions + [manifest.dispositions[0]]}
        )
        duplicate_failure = validate_preservation_manifest(duplicate)
        self.assertFalse(duplicate_failure.ok)
        self.assertTrue(
            any(item.code == "preservation_duplicate_section" for item in duplicate_failure.issues)
        )

        promise_index = next(
            index for index, section in enumerate(manifest.sections) if section.promise_affecting
        )
        obsolete = manifest.dispositions[promise_index].model_copy(
            update={"disposition": "obsolete_with_evidence"}
        )
        obsolete_dispositions = list(manifest.dispositions)
        obsolete_dispositions[promise_index] = obsolete
        obsolete_failure = validate_preservation_manifest(
            manifest.model_copy(update={"dispositions": obsolete_dispositions})
        )
        self.assertFalse(obsolete_failure.ok)
        self.assertEqual(obsolete_failure.data["silent_deletions"], [obsolete.section_id])


if __name__ == "__main__":
    unittest.main()
