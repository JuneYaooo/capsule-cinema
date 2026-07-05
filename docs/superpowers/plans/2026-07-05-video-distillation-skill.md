# Video Distillation Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone `video-distillation/` skill that deep-distills selected social videos into evidence-backed copy logic, whole-video logic, visual/motion/audio logic, production-route decisions, and reusable recipe seeds.

**Architecture:** Add an independent skill folder with references and two scripts. `distill_video.py` owns run orchestration, local media probing, keyframe extraction, optional external extractor/Gemini integration, and artifact layout. `build_video_distillation_report.py` owns pure schema builders for copy logic, beat timelines, production logic, manifests, and recipe seeds so the hardest analysis contracts can be tested without live APIs.

**Tech Stack:** Python 3.12, standard library, PyYAML, ffmpeg/ffprobe for local media, optional external `video_workflow` social-media extractor, optional Gemini-class analysis through the external analyzer when credentials are available, Node/npm existing smoke test.

## Global Constraints

- Create a standalone `video-distillation/` skill inside this repository.
- Do not merge video distillation instructions into the root Capsule Cinema `skill.md`.
- Do not write video distillation artifacts into `capsules/`.
- Do not store account-specific or video-specific run outputs inside `video-distillation/`.
- Do not modify, test, add, or depend on `account-distillation/`; it is private/gitignored and must remain outside this standalone skill.
- Write run outputs under `output/video_distillation/<YYYYMMDD_HHMMSS>_<slug>/`.
- Use `/Users/june2/code/github/video_workflow/backend/video_workflow/custom_tools/extract_content/social_media_content_extractor_tool.py` for URL/share-text acquisition when URL input is used.
- Support `--local-video` as a no-network fallback and as the main test path.
- Tests must not call live social-media APIs, Gemini APIs, or TikHub.
- Deep distillation must include copy logic, whole-video logic, visual style, motion style, audio logic, and production-route classification.
- All major claims must be tied to timestamps, transcript snippets, frame paths, media info, or marked inference.
- Recipe seeds must not include source account identity, copied source scripts, signed media URLs, API keys, or private token values.
- Evidence values must carry concrete evidence forms themselves: timestamps or time ranges, transcript snippets, frame/keyframe paths, media-info refs, or explicit inference markers. Placeholder-only evidence fields are invalid.

---

## File Structure

- `video-distillation/SKILL.md`: trigger rules and workflow for future agents.
- `video-distillation/agents/openai.yaml`: UI metadata for the standalone skill.
- `video-distillation/references/video-distillation-protocol.md`: evidence levels, run layout, and operator workflow.
- `video-distillation/references/output-schema.md`: exact artifact schemas for copy logic, beat timeline, production logic, manifest, evidence map, and recipe seed.
- `video-distillation/references/gemini-video-analysis-prompts.md`: prompts for full-video review, opening audit, keyframe review, transcript/copy analysis, and production-route classification.
- `video-distillation/references/extraction-tool-contract.md`: how to call the external social-media extractor and how to record failures.
- `video-distillation/scripts/build_video_distillation_report.py`: pure deterministic builders for structured artifacts.
- `video-distillation/scripts/distill_video.py`: CLI runner for local-video and URL/share-text distillation.
- `tests/python/test_video_distillation_skill.py`: no-network tests for folder independence, schema builders, local/default CLI output layout, URL extractor failure contracts, evidence discipline, capsules isolation, recipe seed sanitization, and partial failure artifacts.
- `package.json`: add new scripts to the existing py_compile smoke test.

---

### Task 1: No-Network Contract Tests

**Files:**
- Create: `tests/python/test_video_distillation_skill.py`
- Create in Task 2: `video-distillation/SKILL.md`
- Create in Task 3: `video-distillation/scripts/build_video_distillation_report.py`
- Create in Task 4: `video-distillation/scripts/distill_video.py`

**Interfaces:**
- Consumes: no production code initially.
- Produces expectations for:
  - `build_copy_logic(source: dict, transcript: str, beats: list[dict], evidence_level: str) -> dict`
  - `build_beat_timeline(transcript: str, keyframes: list[dict], gemini: dict | None) -> dict`
  - `build_production_logic(media_info: dict, keyframes: list[dict], gemini: dict | None, copy_logic: dict) -> dict`
  - `build_recipe_seed(copy_logic: dict, beat_timeline: dict, production_logic: dict) -> dict`
  - `run_local_distillation(local_video: Path, output_root: Path, run_id: str, transcript_text: str = "", enable_gemini: bool = False, force: bool = False) -> dict`
  - CLI `main()` supporting `--local-video` with default output root `output/video_distillation/<run_id>/`
  - `run_url_distillation(...) -> dict` reporting external extractor import/acquisition failures without live network calls or `account-distillation/`

- [ ] **Step 1: Write the failing test file**

Create `tests/python/test_video_distillation_skill.py`:

Reviewer tightening note: the checked-in Task 1 test file is authoritative if it differs from the historical seed below. It must keep `account-distillation/` private, remove unused imports, patch `socket.socket` for no-network local/default and URL failure contracts, enforce explicit evidence on copy/video/production claims, require `visual_style`, motion, and `audio_logic`, keep all run and manifest paths out of `capsules/`, and recursively sanitize source identity, signed URLs, headers, cookies, API keys, and tokens from recipe seeds.

```python
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

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
PYTHON_BIN=${PYTHON_BIN:-python3.12} ${PYTHON_BIN:-python3.12} -m pytest tests/python/test_video_distillation_skill.py -q
```

Expected: FAIL with assertions that `video-distillation/SKILL.md` or `build_video_distillation_report` does not exist.

- [ ] **Step 3: Commit the RED tests**

```bash
git add tests/python/test_video_distillation_skill.py
git commit -m "test: specify standalone video distillation skill"
```

---

### Task 2: Standalone Skill Skeleton And References

**Files:**
- Create: `video-distillation/SKILL.md`
- Create: `video-distillation/agents/openai.yaml`
- Create: `video-distillation/references/video-distillation-protocol.md`
- Create: `video-distillation/references/output-schema.md`
- Create: `video-distillation/references/gemini-video-analysis-prompts.md`
- Create: `video-distillation/references/extraction-tool-contract.md`
- Test: `tests/python/test_video_distillation_skill.py`

**Interfaces:**
- Consumes: the file-existence and trigger expectations from Task 1.
- Produces: skill metadata and references that later scripts and handoff docs point to.

- [ ] **Step 1: Initialize the skill folder**

Run the system skill initializer:

```bash
python /Users/june2/.codex/skills/.system/skill-creator/scripts/init_skill.py \
  video-distillation \
  --path /Users/june2/code/github/capsule-cinema \
  --resources scripts,references \
  --interface display_name="Video Distillation" \
  --interface short_description="Deep video logic and production-route distillation" \
  --interface default_prompt="Use $video-distillation to deeply distill this social video into copy logic, video logic, visual style, and production route."
```

Expected: `video-distillation/` exists with `SKILL.md`, `agents/openai.yaml`, `scripts/`, and `references/`.

- [ ] **Step 2: Replace `video-distillation/SKILL.md`**

```markdown
---
name: video-distillation
description: Use when deep-distilling a selected social video, short-form winner post, Douyin/Bilibili/XHS/TikTok video, copied share URL, or local video into evidence-backed 文案逻辑, 整个视频逻辑, 画面风格, 动效, audio/TTS/digital-human needs, production route, and reusable recipe seed.
---

# Video Distillation

Deep-distill selected social videos into source-grounded copy logic, whole-video logic, visual/motion/audio logic, and a production-route playbook.

This skill is independent from Capsule Cinema runtime. Do not write run outputs into `video-distillation/`, `capsules/`, or root `skill.md`. Write evidence runs under `output/video_distillation/<run_id>/`.

## Read When Needed

- Protocol and evidence levels: [references/video-distillation-protocol.md](references/video-distillation-protocol.md)
- Artifact schemas: [references/output-schema.md](references/output-schema.md)
- Gemini and keyframe prompts: [references/gemini-video-analysis-prompts.md](references/gemini-video-analysis-prompts.md)
- External extractor contract: [references/extraction-tool-contract.md](references/extraction-tool-contract.md)

## Non-Negotiables

- Do not call a result deep if it only has title/caption/metrics.
- Separate `observed`, `inferred`, and `recommended` claims.
- For 文案逻辑, analyze title, caption, cover/opening text, subtitle/OCR, spoken opening, transcript structure, CTA, and rewrite mechanism.
- For 整个视频逻辑, analyze first frame, 0-1s, 1-3s, 3-5s, 5-8s, setup, promise, proof/demo/story progression, payoff, CTA, ending, and segment-level retention roles.
- For production route, classify whether reproduction needs AI image generation, AI video generation, digital human, TTS, human voiceover, screen recording, local card rendering, motion graphics, subtitles, BGM, SFX, or manual editing.
- Never copy the source script, account identity, watermark, handle, logo, or source frames into reusable recipes.

## Default Workflow

1. Create a run directory under `output/video_distillation/`.
2. Acquire media with `scripts/distill_video.py --url` or `--local-video`.
3. Preserve raw source status, media info, transcript, keyframes, Gemini output, copy logic, video logic, production logic, synthesis, evidence map, and manifest.
4. Mark the evidence depth from `V0_metadata_only` through `V6_recipe_seed_ready`.
5. Use `08_synthesis/recipe_seed.yaml` only as a production planning seed, not as an active capsule.

## Commands

Local video:

```bash
python video-distillation/scripts/distill_video.py \
  --local-video /path/to/video.mp4 \
  --transcript-text "optional known transcript" \
  --output-root output/video_distillation \
  --disable-gemini
```

Social URL or copied share text:

```bash
python video-distillation/scripts/distill_video.py \
  --url "https://v.douyin.com/example/" \
  --external-video-workflow-root /Users/june2/code/github/video_workflow \
  --dotenv-path /Users/june2/code/github/video_workflow/.env
```

## Response Rules

- Lead with the highest completed evidence level and missing layers.
- Cite local artifact paths for each major claim.
- State if production-route fields are observed or inferred.
- If extractor/Gemini fails, report the failed stage and fallback path instead of pretending the video was deeply reviewed.
```

- [ ] **Step 3: Replace `video-distillation/agents/openai.yaml`**

```yaml
interface:
  display_name: "Video Distillation"
  short_description: "Deep video logic and production-route distillation"
  default_prompt: "Use $video-distillation to deeply distill this social video into copy logic, video logic, visual style, and production route."
policy:
  allow_implicit_invocation: true
```

- [ ] **Step 4: Create `video-distillation/references/video-distillation-protocol.md`**

```markdown
# Video Distillation Protocol

Use this protocol for selected winner videos, local short videos, and social share URLs that need deep production-method distillation.

## Evidence Levels

- `V0_metadata_only`: title, caption, tags, stats, and source URL only.
- `V1_media_acquired`: local video, cover, extractor JSON, and media info exist.
- `V2_transcript_ready`: transcript exists and supports copy/script analysis.
- `V3_keyframe_ready`: opening and representative keyframes/contact sheet exist.
- `V4_multimodal_reviewed`: Gemini-class full-video review or equivalent plus keyframe analysis exists.
- `V5_production_logic_distilled`: copy, whole-video logic, visual/motion/audio logic, and production route are classified with evidence.
- `V6_recipe_seed_ready`: reusable recipe seed exists without copied source identity or script.

## Required Deep Layers

Deep means all of these are attempted and explicitly marked as complete, limited, or failed:

1. source acquisition;
2. media info;
3. transcript;
4. keyframes/contact sheet;
5. Gemini or equivalent video analysis;
6. copy logic;
7. whole-video logic;
8. production-route logic;
9. synthesis and recipe seed.

## Run Layout

Write every run under `output/video_distillation/<run_id>/` with the numbered folders defined in `references/output-schema.md`.

## Evidence Discipline

Every major claim must cite one of:

- transcript snippet;
- timestamp;
- frame path;
- Gemini observation;
- media info;
- explicit inference label.

Do not infer camera motion, edit rhythm, voice style, BGM, digital human use, or AI generation route from metadata only.
```

- [ ] **Step 5: Create `video-distillation/references/output-schema.md`**

```markdown
# Video Distillation Output Schema

## Required Run Layout

```text
<run_dir>/
├── 00_source/
├── 01_media/
├── 02_transcript/
├── 03_keyframes/
├── 04_gemini/
├── 05_copy/
├── 06_video_logic/
├── 07_production_logic/
├── 08_synthesis/
├── evidence_map.json
└── artifact_manifest.json
```

## Copy Logic

`05_copy/copy_logic.yaml` uses schema `capsule_cinema.video_copy_logic.v1` and must include `hook`, `promise`, `script_structure`, `copy_devices`, `cta`, `rewrite_template`, and `confidence`.

## Beat Timeline

`06_video_logic/beat_timeline.json` uses schema `capsule_cinema.video_beat_timeline.v1` and must include `beats` plus `logic_summary.core_loop`, `viewer_question_opened`, `viewer_question_closed`, `main_retention_device`, and `weak_points`.

## Production Logic

`07_production_logic/production_logic.yaml` uses schema `capsule_cinema.video_production_logic.v1` and must include `visual_style`, `motion_and_editing` or `motion_style`, `audio_logic`, `production_route`, `cheapest_viable_route`, `highest_fidelity_route`, `recommended_route`, `required_materials`, `replaceable_materials`, `hardest_part_to_reproduce`, `quality_risks`, and `do_not_copy`. Each visual, motion, audio, route, and production-route summary claim must include concrete timestamps or time ranges, transcript snippets, frame/keyframe paths, media-info refs, or explicit inference markers. Placeholder-only evidence fields are invalid.

## Recipe Seed

`08_synthesis/recipe_seed.yaml` uses schema `capsule_cinema.video_distillation_recipe_seed.v1`. It must not include source account identity, copied source script, signed media URLs, API keys, or private token values.
```

- [ ] **Step 6: Create `video-distillation/references/gemini-video-analysis-prompts.md`**

```markdown
# Gemini Video Analysis Prompts

## Full Video Review

Analyze this short-form video as a deep video-distillation sample. Return structured Markdown or JSON with:

1. duration, aspect ratio, language, visible format;
2. first frame, 0-1s, 1-3s, 3-5s, 5-8s;
3. full spoken/subtitle/OCR transcript if readable or audible;
4. timeline beats: hook, setup, promise, proof/demo/story progression, turning point, payoff, CTA, ending;
5. visual style: medium, character/face use, scene density, palette, typography, subtitles, overlays, UI, proof devices;
6. motion/editing: camera movement, cut rhythm, transition style, animation style, text motion, zooms, arrows, caption timing;
7. audio: voice, TTS-likeness, BGM role, SFX role, silence, rhythm authority;
8. production-route inference: AI video, AI image, digital human, TTS, human voiceover, screen recording, card rendering, motion graphics, subtitle burn-in, BGM, SFX, manual editing;
9. observed vs inferred vs recommended, with evidence timestamps.

Never assert the source used a production tool unless visible evidence supports it. Mark uncertain claims as uncertain.

## Keyframe Review

Given keyframes and a contact sheet, analyze frame grammar, visible text, composition, proof devices, typography, palette, character presence, motion implications, and what each frame contributes to retention.

## Copy And Transcript Review

Analyze title, caption, hashtags, visible text, spoken opening, transcript beats, CTA, risk claims, and reusable copy mechanism. Do not copy the source script as a template.
```

- [ ] **Step 7: Create `video-distillation/references/extraction-tool-contract.md`**

```markdown
# Extraction Tool Contract

Use the external social-media extractor only for URL or copied share-text acquisition:

```text
/Users/june2/code/github/video_workflow/backend/video_workflow/custom_tools/extract_content/social_media_content_extractor_tool.py
```

When a caller passes a different `--external-video-workflow-root` in tests, resolve the same relative tool path below that root:
`backend/video_workflow/custom_tools/extract_content/social_media_content_extractor_tool.py`.

Default root:

```text
/Users/june2/code/github/video_workflow
```

Default env file:

```text
/Users/june2/code/github/video_workflow/.env
```

The runner should call `SocialMediaContentExtractorTool()._run(...)` with transcript enabled, video analysis disabled by default, a run-specific output directory, and `save_video=True`.

If the extractor import or parse call fails, write `00_source/source_status.md`, `artifact_manifest.json`, and `evidence_map.json`, then suggest `--local-video` fallback.

Do not persist API keys, cookies, or signed remote media URLs in recipe seeds.
```

- [ ] **Step 8: Run the shape tests**

Run:

```bash
PYTHON_BIN=${PYTHON_BIN:-python3.12} ${PYTHON_BIN:-python3.12} -m pytest tests/python/test_video_distillation_skill.py::VideoDistillationSkillShapeTest -q
```

Expected: PASS for skill shape tests; schema and runner tests still fail because scripts are not implemented.

- [ ] **Step 9: Validate the skill folder**

Run:

```bash
python /Users/june2/.codex/skills/.system/skill-creator/scripts/quick_validate.py video-distillation
```

Expected: PASS.

- [ ] **Step 10: Commit the skill skeleton**

```bash
git add video-distillation
git commit -m "feat: add standalone video distillation skill shell"
```

---

### Task 3: Pure Deep-Distillation Schema Builders

**Files:**
- Create: `video-distillation/scripts/build_video_distillation_report.py`
- Test: `tests/python/test_video_distillation_skill.py`

**Interfaces:**
- Consumes: test calls from `VideoDistillationSchemaTest`.
- Produces:
  - `build_copy_logic(source: dict[str, Any], transcript: str, beats: list[dict[str, Any]], evidence_level: str) -> dict[str, Any]`
  - `build_beat_timeline(transcript: str, keyframes: list[dict[str, Any]], gemini: dict[str, Any] | None) -> dict[str, Any]`
  - `build_production_logic(media_info: dict[str, Any], keyframes: list[dict[str, Any]], gemini: dict[str, Any] | None, copy_logic: dict[str, Any]) -> dict[str, Any]`
  - `build_recipe_seed(copy_logic: dict[str, Any], beat_timeline: dict[str, Any], production_logic: dict[str, Any]) -> dict[str, Any]`
  - `write_json(path: Path, value: Any) -> Path`
  - `write_yaml(path: Path, value: Any) -> Path`
  - `write_text(path: Path, value: str) -> Path`

- [ ] **Step 1: Run schema tests and verify RED**

Run:

```bash
PYTHON_BIN=${PYTHON_BIN:-python3.12} ${PYTHON_BIN:-python3.12} -m pytest \
  tests/python/test_video_distillation_skill.py::VideoDistillationSchemaTest -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'build_video_distillation_report'`.

- [ ] **Step 2: Implement `build_video_distillation_report.py`**

Implementation note: satisfy the tightened Task 1 contracts, not only the historical scaffold below. Copy logic, beat timelines, production sections, route items, and route-summary fields must expose concrete evidence values, not placeholder-only `evidence` keys; `visual_style`, motion, and `audio_logic` are required; recipe seeds must recursively drop source identity, signed URLs, headers, cookies, API keys, tokens, and copied transcript text.

```python
#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml


RouteValue = bool | str


def _text(value: Any) -> str:
    return str(value or "").strip()


def _first_sentence(text: str, fallback: str = "") -> str:
    cleaned = re.sub(r"\s+", " ", _text(text))
    if not cleaned:
        return fallback
    parts = re.split(r"[。！？!?]", cleaned, maxsplit=1)
    return parts[0].strip() or fallback


def _contains_any(text: str, needles: list[str]) -> bool:
    lowered = text.lower()
    return any(needle.lower() in lowered for needle in needles)


def _route_item(value: RouteValue, reason: str, evidence: list[str]) -> dict[str, Any]:
    return {"value": value, "reason": reason, "evidence": evidence}


def _abstract_script_template(transcript: str) -> str:
    del transcript
    return (
        "用一个具体结果或冲突开场 -> 点出观众当下问题 -> 给出证明/演示/故事推进 -> "
        "解释为什么成立 -> 用评论、关注、领取清单或下一步行动收尾。"
    )


def build_copy_logic(
    source: dict[str, Any],
    transcript: str,
    beats: list[dict[str, Any]],
    evidence_level: str,
) -> dict[str, Any]:
    title = _text(source.get("title") or source.get("caption"))
    caption = _text(source.get("caption"))
    opening = _first_sentence(transcript, title)
    cta_observed = ""
    if _contains_any(transcript, ["评论", "关注", "领取", "私信", "收藏", "转发"]):
        cta_observed = _first_sentence(transcript.split("最后")[-1], "contains CTA language")
    return {
        "schema_version": "capsule_cinema.video_copy_logic.v1",
        "evidence_level": evidence_level,
        "source_copy": {
            "title": title,
            "caption": caption,
            "hashtags": re.findall(r"#([^#\\s]+)", f"{title} {caption}"),
        },
        "hook": {
            "exact_observed_text": opening,
            "spoken_opening": opening if transcript else "",
            "visible_opening": _text(source.get("visible_opening")),
            "mechanism": "direct_problem_or_result_first",
            "viewer_pressure": "viewer is given a concrete reason to keep watching",
            "curiosity_gap": "why this result/problem happens and how it resolves",
        },
        "promise": {
            "what_viewer_expects": title or opening,
            "when_promise_is_opened": "opening",
            "when_promise_is_paid_off": "ending_or_main_proof",
        },
        "script_structure": {
            "beats": beats
            or [
                {
                    "time_range": "unknown",
                    "role": "transcript_summary",
                    "transcript_evidence": opening,
                    "visual_evidence": "",
                    "retention_function": "establishes the viewer question",
                }
            ]
        },
        "copy_devices": {
            "specificity": "observed" if re.search(r"\\d", f"{title} {transcript}") else "limited",
            "contrast": "observed" if _contains_any(f"{title} {transcript}", ["不是", "而是", "但是", "却"]) else "limited",
            "numbers": re.findall(r"\\d+(?:\\.\\d+)?", f"{title} {transcript}"),
            "identity_address": "observed" if _contains_any(transcript, ["你", "普通人", "新手"]) else "limited",
            "risk_or_loss": "observed" if _contains_any(transcript, ["别", "不要", "风险", "错", "划走"]) else "limited",
            "proof_language": "observed" if _contains_any(transcript, ["证明", "结果", "实测", "案例", "看"]) else "limited",
        },
        "cta": {
            "observed": cta_observed,
            "type": "comment_or_follow" if cta_observed else "not_observed",
            "timing": "ending" if cta_observed else "",
            "comment_driver": cta_observed,
        },
        "rewrite_template": {
            "reusable_hook_formula": "别先讲背景，先给观众一个具体结果、错误、冲突或可验证承诺。",
            "reusable_script_template": _abstract_script_template(transcript),
            "forbidden_to_copy": ["source title", "source transcript", "source account identity", "source frames"],
        },
        "confidence": {
            "transcript_completeness": "present" if transcript else "missing",
            "unsupported_claims": [],
        },
    }


def build_beat_timeline(
    transcript: str,
    keyframes: list[dict[str, Any]],
    gemini: dict[str, Any] | None,
) -> dict[str, Any]:
    gemini = gemini or {}
    frame_evidence = ", ".join(_text(item.get("path")) for item in keyframes[:3] if item.get("path"))
    opening_text = _first_sentence(transcript, _text(gemini.get("opening")) or "opening unavailable")
    beats = [
        {
            "time_range": "0:00-0:03",
            "role": "hook",
            "copy_evidence": opening_text,
            "visual_evidence": frame_evidence,
            "audio_evidence": "transcript" if transcript else "",
            "retention_function": "opens the viewer question and stop reason",
            "implementation_dependency": "opening copy plus first-frame visual proof",
        },
        {
            "time_range": "0:03-mid",
            "role": "proof_or_development",
            "copy_evidence": _text(gemini.get("proof")) or "middle segment must prove or develop the opening promise",
            "visual_evidence": frame_evidence,
            "audio_evidence": "voiceover_or_subtitle" if transcript else "",
            "retention_function": "keeps the promise alive with proof, demo, story, or explanation",
            "implementation_dependency": "clear sequence of evidence beats",
        },
        {
            "time_range": "ending",
            "role": "ending_or_cta",
            "copy_evidence": "CTA/comment/follow/payoff if observed",
            "visual_evidence": _text(keyframes[-1].get("path")) if keyframes else "",
            "audio_evidence": "ending transcript or final subtitle",
            "retention_function": "closes the viewer question or drives next action",
            "implementation_dependency": "payoff or CTA must match the opening promise",
        },
    ]
    return {
        "schema_version": "capsule_cinema.video_beat_timeline.v1",
        "beats": beats,
        "logic_summary": {
            "core_loop": "open a concrete viewer question, delay closure with proof/development, close with payoff or CTA",
            "viewer_question_opened": opening_text,
            "viewer_question_closed": "ending/payoff needs verification from transcript or Gemini review",
            "main_retention_device": _text(gemini.get("main_retention_device")) or "promise-proof-payoff loop",
            "weak_points": [],
        },
    }


def build_production_logic(
    media_info: dict[str, Any],
    keyframes: list[dict[str, Any]],
    gemini: dict[str, Any] | None,
    copy_logic: dict[str, Any],
) -> dict[str, Any]:
    gemini = gemini or {}
    visual_medium = _text(gemini.get("visual_medium")) or "unknown_or_hybrid"
    keyframe_text = " ".join(_text(item.get("visible_text") or item.get("label") or item.get("path")) for item in keyframes)
    transcript_signal = json.dumps(copy_logic, ensure_ascii=False)
    card_like = _contains_any(f"{visual_medium} {keyframe_text}", ["card", "卡片", "text", "字幕"])
    screen_like = _contains_any(f"{visual_medium} {keyframe_text}", ["screen", "屏录", "ui", "github", "网页"])
    digital_human_like = _contains_any(f"{visual_medium} {keyframe_text}", ["digital human", "数字人", "talking head", "口播"])
    ai_story_like = _contains_any(f"{visual_medium} {keyframe_text}", ["ai animation", "ai_story", "动漫", "storyboard"])
    has_audio = bool(media_info.get("has_audio"))
    route = {
        "needs_ai_image_generation": _route_item(ai_story_like, "AI/storyboard-like visuals need generated stills or source illustrations", [visual_medium]),
        "needs_ai_video_generation": _route_item(ai_story_like, "Moving AI story scenes benefit from image-to-video or text-to-video", [visual_medium]),
        "needs_digital_human": _route_item(digital_human_like, "Talking-head format can be reproduced with a digital human if no human presenter is available", [visual_medium]),
        "needs_tts": _route_item(bool(transcript_signal), "Voice/subtitle-driven logic needs narration; TTS is the cheapest repeatable route", ["copy_logic"]),
        "needs_original_voiceover": _route_item(False, "Original human voice is optional unless creator identity is the moat", ["inference"]),
        "needs_screen_recording": _route_item(screen_like, "Screen/UI evidence must be reproduced with screen recording or UI mock footage", [keyframe_text]),
        "needs_local_card_rendering": _route_item(card_like, "Text-card formats require deterministic text rendering", [keyframe_text or visual_medium]),
        "needs_motion_graphics": _route_item(card_like or screen_like, "Cards, UI, arrows, zooms, or subtitles need simple motion graphics", [visual_medium]),
        "needs_subtitle_burn_in": _route_item(True, "Short-form retention needs visible text or subtitles unless the format is purely visual", ["platform_default"]),
        "needs_bgm": _route_item(has_audio, "Audio track exists; use safe low-volume BGM if source relies on pacing", ["media_info.has_audio"]),
        "needs_sfx": _route_item("optional", "Use SFX only for transitions, proof moments, or UI emphasis", ["inference"]),
        "needs_manual_editing": _route_item(True, "Every route needs final timing, subtitle, audio, and QA assembly", ["release_quality"]),
    }
    return {
        "schema_version": "capsule_cinema.video_production_logic.v1",
        "evidence_level": "V5_production_logic_distilled",
        "visual_style": {
            "medium": visual_medium,
            "aspect_ratio": media_info.get("aspect_ratio") or f"{media_info.get('width', '')}x{media_info.get('height', '')}",
            "frame_grammar": "observed from keyframes" if keyframes else "limited_without_keyframes",
            "typography": "observed" if card_like else "limited",
            "palette": "requires keyframe/Gemini review",
        },
        "motion_and_editing": {
            "motion_patterns": gemini.get("motion") or [],
            "edit_rhythm": gemini.get("edit_rhythm") or "inferred_after_keyframe_or_gemini_review",
            "subtitle_motion": "required_if_subtitles_drive_retention",
        },
        "audio_logic": {
            "has_audio": has_audio,
            "voice_or_tts": "tts_viable" if transcript_signal else "unknown",
            "bgm_role": "pace_support" if has_audio else "not_observed",
            "sfx_role": "optional_emphasis",
        },
        "production_route": route,
        "cheapest_viable_route": "TTS + deterministic cards/subtitles + simple motion graphics + ffmpeg assembly",
        "highest_fidelity_route": "match observed medium with generated/recorded visuals, timed narration, BGM/SFX, and manual edit QA",
        "recommended_route": "choose the cheapest route that preserves the observed hook, proof, visual grammar, and audio timing",
        "required_materials": ["script rewrite", "visual evidence plan", "voice or TTS", "subtitles", "BGM if audio-led"],
        "replaceable_materials": ["source account identity", "source frames", "source exact script"],
        "hardest_part_to_reproduce": "the exact first-three-second stop reason and proof alignment",
        "quality_risks": ["generic visuals", "copied wording", "weak opening proof", "subtitle overcrowding"],
        "do_not_copy": ["source logo", "source watermark", "source handle", "source exact script", "source frames"],
    }


def build_recipe_seed(
    copy_logic: dict[str, Any],
    beat_timeline: dict[str, Any],
    production_logic: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "capsule_cinema.video_distillation_recipe_seed.v1",
        "source_safety": {
            "source_identity_forbidden": True,
            "copy_source_script_forbidden": True,
            "source_frames_forbidden": True,
            "signed_urls_forbidden": True,
        },
        "copy_formula": {
            "hook_formula": copy_logic["rewrite_template"]["reusable_hook_formula"],
            "script_template": copy_logic["rewrite_template"]["reusable_script_template"],
        },
        "video_logic": beat_timeline["logic_summary"],
        "production_route": production_logic["production_route"],
        "recommended_route": production_logic["recommended_route"],
        "quality_gates": [
            "first_three_seconds_stop_reason",
            "promise_proof_payoff_alignment",
            "no_source_identity",
            "no_copied_script",
            "subtitle_readability",
            "route_matches_visual_medium",
        ],
    }


def write_json(path: Path, value: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def write_yaml(path: Path, value: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


def write_text(path: Path, value: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8")
    return path
```

- [ ] **Step 3: Run schema tests and verify GREEN**

Run:

```bash
PYTHON_BIN=${PYTHON_BIN:-python3.12} ${PYTHON_BIN:-python3.12} -m pytest \
  tests/python/test_video_distillation_skill.py::VideoDistillationSchemaTest -q
```

Expected: PASS.

- [ ] **Step 4: Commit schema builders**

```bash
git add video-distillation/scripts/build_video_distillation_report.py tests/python/test_video_distillation_skill.py
git commit -m "feat: add video distillation schema builders"
```

---

### Task 4: Local Video Runner, Keyframes, Manifest, And Evidence Map

**Files:**
- Create: `video-distillation/scripts/distill_video.py`
- Test: `tests/python/test_video_distillation_skill.py`

**Interfaces:**
- Consumes from Task 3:
  - `build_copy_logic(...) -> dict`
  - `build_beat_timeline(...) -> dict`
  - `build_production_logic(...) -> dict`
  - `build_recipe_seed(...) -> dict`
  - `write_json(...) -> Path`
  - `write_yaml(...) -> Path`
  - `write_text(...) -> Path`
- Produces:
  - `run_local_distillation(local_video: Path, output_root: Path, run_id: str, transcript_text: str = "", enable_gemini: bool = False, force: bool = False) -> dict[str, Any]`
  - CLI entrypoint supporting `--local-video`, `--url`, `--transcript-text`, `--output-root`, `--run-id`, `--disable-gemini`, and `--force`.

- [ ] **Step 1: Run local runner tests and verify RED**

Run:

```bash
PYTHON_BIN=${PYTHON_BIN:-python3.12} ${PYTHON_BIN:-python3.12} -m pytest \
  tests/python/test_video_distillation_skill.py::VideoDistillationLocalRunTest -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'distill_video'`.

- [ ] **Step 2: Implement `distill_video.py`**

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from build_video_distillation_report import (
    build_beat_timeline,
    build_copy_logic,
    build_production_logic,
    build_recipe_seed,
    write_json,
    write_text,
    write_yaml,
)


def safe_slug(value: str, default: str = "video") -> str:
    text = str(value or "").strip()
    match = re.search(r"v\.douyin\.com/([A-Za-z0-9_-]+)", text)
    if match:
        return match.group(1)
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", text).strip("_")
    return slug[:48] or default


def make_run_dir(output_root: Path, run_id: str | None, slug: str) -> Path:
    stamp = run_id or f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_slug(slug)}"
    out = output_root / stamp
    out.mkdir(parents=True, exist_ok=True)
    for name in [
        "00_source",
        "01_media",
        "02_transcript",
        "03_keyframes/frames",
        "04_gemini",
        "05_copy",
        "06_video_logic",
        "07_production_logic",
        "08_synthesis",
    ]:
        (out / name).mkdir(parents=True, exist_ok=True)
    return out


def run_cmd(cmd: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def ffprobe_media(video: Path) -> dict[str, Any]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return {"ok": False, "reason": "ffprobe_missing"}
    proc = run_cmd(
        [
            ffprobe,
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_streams",
            "-show_format",
            str(video),
        ],
        timeout=60,
    )
    if proc.returncode != 0:
        return {"ok": False, "reason": "ffprobe_failed", "stderr": proc.stderr}
    data = json.loads(proc.stdout or "{}")
    streams = data.get("streams") if isinstance(data.get("streams"), list) else []
    video_stream = next((item for item in streams if item.get("codec_type") == "video"), {})
    has_audio = any(item.get("codec_type") == "audio" for item in streams)
    width = int(video_stream.get("width") or 0)
    height = int(video_stream.get("height") or 0)
    try:
        duration = float((data.get("format") or {}).get("duration") or 0)
    except (TypeError, ValueError):
        duration = 0.0
    if width and height:
        ratio = width / height
        aspect_ratio = "9:16" if ratio < 0.8 else "16:9" if ratio > 1.2 else "1:1"
    else:
        aspect_ratio = "unknown"
    return {
        "ok": True,
        "width": width,
        "height": height,
        "aspect_ratio": aspect_ratio,
        "duration_seconds": duration,
        "has_audio": has_audio,
        "raw": data,
    }


def extract_keyframes(video: Path, run_dir: Path, duration_seconds: float) -> list[dict[str, Any]]:
    ffmpeg = shutil.which("ffmpeg")
    frames: list[dict[str, Any]] = []
    if not ffmpeg:
        return frames
    timestamps = [0.0, 1.0]
    if duration_seconds >= 2.0:
        timestamps.append(min(3.0, duration_seconds * 0.5))
    timestamps.append(max(duration_seconds - 0.25, 0.0))
    unique: list[float] = []
    for ts in timestamps:
        rounded = round(max(ts, 0.0), 2)
        if rounded not in unique:
            unique.append(rounded)
    for index, ts in enumerate(unique):
        path = run_dir / "03_keyframes" / "frames" / f"frame_{index:04d}_{ts:.2f}.jpg"
        proc = run_cmd(
            [
                ffmpeg,
                "-y",
                "-ss",
                f"{ts:.3f}",
                "-i",
                str(video),
                "-frames:v",
                "1",
                "-q:v",
                "3",
                str(path),
            ],
            timeout=60,
        )
        if proc.returncode == 0 and path.is_file():
            frames.append({"path": str(path.relative_to(run_dir)), "timestamp": ts, "label": "first_frame" if index == 0 else f"frame_{index}"})
    return frames


def write_manifest(run_dir: Path, evidence_level: str, success: bool, failed_stage: str = "") -> None:
    artifacts = []
    for path in sorted(run_dir.rglob("*")):
        if path.is_file():
            artifacts.append({"path": str(path.relative_to(run_dir)), "status": "present"})
    write_json(
        run_dir / "artifact_manifest.json",
        {
            "schema_version": "capsule_cinema.video_distillation_manifest.v1",
            "success": success,
            "failed_stage": failed_stage,
            "artifacts": artifacts,
        },
    )
    write_json(
        run_dir / "evidence_map.json",
        {
            "schema_version": "capsule_cinema.video_distillation_evidence_map.v1",
            "evidence_level": evidence_level,
            "success": success,
            "failed_stage": failed_stage,
            "folders": {
                "source": "00_source",
                "media": "01_media",
                "transcript": "02_transcript",
                "keyframes": "03_keyframes",
                "gemini": "04_gemini",
                "copy": "05_copy",
                "video_logic": "06_video_logic",
                "production_logic": "07_production_logic",
                "synthesis": "08_synthesis",
            },
        },
    )


def _failure(run_dir: Path, stage: str, message: str) -> dict[str, Any]:
    write_text(run_dir / "00_source" / "source_status.md", f"# Source Status\n\n- status: failed\n- failed_stage: {stage}\n- message: {message}\n")
    write_manifest(run_dir, "V0_metadata_only", False, stage)
    return {"success": False, "failed_stage": stage, "output_dir": str(run_dir), "error": message}


def run_local_distillation(
    local_video: Path,
    output_root: Path,
    run_id: str,
    transcript_text: str = "",
    enable_gemini: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    del enable_gemini, force
    run_dir = make_run_dir(output_root, run_id, local_video.stem)
    write_text(run_dir / "00_source" / "source_input.txt", str(local_video))
    if not local_video.is_file():
        return _failure(run_dir, "download_failed", f"local video not found: {local_video}")
    target_video = run_dir / "01_media" / "video.mp4"
    shutil.copy2(local_video, target_video)
    media_info = ffprobe_media(target_video)
    write_json(run_dir / "00_source" / "media_info.json", media_info)
    if not media_info.get("ok"):
        return _failure(run_dir, "ffprobe_failed", str(media_info))
    write_text(run_dir / "00_source" / "source_status.md", "# Source Status\n\n- status: local_video_ready\n")
    transcript = transcript_text.strip()
    write_text(run_dir / "02_transcript" / "transcript.txt", transcript)
    keyframes = extract_keyframes(target_video, run_dir, float(media_info.get("duration_seconds") or 0))
    write_json(run_dir / "03_keyframes" / "keyframe_index.json", {"frames": keyframes})
    write_text(
        run_dir / "03_keyframes" / "keyframe_analysis.md",
        "# Keyframe Analysis\n\n" + "\n".join(f"- {item['label']}: {item['path']} @ {item['timestamp']}s" for item in keyframes),
    )
    beat_timeline = build_beat_timeline(transcript, keyframes, None)
    copy_logic = build_copy_logic(
        source={"title": local_video.stem, "caption": ""},
        transcript=transcript,
        beats=beat_timeline["beats"],
        evidence_level="V2_transcript_ready" if transcript else "V1_media_acquired",
    )
    production_logic = build_production_logic(media_info, keyframes, None, copy_logic)
    recipe_seed = build_recipe_seed(copy_logic, beat_timeline, production_logic)
    write_text(run_dir / "02_transcript" / "transcript_analysis.md", "# Transcript Analysis\n\nTranscript present." if transcript else "# Transcript Analysis\n\nTranscript missing.")
    write_yaml(run_dir / "05_copy" / "copy_logic.yaml", copy_logic)
    write_text(run_dir / "05_copy" / "copy_analysis.md", "# Copy Analysis\n\nSee `copy_logic.yaml`.")
    write_json(run_dir / "06_video_logic" / "beat_timeline.json", beat_timeline)
    write_text(run_dir / "06_video_logic" / "narrative_logic.md", "# Narrative Logic\n\nSee `beat_timeline.json`.")
    write_yaml(run_dir / "06_video_logic" / "retention_logic.yaml", {"main_retention_device": beat_timeline["logic_summary"]["main_retention_device"]})
    write_yaml(run_dir / "07_production_logic" / "production_logic.yaml", production_logic)
    write_json(run_dir / "07_production_logic" / "modality_breakdown.json", production_logic["production_route"])
    write_text(run_dir / "07_production_logic" / "implementation_playbook.md", "# Implementation Playbook\n\n" + production_logic["recommended_route"])
    write_text(run_dir / "08_synthesis" / "video_distillation.md", "# Video Distillation\n\nDeep distillation artifacts generated from local video.")
    write_text(run_dir / "08_synthesis" / "reusable_patterns.md", "# Reusable Patterns\n\nUse the recipe seed without copying source identity.")
    write_yaml(run_dir / "08_synthesis" / "recipe_seed.yaml", recipe_seed)
    write_manifest(run_dir, "V6_recipe_seed_ready", True)
    return {"success": True, "output_dir": str(run_dir), "evidence_level": "V6_recipe_seed_ready"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Deep-distill a social/local video into evidence-backed production logic.")
    parser.add_argument("--local-video", default="")
    parser.add_argument("--url", default="")
    parser.add_argument("--transcript-text", default="")
    parser.add_argument("--output-root", default="output/video_distillation")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--disable-gemini", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--external-video-workflow-root", default="/Users/june2/code/github/video_workflow")
    parser.add_argument("--dotenv-path", default="/Users/june2/code/github/video_workflow/.env")
    args = parser.parse_args()
    if args.local_video:
        run_id = args.run_id or f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_slug(Path(args.local_video).stem)}"
        result = run_local_distillation(
            local_video=Path(args.local_video).expanduser(),
            output_root=Path(args.output_root).expanduser(),
            run_id=run_id,
            transcript_text=args.transcript_text,
            enable_gemini=not args.disable_gemini,
            force=args.force,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    print(json.dumps({"success": False, "failed_stage": "parse_failed", "error": "--url support is added in the extractor integration task; use --local-video now"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run local runner tests and verify GREEN**

Run:

```bash
PYTHON_BIN=${PYTHON_BIN:-python3.12} ${PYTHON_BIN:-python3.12} -m pytest \
  tests/python/test_video_distillation_skill.py::VideoDistillationLocalRunTest -q
```

Expected: PASS or one skip if ffmpeg is unavailable.

- [ ] **Step 4: Commit local runner**

```bash
git add video-distillation/scripts/distill_video.py tests/python/test_video_distillation_skill.py
git commit -m "feat: add local video distillation runner"
```

---

### Task 5: External Extractor And Gemini Integration Surface

**Files:**
- Modify: `video-distillation/scripts/distill_video.py`
- Modify: `video-distillation/references/extraction-tool-contract.md`
- Test: `tests/python/test_video_distillation_skill.py`

**Interfaces:**
- Consumes:
  - `run_local_distillation(...) -> dict`
  - external extractor path and env defaults from design.
- Produces:
  - `run_url_distillation(url: str, output_root: Path, run_id: str, external_video_workflow_root: Path, dotenv_path: Path, enable_gemini: bool = True, force: bool = False) -> dict[str, Any]`, where `url` may be a copied social share-text blob containing a URL.
  - `extract_with_external_tool(url_or_share_text: str, run_dir: Path, external_video_workflow_root: Path, dotenv_path: Path) -> dict[str, Any]`

- [ ] **Step 1: Use the existing RED tests for URL failure and no secret leakage**

Task 1 already adds `VideoDistillationExtractorContractTest` to `tests/python/test_video_distillation_skill.py`. Do not append a duplicate class. Keep the existing no-network assertions, the exact default extractor path string, the copied share-text fake-extractor acquisition path, and the no-`account-distillation/` dependency.

Historical seed for the contract shape:

```python
class VideoDistillationExtractorContractTest(unittest.TestCase):
    def test_url_distillation_records_import_failure_without_live_api(self):
        from distill_video import run_url_distillation

        with tempfile.TemporaryDirectory() as tmp:
            result = run_url_distillation(
                url="https://v.douyin.com/NoNetworkFixture/",
                output_root=Path(tmp) / "runs",
                run_id="20260705_120002_url_failure",
                external_video_workflow_root=Path(tmp) / "missing_video_workflow",
                dotenv_path=Path(tmp) / ".env",
                enable_gemini=False,
                force=True,
            )

            out = Path(result["output_dir"])
            self.assertFalse(result["success"])
            self.assertEqual("extractor_import_failed", result["failed_stage"])
            status = (out / "00_source" / "source_status.md").read_text(encoding="utf-8")
            self.assertIn("extractor_import_failed", status)
            self.assertNotIn("XIAOLVFANG_API_TOKEN", status)
```

- [ ] **Step 2: Run extractor contract test and verify RED**

Run:

```bash
PYTHON_BIN=${PYTHON_BIN:-python3.12} ${PYTHON_BIN:-python3.12} -m pytest \
  tests/python/test_video_distillation_skill.py::VideoDistillationExtractorContractTest -q
```

Expected: FAIL with `ImportError` for `run_url_distillation`.

- [ ] **Step 3: Add extractor integration functions to `distill_video.py`**

Implementation note: the failure status written for extractor import/acquisition failures must mention `references/extraction-tool-contract.md` and `social_media_content_extractor_tool.py`, must not mention or require `account-distillation/`, and must not leak token/env names or secret values.

Insert these functions before `main()`:

```python
def load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
            os.environ.setdefault(key, value.strip().strip('"').strip("'"))


def extract_with_external_tool(
    url: str,
    run_dir: Path,
    external_video_workflow_root: Path,
    dotenv_path: Path,
) -> dict[str, Any]:
    package_root = external_video_workflow_root / "backend" / "video_workflow"
    if not package_root.is_dir():
        return {"success": False, "failed_stage": "extractor_import_failed", "error": f"package root not found: {package_root}"}
    load_env_file(dotenv_path)
    if str(package_root) not in sys.path:
        sys.path.insert(0, str(package_root))
    try:
        from custom_tools.extract_content.social_media_content_extractor_tool import SocialMediaContentExtractorTool
    except Exception as exc:
        return {"success": False, "failed_stage": "extractor_import_failed", "error": type(exc).__name__}
    result = SocialMediaContentExtractorTool()._run(
        url=url,
        enable_transcript=True,
        enable_video_analysis=False,
        output_dir=str(run_dir / "00_source" / "extractor"),
        save_video=True,
    )
    write_json(run_dir / "00_source" / "extract_result.json", result)
    if not result.get("success"):
        return {"success": False, "failed_stage": "parse_failed", "error": str(result.get("error") or "parse failed")}
    return result


def run_url_distillation(
    url: str,
    output_root: Path,
    run_id: str,
    external_video_workflow_root: Path,
    dotenv_path: Path,
    enable_gemini: bool = True,
    force: bool = False,
) -> dict[str, Any]:
    del enable_gemini, force
    run_dir = make_run_dir(output_root, run_id, url)
    write_text(run_dir / "00_source" / "source_input.txt", url)
    extracted = extract_with_external_tool(url, run_dir, external_video_workflow_root, dotenv_path)
    if not extracted.get("success"):
        return _failure(run_dir, extracted.get("failed_stage", "parse_failed"), str(extracted.get("error", "extractor failed")))
    video_path = Path(str(extracted.get("video_file") or extracted.get("video_local_path") or ""))
    if not video_path.is_file():
        return _failure(run_dir, "download_failed", "extractor succeeded but no local video path was found")
    return run_local_distillation(
        local_video=video_path,
        output_root=output_root,
        run_id=run_id,
        transcript_text=str(extracted.get("transcript") or ""),
        enable_gemini=False,
        force=True,
    )
```

Then replace the `--url` branch in `main()` with:

```python
    if args.url:
        run_id = args.run_id or f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_slug(args.url)}"
        result = run_url_distillation(
            url=args.url,
            output_root=Path(args.output_root).expanduser(),
            run_id=run_id,
            external_video_workflow_root=Path(args.external_video_workflow_root).expanduser(),
            dotenv_path=Path(args.dotenv_path).expanduser(),
            enable_gemini=not args.disable_gemini,
            force=args.force,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
```

- [ ] **Step 4: Run extractor contract test and verify GREEN**

Run:

```bash
PYTHON_BIN=${PYTHON_BIN:-python3.12} ${PYTHON_BIN:-python3.12} -m pytest \
  tests/python/test_video_distillation_skill.py::VideoDistillationExtractorContractTest -q
```

Expected: PASS.

- [ ] **Step 5: Commit extractor integration surface**

```bash
git add video-distillation/scripts/distill_video.py video-distillation/references/extraction-tool-contract.md tests/python/test_video_distillation_skill.py
git commit -m "feat: add video extractor integration surface"
```

---

### Task 6: Compile Smoke Test

**Files:**
- Modify: `package.json`
- Test: `tests/python/test_video_distillation_skill.py`

**Interfaces:**
- Consumes: standalone `video-distillation/` skill and scripts.
- Produces: package compile coverage for new scripts.

- [ ] **Step 1: Add new scripts to `package.json` py_compile command**

Append these paths inside the existing `scripts.test` command:

```text
video-distillation/scripts/build_video_distillation_report.py video-distillation/scripts/distill_video.py
```

- [ ] **Step 2: Run full video-distillation tests**

Run:

```bash
PYTHON_BIN=${PYTHON_BIN:-python3.12} ${PYTHON_BIN:-python3.12} -m pytest tests/python/test_video_distillation_skill.py -q
```

Expected: PASS or one local-video test skip if ffmpeg is unavailable.

- [ ] **Step 3: Run skill validation**

Run:

```bash
python /Users/june2/.codex/skills/.system/skill-creator/scripts/quick_validate.py video-distillation
```

Expected: PASS.

- [ ] **Step 4: Run package compile smoke test**

Run:

```bash
npm test
```

Expected: exit 0.

- [ ] **Step 5: Commit smoke coverage**

```bash
git add package.json
git commit -m "chore: add video distillation smoke coverage"
```

---

### Task 7: Manual Fixture Run And Final Review

**Files:**
- Runtime output only under `output/video_distillation/`
- No source file changes expected unless verification exposes a defect.

**Interfaces:**
- Consumes: `video-distillation/scripts/distill_video.py`.
- Produces: one local fixture run directory proving the end-to-end no-network path.

- [ ] **Step 1: Generate a local fixture video**

Run:

```bash
mkdir -p output/video_distillation_fixtures
ffmpeg -y \
  -f lavfi -i color=c=black:s=320x568:d=2 \
  -vf "drawtext=text='HOOK':fontcolor=white:fontsize=42:x=30:y=80" \
  -pix_fmt yuv420p \
  output/video_distillation_fixtures/tiny_hook.mp4
```

Expected: `output/video_distillation_fixtures/tiny_hook.mp4` exists. If `ffmpeg` is unavailable, skip this manual run and record that final verification used automated tests only.

- [ ] **Step 2: Run the local distiller**

Run:

```bash
python video-distillation/scripts/distill_video.py \
  --local-video output/video_distillation_fixtures/tiny_hook.mp4 \
  --transcript-text "先看这个结果。然后解释原因。最后评论关键词。" \
  --output-root output/video_distillation \
  --run-id 20260705_manual_tiny_hook \
  --disable-gemini \
  --force
```

Expected: JSON with `"success": true` and `output_dir` ending in `output/video_distillation/20260705_manual_tiny_hook`.

- [ ] **Step 3: Inspect required manual run artifacts**

Run:

```bash
python - <<'PY'
from pathlib import Path
required = [
    "00_source/media_info.json",
    "01_media/video.mp4",
    "02_transcript/transcript.txt",
    "03_keyframes/keyframe_index.json",
    "05_copy/copy_logic.yaml",
    "06_video_logic/beat_timeline.json",
    "07_production_logic/production_logic.yaml",
    "08_synthesis/recipe_seed.yaml",
    "evidence_map.json",
    "artifact_manifest.json",
]
root = Path("output/video_distillation/20260705_manual_tiny_hook")
missing = [item for item in required if not (root / item).is_file()]
if missing:
    raise SystemExit(f"missing artifacts: {missing}")
print("manual fixture artifacts ok")
PY
```

Expected: `manual fixture artifacts ok`.

- [ ] **Step 4: Confirm no active capsule or root skill was modified for distillation**

Run:

```bash
git diff --name-only HEAD -- capsules skill.md
```

Expected: no output.

- [ ] **Step 5: Final focused verification**

Run:

```bash
PYTHON_BIN=${PYTHON_BIN:-python3.12} ${PYTHON_BIN:-python3.12} -m pytest tests/python/test_video_distillation_skill.py -q
python /Users/june2/.codex/skills/.system/skill-creator/scripts/quick_validate.py video-distillation
npm test
```

Expected: all commands exit 0, with only documented skips if ffmpeg is unavailable.

- [ ] **Step 6: Report final status**

Summarize:

- created standalone skill path;
- tests run and results;
- manual fixture output path if generated;
- note that live URL/Gemini calls were not used in tests;
- note any API availability issues separately from local skill correctness.
