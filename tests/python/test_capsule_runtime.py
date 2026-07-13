import importlib.util
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
CAPSULE_RUNTIME_PATH = ROOT / "scripts" / "capsule_runtime.py"
LIB = ROOT / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))


def load_capsule_runtime():
    spec = importlib.util.spec_from_file_location("capsule_runtime", CAPSULE_RUNTIME_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CapsuleRuntimeAssetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = load_capsule_runtime()

    def test_runtime_defaults_use_packaged_default_bgm_asset(self):
        with tempfile.TemporaryDirectory() as tmp:
            bgm_path = Path(tmp) / "manten_diloty.mp3"
            bgm_path.write_bytes(b"fake mp3")
            capsule = {
                "config": {
                    "output_contract": {"bgm": "external"},
                    "video_elements": {
                        "fixed": {},
                        "defaults": {
                            "default_bgm_asset": bgm_path.name,
                            "bgm_volume": 0.42,
                        },
                        "user_overridable": {},
                        "forbidden": [],
                    },
                },
                "local_assets": [
                    {
                        "key": "manten_diloty_bgm",
                        "role": "bgm",
                        "reuse": "always",
                        "path": str(bgm_path),
                        "tags": ["default"],
                    }
                ],
            }

            defaults = self.runtime.capsule_runtime_defaults(capsule)

            self.assertEqual(defaults["background_music_path"], str(bgm_path))
            self.assertEqual(defaults["background_music_asset_key"], "manten_diloty_bgm")
            self.assertEqual(defaults["bgm_volume"], 0.42)

    def test_default_bgm_ignores_reference_only_asset(self):
        with tempfile.TemporaryDirectory() as tmp:
            bgm_path = Path(tmp) / "mood.mp3"
            bgm_path.write_bytes(b"fake mp3")
            capsule = {
                "config": {
                    "output_contract": {"bgm": "external"},
                    "video_elements": {
                        "fixed": {},
                        "defaults": {},
                        "user_overridable": {},
                        "forbidden": [],
                    },
                },
                "local_assets": [
                    {
                        "key": "mood_bgm",
                        "role": "bgm",
                        "reuse": "reference_only",
                        "path": str(bgm_path),
                    }
                ],
            }

            defaults = self.runtime.capsule_runtime_defaults(capsule)

            self.assertNotIn("background_music_path", defaults)

    def test_capsule_prompt_splits_assets_by_reuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixed_path = Path(tmp) / "intro.wav"
            fixed_path.write_bytes(b"wav")
            ref_path = Path(tmp) / "style.png"
            ref_path.write_bytes(b"png")
            capsule = {
                "name": "asset_capsule",
                "display_name": "Asset Capsule",
                "category": "repo_showcase",
                "description": "test capsule",
                "config": {},
                "method": {},
                "quality_rules": [],
                "local_assets": [
                    {
                        "key": "intro_sfx",
                        "role": "sfx",
                        "reuse": "always",
                        "path": str(fixed_path),
                        "description": "Opening sound",
                    },
                    {
                        "key": "style_ref",
                        "role": "style_reference",
                        "reuse": "reference_only",
                        "path": str(ref_path),
                        "description": "Style guide frame",
                    },
                ],
            }

            prompt = self.runtime.build_capsule_prompt(capsule, "make a short video")

            self.assertIn('"fixed_assets"', prompt)
            self.assertIn('"reference_assets"', prompt)
            self.assertIn('"intro_sfx"', prompt)
            self.assertIn('"style_ref"', prompt)
            # No blanket "prefer all local_assets" contradiction.
            self.assertNotIn("优先使用胶囊 local_assets", prompt)
            # Reference assets are explicitly regenerate-per-topic.
            self.assertIn("重新生成", prompt)

    def test_capsule_prompt_examples_are_non_authoritative(self):
        capsule = {
            "name": "ex_capsule",
            "display_name": "Ex",
            "category": "douyin_story_voiceover",
            "description": "test",
            "config": {},
            "method": {},
            "quality_rules": [],
            "local_assets": [],
            "examples": [
                {"kind": "opening_terms", "value": ["玄学自救", "床头改命"]},
            ],
        }

        prompt = self.runtime.build_capsule_prompt(capsule, "主题：出租屋")

        self.assertIn('"examples"', prompt)
        self.assertIn("玄学自救", prompt)
        self.assertIn("仅示意", prompt)

    def test_capsule_prompt_consumes_staged_lifecycle_context_without_eager_qa(self):
        capsule = {
            "name": "staged",
            "display_name": "Staged",
            "category": "demo",
            "description": "test",
            "config": {},
            "method": {"copy_rules": ["LEGACY_EAGER_METHOD"]},
            "quality_rules": [
                {"id": "eager", "rule": "LEGACY_EAGER_QA", "severity": "blocker"}
            ],
            "local_assets": [],
            "examples": [{"value": "LEGACY_EAGER_EXAMPLE"}],
        }
        lifecycle_context = {
            "instance": {"schema_version": "capsule.instance/v1", "inputs": {}},
            "production_plan": {"digest": "a" * 64, "plan": {}},
            "stages": {
                "routing": {"resources": []},
                "planning": {
                    "resources": [
                        {
                            "relative_path": "recipes/copy.md",
                            "digest": "b" * 64,
                            "content": "STAGED_PLANNING_RULE",
                        }
                    ]
                },
                "generation": {
                    "resources": [
                        {
                            "relative_path": "recipes/motion.md",
                            "digest": "c" * 64,
                            "content": "STAGED_GENERATION_RULE",
                        }
                    ]
                },
            },
        }

        prompt = self.runtime.build_capsule_prompt(
            capsule,
            "主题",
            lifecycle_context=lifecycle_context,
        )

        self.assertIn("STAGED_PLANNING_RULE", prompt)
        self.assertIn("STAGED_GENERATION_RULE", prompt)
        self.assertNotIn("LEGACY_EAGER_METHOD", prompt)
        self.assertNotIn("LEGACY_EAGER_QA", prompt)
        self.assertNotIn("LEGACY_EAGER_EXAMPLE", prompt)

    def test_capsule_prompt_never_includes_evidence(self):
        capsule = {
            "name": "ev_capsule",
            "display_name": "Ev",
            "category": "repo_showcase",
            "description": "test",
            "config": {},
            "method": {},
            "quality_rules": [],
            "local_assets": [],
            "run_history": [{"at": "2026-06-21", "final_video": "/output/run/x.mp4"}],
            "feedback": [{"summary": "leaked"}],
            "changelog": [{"text": "leaked"}],
        }

        prompt = self.runtime.build_capsule_prompt(capsule, "make a short video")

        self.assertNotIn("run_history", prompt)
        self.assertNotIn("leaked", prompt)
        self.assertNotIn("x.mp4", prompt)

    def _write_capsule_row(
        self,
        db_path: Path,
        name: str,
        display_name: str = "Test Capsule",
        *,
        config: dict | None = None,
        method: dict | None = None,
    ) -> None:
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS capsules (
                    name TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    execution_mode TEXT NOT NULL,
                    description TEXT NOT NULL,
                    category TEXT NOT NULL,
                    tags_json TEXT NOT NULL,
                    config_json TEXT NOT NULL,
                    method_json TEXT NOT NULL,
                    input_schema_json TEXT NOT NULL,
                    quality_rules_json TEXT NOT NULL,
                    local_assets_json TEXT NOT NULL,
                    local_script_path TEXT NOT NULL,
                    version INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                """
                INSERT INTO capsules (
                    name, display_name, status, execution_mode, description,
                    category, tags_json, config_json, method_json, input_schema_json,
                    quality_rules_json, local_assets_json, local_script_path, version
                )
                VALUES (?, ?, 'active', 'preset', 'test', 'test', '[]', ?, ?, '{}', '[]', '[]', '', 1)
                """,
                (
                    name,
                    display_name,
                    json.dumps(config or {}, ensure_ascii=False),
                    json.dumps(method or {}, ensure_ascii=False),
                ),
            )
            conn.commit()

    def _write_minimal_package(self, capsule_dir: Path, name: str, *, summary: str) -> None:
        def write(path: Path, text: str) -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

        write(
            capsule_dir / "capsule.yaml",
            f"""
schema_version: capsule.package.v1
name: {name}
display_name: Package {name}
version: 7
status: active
execution_mode: preset
category: package_test
summary: {summary}
when_to_use:
  - package
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
        write(capsule_dir / "CARD.md", f"# Package {name}\n")
        write(
            capsule_dir / "contracts" / "runtime.yaml",
            """
roles: {}
output_contract: {}
video_elements:
  fixed:
    aspect_ratio: '1:1'
  defaults: {}
  user_overridable: {}
  forbidden: []
""".strip()
            + "\n",
        )
        write(capsule_dir / "contracts" / "input_schema.yaml", "fields: {}\n")
        write(capsule_dir / "recipes" / "structure.md", "# Structure\n")
        write(capsule_dir / "recipes" / "motion.md", "# Motion\n")
        write(capsule_dir / "quality" / "rules.yaml", "rules:\n  - id: final_video_required\n    type: artifact_required\n")
        write(capsule_dir / "quality" / "release_gates.yaml", "gates:\n  - final_video_required\n")
        write(capsule_dir / "assets" / "index.yaml", "assets: []\n")
        write(capsule_dir / "examples" / "illustrative.yaml", "examples: []\n")
        write(capsule_dir / "learning" / "promoted_lessons.yaml", "lessons: []\n")

    def test_load_capsule_prefers_package_over_sqlite_when_package_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package_root = root / "capsules"
            self._write_minimal_package(package_root / "sample.capsule", "sample", summary="package wins")
            db_path = root / "capsules.sqlite"
            self._write_capsule_row(db_path, "sample", "SQLite Sample")

            capsule = self.runtime.load_capsule("sample", str(db_path), package_roots=[package_root])

        self.assertEqual(capsule["description"], "package wins")
        self.assertEqual(capsule["display_name"], "Package sample")
        self.assertEqual(capsule["source_format"], "package")
        self.assertEqual(capsule["config"]["video_elements"]["fixed"]["aspect_ratio"], "1:1")
        self.assertEqual(self.runtime.capsule_runtime_defaults(capsule)["aspect_ratio"], "1:1")

    def test_load_capsule_exposes_universal_format_and_evidence_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            package_root = Path(tmp) / "capsules"
            capsule_dir = package_root / "format_capsule.capsule"
            self._write_minimal_package(capsule_dir, "format_capsule", summary="format-aware capsule")
            capsule_yaml = capsule_dir / "capsule.yaml"
            data = yaml.safe_load(capsule_yaml.read_text(encoding="utf-8"))
            data["format_family"] = "product_showcase"
            data["evidence_level"] = "L2_multimodal_probe"
            data["production_capabilities"] = ["demonstration_evidence_sequence", "product_closeup"]
            data["quality_gate_profile"] = "product_showcase_release"
            capsule_yaml.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")

            capsule = self.runtime.load_capsule_package("format_capsule", package_roots=[package_root])

        self.assertEqual("product_showcase", capsule["format_family"])
        self.assertEqual("L2_multimodal_probe", capsule["evidence_level"])
        self.assertEqual(
            ["demonstration_evidence_sequence", "product_closeup"],
            capsule["production_capabilities"],
        )
        self.assertEqual("product_showcase_release", capsule["quality_gate_profile"])
        self.assertEqual("product_showcase", capsule["config"]["format_family"])

    def test_load_capsule_package_exposes_production_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            package_root = Path(tmp) / "capsules"
            capsule_dir = package_root / "contract_capsule.capsule"
            self._write_minimal_package(capsule_dir, "contract_capsule", summary="contract capsule")
            contract_path = capsule_dir / "contracts" / "production_contract.yaml"
            contract_path.write_text(
                """
schema_version: capsule.production_contract.v1
minimum_evidence_for_release: L2_multimodal_probe
required_outputs:
  final_video: required
  voice: required
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
    voice_required: true
    bgm_required: true
    silent_placeholder_forbidden: true
""".strip()
                + "\n",
                encoding="utf-8",
            )

            capsule = self.runtime.load_capsule_package("contract_capsule", package_roots=[package_root])
            prompt = self.runtime.build_capsule_prompt(capsule, "主题：一个产品测评")

        self.assertEqual("capsule.production_contract.v1", capsule["production_contract"]["schema_version"])
        self.assertEqual("L2_multimodal_probe", capsule["production_contract"]["minimum_evidence_for_release"])
        self.assertEqual("required", capsule["production_contract"]["required_outputs"]["voice"])
        self.assertIn('"production_contract"', prompt)
        self.assertIn('"minimum_evidence_for_release": "L2_multimodal_probe"', prompt)

    def test_package_load_injects_copywriting_structure_contract_into_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            package_root = Path(tmp) / "capsules"
            self._write_minimal_package(package_root / "sample.capsule", "sample", summary="copy contract")

            capsule = self.runtime.load_capsule_package("sample", package_roots=[package_root])
            prompt = self.runtime.build_capsule_prompt(capsule, "主题：自律")

        self.assertIn("copywriting_structure_contract", capsule["config"])
        self.assertTrue(capsule["config"]["copywriting_structure_contract"]["topic_to_angle_required"])
        self.assertIn('"copywriting_structure_contract"', prompt)
        self.assertIn('"first_3_seconds"', prompt)

    def test_load_capsule_package_keeps_video_element_defaults_nested(self):
        with tempfile.TemporaryDirectory() as tmp:
            package_root = Path(tmp) / "capsules"
            capsule_dir = package_root / "elements_capsule.capsule"
            self._write_minimal_package(capsule_dir, "elements_capsule", summary="video elements")
            (capsule_dir / "contracts" / "runtime.yaml").write_text(
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
    target_duration: 45
    bgm_volume: 0.15
    voice_volume: 1.2
  user_overridable:
    visual_style_mode:
      - anime_storyboard_drama
      - soft_picture_book
  forbidden:
    - keyword_illustration_storyboard
""".strip()
                + "\n",
                encoding="utf-8",
            )

            capsule = self.runtime.load_capsule_package("elements_capsule", package_roots=[package_root])
            defaults = self.runtime.capsule_runtime_defaults(capsule)

        self.assertNotIn("aspect_ratio", capsule["config"])
        self.assertNotIn("target_duration", capsule["config"])
        self.assertNotIn("bgm_volume", capsule["config"])
        self.assertNotIn("visual_style_mode", capsule["config"])
        self.assertEqual(capsule["config"]["video_elements"]["fixed"]["aspect_ratio"], "16:9")
        self.assertEqual(capsule["config"]["video_elements"]["fixed"]["body_subtitles"], False)
        self.assertEqual(capsule["config"]["video_elements"]["defaults"]["target_duration"], 45)
        self.assertEqual(capsule["config"]["video_elements"]["defaults"]["bgm_volume"], 0.15)
        self.assertEqual(
            capsule["config"]["video_elements"]["user_overridable"]["visual_style_mode"],
            ["anime_storyboard_drama", "soft_picture_book"],
        )
        self.assertEqual(defaults["aspect_ratio"], "16:9")
        self.assertEqual(defaults["target_duration"], 45)
        self.assertEqual(defaults["bgm_volume"], 0.15)
        self.assertEqual(defaults["voice_volume"], 1.2)
        self.assertFalse(defaults["add_subtitles"])
        self.assertTrue(defaults["add_background_music"])

    def test_load_capsule_package_keeps_video_elements_nested_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            package_root = Path(tmp) / "capsules"
            capsule_dir = package_root / "elements_capsule.capsule"
            self._write_minimal_package(capsule_dir, "elements_capsule", summary="video elements")
            (capsule_dir / "contracts" / "runtime.yaml").write_text(
                """
roles: {}
output_contract:
  subtitle: none
video_elements:
  fixed:
    aspect_ratio: "16:9"
  defaults:
    target_duration: 45
  user_overridable:
    aspect_ratio_options:
      - "16:9"
      - "9:16"
  forbidden: []
""".strip()
                + "\n",
                encoding="utf-8",
            )

            capsule = self.runtime.load_capsule_package("elements_capsule", package_roots=[package_root])
            defaults = self.runtime.capsule_runtime_defaults(capsule)

        self.assertNotIn("aspect_ratio", capsule["config"])
        self.assertNotIn("target_duration", capsule["config"])
        self.assertNotIn("aspect_ratio_options", capsule["config"])
        self.assertEqual(capsule["config"]["video_elements"]["fixed"]["aspect_ratio"], "16:9")
        self.assertEqual(defaults["aspect_ratio"], "16:9")
        self.assertEqual(defaults["target_duration"], 45)

    def test_runtime_defaults_ignore_legacy_flat_config_values(self):
        capsule = {
            "name": "flat_old",
            "config": {
                "aspect_ratio": "9:16",
                "target_duration": 99,
                "bgm_volume": 0.5,
                "output_contract": {
                    "subtitle": "none",
                },
            },
            "local_assets": [],
        }

        defaults = self.runtime.capsule_runtime_defaults(capsule)

        self.assertNotIn("aspect_ratio", defaults)
        self.assertNotIn("target_duration", defaults)
        self.assertNotIn("bgm_volume", defaults)
        self.assertFalse(defaults["add_subtitles"])

    def test_runtime_defaults_read_direct_video_elements_config(self):
        capsule = {
            "name": "direct_elements",
            "config": {
                "output_contract": {
                    "subtitle": "none",
                    "bgm": "external",
                },
                "video_elements": {
                    "fixed": {
                        "aspect_ratio": "3:4",
                        "body_subtitles": False,
                    },
                    "defaults": {
                        "target_duration": 12,
                        "bgm_volume": 0.25,
                    },
                    "user_overridable": {},
                    "forbidden": ["visible_bottom_title"],
                },
            },
            "local_assets": [],
        }

        defaults = self.runtime.capsule_runtime_defaults(capsule)

        self.assertEqual(defaults["aspect_ratio"], "3:4")
        self.assertEqual(defaults["target_duration"], 12)
        self.assertEqual(defaults["bgm_volume"], 0.25)
        self.assertFalse(defaults["add_subtitles"])
        self.assertTrue(defaults["add_background_music"])

    def test_load_capsule_falls_back_to_sqlite_when_package_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "capsules.sqlite"
            self._write_capsule_row(db_path, "sample", "SQLite Sample")

            capsule = self.runtime.load_capsule("sample", str(db_path), package_roots=[root / "capsules"])

        self.assertEqual(capsule["display_name"], "SQLite Sample")
        self.assertEqual(capsule["source_format"], "sqlite")

    def test_load_capsule_requires_exact_public_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "capsules.sqlite"
            self._write_capsule_row(db_path, "digital_human", "Digital Human")

            capsule = self.runtime.load_capsule("digital_human", str(db_path), prefer_package=False)

        self.assertEqual(capsule["name"], "digital_human")
        self.assertEqual(capsule["display_name"], "Digital Human")

    def test_load_capsule_does_not_try_legacy_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "capsules.sqlite"
            self._write_capsule_row(db_path, "archive_felt_demo", "Archive ASMR")

            with self.assertRaises(SystemExit):
                self.runtime.load_capsule("felt_asmr", str(db_path), prefer_package=False)

    def test_life_sim_uses_short_name_as_runtime_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "capsules.sqlite"
            self._write_capsule_row(
                db_path,
                "life_sim",
                "Life Sim",
                config={
                    "image_engine": "GptImage2Tool",
                    "video_engine": "none_for_default_route",
                    "visual_generation_type": "still_images_with_ken_burns",
                },
                method={
                    "opening_card_rules": {
                        "series_default": "每天一个模拟人生",
                    },
                    "story_formula": [
                        "0-3.5s: 模拟人生抽取卡开场",
                    ],
                    "visual_rules": {
                        "variation_requirement": "每 1-3 秒给新信息",
                    },
                },
            )

            capsule = self.runtime.load_capsule("life_sim", str(db_path), prefer_package=False)
            prompt = self.runtime.build_capsule_prompt(capsule, "主题：出租屋风水大师的一生")

        self.assertEqual(capsule["name"], "life_sim")
        self.assertIn('"opening_card_rules"', prompt)
        self.assertIn('"story_formula"', prompt)
        self.assertIn('"visual_rules"', prompt)
        self.assertIn('"name": "life_sim"', prompt)
        self.assertNotIn("archive_life_demo", prompt)

    def test_life_sim_defaults_force_gpt_image2_ken_burns_route(self):
        capsule = {
            "name": "life_sim",
            "config": {
                "roles": {
                    "image": {"validated_with": "GptImage2Tool"},
                    "video": {"validated_with": "none_for_default_route"},
                },
                "video_elements": {
                    "fixed": {
                        "visual_generation_type": "still_images_with_ken_burns",
                    },
                    "defaults": {},
                    "user_overridable": {},
                    "forbidden": [],
                },
            },
            "local_assets": [],
        }

        defaults = self.runtime.capsule_runtime_defaults(capsule)

        self.assertEqual(defaults["image_engine"], "gpt-image-2")
        self.assertTrue(defaults["force_image_fallback_video"])
        self.assertEqual(defaults["video_generation_route"], "still_images_with_ken_burns")
        self.assertNotIn("video_engine", defaults)

    def test_specialized_capsule_categories_require_special_route(self):
        for category in [
            "action-animation",
            "action_animation",
            "action_transfer",
            "code-rendered-graphics",
            "code_rendered_graphics",
            "digital-human",
            "digital_human",
            "lip-sync",
            "lip_sync",
            "music-mv",
            "music_mv",
            "super-resolution",
            "super_resolution",
        ]:
            with self.subTest(category=category):
                self.assertTrue(
                    self.runtime.capsule_requires_special_route({"category": category})
                )

    def test_runtime_defaults_read_new_output_contract(self):
        capsule = {
            "name": "roles_capsule",
            "config": {
                "roles": {
                    "image": {"selected": "GptImage2Tool"},
                    "video": {"selected": "Jimeng35ProVideoGeneratorTool"},
                },
                "output_contract": {
                    "voice": "none",
                    "subtitle": "none",
                    "bgm": "none",
                },
            },
            "local_assets": [],
        }

        defaults = self.runtime.capsule_runtime_defaults(capsule)

        self.assertFalse(defaults["add_subtitles"])
        self.assertFalse(defaults["add_background_music"])


if __name__ == "__main__":
    unittest.main()
