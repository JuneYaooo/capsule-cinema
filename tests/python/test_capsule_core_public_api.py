from __future__ import annotations

from pathlib import Path
import unittest

from src import capsules
from src.capsules.loader import load_definition


REPO_ROOT = Path(__file__).resolve().parents[2]


def _snapshot(package: Path) -> dict[str, bytes]:
    return {
        path.relative_to(package).as_posix(): path.read_bytes()
        for path in package.rglob("*")
        if path.is_file()
    }


class CapsuleCorePublicApiTests(unittest.TestCase):
    def test_new_core_contracts_are_public(self) -> None:
        expected = {
            "CapsuleReadOrder",
            "CapsuleInstance",
            "configure_instance",
            "snapshot_package",
            "load_stage_resources",
            "ProductionPlan",
            "build_production_plan",
            "production_plan_digest",
            "EffectReport",
            "build_effect_report",
        }

        self.assertLessEqual(expected, set(capsules.__all__))
        for name in expected:
            self.assertTrue(hasattr(capsules, name), name)

    def test_structurally_different_tracked_capsules_load_losslessly(self) -> None:
        cases = (
            ("guofeng_history", "preset"),
            ("life_sim", "local_script"),
        )
        for name, runner_kind in cases:
            with self.subTest(name=name):
                package = REPO_ROOT / "capsules" / f"{name}.capsule"
                before = _snapshot(package)

                definition = load_definition(package)

                self.assertEqual(definition.metadata.name, name)
                self.assertEqual(definition.implementation.runner.kind, runner_kind)
                self.assertEqual(
                    definition.read_order.routing,
                    ["index.md", "CARD.md", "contracts/input_schema.yaml"],
                )
                self.assertEqual(
                    definition.read_order.learning,
                    ["learning/promoted_lessons.yaml"],
                )
                self.assertEqual(before, _snapshot(package))


if __name__ == "__main__":
    unittest.main()
