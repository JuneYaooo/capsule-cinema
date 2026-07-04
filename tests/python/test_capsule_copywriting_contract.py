import sys
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "lib"
SCRIPTS = ROOT / "scripts"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


class CapsuleCopywritingContractTest(unittest.TestCase):
    def test_generic_contract_lives_in_core_library_not_scaffold_script(self):
        from src.capsule_copywriting_contract import default_copywriting_structure_contract

        contract = default_copywriting_structure_contract()

        self.assertTrue(contract["topic_to_angle_required"])
        self.assertIn("first_3_seconds", contract["required_outputs"])

        runtime_source = (ROOT / "scripts" / "capsule_runtime.py").read_text(encoding="utf-8")
        video_to_capsule_source = (ROOT / "lib" / "src" / "video_to_capsule.py").read_text(encoding="utf-8")
        self.assertNotIn("from capsule_package_create import default_copywriting_structure_contract", runtime_source)
        self.assertNotIn("from capsule_package_create import default_copywriting_structure_contract", video_to_capsule_source)

    def test_default_templates_are_architectural_not_topic_examples(self):
        from src.capsule_copywriting_contract import COPY_RECIPE_DEFAULT_BODY, STRUCTURE_RECIPE_DEFAULT_BODY

        combined = f"{COPY_RECIPE_DEFAULT_BODY}\n{STRUCTURE_RECIPE_DEFAULT_BODY}"
        forbidden_specific_content = [
            "specific account name",
            "specific reference link code",
            "specific episode title",
            "specific video hook",
        ]

        for token in forbidden_specific_content:
            with self.subTest(token=token):
                self.assertNotIn(token, combined)

    def test_create_package_scaffolds_generic_copywriting_contract(self):
        from capsule_package_create import create_capsule_package

        with tempfile.TemporaryDirectory() as tmp:
            cap_dir = create_capsule_package(
                output_root=Path(tmp) / "capsules",
                name="script_capsule",
                display_name="Script Capsule",
                summary="Reusable script-aware video capsule.",
                category="demo",
                primary_workflow="generic_ai_video",
                capabilities=["image_to_video", "tts", "bgm"],
                tags=["demo", "ai-video"],
            )

            runtime = yaml.safe_load((cap_dir / "contracts" / "runtime.yaml").read_text(encoding="utf-8"))
            copy_text = (cap_dir / "recipes" / "copy.md").read_text(encoding="utf-8")
            structure_text = (cap_dir / "recipes" / "structure.md").read_text(encoding="utf-8")

        contract = runtime["defaults"]["copywriting_structure_contract"]
        self.assertTrue(contract["topic_to_angle_required"])
        self.assertIn("first_3_seconds", contract["required_outputs"])
        self.assertIn("topic_to_angle_transform", copy_text)
        self.assertIn("传播角度候选", copy_text)
        self.assertIn("0-3s", structure_text)

    def test_runtime_prompt_injects_contract_for_legacy_capsules(self):
        import capsule_runtime

        capsule = {
            "name": "legacy_capsule",
            "display_name": "Legacy Capsule",
            "description": "Legacy package without explicit copywriting contract.",
            "category": "generic_ai_video",
            "config": {},
            "method": {},
            "quality_rules": [],
            "local_assets": [],
        }

        prompt = capsule_runtime.build_capsule_prompt(capsule, "主题：任意通用话题")

        self.assertIn('"copywriting_structure_contract"', prompt)
        self.assertIn('"first_3_seconds"', prompt)
        self.assertNotIn("specific account name", prompt)


if __name__ == "__main__":
    unittest.main()
