import sys
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "lib"
SCRIPTS = ROOT / "scripts"
for path in (LIB, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def content_scope() -> dict:
    return {
        "schema_version": "capsule.content_scope.v1",
        "series_fixed": ["fast_pacing", "visual_layout"],
        "episode_variable": ["topic", "product", "proof", "episode_copy"],
        "forbidden_reusable_literals": [],
        "policies": {
            "allow_series_fixed_defaults": True,
            "forbid_episode_specific_defaults": True,
            "active_recipe_examples_must_use_placeholders": True,
            "current_run_input_may_reuse_literal": True,
        },
    }


class VideoToCapsuleContractTest(unittest.TestCase):
    def test_analysis_prompt_requires_content_scope_classification(self):
        from src.video_to_capsule import build_analysis_prompt

        prompt = build_analysis_prompt()

        self.assertIn('"content_scope"', prompt)
        self.assertIn("at least three different episode topics", prompt)
        self.assertIn("forbidden_reusable_literals", prompt)
        self.assertIn("recurring characters, BGM, CTA", prompt)

    def test_normalize_complete_analysis_builds_breakdown_and_draft(self):
        from src.video_to_capsule import normalize_video_analysis

        with tempfile.TemporaryDirectory() as tmp:
            video_path = Path(tmp) / "sample.mp4"
            video_path.write_bytes(b"fake video")
            raw = {
                "success": True,
                "summary": "A punchy product demo with fast captions.",
                "source_profile": {
                    "likely_format": "product_showcase",
                    "aspect_ratio": "9:16",
                    "target_platform": "douyin",
                    "primary_audience": "young shoppers",
                },
                "segments": [
                    {
                        "start_time": "00:00.000",
                        "end_time": "00:03.000",
                        "beat": "Hook shows the product result first.",
                        "visuals": "Macro product close-up with clean background.",
                        "motion": "Fast push-in and hard cut.",
                        "copy": "Large benefit caption.",
                        "audio": "Energetic music hit.",
                        "reuse_lesson": "Open with final benefit before explaining features.",
                    }
                ],
                "capsule_recipe": {
                    "when_to_use": ["product demo", "benefit-led short video"],
                    "when_not_to_use": ["slow documentary"],
                    "structure_rules": ["Open with the strongest visible result."],
                    "copy_rules": ["Keep hook caption under 12 Chinese characters."],
                    "visual_rules": ["Use macro close-ups for tactile proof."],
                    "audio_rules": ["Sync first cut to a music hit."],
                    "motion_rules": ["Use fast push-in on the first beat."],
                    "quality_rules": ["Product must remain readable in every segment."],
                    "default_runtime": {"aspect_ratio": "9:16", "target_duration": 30},
                },
                "content_scope": content_scope(),
                "warnings": ["one subtitle is partially occluded"],
            }

            breakdown, draft = normalize_video_analysis(
                raw,
                source_video_path=str(video_path),
                analysis_tool="LocalAnalyzerTool",
                capsule_name="product_demo_capsule",
                capsule_display_name="Product Demo Capsule",
                target_platform="douyin",
            )

        self.assertEqual("capsule_cinema.video_breakdown.v1", breakdown["schema_version"])
        self.assertEqual("LocalAnalyzerTool", breakdown["analysis_tool"])
        self.assertEqual(1, len(breakdown["segments"]))
        self.assertEqual("capsule_cinema.capsule_draft.v1", draft["schema_version"])
        self.assertEqual("product_demo_capsule", draft["name"])
        self.assertEqual("Product Demo Capsule", draft["display_name"])
        self.assertEqual("product_showcase", draft["category"])
        self.assertIn("image_to_video", draft["capabilities"])
        self.assertEqual("Open with the strongest visible result.", draft["recipes"]["structure"][0])
        self.assertEqual("Product must remain readable in every segment.", draft["quality_rules"][0]["rule"])
        self.assertEqual("9:16", draft["runtime"]["video_elements"]["defaults"]["aspect_ratio"])
        self.assertNotIn("defaults", draft["runtime"])
        self.assertTrue(draft["runtime"]["copywriting_structure_contract"]["topic_to_angle_required"])
        self.assertIn("first_3_seconds", draft["runtime"]["copywriting_structure_contract"]["required_outputs"])

    def test_normalize_blocks_failed_analysis(self):
        from src.video_to_capsule import VideoToCapsuleError, normalize_video_analysis

        with tempfile.TemporaryDirectory() as tmp:
            video_path = Path(tmp) / "sample.mp4"
            video_path.write_bytes(b"fake video")
            with self.assertRaises(VideoToCapsuleError):
                normalize_video_analysis(
                    {"success": False, "error": "analysis unavailable"},
                    source_video_path=str(video_path),
                    analysis_tool="LocalAnalyzerTool",
                    capsule_name="bad_capsule",
                )

    def test_materialize_capsule_does_not_copy_source_by_default(self):
        from capsule_package_validate import validate_capsule_dir
        from src.video_to_capsule import materialize_capsule_from_draft, normalize_video_analysis

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            video_path = tmp_path / "sample.mp4"
            video_path.write_bytes(b"fake video")
            _, draft = normalize_video_analysis(
                {
                    "success": True,
                    "summary": "Demo summary",
                    "segments": [],
                    "capsule_recipe": {"structure_rules": ["Use a clear hook."]},
                    "content_scope": content_scope(),
                },
                source_video_path=str(video_path),
                analysis_tool="FakeAnalyzerTool",
                capsule_name="demo_capsule",
            )

            cap_dir = materialize_capsule_from_draft(
                draft,
                source_video_path=str(video_path),
                output_root=tmp_path / "capsules",
            )

            report = validate_capsule_dir(cap_dir, warnings_ok=True)
            assets = yaml.safe_load((cap_dir / "assets" / "index.yaml").read_text(encoding="utf-8"))
            runtime = yaml.safe_load((cap_dir / "contracts" / "runtime.yaml").read_text(encoding="utf-8"))
            copy_text = (cap_dir / "recipes" / "copy.md").read_text(encoding="utf-8")
            structure_text = (cap_dir / "recipes" / "structure.md").read_text(encoding="utf-8")

        self.assertTrue(report["ok"])
        self.assertEqual([], assets["assets"])
        self.assertFalse((cap_dir / "assets" / "source_video.mp4").exists())
        self.assertIn("video_elements", runtime)
        self.assertNotIn("defaults", runtime)
        self.assertIn("copywriting_structure_contract", runtime)
        self.assertIn("topic_to_angle_transform", copy_text)
        self.assertIn("real_first_line_gate", copy_text)
        self.assertIn("0-3s", structure_text)

    def test_materialize_capsule_can_include_reference_only_source_video(self):
        from src.video_to_capsule import materialize_capsule_from_draft, normalize_video_analysis

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            video_path = tmp_path / "sample.mp4"
            video_path.write_bytes(b"fake video")
            _, draft = normalize_video_analysis(
                {
                    "success": True,
                    "summary": "Demo summary",
                    "segments": [],
                    "capsule_recipe": {"visual_rules": ["Match the source lighting rhythm."]},
                    "content_scope": content_scope(),
                },
                source_video_path=str(video_path),
                analysis_tool="FakeAnalyzerTool",
                capsule_name="demo_capsule",
            )

            cap_dir = materialize_capsule_from_draft(
                draft,
                source_video_path=str(video_path),
                output_root=tmp_path / "capsules",
                include_source_video=True,
            )
            assets = yaml.safe_load((cap_dir / "assets" / "index.yaml").read_text(encoding="utf-8"))
            self.assertTrue((cap_dir / "assets" / "source_video.mp4").is_file())
            self.assertEqual("reference_only", assets["assets"][0]["reuse"])
            self.assertEqual("source_video_reference", assets["assets"][0]["role"])

    def test_materialize_blocks_analysis_without_declared_content_scope(self):
        from src.video_to_capsule import VideoToCapsuleError, materialize_capsule_from_draft, normalize_video_analysis

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            video_path = tmp_path / "sample.mp4"
            video_path.write_bytes(b"fake video")
            _, draft = normalize_video_analysis(
                {
                    "success": True,
                    "summary": "Draft-only analysis",
                    "segments": [],
                    "capsule_recipe": {"structure_rules": ["Use a clear hook."]},
                },
                source_video_path=str(video_path),
                analysis_tool="LegacyAnalyzerTool",
                capsule_name="legacy_capsule",
            )

            with self.assertRaisesRegex(VideoToCapsuleError, "did not declare content_scope"):
                materialize_capsule_from_draft(
                    draft,
                    source_video_path=str(video_path),
                    output_root=tmp_path / "capsules",
                )


class VideoToCapsuleCliTest(unittest.TestCase):
    def test_cli_draft_only_writes_analysis_artifacts_with_fake_tool(self):
        import analyze_video_to_capsule

        class FakeAnalyzerTool:
            def _run(self, **kwargs):
                return {
                    "success": True,
                    "summary": "Fast explainer",
                    "segments": [{"beat": "Hook first", "reuse_lesson": "Start with a direct problem."}],
                    "capsule_recipe": {"structure_rules": ["Start with a direct problem."]},
                    "content_scope": content_scope(),
                    "warnings": [],
                }

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = tmp_path / "source.mp4"
            source.write_bytes(b"fake video")
            result = analyze_video_to_capsule.run_video_to_capsule(
                source_video_path=str(source),
                video_analysis_tool="FakeAnalyzerTool",
                output_base_dir=tmp_path / "output",
                capsule_name="fast_explainer",
                tool_factory=lambda _name: FakeAnalyzerTool(),
            )

            analysis_path = Path(result["video_analysis_path"])
            draft_path = Path(result["capsule_draft_path"])
            self.assertTrue(analysis_path.is_file())
            self.assertTrue(draft_path.is_file())

        self.assertIsNone(result["capsule_dir"])
        self.assertEqual("FakeAnalyzerTool", result["analysis_tool_used"])

    def test_cli_write_capsule_creates_package_with_fake_tool(self):
        import analyze_video_to_capsule

        class FakeAnalyzerTool:
            def _run(self, **kwargs):
                return {
                    "success": True,
                    "summary": "Fast explainer",
                    "segments": [{"beat": "Hook first", "reuse_lesson": "Start with a direct problem."}],
                    "capsule_recipe": {"structure_rules": ["Start with a direct problem."]},
                    "content_scope": content_scope(),
                    "warnings": [],
                }

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = tmp_path / "source.mp4"
            source.write_bytes(b"fake video")
            result = analyze_video_to_capsule.run_video_to_capsule(
                source_video_path=str(source),
                video_analysis_tool="FakeAnalyzerTool",
                output_base_dir=tmp_path / "output",
                capsule_output_root=tmp_path / "capsules",
                capsule_name="fast_explainer",
                write_capsule=True,
                include_source_video=True,
                tool_factory=lambda _name: FakeAnalyzerTool(),
            )

            cap_dir = Path(result["capsule_dir"])
            self.assertTrue((cap_dir / "capsule.yaml").is_file())
            self.assertTrue((cap_dir / "assets" / "source_video.mp4").is_file())


if __name__ == "__main__":
    unittest.main()
