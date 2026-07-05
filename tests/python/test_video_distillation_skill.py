import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = ROOT / "video-distillation"
SCRIPTS = SKILL_DIR / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _make_tiny_video(path: Path) -> bool:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False
    cmd = [
        ffmpeg,
        "-y",
        "-f",
        "lavfi",
        "-i",
        "color=c=black:s=320x568:d=2",
        "-vf",
        "drawtext=text='HOOK':fontcolor=white:fontsize=42:x=30:y=80",
        "-pix_fmt",
        "yuv420p",
        str(path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    return proc.returncode == 0 and path.is_file()


class VideoDistillationSkillShapeTest(unittest.TestCase):
    def test_skill_is_standalone_and_not_capsule_runtime(self):
        self.assertTrue((SKILL_DIR / "SKILL.md").is_file())
        self.assertTrue((SKILL_DIR / "agents" / "openai.yaml").is_file())
        self.assertTrue((SKILL_DIR / "references" / "video-distillation-protocol.md").is_file())
        self.assertTrue((SKILL_DIR / "references" / "output-schema.md").is_file())
        self.assertTrue((SKILL_DIR / "references" / "gemini-video-analysis-prompts.md").is_file())
        self.assertTrue((SKILL_DIR / "references" / "extraction-tool-contract.md").is_file())
        self.assertTrue((SKILL_DIR / "scripts" / "distill_video.py").is_file())
        self.assertTrue((SKILL_DIR / "scripts" / "build_video_distillation_report.py").is_file())

        root_skill = (ROOT / "skill.md").read_text(encoding="utf-8")
        self.assertNotIn("video-distillation/scripts/distill_video.py", root_skill)
        self.assertFalse((ROOT / "capsules" / "video-distillation.capsule").exists())

    def test_skill_description_triggers_deep_video_distillation(self):
        content = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("name: video-distillation", content)
        self.assertIn("深度视频蒸馏", content)
        self.assertIn("文案逻辑", content)
        self.assertIn("整个视频逻辑", content)
        self.assertIn("production route", content)


class VideoDistillationSchemaTest(unittest.TestCase):
    def test_copy_logic_contains_hook_promise_script_cta_and_rewrite_template(self):
        from build_video_distillation_report import build_copy_logic

        result = build_copy_logic(
            source={"title": "3秒告诉你为什么没人看完", "caption": "别再这样开头了 #短视频"},
            transcript="别再这样开头了。前三秒没有结果，观众马上划走。最后记得评论关键词。",
            beats=[{"time_range": "0:00-0:03", "role": "hook", "transcript_evidence": "别再这样开头了"}],
            evidence_level="V2_transcript_ready",
        )

        self.assertEqual("capsule_cinema.video_copy_logic.v1", result["schema_version"])
        self.assertEqual("V2_transcript_ready", result["evidence_level"])
        self.assertIn("hook", result)
        self.assertIn("promise", result)
        self.assertIn("script_structure", result)
        self.assertIn("cta", result)
        self.assertIn("rewrite_template", result)
        self.assertIn("confidence", result)
        self.assertNotIn("别再这样开头了。前三秒没有结果", result["rewrite_template"]["reusable_script_template"])

    def test_beat_timeline_models_whole_video_logic_not_only_opening(self):
        from build_video_distillation_report import build_beat_timeline

        result = build_beat_timeline(
            transcript="先看结果。问题在这里。第三步才是真正的证明。最后评论关键词领取清单。",
            keyframes=[
                {"path": "03_keyframes/frames/frame_0000.jpg", "timestamp": 0.0, "label": "first_frame"},
                {"path": "03_keyframes/frames/frame_0003.jpg", "timestamp": 3.0, "label": "opening_3s"},
                {"path": "03_keyframes/frames/frame_end.jpg", "timestamp": 12.0, "label": "ending"},
            ],
            gemini=None,
        )

        self.assertEqual("capsule_cinema.video_beat_timeline.v1", result["schema_version"])
        roles = [beat["role"] for beat in result["beats"]]
        self.assertIn("hook", roles)
        self.assertIn("proof_or_development", roles)
        self.assertIn("ending_or_cta", roles)
        self.assertIn("core_loop", result["logic_summary"])
        self.assertIn("viewer_question_opened", result["logic_summary"])
        self.assertIn("viewer_question_closed", result["logic_summary"])

    def test_production_logic_classifies_modalities_and_routes(self):
        from build_video_distillation_report import build_copy_logic, build_production_logic

        copy_logic = build_copy_logic(
            source={"title": "AI卡片视频"},
            transcript="今天用三张卡片讲清楚。",
            beats=[],
            evidence_level="V2_transcript_ready",
        )
        result = build_production_logic(
            media_info={"duration_seconds": 18.2, "width": 1080, "height": 1920, "has_audio": True},
            keyframes=[{"path": "frame.jpg", "visible_text": "第一张卡片", "label": "first_frame"}],
            gemini={"visual_medium": "text_card_explainer", "motion": ["text_reveal", "hard_cut"]},
            copy_logic=copy_logic,
        )

        self.assertEqual("capsule_cinema.video_production_logic.v1", result["schema_version"])
        route = result["production_route"]
        for key in [
            "needs_ai_image_generation",
            "needs_ai_video_generation",
            "needs_digital_human",
            "needs_tts",
            "needs_original_voiceover",
            "needs_screen_recording",
            "needs_local_card_rendering",
            "needs_motion_graphics",
            "needs_subtitle_burn_in",
            "needs_bgm",
            "needs_sfx",
            "needs_manual_editing",
        ]:
            self.assertIn(key, route)
            self.assertIn("value", route[key])
            self.assertIn("reason", route[key])
            self.assertIn("evidence", route[key])
        self.assertIn("cheapest_viable_route", result)
        self.assertIn("highest_fidelity_route", result)
        self.assertIn("recommended_route", result)
        self.assertIn("hardest_part_to_reproduce", result)

    def test_recipe_seed_excludes_source_identity_and_private_urls(self):
        from build_video_distillation_report import (
            build_beat_timeline,
            build_copy_logic,
            build_production_logic,
            build_recipe_seed,
        )

        copy_logic = build_copy_logic(
            source={"title": "原账号标题", "source_url": "https://v.douyin.com/private/"},
            transcript="原文第一句不要复制。",
            beats=[],
            evidence_level="V2_transcript_ready",
        )
        timeline = build_beat_timeline("原文第一句不要复制。", [], None)
        production = build_production_logic(
            {"duration_seconds": 8, "width": 1080, "height": 1920, "has_audio": True},
            [],
            None,
            copy_logic,
        )
        seed = build_recipe_seed(copy_logic, timeline, production)
        dumped = yaml.safe_dump(seed, allow_unicode=True)

        self.assertEqual("capsule_cinema.video_distillation_recipe_seed.v1", seed["schema_version"])
        self.assertNotIn("https://v.douyin.com/private", dumped)
        self.assertNotIn("原文第一句不要复制", dumped)
        self.assertTrue(seed["source_safety"]["source_identity_forbidden"])
        self.assertTrue(seed["source_safety"]["copy_source_script_forbidden"])


class VideoDistillationLocalRunTest(unittest.TestCase):
    def test_local_video_run_writes_required_layout_and_manifests(self):
        from distill_video import run_local_distillation

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            video = tmp_path / "fixture.mp4"
            if not _make_tiny_video(video):
                self.skipTest("ffmpeg unavailable for tiny video fixture")

            result = run_local_distillation(
                local_video=video,
                output_root=tmp_path / "runs",
                run_id="20260705_120000_fixture",
                transcript_text="先看这个结果。然后解释原因。最后评论关键词。",
                enable_gemini=False,
                force=True,
            )

            out = Path(result["output_dir"])
            self.assertTrue(result["success"])
            for rel in [
                "00_source/source_input.txt",
                "00_source/media_info.json",
                "00_source/source_status.md",
                "01_media/video.mp4",
                "02_transcript/transcript.txt",
                "02_transcript/transcript_analysis.md",
                "03_keyframes/keyframe_index.json",
                "05_copy/copy_logic.yaml",
                "06_video_logic/beat_timeline.json",
                "07_production_logic/production_logic.yaml",
                "08_synthesis/video_distillation.md",
                "08_synthesis/recipe_seed.yaml",
                "evidence_map.json",
                "artifact_manifest.json",
            ]:
                self.assertTrue((out / rel).exists(), rel)

            evidence = json.loads((out / "evidence_map.json").read_text(encoding="utf-8"))
            manifest = json.loads((out / "artifact_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("V6_recipe_seed_ready", evidence["evidence_level"])
            self.assertTrue(any(item["path"].endswith("copy_logic.yaml") for item in manifest["artifacts"]))

    def test_missing_local_video_writes_partial_failure_manifest(self):
        from distill_video import run_local_distillation

        with tempfile.TemporaryDirectory() as tmp:
            result = run_local_distillation(
                local_video=Path(tmp) / "missing.mp4",
                output_root=Path(tmp) / "runs",
                run_id="20260705_120001_missing",
                transcript_text="",
                enable_gemini=False,
                force=True,
            )

            out = Path(result["output_dir"])
            self.assertFalse(result["success"])
            self.assertEqual("download_failed", result["failed_stage"])
            self.assertTrue((out / "00_source/source_status.md").is_file())
            self.assertTrue((out / "artifact_manifest.json").is_file())
            self.assertTrue((out / "evidence_map.json").is_file())


class AccountDistillationHandoffTest(unittest.TestCase):
    def test_account_distillation_points_selected_winner_videos_to_video_distillation(self):
        content = (ROOT / "account-distillation" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("video-distillation", content)
        self.assertIn("selected winner", content)
        self.assertIn("deep video-level distillation", content)


if __name__ == "__main__":
    unittest.main()
