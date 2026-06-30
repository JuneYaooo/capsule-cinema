import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from capsule_v3_convert import (  # noqa: E402
    convert_capsule,
    load_capsule_from_db,
)


def make_db(path: Path) -> None:
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
                "sample",
                "Sample Capsule",
                "active",
                "preset",
                "A sample recipe.",
                "test",
                json.dumps(["sample"]),
                json.dumps(
                    {
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
                    }
                ),
                json.dumps(
                    {
                        "structure": [
                            "opening tactile event",
                            "middle variation",
                            "closing payoff",
                        ],
                        "visual_rules": ["keep wool fiber texture visible"],
                        "known_pitfalls": ["avoid real cream texture"],
                        "custom_unknown": {"note": "preserve me"},
                    }
                ),
                json.dumps({"topic": {"type": "string", "required": True}}),
                json.dumps(
                    [
                        {
                            "id": "wechat_3x4_format",
                            "type": "video_quality",
                            "category": "final_video",
                            "expected_width": 1080,
                            "expected_height": 1440,
                        }
                    ]
                ),
                json.dumps(
                    [
                        {
                            "key": "style_ref",
                            "role": "style_reference",
                            "reuse": "reference_only",
                            "path": "",
                            "description": "style only",
                        }
                    ]
                ),
                json.dumps([{"kind": "opening_terms", "value": ["sample phrase"]}]),
                "",
                7,
                json.dumps([{"workspace_dir": "/tmp/output/run"}]),
                json.dumps([{"summary": "past failure", "fix": "general fix"}]),
                json.dumps([{"version": 7, "text": "changed recipe"}]),
                "",
                "2026-06-30T00:00:00+00:00",
                "2026-06-30T00:00:00+00:00",
            ),
        )
        conn.commit()


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

    def test_convert_refuses_existing_without_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "capsules.sqlite"
            make_db(db)
            payload = load_capsule_from_db(db, "sample")
            out = Path(tmp) / "capsules_v3"
            convert_capsule(payload, out, overwrite=False)
            with self.assertRaises(SystemExit):
                convert_capsule(payload, out, overwrite=False)


if __name__ == "__main__":
    unittest.main()
