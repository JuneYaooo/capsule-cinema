import json
import tempfile
import unittest
from pathlib import Path

import yaml

from src.capsule_gate_runner import run_capsule_gates


class CapsuleGateRunnerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.capsule_dir = Path(self.tmp.name) / "demo.capsule"
        (self.capsule_dir / "quality").mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def write_gates(self, gates):
        (self.capsule_dir / "quality" / "release_gates.yaml").write_text(
            yaml.safe_dump({"gates": gates}, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def test_forbidden_profile_fields_blocks_non_empty_scene_field(self):
        self.write_gates(
            [
                {
                    "id": "bottom_title_not_visible_required",
                    "phase": "pre_render",
                    "severity": "blocker",
                    "checker": "forbidden_profile_fields",
                    "params": {"fields": ["scenes[].bottom_title"]},
                }
            ]
        )

        report = run_capsule_gates(
            self.capsule_dir,
            "pre_render",
            profile={"scenes": [{"bottom_title": "不该出现"}]},
        )

        self.assertFalse(report["ok"])
        self.assertEqual("blocked", report["status"])
        self.assertEqual(["bottom_title_not_visible_required"], report["blockers"])
        self.assertEqual("scenes[0].bottom_title", report["checks"][0]["detail"]["path"])

    def test_list_length_between_blocks_too_few_lines(self):
        self.write_gates(
            [
                {
                    "id": "bottom_card_4_to_5_lines",
                    "phase": "pre_render",
                    "severity": "blocker",
                    "checker": "list_length_between",
                    "params": {"path": "scenes[].bottom_lines", "min": 4, "max": 5},
                }
            ]
        )

        report = run_capsule_gates(
            self.capsule_dir,
            "pre_render",
            profile={"scenes": [{"bottom_lines": ["一", "二"]}]},
        )

        self.assertFalse(report["ok"])
        self.assertEqual(["bottom_card_4_to_5_lines"], report["blockers"])
        self.assertEqual(2, report["checks"][0]["detail"]["actual"])

    def test_manifest_item_flags_block_reconstructed_source_cards(self):
        self.write_gates(
            [
                {
                    "id": "reconstructed_cards_not_real_sources",
                    "phase": "pre_render",
                    "severity": "blocker",
                    "checker": "manifest_item_flags",
                    "params": {
                        "manifest_path": "source_asset_manifest",
                        "require": {"actual_source": True, "reconstructed_card": False},
                    },
                }
            ]
        )

        report = run_capsule_gates(
            self.capsule_dir,
            "pre_render",
            profile={
                "source_asset_manifest": [
                    {
                        "asset_id": "card_1",
                        "actual_source": False,
                        "reconstructed_card": True,
                    }
                ]
            },
        )

        self.assertFalse(report["ok"])
        self.assertEqual(["reconstructed_cards_not_real_sources"], report["blockers"])
        self.assertEqual("source_asset_manifest[0].actual_source", report["checks"][0]["detail"]["path"])

    def test_fallback_blocks_approved_release(self):
        self.write_gates(
            [
                {
                    "id": "fallback_generated_card_preview_only",
                    "phase": "release",
                    "severity": "blocker",
                    "checker": "fallback_blocks_approved_release",
                    "params": {
                        "fallback_markers": ["fallback_generated_card"],
                        "allowed_release_status": ["preview", "blocked"],
                    },
                }
            ]
        )

        report = run_capsule_gates(
            self.capsule_dir,
            "release",
            release={"status": "approved"},
            manifest={
                "artifacts": [
                    {
                        "category": "source_material",
                        "asset_type": "fallback_generated_card",
                    }
                ]
            },
        )

        self.assertFalse(report["ok"])
        self.assertEqual(["fallback_generated_card_preview_only"], report["blockers"])

    def test_cli_writes_gate_report(self):
        self.write_gates(
            [
                {
                    "id": "bottom_title_not_visible_required",
                    "phase": "pre_render",
                    "severity": "blocker",
                    "checker": "forbidden_profile_fields",
                    "params": {"fields": ["scenes[].bottom_title"]},
                }
            ]
        )
        payload = {"profile": {"scenes": [{"bottom_title": "不该出现"}]}}
        payload_path = self.capsule_dir / "payload.json"
        output_path = self.capsule_dir / "gate_report.json"
        payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        from scripts import capsule_gate_run

        code = capsule_gate_run.main(
            [
                "--capsule-dir",
                str(self.capsule_dir),
                "--phase",
                "pre_render",
                "--payload",
                str(payload_path),
                "--output",
                str(output_path),
            ]
        )

        report = json.loads(output_path.read_text(encoding="utf-8"))
        self.assertEqual(1, code)
        self.assertFalse(report["ok"])


if __name__ == "__main__":
    unittest.main()
