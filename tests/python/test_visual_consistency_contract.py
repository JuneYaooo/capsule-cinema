import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

from src.visual_consistency_contract import compile_scene_prompt, validate_prompt_index  # noqa: E402
from src.runtime.general_video_crew.image_generator import ImageGenerator  # noqa: E402


STYLE_CONTRACT = {
    "style_name": "rich heiress cinematic anime storyboard",
    "fixed_style_traits": [
        "clean anime storyboard linework",
        "soft luxury interior lighting",
        "consistent warm skin shading",
    ],
    "allowed_style_variations": ["location lighting may change with the story"],
}

CHARACTER_BIBLE = {
    "character_id": "protagonist",
    "identity_anchor": "same 19-year-old heiress with almond eyes, black long hair, pearl hairpin",
    "fixed_traits": ["black long hair", "pearl hairpin", "navy school blazer"],
    "allowed_variations": ["wet hair after rain", "tired expression"],
}


def prompt_entry(
    scene_id,
    prompt_style_hash,
    *,
    final_prompt_used="stable style block\nstable character block\nscene action",
    consistency_mode="strict_reference_lock",
    reference_image_paths=None,
    attempts=None,
):
    refs = reference_image_paths if reference_image_paths is not None else ["/tmp/character_ref.png"]
    return {
        "category": "image",
        "scene_id": scene_id,
        "final_prompt_used": final_prompt_used,
        "prompt_style_hash": prompt_style_hash,
        "consistency_mode": consistency_mode,
        "reference_image_paths": refs,
        "attempts": attempts
        if attempts is not None
        else [
            {
                "prompt": final_prompt_used,
                "status": "success",
                "reference_image_paths": refs,
            }
        ],
    }


class VisualConsistencyContractTest(unittest.TestCase):
    def test_prompt_compiler_keeps_style_hash_stable_across_scene_actions(self):
        first = compile_scene_prompt(
            {"scene_id": "s1", "action": "pushes open a gold elevator", "actor_state": "hairpin visible"},
            STYLE_CONTRACT,
            CHARACTER_BIBLE,
            "16:9",
        )
        second = compile_scene_prompt(
            {"scene_id": "s2", "action": "stands in a hospital corridor", "actor_state": "same blazer wrinkled"},
            STYLE_CONTRACT,
            CHARACTER_BIBLE,
            "16:9",
        )

        self.assertEqual(first["prompt_style_hash"], second["prompt_style_hash"])
        self.assertIn("pushes open a gold elevator", first["compiled_prompt"])
        self.assertIn("stands in a hospital corridor", second["compiled_prompt"])
        self.assertIn("[STYLE CONTRACT]", first["compiled_prompt"])
        self.assertEqual(first["consistency_mode"], "strict_reference_lock")

    def test_prompt_index_blocks_mid_batch_style_hash_drift(self):
        report = validate_prompt_index(
            {
                "entries": [
                    prompt_entry("s1", "hash-a"),
                    prompt_entry("s2", "hash-b"),
                ]
            }
        )

        self.assertFalse(report["ok"])
        self.assertIn("prompt_style_hash_drift", report["blockers"])

    def test_prompt_index_requires_actual_final_prompt_used(self):
        report = validate_prompt_index(
            {
                "entries": [
                    prompt_entry("s1", "hash-a", final_prompt_used=""),
                ]
            }
        )

        self.assertFalse(report["ok"])
        self.assertIn("final_prompt_used_missing", report["blockers"])

    def test_text_only_soft_lock_is_not_strict_consistency_without_ack(self):
        report = validate_prompt_index(
            {
                "entries": [
                    prompt_entry(
                        "s1",
                        "hash-a",
                        consistency_mode="text_only_soft_lock",
                        reference_image_paths=[],
                        attempts=[
                            {
                                "prompt": "stable style block\nstable character block\nscene action",
                                "status": "success",
                                "reference_image_paths": [],
                                "fallback_reason": "reference_edit_api_failed_403",
                            }
                        ],
                    ),
                ]
            },
            strict_character_required=True,
            soft_consistency_ack=False,
        )

        self.assertFalse(report["ok"])
        self.assertIn("strict_reference_downgraded_without_ack", report["blockers"])

    def test_fallback_attempts_require_reason(self):
        report = validate_prompt_index(
            {
                "entries": [
                    prompt_entry(
                        "s1",
                        "hash-a",
                        attempts=[
                            {"prompt": "first", "status": "failed", "reference_image_paths": ["/tmp/ref.png"]},
                            {"prompt": "second", "status": "success", "reference_image_paths": ["/tmp/ref.png"]},
                        ],
                    ),
                ]
            }
        )

        self.assertFalse(report["ok"])
        self.assertIn("fallback_reason_missing", report["blockers"])

    def test_cli_writes_failed_report_for_hash_drift(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            prompt_index = tmp / "prompt_index.json"
            output = tmp / "style_consistency_report.json"
            prompt_index.write_text(
                json.dumps(
                    {
                        "entries": [
                            prompt_entry("s1", "hash-a"),
                            prompt_entry("s2", "hash-b"),
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "validate_visual_consistency.py"),
                    "--prompt-index",
                    str(prompt_index),
                    "--output",
                    str(output),
                ],
                cwd=str(ROOT),
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 1)
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertFalse(report["ok"])
            self.assertIn("prompt_style_hash_drift", report["blockers"])

    def test_image_generator_records_actual_prompt_and_reference_paths(self):
        class FakeSceneImageTool:
            def __init__(self):
                self.calls = []

            def _run(self, **kwargs):
                self.calls.append(kwargs)
                return {"status": "success", "output_path": "/tmp/generated_scene.png"}

        fake_tool = FakeSceneImageTool()
        generator = ImageGenerator(default_engine="volcengine-seedream")
        generator.scene_image_tool = fake_tool

        result = generator._generate_single_scene(
            0,
            {
                "scene_id": "s1",
                "image_prompt_english": "Stable prompt with locked style and character.",
                "needs_reference": True,
                "reference_type": "character",
                "reference_ids": ["hero"],
            },
            {"char_id_to_image": {"hero": "/tmp/hero_ref.png"}, "object_id_to_image": {}},
            "/tmp",
            "16:9",
            1,
            False,
            False,
            [],
            "volcengine-seedream",
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["final_prompt"], "Stable prompt with locked style and character.")
        self.assertEqual(result["final_prompt_used"], result["final_prompt"])
        self.assertEqual(result["reference_image_paths"], ["/tmp/hero_ref.png"])
        self.assertEqual(result["attempts"][0]["prompt"], result["final_prompt"])
        self.assertEqual(result["attempts"][0]["reference_image_paths"], ["/tmp/hero_ref.png"])


if __name__ == "__main__":
    unittest.main()
