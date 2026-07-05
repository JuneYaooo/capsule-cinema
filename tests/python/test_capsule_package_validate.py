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
schema_version: capsule.package.v1
profile: video.okf.capsule.v1
name: valid
display_name: Valid
version: 1
status: active
execution_mode: preset
category: test
summary: Valid capsule.
primary_workflow: generic_ai_video
capabilities:
  - image_to_video
  - tts
tags:
  - test
  - generic-ai-video
when_to_use: []
when_not_to_use: []
read_order:
  routing: [index.md, CARD.md, contracts/input_schema.yaml]
  planning: [contracts/input_schema.yaml, recipes/structure.md]
  generation: [contracts/runtime.yaml, recipes/motion.md, assets/index.yaml]
  qa: [quality/rules.yaml, quality/release_gates.yaml]
  learning: [learning/promoted_lessons.yaml]
entrypoints:
  preset: general_video
""".strip()
        + "\n",
    )
    write(
        cap / "index.md",
        """
---
okf_version: "0.1"
type: Video Capsule Bundle Index
title: Valid
description: Valid capsule.
profile: video.okf.capsule.v1
---

# Entry

* [Capsule Card](CARD.md) - Routing summary and usage boundary.
""".strip()
        + "\n",
    )
    write(
        cap / "CARD.md",
        """
---
type: Video Capsule Card
title: Valid
description: Valid capsule.
stage: routing
tags: [test]
---

# Valid
""".strip()
        + "\n",
    )
    write(
        cap / "contracts" / "runtime.yaml",
        """
roles: {}
output_contract: {}
video_elements:
  fixed: {}
  defaults: {}
  user_overridable: {}
  forbidden: []
""".strip()
        + "\n",
    )
    write(cap / "contracts" / "input_schema.yaml", "fields: {}\n")
    write(cap / "examples" / "illustrative.yaml", "examples: []\n")
    write(
        cap / "recipes" / "structure.md",
        """
---
type: Video Recipe
title: Structure Recipe
description: Story structure, pacing, and scene architecture.
stage: planning
domain: structure
tags: [structure]
---

# Structure
""".strip()
        + "\n",
    )
    write(
        cap / "recipes" / "motion.md",
        """
---
type: Video Recipe
title: Motion Recipe
description: Camera motion, transitions, dynamic generation, and editing rhythm.
stage: generation
domain: motion
tags: [motion]
---

# Motion
""".strip()
        + "\n",
    )
    write(cap / "quality" / "rules.yaml", "rules:\n  - id: final_video_required\n    type: artifact_required\n")
    write(cap / "quality" / "release_gates.yaml", "gates:\n  - final_video_required\n")
    write(cap / "assets" / "index.yaml", "assets: []\n")
    write(cap / "learning" / "promoted_lessons.yaml", "lessons: []\n")
    return cap


class CapsulePackageValidateTest(unittest.TestCase):
    def test_active_package_requires_video_okf_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            cap = make_valid_capsule(Path(tmp))
            data = yaml.safe_load((cap / "capsule.yaml").read_text(encoding="utf-8"))
            data.pop("profile")
            write(cap / "capsule.yaml", yaml.safe_dump(data, allow_unicode=True, sort_keys=False))

            report = validate_capsule_dir(cap, warnings_ok=True)

        self.assertFalse(report["ok"])
        self.assertTrue(any("profile" in item for item in report["errors"]), report)

    def test_active_package_requires_routing_tags(self):
        with tempfile.TemporaryDirectory() as tmp:
            cap = make_valid_capsule(Path(tmp))
            data = yaml.safe_load((cap / "capsule.yaml").read_text(encoding="utf-8"))
            data.pop("tags")
            write(cap / "capsule.yaml", yaml.safe_dump(data, allow_unicode=True, sort_keys=False))

            report = validate_capsule_dir(cap, warnings_ok=True)

        self.assertFalse(report["ok"])
        self.assertTrue(any("tags" in item for item in report["errors"]), report)

    def test_active_package_accepts_format_family_evidence_and_gate_profile_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            cap = make_valid_capsule(Path(tmp))
            data = yaml.safe_load((cap / "capsule.yaml").read_text(encoding="utf-8"))
            data["format_family"] = "product_showcase"
            data["evidence_level"] = "L2_multimodal_probe"
            data["production_capabilities"] = ["product_closeup", "demo_sequence"]
            data["quality_gate_profile"] = "product_showcase_release"
            write(cap / "capsule.yaml", yaml.safe_dump(data, allow_unicode=True, sort_keys=False))

            report = validate_capsule_dir(cap, warnings_ok=True)

        self.assertTrue(report["ok"], report)

    def test_active_package_rejects_invalid_evidence_level_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            cap = make_valid_capsule(Path(tmp))
            data = yaml.safe_load((cap / "capsule.yaml").read_text(encoding="utf-8"))
            data["format_family"] = "product_showcase"
            data["evidence_level"] = "maybe"
            data["production_capabilities"] = ["product_closeup"]
            data["quality_gate_profile"] = "product_showcase_release"
            write(cap / "capsule.yaml", yaml.safe_dump(data, allow_unicode=True, sort_keys=False))

            report = validate_capsule_dir(cap, warnings_ok=True)

        self.assertFalse(report["ok"])
        self.assertTrue(any("evidence_level" in item for item in report["errors"]), report)

    def test_active_package_accepts_valid_production_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            cap = make_valid_capsule(Path(tmp))
            write(
                cap / "contracts" / "production_contract.yaml",
                """
schema_version: capsule.production_contract.v1
minimum_evidence_for_release: L2_multimodal_probe
required_outputs:
  final_video: required
  voice: optional
  bgm: required
  qa_report: required
modality_contracts:
  copy:
    hook_candidates_min: 12
    first_3_seconds_audit_required: true
  visual:
    contact_sheet_review_required: true
    source_identity_forbidden: true
  audio:
    bgm_required: true
    silent_placeholder_forbidden: true
""".strip()
                + "\n",
            )

            report = validate_capsule_dir(cap, warnings_ok=True)

        self.assertTrue(report["ok"], report)

    def test_active_package_rejects_invalid_production_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            cap = make_valid_capsule(Path(tmp))
            write(
                cap / "contracts" / "production_contract.yaml",
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
            )

            report = validate_capsule_dir(cap, warnings_ok=True)

        self.assertFalse(report["ok"])
        self.assertTrue(any("minimum_evidence_for_release" in item for item in report["errors"]), report)
        self.assertTrue(any("required_outputs" in item for item in report["errors"]), report)
        self.assertTrue(any("hook_candidates_min" in item for item in report["errors"]), report)
        self.assertTrue(any("silent_placeholder_forbidden" in item for item in report["errors"]), report)

    def test_active_package_accepts_structured_release_gate_with_known_checker(self):
        with tempfile.TemporaryDirectory() as tmp:
            cap = make_valid_capsule(Path(tmp))
            write(
                cap / "quality" / "release_gates.yaml",
                """
gates:
  - final_video_required
  - id: bottom_title_not_visible_required
    phase: pre_render
    severity: blocker
    checker: forbidden_profile_fields
    params:
      fields:
        - scenes[].bottom_title
""".strip()
                + "\n",
            )

            report = validate_capsule_dir(cap, warnings_ok=True)

        self.assertTrue(report["ok"], report)

    def test_active_package_rejects_structured_release_gate_with_unknown_checker(self):
        with tempfile.TemporaryDirectory() as tmp:
            cap = make_valid_capsule(Path(tmp))
            write(
                cap / "quality" / "release_gates.yaml",
                """
gates:
  - id: bottom_title_not_visible_required
    phase: pre_render
    severity: blocker
    checker: checker_that_does_not_exist
    params:
      fields:
        - scenes[].bottom_title
""".strip()
                + "\n",
            )

            report = validate_capsule_dir(cap, warnings_ok=True)

        self.assertFalse(report["ok"])
        self.assertTrue(any("unknown checker" in item for item in report["errors"]), report)

    def test_active_package_rejects_structured_release_gate_missing_phase(self):
        with tempfile.TemporaryDirectory() as tmp:
            cap = make_valid_capsule(Path(tmp))
            write(
                cap / "quality" / "release_gates.yaml",
                """
gates:
  - id: bottom_title_not_visible_required
    severity: blocker
    checker: forbidden_profile_fields
    params:
      fields:
        - scenes[].bottom_title
""".strip()
                + "\n",
            )

            report = validate_capsule_dir(cap, warnings_ok=True)

        self.assertFalse(report["ok"])
        self.assertTrue(any("missing phase" in item for item in report["errors"]), report)

    def test_active_package_accepts_valid_video_elements_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            cap = make_valid_capsule(Path(tmp))
            write(
                cap / "contracts" / "runtime.yaml",
                """
roles: {}
output_contract:
  subtitle: none
  bgm: external
video_elements:
  fixed:
    aspect_ratio: "16:9"
    body_subtitles: false
  defaults:
    target_duration: 30
    bgm_volume: 0.1
  user_overridable:
    visual_style_mode:
      - anime_storyboard_drama
      - soft_picture_book
  forbidden:
    - keyword_illustration_storyboard
    - mid_sentence_visual_cut
""".strip()
                + "\n",
            )

            report = validate_capsule_dir(cap, warnings_ok=True)

        self.assertTrue(report["ok"], report)

    def test_active_package_requires_video_elements_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            cap = make_valid_capsule(Path(tmp))
            write(cap / "contracts" / "runtime.yaml", "roles: {}\noutput_contract: {}\n")

            report = validate_capsule_dir(cap, warnings_ok=True)

        self.assertFalse(report["ok"])
        self.assertTrue(any("video_elements" in item and "required" in item for item in report["errors"]), report)

    def test_active_package_rejects_legacy_runtime_defaults_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            cap = make_valid_capsule(Path(tmp))
            write(
                cap / "contracts" / "runtime.yaml",
                """
roles: {}
output_contract: {}
video_elements:
  fixed: {}
  defaults:
    aspect_ratio: "16:9"
  user_overridable: {}
  forbidden: []
defaults:
  target_duration: 30
""".strip()
                + "\n",
            )

            report = validate_capsule_dir(cap, warnings_ok=True)

        self.assertFalse(report["ok"])
        self.assertTrue(any("defaults" in item and "not allowed" in item for item in report["errors"]), report)

    def test_active_package_rejects_legacy_defaults_even_when_video_elements_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            cap = make_valid_capsule(Path(tmp))
            write(
                cap / "contracts" / "runtime.yaml",
                """
roles: {}
output_contract: {}
defaults:
  aspect_ratio: "9:16"
video_elements:
  fixed:
    aspect_ratio: "16:9"
""".strip()
                + "\n",
            )

            report = validate_capsule_dir(cap, warnings_ok=True)

        self.assertFalse(report["ok"])
        self.assertTrue(any("defaults" in item and "not allowed" in item for item in report["errors"]), report)

    def test_active_package_rejects_malformed_video_elements_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            cap = make_valid_capsule(Path(tmp))
            write(
                cap / "contracts" / "runtime.yaml",
                """
roles: {}
output_contract: {}
video_elements:
  fixed:
    aspect_ratio: "16:9"
  defaults:
    target_duration: 30
  user_overridable:
    aspect_ratio: "16:9"
  forbidden: keyword_illustration_storyboard
""".strip()
                + "\n",
            )

            report = validate_capsule_dir(cap, warnings_ok=True)

        self.assertFalse(report["ok"])
        self.assertTrue(any("video_elements.forbidden must be a list" in item for item in report["errors"]), report)
        self.assertTrue(
            any("video_elements.user_overridable.aspect_ratio must be a list" in item for item in report["errors"]),
            report,
        )

    def test_active_package_requires_root_okf_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            cap = make_valid_capsule(Path(tmp))
            (cap / "index.md").unlink()

            report = validate_capsule_dir(cap, warnings_ok=True)

        self.assertFalse(report["ok"])
        self.assertTrue(any("index.md" in item for item in report["errors"]), report)

    def test_markdown_concepts_require_frontmatter(self):
        with tempfile.TemporaryDirectory() as tmp:
            cap = make_valid_capsule(Path(tmp))
            write(cap / "CARD.md", "# Valid\n")

            report = validate_capsule_dir(cap, warnings_ok=True)

        self.assertFalse(report["ok"])
        self.assertTrue(any("frontmatter" in item for item in report["errors"]), report)

    def test_recipe_frontmatter_domain_must_match_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            cap = make_valid_capsule(Path(tmp))
            text = (cap / "recipes" / "structure.md").read_text(encoding="utf-8")
            write(cap / "recipes" / "structure.md", text.replace("domain: structure", "domain: visual"))

            report = validate_capsule_dir(cap, warnings_ok=True)

        self.assertFalse(report["ok"])
        self.assertTrue(any("domain" in item for item in report["errors"]), report)

    def test_migration_placeholder_text_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            cap = make_valid_capsule(Path(tmp))
            text = (cap / "recipes" / "motion.md").read_text(encoding="utf-8")
            write(cap / "recipes" / "motion.md", text + "\nNo capsule-specific rules were migrated for this section.\n")

            report = validate_capsule_dir(cap, warnings_ok=True)

        self.assertFalse(report["ok"])
        self.assertTrue(any("migration placeholder" in item for item in report["errors"]), report)

    def test_video_specific_asset_roles_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            cap = make_valid_capsule(Path(tmp))
            write(cap / "assets" / "reference" / "motion.mp4", "video")
            write(cap / "assets" / "reference" / "voice.wav", "voice")
            write(
                cap / "assets" / "index.yaml",
                """
assets:
  - key: source_performance
    role: performance_reference
    reuse: reference_only
    path: reference/motion.mp4
  - key: voice_reference
    role: voice_reference
    reuse: reference_only
    path: reference/voice.wav
""".strip()
                + "\n",
            )

            report = validate_capsule_dir(cap, warnings_ok=True)

        self.assertTrue(report["ok"], report)
        self.assertEqual(report["errors"], [])

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

    def test_active_package_rejects_missing_asset_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            cap = make_valid_capsule(Path(tmp))
            write(
                cap / "assets" / "index.yaml",
                """
assets:
  - key: style_frame
    role: style_reference
    reuse: reference_only
    path: references/style-frame.png
""".strip()
                + "\n",
            )

            report = validate_capsule_dir(cap, warnings_ok=True)

        self.assertFalse(report["ok"])
        self.assertTrue(any("asset file missing" in item for item in report["errors"]), report)


if __name__ == "__main__":
    unittest.main()
