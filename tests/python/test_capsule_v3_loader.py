import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))

from src.capsule_v3_loader import (  # noqa: E402
    CapsuleV3Error,
    load_assets_index,
    load_capsule_card,
    load_quality_rules,
    load_runtime_contract,
    load_stage_context,
    resolve_capsule_dir,
)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class CapsuleV3LoaderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.root = root
        self.cap = root / "sample.capsule"
        write(
            self.cap / "capsule.yaml",
            """
schema_version: capsule.v3
name: sample
display_name: Sample
version: 3
status: active
execution_mode: preset
category: test
summary: Sample capsule.
when_to_use:
  - sample videos
when_not_to_use:
  - unrelated videos
read_order:
  routing:
    - CARD.md
    - contracts/runtime.yaml
  planning:
    - recipes/structure.md
    - recipes/visual.md
  generation:
    - contracts/runtime.yaml
    - recipes/motion.md
    - assets/index.yaml
  qa:
    - quality/rules.yaml
  learning:
    - learning/promoted_lessons.yaml
entrypoints:
  preset: general_video
""".strip()
            + "\n",
        )
        write(self.cap / "CARD.md", "# Sample\n\nUse for sample videos.\n")
        write(
            self.cap / "contracts" / "runtime.yaml",
            """
roles:
  video:
    modality: video
    requires:
      - image_to_video
    validated_with: SeedanceFastVideoGeneratorTool
output_contract:
  voice: unified_tts
  subtitle: overlay
  bgm: external
defaults:
  aspect_ratio: "9:16"
""".strip()
            + "\n",
        )
        write(self.cap / "contracts" / "input_schema.yaml", "fields:\n  topic:\n    type: string\n")
        write(self.cap / "recipes" / "structure.md", "# Structure\n\nThree beats.\n")
        write(self.cap / "recipes" / "visual.md", "# Visual\n\nWarm macro style.\n")
        write(self.cap / "recipes" / "motion.md", "# Motion\n\nClear subject motion.\n")
        write(
            self.cap / "quality" / "rules.yaml",
            """
rules:
  - id: final_video_required
    type: artifact_required
    severity: blocker
    category: final_video
""".strip()
            + "\n",
        )
        write(self.cap / "quality" / "release_gates.yaml", "gates:\n  - final_video_required\n")
        write(self.cap / "assets" / "index.yaml", "assets:\n  - key: intro\n    role: sfx\n    reuse: always\n    path: intro.wav\n")
        write(self.cap / "learning" / "promoted_lessons.yaml", "lessons: []\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_resolve_capsule_dir_by_name(self):
        path = resolve_capsule_dir("sample", search_roots=[self.root])
        self.assertEqual(path, self.cap.resolve())

    def test_load_capsule_card_reads_small_entry(self):
        card = load_capsule_card("sample", search_roots=[self.root])
        self.assertEqual(card["name"], "sample")
        self.assertEqual(card["version"], 3)
        self.assertIn("Use for sample", card["card_markdown"])
        self.assertNotIn("Three beats", card["card_markdown"])

    def test_load_stage_context_reads_only_requested_stage_files(self):
        context = load_stage_context("sample", "planning", search_roots=[self.root])
        self.assertEqual(context["stage"], "planning")
        self.assertIn("recipes/structure.md", context["files"])
        self.assertIn("recipes/visual.md", context["files"])
        self.assertNotIn("recipes/motion.md", context["files"])
        self.assertNotIn("quality/rules.yaml", context["files"])
        self.assertNotIn("assets/index.yaml", context["files"])

    def test_runtime_quality_and_assets_helpers(self):
        runtime = load_runtime_contract("sample", search_roots=[self.root])
        self.assertEqual(runtime["output_contract"]["voice"], "unified_tts")
        rules = load_quality_rules("sample", search_roots=[self.root])
        self.assertEqual(rules[0]["id"], "final_video_required")
        assets = load_assets_index("sample", search_roots=[self.root])
        self.assertEqual(assets[0]["key"], "intro")

    def test_unknown_stage_raises(self):
        with self.assertRaises(CapsuleV3Error):
            load_stage_context("sample", "unknown", search_roots=[self.root])

    def test_missing_read_order_file_raises(self):
        (self.cap / "recipes" / "visual.md").unlink()
        with self.assertRaises(CapsuleV3Error):
            load_stage_context("sample", "planning", search_roots=[self.root])

    def test_generation_stage_does_not_require_card_when_not_in_generation_read_order(self):
        (self.cap / "CARD.md").unlink()
        context = load_stage_context("sample", "generation", search_roots=[self.root])
        self.assertEqual(context["card_markdown"], "")
        self.assertIn("contracts/runtime.yaml", context["files"])
        self.assertIn("recipes/motion.md", context["files"])


if __name__ == "__main__":
    unittest.main()
