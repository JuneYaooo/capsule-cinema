from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.capsules.lifecycle import (
    LifecycleBundle,
    lifecycle_environment,
    prepare_lifecycle,
)
from src.capsules.loader import load_definition
from src.capsules.result import success

import run_video


ROOT = Path(__file__).resolve().parents[2]


class RunVideoCapsuleLifecycleTests(unittest.TestCase):
    def test_local_script_qa_block_is_not_mislabeled_as_generation_failure(self) -> None:
        dispatched = success(
            "completed",
            {
                "lifecycle": {
                    "release_recommendation": "blocked",
                    "effect_report": "lifecycle/capsule.effect-report.json",
                }
            },
        )
        with (
            patch("src.capsules.dispatch.build_dispatch_plan", return_value=object()),
            patch(
                "src.capsules.dispatch.execute_dispatch_plan",
                return_value=dispatched,
            ),
            patch("run_video.emit_progress_event"),
        ):
            result = run_video.execute_local_script_capsule(
                "life_sim",
                "request",
                {},
                storyboarding_only=False,
            )

        self.assertFalse(result["deliverable"])
        self.assertEqual(result["run_status"], "generated_but_failed_qa")
        self.assertEqual(result["capsule_release_recommendation"], "blocked")

    def test_direct_capsule_run_prepares_staged_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            definition, bundle, context = run_video.prepare_capsule_lifecycle_context(
                "art_motion",
                "A watercolor bird",
                {},
                storyboarding_only=False,
                environment={},
                control_output_dir=Path(tmp) / "control",
            )

            self.assertEqual(definition.metadata.name, "art_motion")
            self.assertIsNotNone(bundle)
            self.assertEqual(
                list(context["stages"]), ["routing", "planning", "generation"]
            )
            self.assertEqual(context["instance"]["inputs"]["prompt"], "A watercolor bird")
            planning_content = "\n".join(
                item["content"]
                for item in context["stages"]["planning"]["resources"]
            )
            self.assertIn("Structure Recipe", planning_content)

    def test_existing_dispatch_context_is_reused_without_duplicate_preparation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            definition = load_definition(ROOT / "capsules" / "art_motion.capsule")
            prepared = prepare_lifecycle(
                definition, "request", {}, Path(tmp) / "outer", "run"
            )
            outer_bundle = LifecycleBundle.model_validate(prepared.data["bundle"])

            with patch("run_video.prepare_lifecycle") as prepare_again:
                loaded_definition, bundle, context = (
                    run_video.prepare_capsule_lifecycle_context(
                        "art_motion",
                        "request",
                        {},
                        storyboarding_only=False,
                        environment=lifecycle_environment(outer_bundle),
                        control_output_dir=Path(tmp) / "unused",
                    )
                )

            self.assertEqual(loaded_definition.metadata.name, "art_motion")
            self.assertIsNone(bundle)
            self.assertEqual(
                context["production_plan"]["digest"], outer_bundle.plan_digest
            )
            prepare_again.assert_not_called()

    def test_direct_capsule_completion_materializes_blocked_real_qa_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            definition, bundle, _ = run_video.prepare_capsule_lifecycle_context(
                "art_motion",
                "request",
                {},
                storyboarding_only=False,
                environment={},
                control_output_dir=root / "control",
            )
            assert bundle is not None
            workspace = root / "workspace"
            workspace.mkdir()
            result = {
                "success": True,
                "deliverable": False,
                "run_status": "generated_but_failed_qa",
                "qa_blockers": ["local_video_qa_failed"],
                "local_video_qa_ok": False,
            }

            evidence = run_video.complete_capsule_lifecycle(
                definition,
                bundle,
                workspace,
                result,
                storyboarding_only=False,
            )

            self.assertEqual(evidence["release_recommendation"], "blocked")
            report_path = Path(evidence["effect_report_path"])
            self.assertTrue(report_path.is_file())
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["release_recommendation"], "blocked")


if __name__ == "__main__":
    unittest.main()
