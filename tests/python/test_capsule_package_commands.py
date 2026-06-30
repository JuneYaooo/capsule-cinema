import sys
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


class CapsulePackageCommandsTest(unittest.TestCase):
    def test_neutral_converter_and_validator_modules_import(self):
        from capsule_package_convert import convert_capsule  # noqa: PLC0415
        from capsule_package_create import create_capsule_package  # noqa: PLC0415
        from capsule_package_update import update_capsule_package  # noqa: PLC0415
        from capsule_package_validate import validate_capsule_dir  # noqa: PLC0415

        self.assertTrue(callable(convert_capsule))
        self.assertTrue(callable(create_capsule_package))
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

            self.assertTrue(report["ok"], report)
            self.assertEqual(cap_dir.name, "demo_capsule.capsule")
            self.assertTrue((cap_dir / "index.md").is_file())
            self.assertTrue((cap_dir / "CARD.md").is_file())
            self.assertTrue((cap_dir / "recipes" / "structure.md").is_file())
            self.assertEqual(capsule["profile"], "video.okf.capsule.v1")
            self.assertEqual(capsule["primary_workflow"], "generic_ai_video")
            self.assertEqual(capsule["capabilities"], ["image_to_video", "tts", "bgm"])
            self.assertEqual(capsule["read_order"]["routing"], ["index.md", "CARD.md", "contracts/input_schema.yaml"])
            self.assertIn("type: Video Capsule Bundle Index", index_text)
            self.assertIn("type: Video Capsule Card", card_text)
            self.assertIn("type: Video Recipe", motion_text)

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
            self.assertTrue(report["ok"], report)
            self.assertEqual(capsule["capabilities"], ["image_to_video", "lip_sync"])
            self.assertEqual(capsule["when_to_use"], ["demo", "digital-human"])
            self.assertEqual(len(lessons), 1)
            self.assertEqual(lessons[0]["id"], "lip_sync_audio_is_timing_authority")
            self.assertEqual(lessons[0]["scope"], "audio")

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


if __name__ == "__main__":
    unittest.main()
