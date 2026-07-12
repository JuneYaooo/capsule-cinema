from __future__ import annotations

import copy
import unittest

from src.capsules.production import build_production_plan, production_plan_digest


def valid_payload() -> dict:
    return {
        "capsule": "sample",
        "instance_digest": "a" * 64,
        "objectives": [{"id": "outcome", "statement": "Produce the promised artifact."}],
        "evidence_requirements": [
            {"id": "source", "description": "Use attributable source evidence."}
        ],
        "quality_requirements": [
            {"id": "contract", "description": "Meet the declared output contract.", "blocker": True}
        ],
        "steps": [
            {
                "id": "route",
                "stage": "routing",
                "objective_refs": ["outcome"],
                "evidence_refs": [],
                "quality_refs": [],
                "input_refs": ["request"],
                "output_refs": ["route-decision"],
                "rule_refs": ["CARD.md"],
            },
            {
                "id": "produce",
                "stage": "generation",
                "objective_refs": ["outcome"],
                "evidence_refs": ["source"],
                "quality_refs": ["contract"],
                "input_refs": ["route-decision"],
                "output_refs": ["artifact"],
                "rule_refs": ["contracts/runtime.yaml"],
            },
        ],
        "fallback_policy": "no_promise_change",
        "human_approval_points": ["final-effect"],
        "domain_payload": {"sample.extension": {"mode": "deterministic"}},
    }


class CapsuleProductionPlanTests(unittest.TestCase):
    def test_valid_plan_is_deterministic_and_does_not_mutate_input(self) -> None:
        payload = valid_payload()
        before = copy.deepcopy(payload)

        first = build_production_plan(payload)
        second = build_production_plan(copy.deepcopy(payload))

        self.assertTrue(first.ok, first.issues)
        self.assertEqual(payload, before)
        self.assertEqual(first.data["digest"], second.data["digest"])
        self.assertEqual(
            first.data["digest"], production_plan_digest(first.data["plan"])
        )
        self.assertEqual(first.data["plan"]["schema_version"], "capsule.production-plan/v1")

    def test_plan_rejects_duplicate_ids_unknown_refs_and_stage_regression(self) -> None:
        mutations = []
        duplicate = valid_payload()
        duplicate["objectives"].append(copy.deepcopy(duplicate["objectives"][0]))
        mutations.append(duplicate)
        unknown = valid_payload()
        unknown["steps"][1]["evidence_refs"] = ["missing"]
        mutations.append(unknown)
        regression = valid_payload()
        regression["steps"][0]["stage"] = "qa"
        regression["steps"][1]["stage"] = "planning"
        mutations.append(regression)

        for payload in mutations:
            with self.subTest(payload=payload):
                result = build_production_plan(payload)
                self.assertFalse(result.ok)
                self.assertEqual(result.status, "invalid")
                self.assertEqual(result.issues[0].code, "production_plan_invalid")
                self.assertNotIn("plan", result.data)

    def test_plan_rejects_non_json_domain_payload_and_blank_logical_refs(self) -> None:
        for domain_payload in (
            {"bad": object()},
            {"bad": float("nan")},
            {"bad": {1, 2}},
        ):
            with self.subTest(domain_payload=domain_payload):
                payload = valid_payload()
                payload["domain_payload"] = domain_payload
                result = build_production_plan(payload)
                self.assertFalse(result.ok)
                self.assertEqual(result.issues[0].code, "production_plan_invalid")

        payload = valid_payload()
        payload["steps"][0]["input_refs"] = [" "]
        result = build_production_plan(payload)
        self.assertFalse(result.ok)


if __name__ == "__main__":
    unittest.main()
