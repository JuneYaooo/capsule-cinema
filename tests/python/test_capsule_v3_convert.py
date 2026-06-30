import json
import sqlite3
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from capsule_v3_convert import (  # noqa: E402
    convert_capsule,
    load_capsule_from_db,
    load_capsule_from_zip_dir,
    main,
)


def make_db(path: Path) -> None:
    make_db_with_payload(path, make_payload())


def make_payload(
    *,
    description: str = "A sample recipe.",
    quality_rules: list[dict] | None = None,
    local_assets: list[dict] | None = None,
    run_history: list[dict] | None = None,
    feedback: list[dict] | None = None,
    changelog: list[dict] | None = None,
) -> dict:
    return {
        "name": "sample",
        "display_name": "Sample Capsule",
        "status": "active",
        "execution_mode": "preset",
        "description": description,
        "category": "test",
        "tags": ["sample"],
        "config": {
            "roles": {
                "video": {
                    "modality": "video",
                    "requires": ["image_to_video"],
                    "validated_with": "SeedanceFastVideoGeneratorTool",
                }
            },
            "output_contract": {
                "voice": "none",
                "subtitle": "none",
                "bgm": "external",
            },
            "aspect_ratio": "9:16",
            "target_duration": 12,
            "bgm_volume": 0.05,
        },
        "method": {
            "structure": [
                "opening tactile event",
                "middle variation",
                "closing payoff",
            ],
            "visual_rules": ["keep wool fiber texture visible"],
            "known_pitfalls": ["avoid real cream texture"],
            "custom_unknown": {"note": "preserve me"},
        },
        "input_schema": {"topic": {"type": "string", "required": True}},
        "quality_rules": quality_rules
        if quality_rules is not None
        else [
            {
                "id": "wechat_3x4_format",
                "type": "video_quality",
                "category": "final_video",
                "expected_width": 1080,
                "expected_height": 1440,
                "checks": {
                    "frame_rate": {"minimum": 24},
                    "safe_area": {"bottom_pct": 0.2},
                },
            }
        ],
        "local_assets": local_assets
        if local_assets is not None
        else [
            {
                "key": "style_ref",
                "role": "style_reference",
                "reuse": "reference_only",
                "path": "",
                "description": "style only",
            }
        ],
        "examples": [{"kind": "opening_terms", "value": ["sample phrase"]}],
        "local_script_path": "",
        "version": 7,
        "run_history": run_history if run_history is not None else [{"workspace_dir": "/tmp/output/run"}],
        "feedback": feedback if feedback is not None else [{"summary": "past failure", "fix": "general fix"}],
        "changelog": changelog if changelog is not None else [{"version": 7, "text": "changed recipe"}],
        "notes": "",
    }


def make_db_with_payload(path: Path, payload: dict) -> None:
    with sqlite3.connect(path) as conn:
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
                examples_json TEXT NOT NULL,
                local_script_path TEXT NOT NULL,
                version INTEGER NOT NULL,
                run_history_json TEXT NOT NULL,
                feedback_json TEXT NOT NULL,
                changelog_json TEXT NOT NULL,
                notes TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO capsules VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                payload["name"],
                payload["display_name"],
                payload["status"],
                payload["execution_mode"],
                payload["description"],
                payload["category"],
                json.dumps(payload["tags"]),
                json.dumps(payload["config"]),
                json.dumps(payload["method"]),
                json.dumps(payload["input_schema"]),
                json.dumps(payload["quality_rules"]),
                json.dumps(payload["local_assets"]),
                json.dumps(payload["examples"]),
                payload["local_script_path"],
                payload["version"],
                json.dumps(payload["run_history"]),
                json.dumps(payload["feedback"]),
                json.dumps(payload["changelog"]),
                payload["notes"],
                "2026-06-30T00:00:00+00:00",
                "2026-06-30T00:00:00+00:00",
            ),
        )
        conn.commit()


def make_zip_dir(zip_dir: Path, payload: dict) -> None:
    zip_dir.mkdir(parents=True, exist_ok=True)
    package = zip_dir / f"{payload['name']}.capsule.zip"
    manifest = {"capsule": payload, "package_version": 2}
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))


class CapsuleV3ConvertTest(unittest.TestCase):
    def test_load_capsule_from_db(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "capsules.sqlite"
            make_db(db)
            payload = load_capsule_from_db(db, "sample")
        self.assertIsNotNone(payload)
        self.assertEqual(payload["name"], "sample")
        self.assertEqual(payload["version"], 7)
        self.assertEqual(payload["config"]["aspect_ratio"], "9:16")

    def test_convert_capsule_writes_stage_files_and_isolates_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "capsules.sqlite"
            make_db(db)
            payload = load_capsule_from_db(db, "sample")
            out = Path(tmp) / "capsules_v3"
            cap_dir = convert_capsule(payload, out, include_evidence=True, overwrite=False)

            self.assertEqual(cap_dir.name, "sample.capsule")
            self.assertTrue((cap_dir / "capsule.yaml").is_file())
            self.assertTrue((cap_dir / "CARD.md").is_file())
            self.assertTrue((cap_dir / "contracts" / "runtime.yaml").is_file())
            self.assertTrue((cap_dir / "recipes" / "structure.md").is_file())
            self.assertTrue((cap_dir / "recipes" / "visual.md").is_file())
            self.assertTrue((cap_dir / "recipes" / "repair_playbook.md").is_file())
            self.assertTrue((cap_dir / "recipes" / "legacy_notes.md").is_file())
            self.assertTrue((cap_dir / "quality" / "rules.yaml").is_file())
            self.assertTrue((cap_dir / "examples" / "illustrative.yaml").is_file())

            quality_text = (cap_dir / "quality" / "rules.yaml").read_text(encoding="utf-8")
            self.assertIn("expected_width: 1080", quality_text)
            self.assertIn("expected_height: 1440", quality_text)

            recipe_text = "\n".join(
                path.read_text(encoding="utf-8")
                for path in (cap_dir / "recipes").glob("*.md")
            )
            self.assertNotIn("/tmp/output/run", recipe_text)
            self.assertNotIn("past failure", recipe_text)

            evidence_dir = out / "_legacy_evidence" / "sample"
            self.assertTrue((evidence_dir / "run_history.json").is_file())
            self.assertTrue((evidence_dir / "feedback.json").is_file())

    def test_convert_capsule_omits_local_source_paths_from_capsule_yaml(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "capsules.sqlite"
            make_db(db)
            payload = load_capsule_from_db(db, "sample")
            payload["source"]["db_path"] = "/Users/june2/.codex/video-production/capsules.sqlite"
            out = Path(tmp) / "capsules_v3"

            cap_dir = convert_capsule(payload, out, overwrite=False)

            capsule_yaml = yaml.safe_load((cap_dir / "capsule.yaml").read_text(encoding="utf-8"))
            source = capsule_yaml["source"]
            serialized = yaml.safe_dump(source, sort_keys=False)
            self.assertEqual(source["type"], "sqlite")
            self.assertEqual(source["legacy_version"], 7)
            self.assertIn("converted_at", source)
            self.assertNotIn("db_path", source)
            self.assertNotIn("/Users", serialized)
            self.assertNotIn(".codex", serialized)
            self.assertNotIn("capsules.sqlite", serialized)

    def test_convert_refuses_existing_without_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "capsules.sqlite"
            make_db(db)
            payload = load_capsule_from_db(db, "sample")
            out = Path(tmp) / "capsules_v3"
            convert_capsule(payload, out, overwrite=False)
            with self.assertRaises(SystemExit):
                convert_capsule(payload, out, overwrite=False)

    def test_load_capsule_from_zip_dir_reads_manifest_capsule_object(self):
        with tempfile.TemporaryDirectory() as tmp:
            zip_dir = Path(tmp) / "capsules"
            make_zip_dir(zip_dir, make_payload(description="Loaded from zip manifest"))

            payload = load_capsule_from_zip_dir(zip_dir, "sample")

        self.assertIsNotNone(payload)
        self.assertEqual(payload["description"], "Loaded from zip manifest")
        self.assertEqual(payload["source"]["type"], "zip")
        self.assertTrue(payload["source"]["package"].endswith("sample.capsule.zip"))

    def test_convert_capsule_omits_package_source_path_from_capsule_yaml(self):
        with tempfile.TemporaryDirectory() as tmp:
            zip_dir = Path(tmp) / "capsules"
            make_zip_dir(zip_dir, make_payload())
            payload = load_capsule_from_zip_dir(zip_dir, "sample")
            out = Path(tmp) / "capsules_v3"

            cap_dir = convert_capsule(payload, out, overwrite=False)

            capsule_yaml = yaml.safe_load((cap_dir / "capsule.yaml").read_text(encoding="utf-8"))
            source = capsule_yaml["source"]
            serialized = yaml.safe_dump(source, sort_keys=False)
            self.assertEqual(source["type"], "zip")
            self.assertEqual(source["legacy_version"], 7)
            self.assertIn("converted_at", source)
            self.assertNotIn("package", source)
            self.assertNotIn(str(zip_dir), serialized)

    def test_convert_capsule_checks_free_space_before_creating_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = make_payload()
            out = Path(tmp) / "capsules_v3"

            with mock.patch("capsule_v3_convert._ensure_free_space") as ensure_free_space:
                convert_capsule(payload, out, overwrite=False)

        ensure_free_space.assert_called_once_with(out)

    def test_convert_capsule_rejects_unsafe_names_before_writing_output(self):
        unsafe_names = ["", ".", "..", "../escape", "nested/name", "name.with.dot"]

        for unsafe_name in unsafe_names:
            with self.subTest(name=unsafe_name or "<empty>"):
                with tempfile.TemporaryDirectory() as tmp:
                    payload = make_payload()
                    payload["name"] = unsafe_name
                    out = Path(tmp) / "capsules_v3"

                    with self.assertRaises(SystemExit):
                        convert_capsule(payload, out, overwrite=False)

                    self.assertFalse(out.exists())
                    self.assertFalse((Path(tmp) / "escape.capsule").exists())

    def test_convert_capsule_checks_free_space_before_overwrite_deletes_existing_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = make_payload()
            out = Path(tmp) / "capsules_v3"
            cap_dir = out / "sample.capsule"
            marker = cap_dir / "keep.txt"
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text("preserve me", encoding="utf-8")

            with mock.patch(
                "capsule_v3_convert._ensure_free_space",
                side_effect=SystemExit("disk too low"),
            ):
                with self.assertRaises(SystemExit):
                    convert_capsule(payload, out, overwrite=True)

            self.assertTrue(marker.is_file())
            self.assertEqual(marker.read_text(encoding="utf-8"), "preserve me")

    def test_convert_capsule_fails_before_writing_when_local_script_source_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = make_payload()
            payload["execution_mode"] = "local_script"
            payload["local_script_path"] = str(Path(tmp) / "missing" / "run_sample.py")
            out = Path(tmp) / "capsules_v3"

            with self.assertRaises(SystemExit):
                convert_capsule(payload, out, overwrite=False)

            self.assertFalse((out / "sample.capsule").exists())

    def test_convert_capsule_sanitizes_asset_index_and_skips_ephemeral_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            reusable = tmp_path / "refs" / "style.png"
            qa_report = tmp_path / "reports" / "qa_report.json"
            prompt_snapshot = tmp_path / "prompts" / "prompt_snapshot.txt"
            final_video = tmp_path / "final" / "deliverable.mp4"
            for path, text in (
                (reusable, "style"),
                (qa_report, "qa"),
                (prompt_snapshot, "prompt"),
                (final_video, "video"),
            ):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")

            payload = make_payload(
                local_assets=[
                    {
                        "key": "style_ref",
                        "role": "style_reference",
                        "reuse": "reference_only",
                        "path": str(reusable),
                        "description": "style only",
                    },
                    {
                        "key": "qa_report",
                        "role": "qa_report",
                        "reuse": "evidence_only",
                        "path": str(qa_report),
                    },
                    {
                        "key": "prompt_snapshot",
                        "role": "prompt_snapshot",
                        "reuse": "evidence_only",
                        "path": str(prompt_snapshot),
                    },
                    {
                        "key": "final_artifact",
                        "role": "final_artifact",
                        "reuse": "deliverable",
                        "path": str(final_video),
                    },
                ]
            )
            out = tmp_path / "capsules_v3"

            cap_dir = convert_capsule(payload, out, overwrite=False)

            assets = yaml.safe_load((cap_dir / "assets" / "index.yaml").read_text(encoding="utf-8"))["assets"]
            asset_by_key = {entry["key"]: entry for entry in assets}

            self.assertEqual(set(asset_by_key), {"style_ref"})
            self.assertEqual(asset_by_key["style_ref"]["path"], "style_ref__style.png")
            self.assertNotIn("source_path", asset_by_key["style_ref"])
            index_text = (cap_dir / "assets" / "index.yaml").read_text(encoding="utf-8")
            self.assertNotIn(str(reusable), index_text)
            self.assertNotIn(str(qa_report), index_text)
            self.assertTrue((cap_dir / "assets" / "style_ref__style.png").is_file())
            self.assertFalse((cap_dir / "assets" / "qa_report__qa_report.json").exists())
            self.assertFalse((cap_dir / "assets" / "prompt_snapshot__prompt_snapshot.txt").exists())
            self.assertFalse((cap_dir / "assets" / "final_artifact__deliverable.mp4").exists())

    def test_convert_capsule_keeps_complete_quality_rules_and_isolates_legacy_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = make_payload()
            out = Path(tmp) / "capsules_v3"

            cap_dir = convert_capsule(payload, out, include_evidence=False, overwrite=False)

            rules = yaml.safe_load((cap_dir / "quality" / "rules.yaml").read_text(encoding="utf-8"))["rules"]
            self.assertEqual(rules, payload["quality_rules"])
            self.assertFalse((out / "_legacy_evidence").exists())
            package_text = "\n".join(
                path.read_text(encoding="utf-8")
                for path in cap_dir.rglob("*")
                if path.is_file() and path.suffix in {".md", ".yaml", ".json"}
            )
            self.assertNotIn("past failure", package_text)
            self.assertNotIn("/tmp/output/run", package_text)
            self.assertNotIn("changed recipe", package_text)

    def test_convert_capsule_sanitizes_forbidden_recipe_evidence_tokens(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = make_payload(
                quality_rules=[{"id": "final_video_required", "type": "artifact_required"}],
            )
            payload["method"]["custom_unknown"] = {
                "manifest_rule": "发布包必须写入 artifact_manifest.json，category 为 publishing_package",
                "feedback_export": "不要把 feedback_json 混进正常 recipe。",
                "history_export": "run_history 只留在 legacy evidence。",
            }
            out = Path(tmp) / "capsules_v3"

            cap_dir = convert_capsule(payload, out, include_evidence=False, overwrite=False)

            recipe_text = (cap_dir / "recipes" / "legacy_notes.md").read_text(encoding="utf-8")
            self.assertNotIn("artifact_manifest.json", recipe_text)
            self.assertNotIn("feedback_json", recipe_text)
            self.assertNotIn("run_history", recipe_text)

    def test_convert_capsule_sanitizes_feedback_vocabulary_and_local_paths_in_recipe_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = make_payload(
                quality_rules=[{"id": "final_video_required", "type": "artifact_required"}],
            )
            payload["method"] = {
                "feedback_summary": "Turn user feedback into the next revision.",
                "coach_notes": {
                    "feedback_export": "Archive feedback_json beside artifact_manifest.json.",
                    "repair_path": "/Users/me/project/output/final.mp4",
                },
            }
            out = Path(tmp) / "capsules_v3"

            cap_dir = convert_capsule(payload, out, include_evidence=False, overwrite=False)

            recipe_text = (cap_dir / "recipes" / "legacy_notes.md").read_text(encoding="utf-8").lower()
            self.assertNotIn("feedback", recipe_text)
            self.assertNotIn("feedback_json", recipe_text)
            self.assertNotIn("artifact_manifest.json", recipe_text)
            self.assertNotIn("/users", recipe_text)
            self.assertNotIn("/output/", recipe_text)
            self.assertIn("revision", recipe_text)

    def test_convert_capsule_defaults_unknown_asset_role_to_source_media(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            raw_asset = tmp_path / "refs" / "clip.mov"
            raw_asset.parent.mkdir(parents=True, exist_ok=True)
            raw_asset.write_text("binary-ish", encoding="utf-8")
            payload = make_payload(
                local_assets=[
                    {
                        "key": "raw_clip",
                        "path": str(raw_asset),
                    }
                ]
            )
            out = tmp_path / "capsules_v3"

            cap_dir = convert_capsule(payload, out, overwrite=False)

            assets = yaml.safe_load((cap_dir / "assets" / "index.yaml").read_text(encoding="utf-8"))["assets"]
            self.assertEqual(assets[0]["role"], "source_media")

    def test_convert_capsule_sanitizes_unsafe_asset_keys_for_metadata_and_copy_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            assets_dir = tmp_path / "source-assets"
            assets_dir.mkdir(parents=True, exist_ok=True)
            parent_source = assets_dir / "parent.png"
            nested_source = assets_dir / "nested.png"
            absolute_source = assets_dir / "absolute.png"
            for path, text in (
                (parent_source, "parent"),
                (nested_source, "nested"),
                (absolute_source, "absolute"),
            ):
                path.write_text(text, encoding="utf-8")

            absolute_like_key = str(tmp_path / "outside" / "absolute-key")
            payload = make_payload(
                local_assets=[
                    {
                        "key": "../parent-ref",
                        "role": "style_reference",
                        "reuse": "reference_only",
                        "path": str(parent_source),
                    },
                    {
                        "key": "nested/ref",
                        "role": "style_reference",
                        "reuse": "reference_only",
                        "path": str(nested_source),
                    },
                    {
                        "key": absolute_like_key,
                        "role": "style_reference",
                        "reuse": "reference_only",
                        "path": str(absolute_source),
                    },
                ]
            )
            out = tmp_path / "capsules_v3"

            cap_dir = convert_capsule(payload, out, overwrite=False)

            assets = yaml.safe_load((cap_dir / "assets" / "index.yaml").read_text(encoding="utf-8"))["assets"]
            copied_root = (cap_dir / "assets").resolve()
            self.assertEqual(len(assets), 3)

            for entry in assets:
                self.assertNotIn("..", entry["key"])
                self.assertNotIn("/", entry["key"])
                self.assertNotIn("\\", entry["key"])
                self.assertNotIn("/", entry["path"])
                self.assertNotIn("\\", entry["path"])
                copied_path = (cap_dir / "assets" / entry["path"]).resolve()
                self.assertTrue(copied_path.is_relative_to(copied_root))
                self.assertTrue(copied_path.is_file())

            self.assertFalse((cap_dir / "parent-ref__parent.png").exists())
            self.assertFalse((cap_dir / "assets" / "nested" / "ref__nested.png").exists())
            self.assertFalse((Path(absolute_like_key).parent / f"{Path(absolute_like_key).name}__{absolute_source.name}").exists())

    def test_main_honors_names_and_creates_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db = tmp_path / "capsules.sqlite"
            make_db(db)
            out = tmp_path / "capsules_v3"
            stdout = StringIO()

            with mock.patch.object(sys, "argv", ["capsule_v3_convert.py", "--from-db", str(db), "--names", "sample", "--out", str(out)]):
                with redirect_stdout(stdout):
                    main()

            payload = json.loads(stdout.getvalue())
            self.assertEqual(len(payload["converted"]), 1)
            self.assertTrue((out / "sample.capsule" / "capsule.yaml").is_file())

    def test_main_prefers_db_source_over_zip_when_both_are_passed(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db = tmp_path / "capsules.sqlite"
            make_db_with_payload(db, make_payload(description="Loaded from db"))
            zip_dir = tmp_path / "capsules"
            make_zip_dir(zip_dir, make_payload(description="Loaded from zip"))
            out = tmp_path / "capsules_v3"

            with mock.patch.object(
                sys,
                "argv",
                [
                    "capsule_v3_convert.py",
                    "--from-db",
                    str(db),
                    "--from-zip-dir",
                    str(zip_dir),
                    "--names",
                    "sample",
                    "--out",
                    str(out),
                ],
            ):
                with redirect_stdout(StringIO()):
                    main()

            capsule = yaml.safe_load((out / "sample.capsule" / "capsule.yaml").read_text(encoding="utf-8"))
            self.assertEqual(capsule["summary"], "Loaded from db")
            self.assertEqual(capsule["source"]["type"], "sqlite")


if __name__ == "__main__":
    unittest.main()
