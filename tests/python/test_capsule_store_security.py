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
                        "local_assets": [{"key": "reference", "path": "assets/reference.txt"}],
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

    def test_migration_preserves_new_execution_mode_over_legacy_mode(self):
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
                        mode TEXT NOT NULL DEFAULT 'preset',
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
                        id, name, status, mode, execution_mode, local_script_path,
                        config_json, local_assets_json, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "capsule-id",
                        "script_capsule",
                        "active",
                        "preset",
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


if __name__ == "__main__":
    unittest.main()
