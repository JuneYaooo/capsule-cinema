import sys
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from capsule_package_validate import validate_capsule_dir  # noqa: E402


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_valid_capsule(root: Path) -> Path:
    cap = root / "valid.capsule"
    write(
        cap / "capsule.yaml",
        """
schema_version: capsule.v3
name: valid
display_name: Valid
version: 1
status: active
execution_mode: preset
category: test
summary: Valid capsule.
when_to_use: []
when_not_to_use: []
read_order:
  routing: [CARD.md, contracts/runtime.yaml]
  planning: [recipes/structure.md]
  generation: [contracts/runtime.yaml, recipes/motion.md, assets/index.yaml]
  qa: [quality/rules.yaml]
  learning: [learning/promoted_lessons.yaml]
entrypoints:
  preset: general_video
""".strip()
        + "\n",
    )
    write(cap / "CARD.md", "# Valid\n")
    write(cap / "contracts" / "runtime.yaml", "roles: {}\noutput_contract: {}\ndefaults: {}\n")
    write(cap / "contracts" / "input_schema.yaml", "fields: {}\n")
    write(cap / "examples" / "illustrative.yaml", "examples: []\n")
    write(cap / "recipes" / "structure.md", "# Structure\n")
    write(cap / "recipes" / "motion.md", "# Motion\n")
    write(cap / "quality" / "rules.yaml", "rules:\n  - id: final_video_required\n    type: artifact_required\n")
    write(cap / "quality" / "release_gates.yaml", "gates:\n  - final_video_required\n")
    write(cap / "assets" / "index.yaml", "assets: []\n")
    write(cap / "learning" / "promoted_lessons.yaml", "lessons: []\n")
    return cap


class CapsulePackageValidateTest(unittest.TestCase):
    def test_active_package_rejects_migration_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            cap = make_valid_capsule(Path(tmp))
            data = yaml.safe_load((cap / "capsule.yaml").read_text(encoding="utf-8"))
            data["source"] = {
                "type": "sqlite",
                "legacy_version": 1,
                "converted_at": "2026-06-30T00:00:00Z",
            }
            write(cap / "capsule.yaml", yaml.safe_dump(data, allow_unicode=True, sort_keys=False))

            report = validate_capsule_dir(cap, warnings_ok=True)

        self.assertFalse(report["ok"])
        self.assertTrue(any("migration metadata" in item for item in report["errors"]), report)

    def test_active_package_rejects_unreferenced_recipe_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            cap = make_valid_capsule(Path(tmp))
            write(cap / "recipes" / "legacy_notes.md", "# Legacy Notes\n\nOld notes.\n")

            report = validate_capsule_dir(cap, warnings_ok=True)

        self.assertFalse(report["ok"])
        self.assertTrue(any("unreferenced recipe file" in item for item in report["errors"]), report)


if __name__ == "__main__":
    unittest.main()
