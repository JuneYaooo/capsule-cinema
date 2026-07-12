from __future__ import annotations

import unittest

from pydantic import ValidationError

from src.capsules.effect import EffectReport, build_effect_report


class CapsuleEffectReportTests(unittest.TestCase):
    def build(self, **overrides):
        payload = {
            "capsule": "sample",
            "production_plan_digest": "b" * 64,
            "checks": [
                {
                    "id": "contract",
                    "passed": True,
                    "severity": "blocker",
                    "message": "Output contract is satisfied.",
                    "evidence_refs": ["report"],
                }
            ],
            "artifacts": [
                {"id": "report", "reference": "qa/report.json", "description": "QA evidence"}
            ],
            "human_review_required": False,
            "human_review_status": "not_required",
        }
        payload.update(overrides)
        return build_effect_report(payload)

    def test_failed_blocker_derives_blocked_release(self) -> None:
        result = self.build(
            checks=[
                {
                    "id": "contract",
                    "passed": False,
                    "severity": "blocker",
                    "message": "Output contract failed.",
                    "evidence_refs": ["report"],
                }
            ]
        )
        self.assertTrue(result.ok, result.issues)
        self.assertEqual(result.status, "complete")
        self.assertEqual(result.data["report"]["release_recommendation"], "blocked")

    def test_pending_human_review_derives_review_required(self) -> None:
        result = self.build(human_review_required=True, human_review_status="pending")
        self.assertTrue(result.ok)
        self.assertEqual(
            result.data["report"]["release_recommendation"], "review_required"
        )

    def test_clean_report_derives_ready_and_warnings_do_not_block(self) -> None:
        result = self.build(
            checks=[
                {
                    "id": "advisory",
                    "passed": False,
                    "severity": "warning",
                    "message": "Optional improvement remains.",
                    "evidence_refs": [],
                }
            ]
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.data["report"]["release_recommendation"], "ready")

    def test_report_rejects_unknown_evidence_duplicate_checks_and_bad_human_state(self) -> None:
        cases = (
            {"checks": [{"id": "x", "passed": True, "severity": "info", "message": "x", "evidence_refs": ["missing"]}]},
            {"checks": [
                {"id": "x", "passed": True, "severity": "info", "message": "x", "evidence_refs": []},
                {"id": "x", "passed": True, "severity": "info", "message": "x", "evidence_refs": []},
            ]},
            {"human_review_required": True, "human_review_status": "not_required"},
            {"human_review_required": False, "human_review_status": "pending"},
        )
        for overrides in cases:
            with self.subTest(overrides=overrides):
                result = self.build(**overrides)
                self.assertFalse(result.ok)
                self.assertEqual(result.status, "invalid")
                self.assertEqual(result.issues[0].code, "effect_report_invalid")

    def test_report_model_rejects_a_forged_release_recommendation(self) -> None:
        with self.assertRaises(ValidationError):
            EffectReport.model_validate(
                {
                    "capsule": "sample",
                    "production_plan_digest": "c" * 64,
                    "checks": [
                        {
                            "id": "failed",
                            "passed": False,
                            "severity": "blocker",
                            "message": "A blocker failed.",
                        }
                    ],
                    "human_review_required": False,
                    "human_review_status": "not_required",
                    "release_recommendation": "ready",
                }
            )


if __name__ == "__main__":
    unittest.main()
