import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


class CapsulePackageCommandsTest(unittest.TestCase):
    def test_package_command_modules_import(self):
        from capsule_package_create import create_capsule_package  # noqa: PLC0415
        from capsule_package_install import install_capsule_package  # noqa: PLC0415
        from capsule_package_pack import pack_capsule_package  # noqa: PLC0415
        from capsule_package_update import update_capsule_package  # noqa: PLC0415
        from capsule_package_validate import validate_capsule_dir  # noqa: PLC0415

        self.assertTrue(callable(create_capsule_package))
        self.assertTrue(callable(install_capsule_package))
        self.assertTrue(callable(pack_capsule_package))
        self.assertTrue(callable(update_capsule_package))
        self.assertTrue(callable(validate_capsule_dir))

    def test_create_capsule_package_scaffolds_valid_video_okf_package(self):
        from capsule_package_create import create_capsule_package  # noqa: PLC0415
        from capsule_package_validate import validate_capsule_dir  # noqa: PLC0415

        with tempfile.TemporaryDirectory() as tmp:
            cap_dir = create_capsule_package(
                output_root=Path(tmp) / "capsules",
                name="demo_capsule",
                display_name="Demo Capsule",
                summary="A reusable demo video capsule.",
                category="demo",
                primary_workflow="generic_ai_video",
                capabilities=["image_to_video", "tts", "bgm"],
                tags=["demo", "ai-video"],
                overwrite=False,
            )

            report = validate_capsule_dir(cap_dir, warnings_ok=True)
            capsule = yaml.safe_load((cap_dir / "capsule.yaml").read_text(encoding="utf-8"))
            index_text = (cap_dir / "index.md").read_text(encoding="utf-8")
            card_text = (cap_dir / "CARD.md").read_text(encoding="utf-8")
            motion_text = (cap_dir / "recipes" / "motion.md").read_text(encoding="utf-8")
            content_scope = yaml.safe_load(
                (cap_dir / "contracts" / "content_scope.yaml").read_text(encoding="utf-8")
            )

            self.assertTrue(report["ok"], report)
            self.assertEqual(cap_dir.name, "demo_capsule.capsule")
            self.assertTrue((cap_dir / "index.md").is_file())
            self.assertTrue((cap_dir / "CARD.md").is_file())
            self.assertTrue((cap_dir / "recipes" / "structure.md").is_file())
            self.assertEqual(capsule["profile"], "video.okf.capsule.v1")
            self.assertEqual(capsule["primary_workflow"], "generic_ai_video")
            self.assertEqual(capsule["capabilities"], ["image_to_video", "tts", "bgm"])
            self.assertEqual(capsule["tags"], ["demo", "ai-video"])
            self.assertEqual(
                capsule["read_order"]["routing"],
                ["index.md", "CARD.md", "contracts/input_schema.yaml", "contracts/content_scope.yaml"],
            )
            self.assertIn("contracts/content_scope.yaml", capsule["read_order"]["planning"])
            self.assertEqual(content_scope["schema_version"], "capsule.content_scope.v1")
            self.assertTrue(content_scope["series_fixed"])
            self.assertTrue(content_scope["episode_variable"])
            self.assertIn("type: Video Capsule Bundle Index", index_text)
            self.assertIn("type: Video Capsule Card", card_text)
            self.assertIn("type: Video Recipe", motion_text)

    def test_create_capsule_package_scaffolds_copywriting_structure_contract(self):
        from capsule_package_create import create_capsule_package  # noqa: PLC0415
        from capsule_package_validate import validate_capsule_dir  # noqa: PLC0415

        with tempfile.TemporaryDirectory() as tmp:
            cap_dir = create_capsule_package(
                output_root=Path(tmp) / "capsules",
                name="script_capsule",
                display_name="Script Capsule",
                summary="A reusable script-aware video capsule.",
                category="demo",
                primary_workflow="generic_ai_video",
                capabilities=["image_to_video", "tts", "bgm"],
                tags=["demo", "ai-video"],
                overwrite=False,
            )

            report = validate_capsule_dir(cap_dir, warnings_ok=True)
            runtime = yaml.safe_load((cap_dir / "contracts" / "runtime.yaml").read_text(encoding="utf-8"))
            copy_text = (cap_dir / "recipes" / "copy.md").read_text(encoding="utf-8")
            structure_text = (cap_dir / "recipes" / "structure.md").read_text(encoding="utf-8")
            rules = yaml.safe_load((cap_dir / "quality" / "rules.yaml").read_text(encoding="utf-8"))["rules"]
            rule_ids = {rule["id"] for rule in rules}

            self.assertTrue(report["ok"], report)
            contract = runtime["copywriting_structure_contract"]
            self.assertTrue(contract["topic_to_angle_required"])
            self.assertTrue(contract["true_first_line_audit_required"])
            self.assertIn("first_3_seconds", contract["required_outputs"])
            self.assertIn("script_outline", contract["required_outputs"])
            self.assertIn("topic_to_angle_transform", copy_text)
            self.assertIn("传播角度候选", copy_text)
            self.assertIn("real_first_line_gate", copy_text)
            self.assertIn("0-3s", structure_text)
            self.assertIn("3-8s", structure_text)
            self.assertIn("copywriting_structure_contract_required", rule_ids)
            self.assertIn("first_three_seconds_hook_required", rule_ids)

    def test_create_capsule_package_accepts_explicit_content_scope(self):
        from capsule_package_create import create_capsule_package  # noqa: PLC0415

        with tempfile.TemporaryDirectory() as tmp:
            cap_dir = create_capsule_package(
                output_root=Path(tmp) / "capsules",
                name="scoped_capsule",
                display_name="Scoped Capsule",
                summary="A reusable scoped capsule.",
                category="demo",
                primary_workflow="generic_ai_video",
                capabilities=["image_to_video"],
                tags=["demo"],
                series_fixed=["recurring_character", "default_bgm"],
                episode_variable=["topic", "project_facts", "episode_copy"],
                forbidden_reusable_literals=["某期项目名"],
            )
            scope = yaml.safe_load(
                (cap_dir / "contracts" / "content_scope.yaml").read_text(encoding="utf-8")
            )

        self.assertEqual(scope["series_fixed"], ["recurring_character", "default_bgm"])
        self.assertEqual(scope["episode_variable"], ["topic", "project_facts", "episode_copy"])
        self.assertEqual(scope["forbidden_reusable_literals"], ["某期项目名"])

    def test_create_capsule_package_accepts_format_and_evidence_metadata(self):
        from capsule_package_create import create_capsule_package  # noqa: PLC0415
        from capsule_package_validate import validate_capsule_dir  # noqa: PLC0415

        with tempfile.TemporaryDirectory() as tmp:
            cap_dir = create_capsule_package(
                output_root=Path(tmp) / "capsules",
                name="format_capsule",
                display_name="Format Capsule",
                summary="A reusable format-aware video capsule.",
                category="product_showcase",
                primary_workflow="product_showcase_video",
                capabilities=["product_closeup", "tts", "bgm"],
                tags=["product"],
                format_family="product_showcase",
                evidence_level="L2_multimodal_probe",
                production_capabilities=["product_closeup", "demo_sequence"],
                quality_gate_profile="product_showcase_release",
            )

            report = validate_capsule_dir(cap_dir, warnings_ok=True)
            capsule = yaml.safe_load((cap_dir / "capsule.yaml").read_text(encoding="utf-8"))
            production_contract = yaml.safe_load(
                (cap_dir / "contracts" / "production_contract.yaml").read_text(encoding="utf-8")
            )

        self.assertTrue(report["ok"], report)
        self.assertEqual("product_showcase", capsule["format_family"])
        self.assertEqual("L2_multimodal_probe", capsule["evidence_level"])
        self.assertEqual(["product_closeup", "demo_sequence"], capsule["production_capabilities"])
        self.assertEqual("product_showcase_release", capsule["quality_gate_profile"])
        self.assertEqual("capsule.production_contract.v1", production_contract["schema_version"])
        self.assertEqual("L2_multimodal_probe", production_contract["minimum_evidence_for_release"])
        self.assertEqual("required", production_contract["required_outputs"]["final_video"])
        self.assertEqual("required", production_contract["required_outputs"]["voice"])
        self.assertEqual("required", production_contract["required_outputs"]["bgm"])
        self.assertTrue(production_contract["modality_contracts"]["copy"]["first_3_seconds_audit_required"])
        self.assertTrue(production_contract["modality_contracts"]["visual"]["source_identity_forbidden"])
        self.assertTrue(production_contract["modality_contracts"]["audio"]["silent_placeholder_forbidden"])

    def test_create_capsule_package_refuses_existing_without_overwrite(self):
        from capsule_package_create import create_capsule_package  # noqa: PLC0415

        with tempfile.TemporaryDirectory() as tmp:
            kwargs = {
                "output_root": Path(tmp) / "capsules",
                "name": "demo_capsule",
                "display_name": "Demo Capsule",
                "summary": "A reusable demo video capsule.",
                "category": "demo",
                "primary_workflow": "generic_ai_video",
                "capabilities": ["image_to_video"],
                "tags": ["demo"],
                "overwrite": False,
            }
            create_capsule_package(**kwargs)
            with self.assertRaises(SystemExit):
                create_capsule_package(**kwargs)

    def test_update_capsule_package_adds_metadata_and_promoted_lesson(self):
        from capsule_package_create import create_capsule_package  # noqa: PLC0415
        from capsule_package_update import update_capsule_package  # noqa: PLC0415
        from capsule_package_validate import validate_capsule_dir  # noqa: PLC0415

        with tempfile.TemporaryDirectory() as tmp:
            cap_dir = create_capsule_package(
                output_root=Path(tmp) / "capsules",
                name="demo_capsule",
                display_name="Demo Capsule",
                summary="A reusable demo video capsule.",
                category="demo",
                primary_workflow="generic_ai_video",
                capabilities=["image_to_video"],
                tags=["demo"],
                overwrite=False,
            )

            result = update_capsule_package(
                cap_dir,
                add_capabilities=["lip_sync", "image_to_video"],
                add_tags=["digital-human", "demo"],
                lesson={
                    "id": "lip_sync_audio_is_timing_authority",
                    "scope": "audio",
                    "rule": "Lip-sync generation must use final mixed speech audio as the timing authority.",
                    "applies_when": ["lip_sync", "digital_human"],
                    "promote_to": ["recipes/audio.md", "quality/rules.yaml"],
                },
            )
            report = validate_capsule_dir(cap_dir, warnings_ok=True)
            capsule = yaml.safe_load((cap_dir / "capsule.yaml").read_text(encoding="utf-8"))
            lessons = yaml.safe_load((cap_dir / "learning" / "promoted_lessons.yaml").read_text(encoding="utf-8"))["lessons"]

            self.assertTrue(result["ok"], result)
            self.assertEqual(result["conflicts"], [])
            self.assertTrue(report["ok"], report)
            self.assertEqual(capsule["capabilities"], ["image_to_video", "lip_sync"])
            self.assertEqual(capsule["tags"], ["demo", "digital-human"])
            self.assertEqual(capsule["when_to_use"], ["demo", "digital-human"])
            self.assertEqual(len(lessons), 1)
            self.assertEqual(lessons[0]["id"], "lip_sync_audio_is_timing_authority")
            self.assertEqual(lessons[0]["scope"], "audio")
            self.assertEqual(lessons[0]["content_scope"], "series")

    def test_validator_blocks_episode_literal_in_reusable_surface_but_not_examples(self):
        from capsule_package_create import create_capsule_package  # noqa: PLC0415
        from capsule_package_validate import validate_capsule_dir  # noqa: PLC0415

        with tempfile.TemporaryDirectory() as tmp:
            cap_dir = create_capsule_package(
                output_root=Path(tmp) / "capsules",
                name="scope_capsule",
                display_name="Scope Capsule",
                summary="A reusable capsule.",
                category="demo",
                primary_workflow="generic_ai_video",
                capabilities=["image_to_video"],
                tags=["demo"],
            )
            scope_path = cap_dir / "contracts" / "content_scope.yaml"
            scope = yaml.safe_load(scope_path.read_text(encoding="utf-8"))
            scope["forbidden_reusable_literals"] = ["某期专属项目"]
            scope_path.write_text(yaml.safe_dump(scope, allow_unicode=True, sort_keys=False), encoding="utf-8")

            example_path = cap_dir / "examples" / "illustrative.yaml"
            example_path.write_text("topic: 某期专属项目\n", encoding="utf-8")
            self.assertTrue(validate_capsule_dir(cap_dir, warnings_ok=True)["ok"])

            recipe_path = cap_dir / "recipes" / "visual.md"
            recipe_path.write_text(recipe_path.read_text(encoding="utf-8") + "\n- 某期专属项目\n", encoding="utf-8")
            report = validate_capsule_dir(cap_dir, warnings_ok=True)

        self.assertFalse(report["ok"])
        self.assertTrue(
            any("episode-specific literal found" in error and "recipes/visual.md" in error for error in report["errors"]),
            report,
        )

    def test_update_blocks_forbidden_episode_literal_even_with_resolution(self):
        from capsule_package_create import create_capsule_package  # noqa: PLC0415
        from capsule_package_update import CapsuleUpdateConflictError, update_capsule_package  # noqa: PLC0415

        with tempfile.TemporaryDirectory() as tmp:
            cap_dir = create_capsule_package(
                output_root=Path(tmp) / "capsules",
                name="scope_capsule",
                display_name="Scope Capsule",
                summary="A reusable capsule.",
                category="demo",
                primary_workflow="generic_ai_video",
                capabilities=["image_to_video"],
                tags=["demo"],
            )
            scope_path = cap_dir / "contracts" / "content_scope.yaml"
            scope = yaml.safe_load(scope_path.read_text(encoding="utf-8"))
            scope["forbidden_reusable_literals"] = ["某期专属项目"]
            scope_path.write_text(yaml.safe_dump(scope, allow_unicode=True, sort_keys=False), encoding="utf-8")
            before = (cap_dir / "capsule.yaml").read_text(encoding="utf-8")

            with self.assertRaises(CapsuleUpdateConflictError) as ctx:
                update_capsule_package(
                    cap_dir,
                    summary="专门介绍某期专属项目的胶囊",
                    conflict_resolution={
                        "resolved_conflicts": [
                            {"id": "capsule_update_conflict_1", "resolution": "keep it"}
                        ]
                    },
                )

            self.assertEqual(
                ctx.exception.conflicts[0]["kind"],
                "episode_specific_literal_in_reusable_update",
            )
            self.assertEqual(before, (cap_dir / "capsule.yaml").read_text(encoding="utf-8"))

    def test_update_capsule_package_blocks_conflict_before_writing(self):
        from capsule_package_create import create_capsule_package  # noqa: PLC0415
        from capsule_package_update import update_capsule_package  # noqa: PLC0415
        from capsule_package_validate import validate_capsule_dir  # noqa: PLC0415

        with tempfile.TemporaryDirectory() as tmp:
            cap_dir = create_capsule_package(
                output_root=Path(tmp) / "capsules",
                name="demo_capsule",
                display_name="Demo Capsule",
                summary="A reusable demo video capsule.",
                category="demo",
                primary_workflow="generic_ai_video",
                capabilities=["image_to_video"],
                tags=["demo"],
                overwrite=False,
            )
            before_capsule = (cap_dir / "capsule.yaml").read_text(encoding="utf-8")
            before_lessons = (cap_dir / "learning" / "promoted_lessons.yaml").read_text(encoding="utf-8")

            with self.assertRaises(SystemExit) as ctx:
                update_capsule_package(
                    cap_dir,
                    add_tags=["digital-human"],
                    lesson={
                        "id": "bad_promotion_target",
                        "scope": "audio",
                        "rule": "Use the final voice track as the timing authority.",
                        "applies_when": ["lip_sync"],
                        "promote_to": ["recipes/not_declared.md"],
                    },
                )

            after_capsule = (cap_dir / "capsule.yaml").read_text(encoding="utf-8")
            after_lessons = (cap_dir / "learning" / "promoted_lessons.yaml").read_text(encoding="utf-8")
            report = validate_capsule_dir(cap_dir, warnings_ok=True)

        self.assertIn("capsule update conflicts require user resolution", str(ctx.exception))
        self.assertIn("capsule_update_conflict_1", str(ctx.exception))
        self.assertEqual(after_capsule, before_capsule)
        self.assertEqual(after_lessons, before_lessons)
        self.assertTrue(report["ok"], report)

    def test_update_capsule_package_blocks_tag_conflicting_with_when_not_to_use(self):
        from capsule_package_create import create_capsule_package  # noqa: PLC0415
        from capsule_package_update import update_capsule_package  # noqa: PLC0415

        with tempfile.TemporaryDirectory() as tmp:
            cap_dir = create_capsule_package(
                output_root=Path(tmp) / "capsules",
                name="demo_capsule",
                display_name="Demo Capsule",
                summary="A reusable demo video capsule.",
                category="demo",
                primary_workflow="generic_ai_video",
                capabilities=["image_to_video"],
                tags=["demo"],
                overwrite=False,
            )
            capsule_path = cap_dir / "capsule.yaml"
            capsule = yaml.safe_load(capsule_path.read_text(encoding="utf-8"))
            capsule["when_not_to_use"] = ["Do not use for digital-human or lip-sync work."]
            capsule_path.write_text(yaml.safe_dump(capsule, allow_unicode=True, sort_keys=False), encoding="utf-8")
            before_capsule = capsule_path.read_text(encoding="utf-8")

            with self.assertRaises(SystemExit) as ctx:
                update_capsule_package(cap_dir, add_tags=["digital-human"])

            after_capsule = capsule_path.read_text(encoding="utf-8")

        self.assertIn("capsule update conflicts require user resolution", str(ctx.exception))
        self.assertIn("capsule_update_conflict_1", str(ctx.exception))
        self.assertEqual(after_capsule, before_capsule)

    def test_update_capsule_package_blocks_self_conflicting_lesson(self):
        from capsule_package_create import create_capsule_package  # noqa: PLC0415
        from capsule_package_update import update_capsule_package  # noqa: PLC0415

        with tempfile.TemporaryDirectory() as tmp:
            cap_dir = create_capsule_package(
                output_root=Path(tmp) / "capsules",
                name="demo_capsule",
                display_name="Demo Capsule",
                summary="A reusable demo video capsule.",
                category="demo",
                primary_workflow="generic_ai_video",
                capabilities=["image_to_video"],
                tags=["demo"],
                overwrite=False,
            )

            with self.assertRaises(SystemExit) as ctx:
                update_capsule_package(
                    cap_dir,
                    lesson={
                        "id": "contradictory_lesson",
                        "scope": "audio",
                        "rule": "Use lip sync timing when the speaker is visible.",
                        "applies_when": ["lip_sync"],
                        "promote_to": ["recipes/audio.md"],
                        "avoid": ["lip-sync"],
                    },
                )

        self.assertIn("capsule update conflicts require user resolution", str(ctx.exception))
        self.assertIn("capsule_update_conflict_1", str(ctx.exception))

    def test_update_capsule_package_allows_user_resolved_conflicts(self):
        from capsule_package_create import create_capsule_package  # noqa: PLC0415
        from capsule_package_update import update_capsule_package  # noqa: PLC0415

        with tempfile.TemporaryDirectory() as tmp:
            cap_dir = create_capsule_package(
                output_root=Path(tmp) / "capsules",
                name="demo_capsule",
                display_name="Demo Capsule",
                summary="A reusable demo video capsule.",
                category="demo",
                primary_workflow="generic_ai_video",
                capabilities=["image_to_video"],
                tags=["demo"],
                overwrite=False,
            )

            result = update_capsule_package(
                cap_dir,
                lesson={
                    "id": "bad_promotion_target",
                    "scope": "audio",
                    "rule": "Use the final voice track as the timing authority.",
                    "applies_when": ["lip_sync"],
                    "promote_to": ["recipes/not_declared.md"],
                },
                conflict_resolution={
                    "resolved_conflicts": [
                        {
                            "id": "capsule_update_conflict_1",
                            "resolution": "User confirmed the lesson should be kept for this capsule update.",
                        }
                    ]
                },
            )
            lessons = yaml.safe_load((cap_dir / "learning" / "promoted_lessons.yaml").read_text(encoding="utf-8"))["lessons"]

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["resolved_conflicts"], ["capsule_update_conflict_1"])
        self.assertEqual(lessons[0]["id"], "bad_promotion_target")

    def test_update_capsule_package_blocks_incomplete_conflict_resolution(self):
        from capsule_package_create import create_capsule_package  # noqa: PLC0415
        from capsule_package_update import update_capsule_package  # noqa: PLC0415

        with tempfile.TemporaryDirectory() as tmp:
            cap_dir = create_capsule_package(
                output_root=Path(tmp) / "capsules",
                name="demo_capsule",
                display_name="Demo Capsule",
                summary="A reusable demo video capsule.",
                category="demo",
                primary_workflow="generic_ai_video",
                capabilities=["image_to_video"],
                tags=["demo"],
                overwrite=False,
            )

            with self.assertRaises(SystemExit) as ctx:
                update_capsule_package(
                    cap_dir,
                    lesson={
                        "id": "bad_promotion_target",
                        "scope": "audio",
                        "rule": "Use the final voice track as the timing authority.",
                        "applies_when": ["lip_sync"],
                        "promote_to": ["recipes/not_declared.md"],
                    },
                    conflict_resolution={"resolved_conflicts": []},
                )

        self.assertIn("unresolved capsule update conflicts", str(ctx.exception))
        self.assertIn("capsule_update_conflict_1", str(ctx.exception))

    def test_update_capsule_package_rejects_unsafe_lesson_and_rolls_back(self):
        from capsule_package_create import create_capsule_package  # noqa: PLC0415
        from capsule_package_update import update_capsule_package  # noqa: PLC0415
        from capsule_package_validate import validate_capsule_dir  # noqa: PLC0415

        with tempfile.TemporaryDirectory() as tmp:
            cap_dir = create_capsule_package(
                output_root=Path(tmp) / "capsules",
                name="demo_capsule",
                display_name="Demo Capsule",
                summary="A reusable demo video capsule.",
                category="demo",
                primary_workflow="generic_ai_video",
                capabilities=["image_to_video"],
                tags=["demo"],
                overwrite=False,
            )
            before = (cap_dir / "learning" / "promoted_lessons.yaml").read_text(encoding="utf-8")

            with self.assertRaises(SystemExit):
                update_capsule_package(
                    cap_dir,
                    lesson={
                        "id": "bad_local_path",
                        "scope": "visual",
                        "rule": "Reuse the successful frame from /Users/me/output/final.mp4.",
                        "applies_when": ["image_to_video"],
                        "promote_to": ["recipes/visual.md"],
                    },
                )
            after = (cap_dir / "learning" / "promoted_lessons.yaml").read_text(encoding="utf-8")
            report = validate_capsule_dir(cap_dir, warnings_ok=True)

        self.assertEqual(after, before)
        self.assertTrue(report["ok"], report)

    def test_pack_capsule_package_writes_share_manifest_with_tags_and_checksums(self):
        from capsule_package_create import create_capsule_package  # noqa: PLC0415
        from capsule_package_pack import SHARE_PACKAGE_FORMAT, pack_capsule_package  # noqa: PLC0415

        with tempfile.TemporaryDirectory() as tmp:
            cap_dir = create_capsule_package(
                output_root=Path(tmp) / "capsules",
                name="demo_capsule",
                display_name="Demo Capsule",
                summary="A reusable demo video capsule.",
                category="demo",
                primary_workflow="generic_ai_video",
                capabilities=["image_to_video", "tts"],
                tags=["demo", "ai-video"],
                overwrite=False,
            )

            package = pack_capsule_package(cap_dir, output=Path(tmp) / "dist")

            with zipfile.ZipFile(package) as archive:
                manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
                package_names = set(archive.namelist())
                capsule_entry = f"{cap_dir.name}/capsule.yaml"
                capsule_data = archive.read(capsule_entry)

            capsule_file = next(item for item in manifest["files"] if item["path"] == capsule_entry)
            self.assertEqual(package.name, "demo_capsule.video-capsule.zip")
            self.assertEqual(manifest["package_format"], SHARE_PACKAGE_FORMAT)
            self.assertEqual(manifest["profile"], "video.okf.capsule.v1")
            self.assertEqual(manifest["name"], "demo_capsule")
            self.assertEqual(manifest["tags"], ["demo", "ai-video"])
            self.assertEqual(manifest["capabilities"], ["image_to_video", "tts"])
            self.assertIn(capsule_entry, package_names)
            self.assertEqual(capsule_file["sha256"], __import__("hashlib").sha256(capsule_data).hexdigest())

    def test_install_capsule_package_verifies_manifest_and_validates_package(self):
        from capsule_package_create import create_capsule_package  # noqa: PLC0415
        from capsule_package_install import install_capsule_package  # noqa: PLC0415
        from capsule_package_pack import pack_capsule_package  # noqa: PLC0415
        from capsule_package_validate import validate_capsule_dir  # noqa: PLC0415

        with tempfile.TemporaryDirectory() as tmp:
            cap_dir = create_capsule_package(
                output_root=Path(tmp) / "capsules",
                name="demo_capsule",
                display_name="Demo Capsule",
                summary="A reusable demo video capsule.",
                category="demo",
                primary_workflow="generic_ai_video",
                capabilities=["image_to_video"],
                tags=["demo", "replacement"],
                overwrite=False,
            )
            package = pack_capsule_package(cap_dir, output=Path(tmp) / "dist")

            installed = install_capsule_package(package, output_root=Path(tmp) / "installed")
            report = validate_capsule_dir(installed, warnings_ok=True)
            capsule = yaml.safe_load((installed / "capsule.yaml").read_text(encoding="utf-8"))

        self.assertEqual(installed.name, "demo_capsule.capsule")
        self.assertTrue(report["ok"], report)
        self.assertEqual(capsule["tags"], ["demo", "replacement"])

    def test_install_capsule_package_refuses_overwrite_without_force(self):
        from capsule_package_create import create_capsule_package  # noqa: PLC0415
        from capsule_package_install import install_capsule_package  # noqa: PLC0415
        from capsule_package_pack import pack_capsule_package  # noqa: PLC0415

        with tempfile.TemporaryDirectory() as tmp:
            cap_dir = create_capsule_package(
                output_root=Path(tmp) / "capsules",
                name="demo_capsule",
                display_name="Demo Capsule",
                summary="A reusable demo video capsule.",
                category="demo",
                primary_workflow="generic_ai_video",
                capabilities=["image_to_video"],
                tags=["demo"],
                overwrite=False,
            )
            package = pack_capsule_package(cap_dir, output=Path(tmp) / "dist")
            output_root = Path(tmp) / "installed"

            install_capsule_package(package, output_root=output_root)
            with self.assertRaises(SystemExit):
                install_capsule_package(package, output_root=output_root)
            installed = install_capsule_package(package, output_root=output_root, force=True)

        self.assertEqual(installed, (output_root / "demo_capsule.capsule").resolve())

    def test_install_capsule_package_rejects_checksum_mismatch(self):
        from capsule_package_create import create_capsule_package  # noqa: PLC0415
        from capsule_package_install import install_capsule_package  # noqa: PLC0415
        from capsule_package_pack import pack_capsule_package  # noqa: PLC0415

        with tempfile.TemporaryDirectory() as tmp:
            cap_dir = create_capsule_package(
                output_root=Path(tmp) / "capsules",
                name="demo_capsule",
                display_name="Demo Capsule",
                summary="A reusable demo video capsule.",
                category="demo",
                primary_workflow="generic_ai_video",
                capabilities=["image_to_video"],
                tags=["demo"],
                overwrite=False,
            )
            package = pack_capsule_package(cap_dir, output=Path(tmp) / "dist")
            tampered = Path(tmp) / "tampered.video-capsule.zip"
            with zipfile.ZipFile(package) as source, zipfile.ZipFile(tampered, "w", zipfile.ZIP_DEFLATED) as dest:
                for info in source.infolist():
                    data = source.read(info.filename)
                    if info.filename.endswith("/CARD.md"):
                        data += b"\nchanged"
                    dest.writestr(info, data)

            with self.assertRaises(SystemExit):
                install_capsule_package(tampered, output_root=Path(tmp) / "installed")

    def test_install_capsule_package_rejects_unsafe_member_path(self):
        from capsule_package_install import install_capsule_package  # noqa: PLC0415
        from capsule_package_pack import SHARE_PACKAGE_FORMAT  # noqa: PLC0415

        with tempfile.TemporaryDirectory() as tmp:
            package = Path(tmp) / "bad.video-capsule.zip"
            manifest = {
                "package_format": SHARE_PACKAGE_FORMAT,
                "profile": "video.okf.capsule.v1",
                "name": "bad",
                "capsule_dir": "bad.capsule",
                "files": [{"path": "../bad.capsule/CARD.md", "sha256": "bad", "size": 3}],
            }
            with zipfile.ZipFile(package, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("manifest.json", json.dumps(manifest))
                archive.writestr("../bad.capsule/CARD.md", b"bad")

            with self.assertRaises(SystemExit):
                install_capsule_package(package, output_root=Path(tmp) / "installed")

    def test_pack_capsule_package_rejects_blocked_runtime_files(self):
        from capsule_package_create import create_capsule_package  # noqa: PLC0415
        from capsule_package_pack import pack_capsule_package  # noqa: PLC0415

        with tempfile.TemporaryDirectory() as tmp:
            cap_dir = create_capsule_package(
                output_root=Path(tmp) / "capsules",
                name="demo_capsule",
                display_name="Demo Capsule",
                summary="A reusable demo video capsule.",
                category="demo",
                primary_workflow="generic_ai_video",
                capabilities=["image_to_video"],
                tags=["demo"],
                overwrite=False,
            )
            blocked = cap_dir / "output" / "run.txt"
            blocked.parent.mkdir()
            blocked.write_text("runtime output", encoding="utf-8")

            with self.assertRaises(SystemExit):
                pack_capsule_package(cap_dir, output=Path(tmp) / "dist")


if __name__ == "__main__":
    unittest.main()
