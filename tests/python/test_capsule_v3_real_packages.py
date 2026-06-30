import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))
sys.path.insert(0, str(ROOT / "scripts"))

from src.capsule_v3_loader import load_quality_rules, load_runtime_contract, load_stage_context  # noqa: E402
from capsule_v3_validate import validate_capsule_dir  # noqa: E402


CAPSULES = [
    "repo_showcase",
    "life_sim",
    "felt_asmr",
    "guofeng_history",
    "ecommerce_product_showcase",
    "art_motion",
]


class CapsuleV3RealPackagesTest(unittest.TestCase):
    def test_all_first_slice_capsules_exist_and_validate(self):
        for name in CAPSULES:
            with self.subTest(name=name):
                cap_dir = ROOT / "capsules_v3" / f"{name}.capsule"
                self.assertTrue((cap_dir / "capsule.yaml").is_file())
                report = validate_capsule_dir(cap_dir, warnings_ok=True)
                self.assertTrue(report["ok"], report)

    def test_loader_reads_each_stage(self):
        for name in CAPSULES:
            with self.subTest(name=name):
                cap_dir = ROOT / "capsules_v3" / f"{name}.capsule"
                routing = load_stage_context(cap_dir, "routing")
                planning = load_stage_context(cap_dir, "planning")
                generation = load_stage_context(cap_dir, "generation")
                qa = load_stage_context(cap_dir, "qa")
                learning = load_stage_context(cap_dir, "learning")
                self.assertIn("CARD.md", routing["files"])
                self.assertTrue(planning["files"])
                self.assertTrue(generation["files"])
                self.assertTrue(qa["files"])
                self.assertTrue(learning["files"])

    def test_runtime_contract_and_quality_rules_are_present(self):
        for name in CAPSULES:
            with self.subTest(name=name):
                cap_dir = ROOT / "capsules_v3" / f"{name}.capsule"
                runtime = load_runtime_contract(cap_dir)
                self.assertIn("roles", runtime)
                self.assertIn("output_contract", runtime)
                rules = load_quality_rules(cap_dir)
                self.assertGreater(len(rules), 0)
                self.assertTrue(all("id" in rule for rule in rules))

    def test_no_raw_evidence_in_recipe_files(self):
        for name in CAPSULES:
            with self.subTest(name=name):
                recipe_root = ROOT / "capsules_v3" / f"{name}.capsule" / "recipes"
                text = "\n".join(path.read_text(encoding="utf-8") for path in recipe_root.glob("*.md"))
                self.assertNotIn("run_history", text)
                self.assertNotIn("feedback_json", text)
                self.assertNotIn("artifact_manifest.json", text)

    def test_capsule_metadata_does_not_include_local_source_paths(self):
        forbidden = ["/Users", "/home", "/tmp", ".codex", "capsules.sqlite"]
        for name in CAPSULES:
            with self.subTest(name=name):
                capsule_yaml = (ROOT / "capsules_v3" / f"{name}.capsule" / "capsule.yaml").read_text(encoding="utf-8")
                for token in forbidden:
                    self.assertNotIn(token, capsule_yaml)


if __name__ == "__main__":
    unittest.main()
