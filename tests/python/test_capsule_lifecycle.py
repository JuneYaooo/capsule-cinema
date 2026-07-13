from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from src.capsules.lifecycle import (
    LifecycleBundle,
    finalize_lifecycle,
    load_lifecycle_context,
    prepare_lifecycle,
    relocate_lifecycle,
)
from src.capsules.loader import load_definition
from src.capsules.result import Issue, failure, success


MANIFEST = """schema_version: capsule.package.v1
name: lifecycle_demo
display_name: Lifecycle Demo
version: 1
status: active
execution_mode: preset
category: demo
primary_workflow: demo
summary: Exercise lifecycle wiring.
capabilities: []
tags: []
when_to_use: []
when_not_to_use: []
read_order:
  routing: [CARD.md]
  planning: [recipes/structure.md]
  generation: [contracts/runtime.yaml]
  qa: [quality/rules.yaml]
  learning: [learning/promoted_lessons.yaml]
entrypoints:
  preset: general_video
"""


class CapsuleLifecycleTests(unittest.TestCase):
    def make_package(self, root: Path, *, fields: str | None = None) -> Path:
        package = root / "lifecycle_demo.capsule"
        for directory in ("contracts", "recipes", "quality", "learning"):
            (package / directory).mkdir(parents=True, exist_ok=True)
        (package / "capsule.yaml").write_text(MANIFEST, encoding="utf-8")
        (package / "contracts" / "input_schema.yaml").write_text(
            fields
            or """fields:
  prompt:
    type: string
    required: true
  mood:
    type: string
    default: calm
""",
            encoding="utf-8",
        )
        resources = {
            "CARD.md": "# Route\n",
            "recipes/structure.md": "# Plan\n",
            "contracts/runtime.yaml": "roles: {}\n",
            "quality/rules.yaml": "rules: []\n",
            "learning/promoted_lessons.yaml": "lessons: []\n",
        }
        for relative, content in resources.items():
            (package / relative).write_text(content, encoding="utf-8")
        return package

    def snapshot(self, package: Path) -> dict[str, bytes]:
        return {
            path.relative_to(package).as_posix(): path.read_bytes()
            for path in package.rglob("*")
            if path.is_file()
        }

    def test_prepare_maps_topic_and_enters_only_pre_run_stages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = self.make_package(root)
            definition = load_definition(package)
            output = root / "output"
            before = self.snapshot(package)

            result = prepare_lifecycle(
                definition,
                "A precise request",
                {"transport_only": "preserved elsewhere"},
                output,
                "run",
            )

            self.assertTrue(result.ok, result.issues)
            bundle = LifecycleBundle.model_validate(result.data["bundle"])
            self.assertEqual(bundle.entered_stages, ["routing", "planning", "generation"])
            self.assertNotIn("qa", bundle.stage_paths)
            self.assertNotIn("learning", bundle.stage_paths)
            instance = json.loads(Path(bundle.instance_path).read_text(encoding="utf-8"))
            self.assertEqual(instance["inputs"], {"mood": "calm", "prompt": "A precise request"})
            self.assertEqual(instance["resolved"]["inferred_values"], ["prompt"])
            plan_artifact = json.loads(Path(bundle.plan_path).read_text(encoding="utf-8"))
            self.assertEqual(plan_artifact["digest"], bundle.plan_digest)
            self.assertEqual(
                [step["stage"] for step in plan_artifact["plan"]["steps"]],
                ["routing", "planning", "generation"],
            )
            generation = json.loads(
                Path(bundle.stage_paths["generation"]).read_text(encoding="utf-8")
            )
            self.assertEqual(
                [item["relative_path"] for item in generation["resources"]],
                ["contracts/runtime.yaml"],
            )
            self.assertEqual(before, self.snapshot(package))

    def test_prepare_refuses_ambiguous_required_inputs_before_writing_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = self.make_package(
                root,
                fields="""fields:
  first:
    type: string
    required: true
  second:
    type: string
    required: true
""",
            )

            result = prepare_lifecycle(
                load_definition(package), "Do not guess", {}, root / "output", "run"
            )

            self.assertFalse(result.ok)
            self.assertEqual(result.status, "needs_input")
            self.assertEqual(
                [issue.subject for issue in result.issues], ["first", "second"]
            )
            self.assertFalse((root / "output" / "lifecycle").exists())

    def test_finalize_loads_qa_and_derives_ready_or_blocked(self) -> None:
        for return_code, expected in ((0, "ready"), (7, "blocked")):
            with self.subTest(return_code=return_code), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                definition = load_definition(self.make_package(root))
                prepared = prepare_lifecycle(
                    definition, "request", {}, root / "output", "run"
                )
                bundle = LifecycleBundle.model_validate(prepared.data["bundle"])
                runner_result = (
                    success("completed", {"return_code": 0})
                    if return_code == 0
                    else failure(
                        "run_failed",
                        [Issue(code="runner_failed", message="Runner failed.")],
                        {"return_code": return_code},
                    )
                )

                finalized = finalize_lifecycle(definition, bundle, runner_result)

                self.assertTrue(finalized.ok, finalized.issues)
                self.assertEqual(finalized.data["release_recommendation"], expected)
                report_path = Path(finalized.data["effect_report_path"])
                report = json.loads(report_path.read_text(encoding="utf-8"))
                self.assertEqual(report["release_recommendation"], expected)
                qa_path = Path(finalized.data["qa_context_path"])
                self.assertEqual(
                    json.loads(qa_path.read_text(encoding="utf-8"))["stage"], "qa"
                )
                self.assertFalse(
                    (root / "output" / "lifecycle" / "stages" / "learning.json").exists()
                )

    def test_finalize_blocks_explicit_qa_failure_even_when_process_exits_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            definition = load_definition(self.make_package(root))
            prepared = prepare_lifecycle(
                definition, "request", {}, root / "output", "run"
            )
            bundle = LifecycleBundle.model_validate(prepared.data["bundle"])
            runner_result = success(
                "completed",
                {
                    "return_code": 0,
                    "_runner_payload": {
                        "success": True,
                        "deliverable": False,
                        "run_status": "generated_but_failed_qa",
                        "qa_blockers": ["local_video_qa_failed"],
                        "local_video_qa_ok": False,
                        "edit_plan_validation_ok": True,
                        "release_checkpoint_status": "fail",
                    },
                },
            )

            finalized = finalize_lifecycle(definition, bundle, runner_result)

            self.assertTrue(finalized.ok, finalized.issues)
            self.assertEqual(finalized.data["release_recommendation"], "blocked")
            report = json.loads(
                Path(finalized.data["effect_report_path"]).read_text(encoding="utf-8")
            )
            failed_ids = {
                check["id"] for check in report["checks"] if not check["passed"]
            }
            self.assertIn("deliverable", failed_ids)
            self.assertIn("qa-blockers", failed_ids)
            self.assertIn("local-video-qa", failed_ids)
            self.assertIn("release-checkpoint", failed_ids)

    def test_finalize_preserves_pending_required_human_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            definition = load_definition(self.make_package(root))
            prepared = prepare_lifecycle(
                definition, "request", {}, root / "output", "run"
            )
            bundle = LifecycleBundle.model_validate(prepared.data["bundle"])

            finalized = finalize_lifecycle(
                definition,
                bundle,
                success(
                    "completed",
                    {
                        "return_code": 0,
                        "_runner_payload": {
                            "deliverable": True,
                            "human_review_required": True,
                            "human_review_status": "pending",
                        },
                    },
                ),
            )

            self.assertTrue(finalized.ok, finalized.issues)
            self.assertEqual(
                finalized.data["release_recommendation"], "review_required"
            )

    def test_artifact_write_failure_is_sanitized(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            definition = load_definition(self.make_package(root))
            output = root / "output"
            output.mkdir()
            (output / "lifecycle").write_text("not a directory\n", encoding="utf-8")

            result = prepare_lifecycle(definition, "request", {}, output, "plan")

            self.assertFalse(result.ok)
            self.assertEqual(result.issues[0].code, "lifecycle_artifact_write_failed")
            serialized = result.model_dump_json()
            self.assertNotIn(str(root), serialized)
            self.assertNotIn("not a directory", serialized)

    def test_runtime_context_loads_only_entered_pre_run_stages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            definition = load_definition(self.make_package(root))
            prepared = prepare_lifecycle(
                definition, "request", {}, root / "control", "run"
            )
            bundle = LifecycleBundle.model_validate(prepared.data["bundle"])

            context = load_lifecycle_context(bundle)

            self.assertEqual(
                list(context["stages"]), ["routing", "planning", "generation"]
            )
            self.assertNotIn("qa", context["stages"])
            self.assertNotIn("learning", context["stages"])
            self.assertEqual(
                context["instance"]["inputs"]["prompt"], "request"
            )

    def test_relocate_lifecycle_preserves_artifacts_and_updates_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            definition = load_definition(self.make_package(root))
            prepared = prepare_lifecycle(
                definition, "request", {}, root / "control", "run"
            )
            bundle = LifecycleBundle.model_validate(prepared.data["bundle"])

            relocated = relocate_lifecycle(bundle, root / "workspace")

            self.assertEqual(relocated.output_dir, str((root / "workspace").resolve()))
            self.assertTrue(Path(relocated.instance_path).is_file())
            self.assertTrue(Path(relocated.plan_path).is_file())
            self.assertEqual(
                load_lifecycle_context(relocated)["production_plan"]["digest"],
                bundle.plan_digest,
            )


if __name__ == "__main__":
    unittest.main()
