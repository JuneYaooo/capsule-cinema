import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CAPSULE_STORE_PATH = ROOT / "scripts" / "capsule_store.py"


def load_capsule_store():
    spec = importlib.util.spec_from_file_location("capsule_store", CAPSULE_STORE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CapsuleStoreSecurityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = load_capsule_store()

    def test_store_no_longer_exposes_engine_name_map(self):
        self.assertFalse(hasattr(self.store, "ENGINE_NAME_MAP"))

    def test_new_capsule_defaults_use_roles_and_output_contract(self):
        old_db = os.environ.get("VIDEO_CAPSULE_DB")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                db_path = Path(tmp) / "capsules.sqlite"
                os.environ["VIDEO_CAPSULE_DB"] = str(db_path)

                with contextlib.redirect_stdout(io.StringIO()):
                    self.store.upsert(
                        argparse.Namespace(
                            name="new_roles_capsule",
                            display_name="New Roles Capsule",
                            status="active",
                            execution_mode="preset",
                            description="new format",
                            category="general",
                            tags="test",
                            config_json="{}",
                            method_json="{}",
                            input_schema_json='{"topic":{"type":"string","required":true}}',
                            quality_rules_json=None,
                            local_assets_json="[]",
                            local_script_path="",
                            notes="",
                            bump_version=False,
                            changelog="create new format capsule",
                            change_source="test",
                        )
                    )

                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.store.show(argparse.Namespace(name="new_roles_capsule", json=True, contract=False))

                payload = json.loads(output.getvalue())
                config = payload["contract"]["config"]
                self.assertIn("roles", config)
                self.assertIn("output_contract", config)
                self.assertEqual(config["roles"]["video"]["validated_with"], "SeedanceFastVideoGeneratorTool")
                self.assertEqual(config["output_contract"]["voice"], "unified_tts")
                for legacy_key in (
                    "image_engine",
                    "video_engine",
                    "tts_provider",
                    "has_narration",
                    "add_subtitles",
                    "add_background_music",
                ):
                    self.assertNotIn(legacy_key, config)
                self.assertFalse(
                    any(rule.get("key") in {"image_engine", "video_engine"} for rule in payload["contract"]["quality_rules"])
                )
        finally:
            if old_db is None:
                os.environ.pop("VIDEO_CAPSULE_DB", None)
            else:
                os.environ["VIDEO_CAPSULE_DB"] = old_db

    def test_legacy_engine_config_migrates_to_capability_contract(self):
        old_db = os.environ.get("VIDEO_CAPSULE_DB")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                db_path = Path(tmp) / "capsules.sqlite"
                os.environ["VIDEO_CAPSULE_DB"] = str(db_path)

                legacy_config = {
                    "image_engine": "gpt-image-2",
                    "video_engine": "jimeng35pro",
                    "tts_provider": "minimax",
                    "tts_voice": "Chinese_deep_voiced_male_vv1",
                    "has_narration": True,
                    "add_subtitles": False,
                    "add_background_music": False,
                }
                with contextlib.redirect_stdout(io.StringIO()):
                    self.store.upsert(
                        argparse.Namespace(
                            name="legacy_runtime_capsule",
                            display_name="Legacy Runtime Capsule",
                            status="active",
                            execution_mode="preset",
                            description="legacy config",
                            category="general",
                            tags="test",
                            config_json=json.dumps(legacy_config),
                            method_json="{}",
                            input_schema_json='{"topic":{"type":"string","required":true}}',
                            quality_rules_json=None,
                            local_assets_json="[]",
                            local_script_path="",
                            notes="",
                            bump_version=False,
                            changelog="create legacy capsule",
                            change_source="test",
                        )
                    )

                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.store.show(argparse.Namespace(name="legacy_runtime_capsule", json=True, contract=False))

                config = json.loads(output.getvalue())["contract"]["config"]
                self.assertEqual(config["roles"]["image"]["validated_with"], "GptImage2Tool")
                self.assertEqual(config["roles"]["video"]["validated_with"], "Jimeng35ProVideoGeneratorTool")
                self.assertEqual(config["roles"]["voice"]["validated_with"], "minimax/Chinese_deep_voiced_male_vv1")
                self.assertEqual(config["output_contract"]["clip_audio"], "silent")
                self.assertEqual(config["output_contract"]["subtitle"], "none")
                self.assertEqual(config["output_contract"]["bgm"], "none")
                for legacy_key in legacy_config:
                    self.assertNotIn(legacy_key, config)
        finally:
            if old_db is None:
                os.environ.pop("VIDEO_CAPSULE_DB", None)
            else:
                os.environ["VIDEO_CAPSULE_DB"] = old_db

    def test_rejects_unsafe_package_paths(self):
        for value in ["", "../x", "/tmp/x", "assets/../../x", "assets\\x", "assets//x", "assets/"]:
            with self.subTest(value=value):
                with self.assertRaises(SystemExit):
                    self.store.validate_package_path(value)

    def test_import_rejects_malicious_package_path(self):
        old_db = os.environ.get("VIDEO_CAPSULE_DB")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                os.environ["VIDEO_CAPSULE_DB"] = str(tmp_path / "capsules.sqlite")
                package_path = tmp_path / "malicious.capsule.zip"
                manifest = {
                    "capsule_package_version": self.store.CAPSULE_PACKAGE_VERSION,
                    "schema_version": self.store.SCHEMA_VERSION,
                    "exported_at": self.store.now(),
                    "capsule": {"name": "malicious_capsule"},
                    "files": [{"package_path": "../escaped.txt", "sha256": "bad"}],
                    "missing_assets": [],
                }
                with zipfile.ZipFile(package_path, "w", zipfile.ZIP_DEFLATED) as archive:
                    archive.writestr("manifest.json", json.dumps(manifest))
                    archive.writestr("../escaped.txt", b"bad")

                with self.assertRaises(SystemExit):
                    with contextlib.redirect_stdout(io.StringIO()):
                        self.store.import_capsule(
                            argparse.Namespace(
                                package=str(package_path),
                                assets_dir=str(tmp_path / "restored_assets"),
                                name="",
                                force=False,
                            )
                        )

                self.assertFalse((tmp_path / "escaped.txt").exists())
        finally:
            if old_db is None:
                os.environ.pop("VIDEO_CAPSULE_DB", None)
            else:
                os.environ["VIDEO_CAPSULE_DB"] = old_db

    def test_accepts_safe_package_path_and_slugifies_asset_dir(self):
        self.assertEqual(self.store.validate_package_path("assets/reference.txt"), "assets/reference.txt")
        self.assertEqual(self.store.safe_asset_dir_name(" Capsule / Weird 名称 "), "Capsule_Weird")
        self.assertEqual(self.store.safe_asset_dir_name("../"), "capsule")

    def test_secret_scan_ignores_quality_rule_descriptions(self):
        payload = {
            "common_issue_checklist": {
                "secret_or_remote_url_leak": "报告或 manifest 里泄露密钥、token、cookie、签名 URL 或远程私有资源。"
            }
        }

        self.assertFalse(self.store.contains_secret(payload))
        fake_secret = "sk-" + "test_" + "abcdefghijklmnopqrstu"
        self.assertTrue(self.store.contains_secret({"api_key": fake_secret}))

    def test_legal_capsule_import_restores_asset_with_checksum(self):
        old_db = os.environ.get("VIDEO_CAPSULE_DB")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                os.environ["VIDEO_CAPSULE_DB"] = str(tmp_path / "capsules.sqlite")
                asset_data = b"capsule asset content\n"
                digest = hashlib.sha256(asset_data).hexdigest()
                package_path = tmp_path / "legal.capsule.zip"
                assets_dir = tmp_path / "restored_assets"
                manifest = {
                    "capsule_package_version": self.store.CAPSULE_PACKAGE_VERSION,
                    "schema_version": self.store.SCHEMA_VERSION,
                    "exported_at": self.store.now(),
                    "capsule": {
                        "name": "legal_capsule",
                        "display_name": "Legal Capsule",
                        "status": "draft",
                        "execution_mode": "preset",
                        "description": "test import",
                        "category": "test",
                        "tags": ["test"],
                        "config": {},
                        "method": {},
                        "input_schema": {"topic": {"type": "string", "required": True}},
                        "quality_rules": [{"id": "has_final", "type": "artifact_exists"}],
                        "local_assets": [{"key": "reference", "role": "template", "reuse": "reference_only", "path": "assets/reference.txt"}],
                        "local_script_path": "",
                        "version": 1,
                        "run_history": [],
                        "feedback": [],
                        "changelog": [],
                        "notes": "",
                    },
                    "files": [
                        {
                            "package_path": "assets/reference.txt",
                            "sha256": digest,
                            "size": len(asset_data),
                            "asset_key": "reference",
                        }
                    ],
                    "missing_assets": [],
                }
                with zipfile.ZipFile(package_path, "w", zipfile.ZIP_DEFLATED) as archive:
                    archive.writestr("manifest.json", json.dumps(manifest))
                    archive.writestr("assets/reference.txt", asset_data)

                with contextlib.redirect_stdout(io.StringIO()):
                    self.store.import_capsule(
                        argparse.Namespace(
                            package=str(package_path),
                            assets_dir=str(assets_dir),
                            name="",
                            force=False,
                        )
                    )

                restored = assets_dir / "assets" / "reference.txt"
                self.assertTrue(restored.exists())
                self.assertEqual(hashlib.sha256(restored.read_bytes()).hexdigest(), digest)
        finally:
            if old_db is None:
                os.environ.pop("VIDEO_CAPSULE_DB", None)
            else:
                os.environ["VIDEO_CAPSULE_DB"] = old_db

    def test_install_defaults_uses_custom_assets_dir(self):
        old_db = os.environ.get("VIDEO_CAPSULE_DB")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                os.environ["VIDEO_CAPSULE_DB"] = str(tmp_path / "capsules.sqlite")
                packages_dir = tmp_path / "packages"
                assets_dir = tmp_path / "installed_assets"
                packages_dir.mkdir()
                asset_data = b"default capsule asset\n"
                digest = hashlib.sha256(asset_data).hexdigest()
                manifest = {
                    "capsule_package_version": self.store.CAPSULE_PACKAGE_VERSION,
                    "schema_version": self.store.SCHEMA_VERSION,
                    "exported_at": self.store.now(),
                    "capsule": {
                        "name": "default_asset_capsule",
                        "display_name": "Default Asset Capsule",
                        "status": "draft",
                        "execution_mode": "preset",
                        "description": "test install-defaults",
                        "category": "test",
                        "tags": ["test"],
                        "config": {},
                        "method": {},
                        "input_schema": {"topic": {"type": "string", "required": True}},
                        "quality_rules": [{"id": "has_final", "type": "artifact_exists"}],
                        "local_assets": [{"key": "reference", "role": "template", "reuse": "reference_only", "path": "assets/reference.txt"}],
                        "local_script_path": "",
                        "version": 1,
                        "run_history": [],
                        "feedback": [],
                        "changelog": [],
                        "notes": "",
                    },
                    "files": [
                        {
                            "package_path": "assets/reference.txt",
                            "sha256": digest,
                            "size": len(asset_data),
                            "asset_key": "reference",
                        }
                    ],
                    "missing_assets": [],
                }
                with zipfile.ZipFile(packages_dir / "default_asset_capsule.capsule.zip", "w", zipfile.ZIP_DEFLATED) as archive:
                    archive.writestr("manifest.json", json.dumps(manifest))
                    archive.writestr("assets/reference.txt", asset_data)

                with contextlib.redirect_stdout(io.StringIO()):
                    self.store.install_defaults(
                        argparse.Namespace(
                            dir=str(packages_dir),
                            assets_dir=str(assets_dir),
                            force=False,
                        )
                    )

                restored = assets_dir / "default_asset_capsule" / "assets" / "reference.txt"
                self.assertTrue(restored.exists())
                self.assertEqual(restored.read_bytes(), asset_data)
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.store.show(argparse.Namespace(name="default_asset_capsule", json=True, contract=False))
                payload = json.loads(output.getvalue())
                self.assertEqual(payload["local_assets"][0]["path"], str(restored.resolve()))
        finally:
            if old_db is None:
                os.environ.pop("VIDEO_CAPSULE_DB", None)
            else:
                os.environ["VIDEO_CAPSULE_DB"] = old_db

    def test_list_counts_legacy_pass_run_status_as_success(self):
        old_db = os.environ.get("VIDEO_CAPSULE_DB")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                os.environ["VIDEO_CAPSULE_DB"] = str(Path(tmp) / "capsules.sqlite")
                with contextlib.redirect_stdout(io.StringIO()):
                    self.store.upsert(
                        argparse.Namespace(
                            name="legacy_pass_capsule",
                            display_name="Legacy Pass Capsule",
                            status="active",
                            execution_mode="preset",
                            description="has old pass status",
                            category="test",
                            tags="test",
                            config_json="{}",
                            method_json="{}",
                            input_schema_json='{"topic":{"type":"string","required":true}}',
                            quality_rules_json='[{"id":"final_video_required","type":"artifact_required"}]',
                            local_assets_json="[]",
                            local_script_path="",
                            notes="",
                            bump_version=False,
                            changelog="create capsule",
                            change_source="test",
                        )
                    )
                    self.store.record_run(
                        argparse.Namespace(
                            name="legacy_pass_capsule",
                            topic="old sample",
                            status="pass",
                            input_params_json="{}",
                            workspace_dir="/tmp/old",
                            final_video="/tmp/old/final.mp4",
                            manifest_path="/tmp/old/artifact_manifest.json",
                            compliance_report_json="{}",
                            metrics_json="{}",
                            notes="legacy pass",
                            error="",
                        )
                    )

                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.store.list_capsules(argparse.Namespace(status=None, execution_mode=None))

                self.assertIn("legacy_pass_capsule", output.getvalue())
                self.assertIn("pass=100%", output.getvalue())
        finally:
            if old_db is None:
                os.environ.pop("VIDEO_CAPSULE_DB", None)
            else:
                os.environ["VIDEO_CAPSULE_DB"] = old_db

    def test_record_run_dir_reads_default_qa_directory(self):
        old_db = os.environ.get("VIDEO_CAPSULE_DB")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                os.environ["VIDEO_CAPSULE_DB"] = str(tmp_path / "capsules.sqlite")
                run_dir = tmp_path / "run"
                final_video = run_dir / "final" / "video.mp4"
                qa_path = run_dir / "qa" / "local_video_qa.json"
                final_video.parent.mkdir(parents=True)
                qa_path.parent.mkdir(parents=True)
                final_video.write_bytes(b"fake mp4")
                (run_dir / "artifact_manifest.json").write_text(
                    json.dumps(
                        {
                            "artifacts": [
                                {
                                    "path": str(final_video),
                                    "category": "final_video",
                                    "title": "Final video",
                                }
                            ]
                        }
                    ),
                    encoding="utf-8",
                )
                qa_path.write_text(
                    json.dumps(
                        {
                            "ok": True,
                            "probe": {
                                "duration": 8.0,
                                "width": 720,
                                "height": 1280,
                            },
                        }
                    ),
                    encoding="utf-8",
                )

                with contextlib.redirect_stdout(io.StringIO()):
                    self.store.upsert(
                        argparse.Namespace(
                            name="qa_dir_capsule",
                            display_name="QA Dir Capsule",
                            status="active",
                            execution_mode="preset",
                            description="qa dir",
                            category="test",
                            tags="test",
                            config_json="{}",
                            method_json="{}",
                            input_schema_json='{"topic":{"type":"string","required":true}}',
                            quality_rules_json='[{"id":"final_video_required","type":"artifact_required"}]',
                            local_assets_json="[]",
                            local_script_path="",
                            notes="",
                            bump_version=False,
                            changelog="create capsule",
                            change_source="test",
                        )
                    )
                    self.store.record_run_dir(
                        argparse.Namespace(
                            name="qa_dir_capsule",
                            run_dir=str(run_dir),
                            topic="qa dir sample",
                            status="",
                            input_params_json="{}",
                            manifest_path="",
                            qa_report="",
                            final_video="",
                            notes="",
                            error="",
                        )
                    )

                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.store.show(argparse.Namespace(name="qa_dir_capsule", json=True, contract=False))
                payload = json.loads(output.getvalue())
                self.assertEqual(payload["run_history"][-1]["status"], "success")
                self.assertEqual(payload["run_history"][-1]["metrics"]["duration"], 8.0)
        finally:
            if old_db is None:
                os.environ.pop("VIDEO_CAPSULE_DB", None)
            else:
                os.environ["VIDEO_CAPSULE_DB"] = old_db

    def test_existing_rows_keep_current_execution_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "capsules.sqlite"
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                conn.execute(
                    """
                    CREATE TABLE capsules (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL UNIQUE,
                        status TEXT NOT NULL DEFAULT 'draft',
                        execution_mode TEXT NOT NULL DEFAULT 'preset',
                        local_script_path TEXT NOT NULL DEFAULT '',
                        config_json TEXT NOT NULL DEFAULT '{}',
                        local_assets_json TEXT NOT NULL DEFAULT '[]',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO capsules (
                        id, name, status, execution_mode, local_script_path,
                        config_json, local_assets_json, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "capsule-id",
                        "script_capsule",
                        "active",
                        "local_script",
                        "/tmp/render.py",
                        "{}",
                        "[]",
                        self.store.now(),
                        self.store.now(),
                    ),
                )
                conn.commit()

                self.store.init_db(conn)
                row = conn.execute("SELECT execution_mode FROM capsules WHERE name = ?", ("script_capsule",)).fetchone()

            self.assertEqual(row["execution_mode"], "local_script")

    def test_upsert_requires_current_text_id_schema(self):
        old_db = os.environ.get("VIDEO_CAPSULE_DB")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                db_path = Path(tmp) / "capsules.sqlite"
                os.environ["VIDEO_CAPSULE_DB"] = str(db_path)
                with sqlite3.connect(db_path) as conn:
                    old_config_field = "_".join(["capsule", "config", "json"])
                    conn.execute(
                        f"""
                        CREATE TABLE capsules (
                            id INTEGER PRIMARY KEY,
                            name TEXT NOT NULL UNIQUE,
                            status TEXT NOT NULL DEFAULT 'draft',
                            mode TEXT NOT NULL DEFAULT 'preset',
                            description TEXT NOT NULL DEFAULT '',
                            tags_json TEXT NOT NULL DEFAULT '[]',
                            {old_config_field} TEXT NOT NULL DEFAULT '{{}}',
                            skill_content TEXT NOT NULL DEFAULT '',
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL
                        )
                        """
                    )
                    conn.commit()

                with self.assertRaises(SystemExit):
                    with contextlib.redirect_stdout(io.StringIO()):
                        self.store.upsert(
                            argparse.Namespace(
                                name="new_capsule",
                                display_name="New Capsule",
                                status="active",
                                execution_mode="preset",
                                description="current schema only",
                                category="test",
                                tags="test",
                                config_json="{}",
                                method_json="{}",
                                input_schema_json='{"topic":{"type":"string","required":true}}',
                                quality_rules_json='[{"id":"final_video_required","type":"artifact_required"}]',
                                local_assets_json="[]",
                                local_script_path="",
                                notes="",
                                bump_version=False,
                                changelog="create in current db",
                                change_source="test",
                            )
                        )
        finally:
            if old_db is None:
                os.environ.pop("VIDEO_CAPSULE_DB", None)
            else:
                os.environ["VIDEO_CAPSULE_DB"] = old_db

    def test_show_requires_exact_capsule_name_without_alias(self):
        old_db = os.environ.get("VIDEO_CAPSULE_DB")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                db_path = Path(tmp) / "capsules.sqlite"
                os.environ["VIDEO_CAPSULE_DB"] = str(db_path)
                with contextlib.redirect_stdout(io.StringIO()):
                    self.store.upsert(
                        argparse.Namespace(
                            name="archive_life_demo",
                            display_name="Archive Life Sim",
                            status="active",
                            execution_mode="preset",
                            description="life sim",
                            category="douyin_story_voiceover",
                            tags="life-sim",
                            config_json="{}",
                            method_json='{"opening_card_rules":{"series_default":"每天一个模拟人生"}}',
                            input_schema_json='{"topic":{"type":"string","required":true}}',
                            quality_rules_json='[{"id":"final_video_required","type":"artifact_required"}]',
                            local_assets_json="[]",
                            local_script_path="",
                            notes="",
                            bump_version=False,
                            changelog="create life sim",
                            change_source="test",
                        )
                    )

                with self.assertRaises(SystemExit):
                    with contextlib.redirect_stdout(io.StringIO()):
                        self.store.show(argparse.Namespace(name="life_sim", json=True, contract=False))

                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.store.show(
                        argparse.Namespace(
                            name="archive_life_demo",
                            json=True,
                            contract=False,
                        )
                    )

                payload = json.loads(output.getvalue())
                self.assertEqual(payload["name"], "archive_life_demo")
                self.assertEqual(payload["contract"]["capsule_name"], "archive_life_demo")
                self.assertIn("opening_card_rules", payload["contract"]["method"])
        finally:
            if old_db is None:
                os.environ.pop("VIDEO_CAPSULE_DB", None)
            else:
                os.environ["VIDEO_CAPSULE_DB"] = old_db


if __name__ == "__main__":
    unittest.main()
