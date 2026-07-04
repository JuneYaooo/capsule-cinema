import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load_capsule_runtime():
    runtime_path = SCRIPTS / "capsule_runtime.py"
    spec = importlib.util.spec_from_file_location("capsule_runtime", runtime_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CapsuleProductionContractSupportTest(unittest.TestCase):
    def test_created_capsule_scaffolds_and_loads_production_contract(self):
        from capsule_package_create import create_capsule_package
        from capsule_package_validate import validate_capsule_dir

        runtime = load_capsule_runtime()
        with tempfile.TemporaryDirectory() as tmp:
            cap_dir = create_capsule_package(
                output_root=Path(tmp) / "capsules",
                name="contract_capsule",
                display_name="Contract Capsule",
                summary="A reusable production-contract-aware capsule.",
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
            contract = yaml.safe_load((cap_dir / "contracts" / "production_contract.yaml").read_text(encoding="utf-8"))
            loaded = runtime.load_capsule_package("contract_capsule", package_roots=[Path(tmp) / "capsules"])
            prompt = runtime.build_capsule_prompt(loaded, "主题：一个真实产品测评")

        self.assertTrue(report["ok"], report)
        self.assertEqual("capsule.production_contract.v1", contract["schema_version"])
        self.assertEqual("L2_multimodal_probe", contract["minimum_evidence_for_release"])
        self.assertEqual("required", contract["required_outputs"]["voice"])
        self.assertEqual("required", contract["required_outputs"]["bgm"])
        self.assertTrue(contract["modality_contracts"]["copy"]["first_3_seconds_audit_required"])
        self.assertTrue(contract["modality_contracts"]["visual"]["source_identity_forbidden"])
        self.assertTrue(contract["modality_contracts"]["audio"]["silent_placeholder_forbidden"])
        self.assertEqual("capsule.production_contract.v1", loaded["production_contract"]["schema_version"])
        self.assertIn('"production_contract"', prompt)
        self.assertIn('"minimum_evidence_for_release": "L2_multimodal_probe"', prompt)
        self.assertIn("production_contract.required_outputs 必须交付:", prompt)
        self.assertIn("final_video", prompt)
        self.assertIn("publishing_package", prompt)
        self.assertIn("product_evidence_board", prompt)
        self.assertIn("metadata-only 只能产出内容结构草案", prompt)

    def test_created_product_capsule_gets_format_specific_contract_profile(self):
        from capsule_package_create import create_capsule_package
        from capsule_package_validate import validate_capsule_dir

        with tempfile.TemporaryDirectory() as tmp:
            cap_dir = create_capsule_package(
                output_root=Path(tmp) / "capsules",
                name="product_capsule",
                display_name="Product Capsule",
                summary="A reusable product-showcase capsule.",
                category="product_showcase",
                primary_workflow="product_showcase_video",
                capabilities=["product_closeup", "demo_sequence", "bgm"],
                tags=["product"],
                format_family="product_showcase",
                evidence_level="L2_multimodal_probe",
                production_capabilities=["product_closeup", "demo_sequence", "claim_evidence_mapping"],
                quality_gate_profile="product_showcase_release",
            )

            report = validate_capsule_dir(cap_dir, warnings_ok=True)
            contract = yaml.safe_load((cap_dir / "contracts" / "production_contract.yaml").read_text(encoding="utf-8"))

        self.assertTrue(report["ok"], report)
        self.assertEqual("product_showcase", contract["format_contract_profile"])
        self.assertEqual("product_showcase_release", contract["quality_gate_profile"])
        self.assertTrue(contract["evidence_policy"]["metadata_only_release_allowed"] is False)
        self.assertEqual("L1_metadata_plus_keyframes", contract["evidence_policy"]["visual_claims_require"])
        self.assertEqual("L2_multimodal_probe", contract["evidence_policy"]["motion_audio_claims_require"])
        self.assertEqual("required", contract["required_outputs"]["product_evidence_board"])
        self.assertTrue(contract["modality_contracts"]["visual"]["product_visible_first_three_seconds_required"])
        self.assertTrue(contract["modality_contracts"]["visual"]["claim_evidence_mapping_required"])
        self.assertTrue(contract["modality_contracts"]["motion"]["demo_sequence_required"])

    def test_created_knowledge_card_capsule_gets_svg_and_reveal_contract_profile(self):
        from capsule_package_create import create_capsule_package
        from capsule_package_validate import validate_capsule_dir

        with tempfile.TemporaryDirectory() as tmp:
            cap_dir = create_capsule_package(
                output_root=Path(tmp) / "capsules",
                name="card_capsule",
                display_name="Card Capsule",
                summary="A reusable knowledge-card capsule.",
                category="douyin_card_explainer",
                primary_workflow="knowledge_card_video",
                capabilities=["local_card_rendering", "semantic_vector_metaphor", "animated_card_reveal", "tts", "bgm"],
                tags=["card"],
                format_family="knowledge_card_explainer",
                evidence_level="L2_multimodal_probe",
                production_capabilities=["semantic_vector_metaphor", "animated_card_reveal"],
                quality_gate_profile="knowledge_card_release",
            )

            report = validate_capsule_dir(cap_dir, warnings_ok=True)
            contract = yaml.safe_load((cap_dir / "contracts" / "production_contract.yaml").read_text(encoding="utf-8"))

        self.assertTrue(report["ok"], report)
        self.assertEqual("knowledge_card_explainer", contract["format_contract_profile"])
        self.assertEqual("required", contract["required_outputs"]["middle_vector_metaphor"])
        self.assertEqual("required", contract["required_outputs"]["svg_assets"])
        self.assertTrue(contract["modality_contracts"]["visual"]["semantic_middle_illustration_required"])
        self.assertTrue(contract["modality_contracts"]["visual"]["svg_asset_export_required"])
        self.assertTrue(contract["modality_contracts"]["motion"]["animated_vector_reveal_required"])

    def test_validator_rejects_malformed_evidence_policy(self):
        from capsule_package_create import create_capsule_package
        from capsule_package_validate import validate_capsule_dir

        with tempfile.TemporaryDirectory() as tmp:
            cap_dir = create_capsule_package(
                output_root=Path(tmp) / "capsules",
                name="bad_evidence_policy_capsule",
                display_name="Bad Evidence Policy Capsule",
                summary="A capsule with an intentionally invalid evidence policy.",
                category="demo",
                primary_workflow="generic_ai_video",
                capabilities=["image_to_video"],
                tags=["demo"],
            )
            contract = yaml.safe_load((cap_dir / "contracts" / "production_contract.yaml").read_text(encoding="utf-8"))
            contract["evidence_policy"] = {
                "metadata_only_release_allowed": "no",
                "visual_claims_require": "maybe",
                "motion_audio_claims_require": "unknown",
                "l3_requires_sample_qa": "yes",
            }
            (cap_dir / "contracts" / "production_contract.yaml").write_text(
                yaml.safe_dump(contract, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )

            report = validate_capsule_dir(cap_dir, warnings_ok=True)

        self.assertFalse(report["ok"])
        self.assertTrue(any("metadata_only_release_allowed" in item for item in report["errors"]), report)
        self.assertTrue(any("visual_claims_require" in item for item in report["errors"]), report)
        self.assertTrue(any("motion_audio_claims_require" in item for item in report["errors"]), report)
        self.assertTrue(any("l3_requires_sample_qa" in item for item in report["errors"]), report)

    def test_validator_rejects_malformed_production_contract(self):
        from capsule_package_create import create_capsule_package
        from capsule_package_validate import validate_capsule_dir

        with tempfile.TemporaryDirectory() as tmp:
            cap_dir = create_capsule_package(
                output_root=Path(tmp) / "capsules",
                name="bad_contract_capsule",
                display_name="Bad Contract Capsule",
                summary="A capsule with an intentionally invalid contract.",
                category="demo",
                primary_workflow="generic_ai_video",
                capabilities=["image_to_video"],
                tags=["demo"],
            )
            (cap_dir / "contracts" / "production_contract.yaml").write_text(
                """
schema_version: capsule.production_contract.v1
minimum_evidence_for_release: maybe
required_outputs:
  final_video: mandatory
modality_contracts:
  copy:
    hook_candidates_min: 0
  audio:
    silent_placeholder_forbidden: "yes"
""".strip()
                + "\n",
                encoding="utf-8",
            )

            report = validate_capsule_dir(cap_dir, warnings_ok=True)

        self.assertFalse(report["ok"])
        self.assertTrue(any("minimum_evidence_for_release" in item for item in report["errors"]), report)
        self.assertTrue(any("required_outputs" in item for item in report["errors"]), report)
        self.assertTrue(any("hook_candidates_min" in item for item in report["errors"]), report)
        self.assertTrue(any("silent_placeholder_forbidden" in item for item in report["errors"]), report)


if __name__ == "__main__":
    unittest.main()
