# Life Sim Snow Destiny Girl Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and render a horizontal `life_sim` release package for a cinematic anime "雪场天命少女"爽文人生副本 inspired by the Gu Ailing/Eileen Gu archetype without impersonation.

**Architecture:** Create one project-specific renderer under `output/life_sim_snow_destiny_girl/` that preserves the `life_sim` local-script gates, emits a storyboard package with per-micro-cut Image2 prompts, renders a prototype climax frame before batch work, then assembles opening, TTS, keyframe motion, BGM, QA, and release manifests. Keep reusable capsule rules in the existing SQLite capsule and avoid changing shared runtime unless a blocker is proven.

**Tech Stack:** Python 3.12, PIL/Pillow, ffmpeg/ffprobe, existing `GptImage2Tool`, existing `UniversalTTSTool`/MiniMax path, `life_shaker_opening_renderer.py`, `scripts/capsule_store.py`, `scripts/local_video_qa.py`, `scripts/visible_copy_lint.py`, unittest/pytest-compatible tests.

## Global Constraints

- Capsule: `life_sim`.
- Aspect ratio: horizontal `16:9`, using the capsule default.
- Runtime: under 5 minutes, target 4:00-4:30.
- Story shape: from birth to a major competition climax.
- Tone: pure high-energy "爽文", not reflective documentary.
- Visual style: attractive, cinematic anime, strong impact, sports-anime energy.
- Subject framing: Gu Ailing/Eileen Gu-inspired, but not a deepfake, not a voice clone, not a simulated real statement from her.
- Do not recreate Gu Ailing's exact face, voice, signature, endorsements, real interviews, or private speech.
- Do not imply she approved, narrated, sponsored, or appeared in the video.
- Do not use real Olympic, FIS, brand, sponsor, school, platform, or team logos.
- Do not ask image generation to render Chinese text, UI text, medals text, scoreboards, or news comments.
- Viewer-facing on-screen text should use the fictional identity: "雪场天命少女".
- Opening shaker text and top scene labels only; no bottom body narration subtitles unless separately requested.
- Every 1-3 second micro-cut must introduce a new state: new age, new location, new posture, new pressure, new action, or new emotional turn.
- Generate a strong representative prototype frame for the final-jump climax before batching the full image set.
- Stop rather than silently switching to an unapproved voice or local fallback if TTS fails.
- Final QA requires `life_sim` dry-run contract report, ffprobe, local decode, `local_video_qa.py`, `visible_copy_lint.py`, unique image path/hash report, alignment audit, compliance review, and release manifest.

---

## File Structure

- Create `output/life_sim_snow_destiny_girl/render_snow_destiny_video.py`: project-specific renderer, story constants, prompt generation, prototype generation, Image2 keyframe generation, TTS, opening render, assembly, QA files, manifests.
- Create `tests/python/test_snow_destiny_life_sim_contract.py`: contract tests for story shape, safety boundaries, aspect ratio, duration estimate, micro-cut density, viewer-visible text, and prompt rules.
- Create `docs/superpowers/plans/2026-06-29-life-sim-snow-destiny-girl.md`: this execution plan.
- Produce runtime artifacts under `output/life_sim_snow_destiny_girl/release/snow_destiny_girl_20260629_v1/`.

---

### Task 1: Renderer Skeleton And Story Contract

**Files:**
- Create: `output/life_sim_snow_destiny_girl/render_snow_destiny_video.py`
- Create: `tests/python/test_snow_destiny_life_sim_contract.py`

**Interfaces:**
- Produces: `Scene` dataclass with fields `slug: str`, `title: str`, `narration: str`, `image_prompt: str`, `camera: str`, `intensity: str`.
- Produces: constants `WIDTH = 1920`, `HEIGHT = 1080`, `CAPSULE_NAME = "life_sim"`, `BODY_SUBTITLES_ENABLED = False`, `TARGET_DURATION_RANGE = (240, 270)`.
- Produces: `SCENES: list[Scene]`, `OPENING_TEXT: str`, `RESULT_TITLE: str`, `RESULT_TAIL: str`, `OPENING_TERMS: list[str]`.
- Later tasks consume: `SCENES`, `STYLE_BASE`, `build_viewer_visible_lines()`, `clean_char_count(text: str) -> int`.

- [ ] **Step 1: Write the failing story contract tests**

Add this exact test file:

```python
import importlib.util
import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "output" / "life_sim_snow_destiny_girl" / "render_snow_destiny_video.py"


def load_module():
    spec = importlib.util.spec_from_file_location("snow_destiny_video", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class SnowDestinyLifeSimContractTest(unittest.TestCase):
    def test_horizontal_life_sim_defaults(self):
        module = load_module()
        self.assertEqual(module.CAPSULE_NAME, "life_sim")
        self.assertEqual((module.WIDTH, module.HEIGHT), (1920, 1080))
        self.assertEqual(module.ASPECT_RATIO, "16:9")
        self.assertEqual(module.TARGET_DURATION_RANGE, (240, 270))
        self.assertFalse(module.BODY_SUBTITLES_ENABLED)
        self.assertLess(module.TARGET_DURATION_RANGE[1], 300)

    def test_opening_uses_fictional_identity(self):
        module = load_module()
        self.assertTrue(module.OPENING_TEXT.startswith("每天一个模拟人生"))
        self.assertIn("雪场天命少女", module.OPENING_TEXT)
        self.assertEqual(module.RESULT_TITLE, "雪场天命少女")
        self.assertIn("最终一跳", module.OPENING_TERMS)
        visible = "\n".join(module.build_viewer_visible_lines())
        self.assertIn("雪场天命少女", visible)
        self.assertNotIn("谷爱凌本人", visible)
        self.assertNotIn("Eileen Gu本人", visible)

    def test_story_runs_from_birth_to_climax(self):
        module = load_module()
        titles = [scene.title for scene in module.SCENES]
        joined = "\n".join(scene.title + scene.narration for scene in module.SCENES)
        self.assertGreaterEqual(len(module.SCENES), 18)
        self.assertLessEqual(len(module.SCENES), 26)
        for marker in ["出生", "三岁", "九岁", "全服质疑", "摔倒重置", "赛前夜", "最终一跳", "系统结算"]:
            self.assertIn(marker, joined)
        self.assertIn("最终一跳", titles[-3:])

    def test_second_person_sports_anime_s爽文_voice(self):
        module = load_module()
        narration = "\n".join(scene.narration for scene in module.SCENES)
        self.assertGreaterEqual(narration.count("你"), 70)
        self.assertIn("通关", narration)
        self.assertIn("系统", narration)
        self.assertIn("最高难度", narration)
        self.assertNotIn("所以我们要", narration)
        self.assertNotIn("人生道理", narration)

    def test_prompts_avoid_real_person_and_text_rendering(self):
        module = load_module()
        all_prompts = "\n".join([module.STYLE_BASE] + [scene.image_prompt for scene in module.SCENES])
        forbidden = ["Olympic logo", "FIS logo", "Red Bull", "Louis Vuitton", "Tiffany", "Stanford logo", "scoreboard text"]
        for term in forbidden:
            self.assertNotIn(term, all_prompts)
        self.assertIn("No readable text", module.STYLE_BASE)
        self.assertIn("not a portrait of any real public figure", module.STYLE_BASE)
        self.assertNotRegex(all_prompts, re.compile(r"exact.*Gu|谷爱凌.*脸|Eileen Gu.*face", re.I))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/python/test_snow_destiny_life_sim_contract.py -q`

Expected: FAIL because `output/life_sim_snow_destiny_girl/render_snow_destiny_video.py` does not exist.

- [ ] **Step 3: Create minimal renderer skeleton and story constants**

Create `output/life_sim_snow_destiny_girl/render_snow_destiny_video.py` with imports, constants, `Scene`, `clean_char_count`, `build_viewer_visible_lines`, `STYLE_BASE`, opening fields, and `SCENES`. Include 20-22 scenes so the first passing version already covers birth, age three, childhood training, age nine, pressure, reset, pre-night, final jump, and settlement.

Use this constant block exactly:

```python
WIDTH, HEIGHT = 1920, 1080
FPS = 30
ASPECT_RATIO = "16:9"
CAPSULE_NAME = "life_sim"
CAPSULE_VERSION_EXPECTED = 17
TARGET_DURATION_RANGE = (240, 270)
BODY_SUBTITLES_ENABLED = False
MICRO_SHOT_SECONDS = 2.05
MIN_MICRO_SHOTS_PER_SCENE = 3
DISTINCT_IMAGE_PER_MICRO_SHOT_REQUIRED = True
VERSION = "snow_destiny_girl_20260629_v1"
RUN_ROOT = ROOT / "output" / "life_sim_snow_destiny_girl"
RELEASE = RUN_ROOT / "release" / VERSION
PUBLIC = RELEASE / "public"
WORK = RELEASE / "work"
INTERNAL = RELEASE / "internal"
TECHNICAL = RELEASE / "technical"
QA = RELEASE / "qa"
```

Use this style anchor exactly:

```python
STYLE_BASE = (
    "Use case: cinematic anime sports-drama life-simulation video. Asset type: horizontal 16:9 key frame. "
    "A fictional young Chinese/Chinese-American freeski heroine, athletic and sharp-eyed, long dark hair tied high or tucked into helmet, "
    "white and silver ski suit with small red accents, red goggles, no logos, not a portrait of any real public figure. "
    "High-end hand-drawn feature-animation frame, sports-anime energy, dramatic snow glare, speed trails, powder bursts, "
    "strong foreground-midground-background composition, cinematic depth, cold blue shadows and gold climax light. "
    "No readable text, no Chinese characters, no English words, no logos, no watermark, no real event marks, no scoreboards, no sponsor marks."
)
```

- [ ] **Step 4: Run tests and commit**

Run: `python -m pytest tests/python/test_snow_destiny_life_sim_contract.py -q`

Expected: PASS.

Commit:

```bash
git add output/life_sim_snow_destiny_girl/render_snow_destiny_video.py tests/python/test_snow_destiny_life_sim_contract.py
git commit -m "feat: add snow destiny life_sim story contract"
```

---

### Task 2: Storyboard Package And `life_sim` Dry-Run Gate

**Files:**
- Modify: `output/life_sim_snow_destiny_girl/render_snow_destiny_video.py`
- Modify: `tests/python/test_snow_destiny_life_sim_contract.py`

**Interfaces:**
- Consumes: `SCENES`, `Scene`, `MICRO_SHOT_SECONDS`.
- Produces: `micro_shot_count(duration: float) -> int`.
- Produces: `estimate_scene_duration(scene: Scene) -> float`.
- Produces: `make_scene_prompt(scene: Scene, scene_index: int, shot_index: int, shot_count: int) -> str`.
- Produces: `build_storyboard_package() -> dict`.
- Produces: `write_storyboard_package() -> Path`.
- Produces: `write_life_sim_params(storyboard_path: Path) -> Path`.
- Produces: `run_life_sim_dry_run() -> Path`.

- [ ] **Step 1: Add failing storyboard tests**

Append these tests:

```python
    def test_storyboard_package_has_per_micro_cut_prompts(self):
        module = load_module()
        package = module.build_storyboard_package()
        self.assertEqual(package["capsule"], "life_sim")
        self.assertEqual(package["aspect_ratio"], "16:9")
        self.assertEqual(package["body_subtitles_enabled"], False)
        micro_cuts = package["micro_cuts"]
        self.assertGreaterEqual(len(micro_cuts), 110)
        self.assertLessEqual(len(micro_cuts), 145)
        self.assertTrue(all(item["image_prompt"] for item in micro_cuts))
        self.assertTrue(all(item["duration"] <= 3.0 for item in micro_cuts))
        self.assertTrue(all("No readable text" in item["image_prompt"] for item in micro_cuts))

    def test_life_sim_params_acknowledge_generation_budget(self):
        module = load_module()
        package = module.build_storyboard_package()
        params = module.build_life_sim_params(package)
        self.assertTrue(params["generation_budget_ack"])
        self.assertEqual(params["aspect_ratio"], "16:9")
        self.assertEqual(params["target_duration_seconds"], 255)
        self.assertIn("config", params)
        self.assertEqual(params["config"]["visual_generation_type"], "unique_image2_keyframes_with_micro_cuts")
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/python/test_snow_destiny_life_sim_contract.py -q`

Expected: FAIL because the storyboard and params functions do not exist.

- [ ] **Step 3: Implement storyboard package and dry-run helpers**

Implement deterministic scene duration estimates using `max(7.5, clean_char_count(scene.narration) / 4.25 + 0.45)`, then split each scene into micro-cuts no longer than 3.0 seconds. Implement `build_life_sim_params(package)` with:

```python
{
    "topic": "雪场天命少女的一生",
    "aspect_ratio": "16:9",
    "target_duration_seconds": 255,
    "generation_budget_ack": True,
    "storyboard": package,
    "config": {
        "aspect_ratio": "16:9",
        "visual_generation_type": "unique_image2_keyframes_with_micro_cuts",
        "micro_cut_visual_source": "unique_image2_keyframe_per_cut",
        "distinct_body_image_per_micro_cut_required": True,
        "body_image_content_hash_unique_required": True,
        "body_subtitles_default": False,
        "output_contract": {"bgm": "external", "clip_audio": "silent", "on_frame_text": "opening_and_scene_labels_only", "subtitle": "none", "voice": "unified_tts"},
        "opening_template": {"tts_required_lines": ["series_title", "episode_topic"], "duration_seconds": {"default": 3.9}},
        "micro_cut_seconds": {"min": 1.0, "ideal": [1.8, 2.25], "max": 3.0},
    },
}
```

Implement `run_life_sim_dry_run()` with command:

```python
[
    sys.executable,
    str(ROOT / "capsule_assets" / "life_sim" / "scripts" / "life_sim_executor.py"),
    "--topic",
    "雪场天命少女的一生",
    "--params",
    str(params_path),
    "--output-dir",
    str(RELEASE),
    "--dry-run",
]
```

- [ ] **Step 4: Run tests and dry-run**

Run: `python -m pytest tests/python/test_snow_destiny_life_sim_contract.py -q`

Expected: PASS.

Run: `python output/life_sim_snow_destiny_girl/render_snow_destiny_video.py --stage dry-run`

Expected: writes `release/snow_destiny_girl_20260629_v1/reports/run_notes.json` and `artifact_manifest.json`; exits `0`.

- [ ] **Step 5: Commit**

```bash
git add output/life_sim_snow_destiny_girl/render_snow_destiny_video.py tests/python/test_snow_destiny_life_sim_contract.py output/life_sim_snow_destiny_girl/release/snow_destiny_girl_20260629_v1/reports/run_notes.json
git commit -m "feat: add snow destiny life_sim storyboard gate"
```

---

### Task 3: Prototype Frame And Image Generation Cache

**Files:**
- Modify: `output/life_sim_snow_destiny_girl/render_snow_destiny_video.py`
- Modify: `tests/python/test_snow_destiny_life_sim_contract.py`

**Interfaces:**
- Consumes: `make_scene_prompt`, `build_storyboard_package`.
- Produces: `run_gpt_image2_with_retries(prompt: str, output_path: Path, reference_image_paths: list[str] | None = None, attempts: int = 3) -> str`.
- Produces: `generate_character_reference(force: bool = False) -> Path`.
- Produces: `generate_prototype_frame(force: bool = False) -> Path`.
- Produces: `generate_scene_images(limit: int | None = None, force: bool = False) -> list[dict]`.
- Produces: `cached_image_is_valid(path: Path, aspect_ratio: str = "16:9") -> bool`.

- [ ] **Step 1: Add failing image-flow tests**

Append:

```python
    def test_prototype_targets_final_jump_before_batch(self):
        module = load_module()
        package = module.build_storyboard_package()
        proto = module.select_prototype_micro_cut(package)
        self.assertEqual(proto["scene_title"], "最终一跳")
        self.assertIn("white-sky void", proto["image_prompt"])
        self.assertIn("landing impact", proto["image_prompt"])

    def test_cached_image_validation_rejects_wrong_ratio(self):
        module = load_module()
        from PIL import Image
        workspace = module.RELEASE / "test_cache"
        workspace.mkdir(parents=True, exist_ok=True)
        bad = workspace / "bad.png"
        Image.new("RGB", (900, 1600), "white").save(bad)
        self.assertFalse(module.cached_image_is_valid(bad, "16:9"))
        self.assertFalse(bad.exists())
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/python/test_snow_destiny_life_sim_contract.py -q`

Expected: FAIL because image-flow functions do not exist.

- [ ] **Step 3: Implement prototype-first image flow**

Use `GptImage2Tool` only, mapped through existing environment behavior. Implement `select_prototype_micro_cut(package)` by returning the first micro-cut whose `scene_title == "最终一跳"` and enriching its prompt with:

```text
white-sky void, suspended snow particles, wide low-angle takeoff, red goggles catching electric cyan light, decisive landing impact, sports-anime climax frame
```

Implement `generate_prototype_frame()` so it writes:

```text
output/life_sim_snow_destiny_girl/release/snow_destiny_girl_20260629_v1/work/images/prototype_final_jump.png
output/life_sim_snow_destiny_girl/release/snow_destiny_girl_20260629_v1/technical/prototype_prompt.json
```

Do not call `generate_scene_images()` from the `all` stage until `prototype_final_jump.png` exists and passes `cached_image_is_valid`.

- [ ] **Step 4: Run tests and prototype command**

Run: `python -m pytest tests/python/test_snow_destiny_life_sim_contract.py -q`

Expected: PASS.

Run: `python output/life_sim_snow_destiny_girl/render_snow_destiny_video.py --stage prototype`

Expected: one 16:9 prototype PNG exists. Inspect it manually before batch generation.

- [ ] **Step 5: Commit**

```bash
git add output/life_sim_snow_destiny_girl/render_snow_destiny_video.py tests/python/test_snow_destiny_life_sim_contract.py output/life_sim_snow_destiny_girl/release/snow_destiny_girl_20260629_v1/technical/prototype_prompt.json
git commit -m "feat: add snow destiny prototype image gate"
```

---

### Task 4: TTS, Opening, Motion Assembly, And Micro-Cut QA

**Files:**
- Modify: `output/life_sim_snow_destiny_girl/render_snow_destiny_video.py`
- Modify: `tests/python/test_snow_destiny_life_sim_contract.py`

**Interfaces:**
- Consumes: `SCENES`, generated images, opening assets.
- Produces: `prepare_tts(force: bool = False) -> list[dict]`.
- Produces: `make_opening() -> Path`.
- Produces: `render_scene_video(index: int, scene: Scene) -> dict`.
- Produces: `assemble(force_tts: bool = False, limit: int | None = None) -> Path`.
- Produces: `write_micro_cut_report(segment_records: list[dict]) -> Path`.

- [ ] **Step 1: Add failing assembly contract tests**

Append:

```python
    def test_micro_motion_and_report_contract(self):
        module = load_module()
        self.assertEqual(module.micro_motion(1, 0, 0.0).__class__, tuple)
        self.assertEqual(len(module.micro_motion(1, 0, 0.5)), 3)
        fake_segments = [
            {"slug": "s01", "image_paths": ["/tmp/a.png", "/tmp/b.png"], "max_micro_shot_seconds": 2.1, "distinct_image_per_micro_shot": True}
        ]
        report = module.build_micro_cut_report_payload(fake_segments, {"a": "hash-a", "b": "hash-b"})
        self.assertTrue(report["ok"])
        self.assertEqual(report["body_image_count"], 2)

    def test_opening_assets_exist(self):
        module = load_module()
        self.assertTrue(module.OPENING_RENDERER.exists())
        self.assertTrue(module.OPENING_BG.exists())
        self.assertTrue(module.OPENING_SFX.exists())
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/python/test_snow_destiny_life_sim_contract.py -q`

Expected: FAIL because assembly functions are missing.

- [ ] **Step 3: Implement TTS and opening**

Use the existing `UniversalTTSTool` MiniMax path with `fallback_to_doubao=False` when provider is MiniMax. Use `OPENING_TEXT` for the opening audio and one audio file per scene. Normalize each file to 48 kHz stereo WAV using ffmpeg. Call `life_shaker_opening_renderer.py` with:

```bash
--aspect-ratio 16:9
--result-title 雪场天命少女
--result-tail 的一生
--candidate-terms '["出生异象","三岁上雪","全服质疑","最终一跳","系统通关"]'
--sfx-volume 0.35
```

- [ ] **Step 4: Implement motion assembly**

For each scene, render frames from the unique keyframes with Ken Burns-style `fit_cover`, `micro_motion`, top scene label, contrast/color polish, and no bottom body subtitles. Concatenate opening and body scene clips into `work/video/01_concat.mp4`, then mix low BGM into `public/snow_destiny_girl_16x9.mp4`.

- [ ] **Step 5: Run tests and limited assembly smoke**

Run: `python -m pytest tests/python/test_snow_destiny_life_sim_contract.py -q`

Expected: PASS.

Run with a small image limit after generating enough cached images:

```bash
python output/life_sim_snow_destiny_girl/render_snow_destiny_video.py --stage assemble --limit-scenes 2
```

Expected: a short horizontal MP4 exists for the opening and first two body scenes.

- [ ] **Step 6: Commit**

```bash
git add output/life_sim_snow_destiny_girl/render_snow_destiny_video.py tests/python/test_snow_destiny_life_sim_contract.py
git commit -m "feat: assemble snow destiny life_sim video"
```

---

### Task 5: Release Package, Compliance, And Final Full Render

**Files:**
- Modify: `output/life_sim_snow_destiny_girl/render_snow_destiny_video.py`
- Produce: `output/life_sim_snow_destiny_girl/CURRENT_RELEASE.md`
- Produce: `output/life_sim_snow_destiny_girl/release/snow_destiny_girl_20260629_v1/README.md`
- Produce: `output/life_sim_snow_destiny_girl/release/snow_destiny_girl_20260629_v1/release_manifest.json`
- Produce: `output/life_sim_snow_destiny_girl/release/snow_destiny_girl_20260629_v1/public/platform_copy.txt`
- Produce: `output/life_sim_snow_destiny_girl/release/snow_destiny_girl_20260629_v1/qa/compliance_review.md`

**Interfaces:**
- Consumes: final video, clean concat, visible text, storyboard package, TTS status, image records.
- Produces: `write_release_files(final_video: Path, clean_concat: Path, bgm: Path, segment_records: list[dict], image_records: list[dict]) -> None`.
- Produces: `artifact_manifest.json` with categories `final_video`, `assembly_clean`, `copywriting`, `storyboard`, `visible_copy`, `micro_cut_report`, `compliance_review`, `alignment_audit`, `local_video_qa`, `storyboard_prompt`.

- [ ] **Step 1: Add release manifest tests**

Append:

```python
    def test_public_copy_uses_safe_fictional_framing(self):
        module = load_module()
        copy = module.build_platform_copy()
        self.assertIn("谷爱凌式", copy)
        self.assertIn("虚构动漫人生副本", copy)
        self.assertNotIn("谷爱凌本人", copy)
        self.assertNotIn("真实经历", copy)

    def test_manifest_categories_include_required_qa(self):
        module = load_module()
        manifest = module.build_artifact_manifest_payload(
            final_video="/tmp/final.mp4",
            clean_concat="/tmp/clean.mp4",
            copy_path="/tmp/copy.txt",
            storyboard_path="/tmp/storyboard.json",
            qa_paths={
                "local_video_qa": "/tmp/local_video_qa.json",
                "visible_copy_lint": "/tmp/visible_copy_lint.json",
                "micro_cut_report": "/tmp/micro_cut_report.json",
                "compliance_review": "/tmp/compliance_review.md",
            },
        )
        categories = {item["category"] for item in manifest["artifacts"]}
        for category in ["final_video", "assembly_clean", "copywriting", "storyboard", "local_video_qa", "visible_copy_lint", "micro_cut_report", "compliance_review"]:
            self.assertIn(category, categories)
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/python/test_snow_destiny_life_sim_contract.py -q`

Expected: FAIL because release helper functions do not exist.

- [ ] **Step 3: Implement release helpers**

Implement `build_platform_copy()` returning:

```text
标题：雪场天命少女的一生｜每天一个模拟人生
简介：受谷爱凌式雪场爽文人生启发的虚构动漫人生副本。不是本人经历复刻，也不是本人发言。看一个从出生刷出雪场天赋、一路训练到最后一跳封神的高燃故事。
标签：#模拟人生 #人生副本 #动漫短片 #滑雪 #爽文
```

Implement compliance review with conclusion `Medium-Low`, risk notes for public-figure inspiration, AI-generated anime imagery, no impersonation, no real logos, no real voice clone, no real event footage, and platform copy boundary.

- [ ] **Step 4: Run full render and QA**

Run:

```bash
python output/life_sim_snow_destiny_girl/render_snow_destiny_video.py --stage all
python scripts/local_video_qa.py --run-dir output/life_sim_snow_destiny_girl/release/snow_destiny_girl_20260629_v1 --manifest output/life_sim_snow_destiny_girl/release/snow_destiny_girl_20260629_v1/artifact_manifest.json --aspect-ratio 16:9 --expect-audio --min-duration 240 --require-prompts --output output/life_sim_snow_destiny_girl/release/snow_destiny_girl_20260629_v1/qa/local_video_qa.json
python scripts/visible_copy_lint.py output/life_sim_snow_destiny_girl/release/snow_destiny_girl_20260629_v1/internal/viewer_visible_text.txt output/life_sim_snow_destiny_girl/release/snow_destiny_girl_20260629_v1/public/platform_copy.txt --json > output/life_sim_snow_destiny_girl/release/snow_destiny_girl_20260629_v1/qa/visible_copy_lint.json
```

Expected:

- `public/snow_destiny_girl_16x9.mp4` exists.
- `qa/local_video_qa.json` has `"ok": true`.
- `qa/visible_copy_lint.json` has `"ok": true`.
- `qa/micro_cut_report.json` has `"ok": true`, unique image paths, and unique content hashes.
- Final duration is between 240 and 300 seconds.

- [ ] **Step 5: Record run evidence**

Run:

```bash
python scripts/capsule_store.py record-run-dir --name life_sim --run-dir output/life_sim_snow_destiny_girl/release/snow_destiny_girl_20260629_v1 --topic "雪场天命少女的一生" --qa-report output/life_sim_snow_destiny_girl/release/snow_destiny_girl_20260629_v1/qa/local_video_qa.json
```

Expected: capsule run history records this release as success or needs-review according to QA.

- [ ] **Step 6: Commit final production code and manifests**

```bash
git add output/life_sim_snow_destiny_girl/render_snow_destiny_video.py tests/python/test_snow_destiny_life_sim_contract.py output/life_sim_snow_destiny_girl/CURRENT_RELEASE.md output/life_sim_snow_destiny_girl/release/snow_destiny_girl_20260629_v1/README.md output/life_sim_snow_destiny_girl/release/snow_destiny_girl_20260629_v1/artifact_manifest.json output/life_sim_snow_destiny_girl/release/snow_destiny_girl_20260629_v1/release_manifest.json
git commit -m "feat: render snow destiny life_sim release"
```

---

## Self-Review

- Spec coverage: this plan covers horizontal `life_sim`, under-5-minute runtime, birth-to-climax story, fictional public-figure framing, cinematic anime visuals, prototype-first image generation, no body subtitles, unique Image2 micro-cuts, TTS timing, opening renderer, release package, QA, visible-copy lint, and capsule run evidence.
- Scope: one project-specific video renderer and release package. No shared runtime refactor is included because the existing `life_sim_executor.py` gate can be respected through a storyboard package and project renderer.
- Type consistency: functions consumed by later tasks are introduced in earlier tasks with exact names.
- Placeholder scan: no implementation step relies on unspecified future decisions; each command and expected output is explicit.
