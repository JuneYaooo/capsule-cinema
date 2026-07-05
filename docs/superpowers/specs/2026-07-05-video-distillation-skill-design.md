# Standalone Video Distillation Skill Design

## Goal

Create a standalone `video-distillation/` skill inside this repository for deep video-level distillation. The skill must not merge into the root Capsule Cinema `skill.md`, must not write into `capsules/`, and must not store account-specific run outputs in the skill source directory.

The skill turns one selected social video into a source-grounded production playbook. It must distill not only content metadata, but also:

- full copywriting logic;
- whole-video narrative logic;
- visual style and frame grammar;
- motion, editing, and animation logic;
- audio, voice, TTS, BGM, and SFX logic;
- implementation route: whether the reusable version needs AI video generation, AI image generation, digital human talking head, TTS, screen recording, local card rendering, motion graphics, live footage, manual editing, or a hybrid pipeline.

This skill is an evidence layer between `account-distillation/` and future capsule creation. `account-distillation/` finds accounts and winner posts; `video-distillation/` deeply analyzes selected winner videos; only a later explicit promotion step may turn distilled lessons into a capsule.

## Recommended Approach

Use a new standalone skill folder:

```text
video-distillation/
├── SKILL.md
├── agents/
│   └── openai.yaml
├── references/
│   ├── video-distillation-protocol.md
│   ├── output-schema.md
│   ├── gemini-video-analysis-prompts.md
│   └── extraction-tool-contract.md
└── scripts/
    ├── distill_video.py
    └── build_video_distillation_report.py
```

This is better than adding more logic to `account-distillation/` because it keeps account research separate from single-video production-route reverse engineering. It is also better than adding it to Capsule runtime because distillation is a research/evidence task, not a production recipe until explicitly promoted.

## Skill Boundary

`video-distillation/` owns:

- deep analysis of a single social video or a small list of selected winner videos;
- evidence collection through the existing social-media extractor, local video paths, Gemini video analysis, ffmpeg keyframes, transcription, and structured synthesis;
- reusable production-route diagnosis and recipe seed output.

`video-distillation/` does not own:

- broad account scouting or winner ranking;
- creating or editing active capsule packages;
- generating a final video by default;
- storing raw account/video evidence inside the skill folder.

Run outputs land under:

```text
output/video_distillation/<YYYYMMDD_HHMMSS>_<slug>/
```

## Evidence Depth Levels

Each run must declare the highest completed level:

```text
V0_metadata_only
Title, caption, tags, stats, and source URL only. No confident visual, audio, pacing, or production-route claims.

V1_media_acquired
Local video, cover, raw extractor JSON, and media info are available.

V2_transcript_ready
Speech/subtitle transcript is available and can support copy/script analysis.

V3_keyframe_ready
Opening frames and representative keyframes/contact sheet are available.

V4_multimodal_reviewed
Gemini-class full-video analysis and keyframe visual analysis are available.

V5_production_logic_distilled
Visual style, motion, audio, copy, narrative logic, and implementation route are explicitly classified with evidence links.

V6_recipe_seed_ready
The run includes a reusable recipe seed that can guide future production without copying source identity, source script, or source frames.
```

The default target for user-facing "deep distillation" is `V6_recipe_seed_ready`. If a tool fails, the run still writes partial artifacts and marks the blocked layer.

## Input Contract

The primary command accepts:

- `--url`: social share/full URL or copied share text.
- `--local-video`: optional local video path when platform parsing fails or source media is already available.
- `--output-root`: optional base output directory, defaulting to `output/video_distillation`.
- `--external-video-workflow-root`: default `/Users/june2/code/github/video_workflow`.
- `--dotenv-path`: default `/Users/june2/code/github/video_workflow/.env`.
- `--enable-gemini`: default true when credentials are available.
- `--enable-transcript`: default true.
- `--frame-plan`: default `opening_plus_representative`, extracting first frame, 1s, 3s, 5s, 8s, midpoints, proof/payoff candidates, and ending.
- `--analysis-depth`: `quick`, `standard`, or `deep`; default `deep`.

The extractor integration must use:

```text
/Users/june2/code/github/video_workflow/backend/video_workflow/custom_tools/extract_content/social_media_content_extractor_tool.py
```

The integration should import only the necessary extractor module and run with Python 3.12 or the configured `PYTHON_BIN`, avoiding global imports that pull unrelated video generation tools when possible.

## Output Layout

Each run writes:

```text
output/video_distillation/<run_id>/
├── 00_source/
│   ├── source_input.txt
│   ├── extract_result.json
│   ├── media_info.json
│   └── source_status.md
├── 01_media/
│   ├── video.mp4
│   └── cover.*
├── 02_transcript/
│   ├── transcript.txt
│   └── transcript_analysis.md
├── 03_keyframes/
│   ├── frames/
│   ├── contact_sheet.jpg
│   ├── keyframe_index.json
│   └── keyframe_analysis.md
├── 04_gemini/
│   ├── video_analysis.md
│   └── video_analysis.json
├── 05_copy/
│   ├── copy_analysis.md
│   └── copy_logic.yaml
├── 06_video_logic/
│   ├── narrative_logic.md
│   ├── beat_timeline.json
│   └── retention_logic.yaml
├── 07_production_logic/
│   ├── production_logic.yaml
│   ├── modality_breakdown.json
│   └── implementation_playbook.md
├── 08_synthesis/
│   ├── video_distillation.md
│   ├── reusable_patterns.md
│   └── recipe_seed.yaml
├── evidence_map.json
└── artifact_manifest.json
```

Missing layers must still be represented in `artifact_manifest.json` and `evidence_map.json` with status `missing`, `failed`, or `limited`.

## Core Analysis Artifacts

### Copy Logic

`05_copy/copy_logic.yaml` must deeply analyze all available copy layers:

- source title/caption;
- hashtags and tag strategy;
- visible cover/opening text;
- subtitle/OCR text;
- spoken opening;
- full transcript;
- CTA and comment driver;
- risk words and claims that require proof.

It must output:

```yaml
schema_version: capsule_cinema.video_copy_logic.v1
evidence_level: V2_transcript_ready
hook:
  exact_observed_text:
  spoken_opening:
  visible_opening:
  mechanism:
  viewer_pressure:
  curiosity_gap:
promise:
  what_viewer_expects:
  when_promise_is_opened:
  when_promise_is_paid_off:
script_structure:
  beats:
    - time_range:
      role:
      transcript_evidence:
      visual_evidence:
      retention_function:
copy_devices:
  specificity:
  contrast:
  numbers:
  identity_address:
  risk_or_loss:
  proof_language:
cta:
  observed:
  type:
  timing:
  comment_driver:
rewrite_template:
  reusable_hook_formula:
  reusable_script_template:
  forbidden_to_copy:
confidence:
  transcript_completeness:
  unsupported_claims:
```

The output must not copy the source script as a reusable template. It should abstract the mechanism and include a fill-in template.

### Whole Video Logic

`06_video_logic/narrative_logic.md` and `beat_timeline.json` must explain how the entire video works, not just the opening:

- first-frame stop reason;
- 0-1s, 1-3s, 3-5s, 5-8s opening audit;
- setup;
- promise;
- proof/demo/story progression;
- tension or information gap;
- transition points;
- payoff;
- CTA or ending move;
- retention mechanics by segment;
- which visual/audio/copy elements carry each beat.

The beat timeline should use a structure like:

```json
{
  "schema_version": "capsule_cinema.video_beat_timeline.v1",
  "beats": [
    {
      "time_range": "0:00-0:03",
      "role": "hook",
      "copy_evidence": "",
      "visual_evidence": "",
      "audio_evidence": "",
      "retention_function": "",
      "implementation_dependency": ""
    }
  ],
  "logic_summary": {
    "core_loop": "",
    "viewer_question_opened": "",
    "viewer_question_closed": "",
    "main_retention_device": "",
    "weak_points": []
  }
}
```

### Visual And Motion Logic

`07_production_logic/production_logic.yaml` must classify:

- visual medium: live action, AI animation, AI storyboards, screen recording, text cards, digital human, product demo, hybrid;
- aspect ratio and framing;
- character presence and whether a face/digital human is functionally required;
- scene density and environment logic;
- color palette, lighting, texture, typography, and subtitle style;
- camera movement and edit rhythm;
- animation style, transitions, overlays, arrows, zooms, UI annotations, kinetic typography, and caption timing.

It must distinguish `observed` from `inferred`. For example, it may observe a talking head and infer that digital human is a possible reproduction route, but it must not claim the source used a digital human unless evidence supports it.

### Production Route And Modality Breakdown

The system must answer the practical implementation question:

```yaml
production_route:
  needs_ai_image_generation:
    value: true
    reason:
    evidence:
  needs_ai_video_generation:
    value: false
    reason:
    evidence:
  needs_digital_human:
    value: false
    reason:
    evidence:
  needs_tts:
    value: true
    reason:
    evidence:
  needs_original_voiceover:
    value: false
    reason:
    evidence:
  needs_screen_recording:
    value: false
    reason:
    evidence:
  needs_local_card_rendering:
    value: false
    reason:
    evidence:
  needs_motion_graphics:
    value: true
    reason:
    evidence:
  needs_subtitle_burn_in:
    value: true
    reason:
    evidence:
  needs_bgm:
    value: true
    reason:
    evidence:
  needs_sfx:
    value: optional
    reason:
    evidence:
  needs_manual_editing:
    value: true
    reason:
    evidence:
```

It must also output:

- `cheapest_viable_route`;
- `highest_fidelity_route`;
- `recommended_route`;
- `required_materials`;
- `replaceable_materials`;
- `hardest_part_to_reproduce`;
- `quality_risks`;
- `do_not_copy`.

This makes the distillation directly useful for production planning without forcing immediate video generation.

## Gemini And Keyframe Prompts

The skill should include reference prompts for:

1. Full-video Gemini review.
2. Opening audit.
3. Keyframe/contact-sheet review.
4. Copy and transcript logic analysis.
5. Production route classification.

The prompts must force evidence-backed answers:

- quote or cite transcript snippets only briefly;
- reference timestamps and frame filenames;
- mark uncertainty explicitly;
- separate `observed`, `inferred`, and `recommended`;
- never assert source production tools without evidence.

## Data Flow

1. Create run directory and write `source_input.txt`.
2. Acquire media:
   - use social-media extractor for URL/share text;
   - use `--local-video` if provided;
   - copy local media into `01_media/video.mp4`;
   - write structured failure status if parsing or download fails.
3. Probe media with `ffprobe`; write `media_info.json`.
4. Generate or import transcript; write transcript artifacts.
5. Extract keyframes and contact sheet with `ffmpeg`.
6. Run Gemini full-video analysis if enabled and available.
7. Analyze transcript/copy and keyframes into structured artifacts.
8. Build production logic and modality breakdown.
9. Build synthesis report, recipe seed, evidence map, and artifact manifest.

Each step should be restartable: if an artifact already exists and `--force` is not provided, reuse it.

## Error Handling

The runner must never erase partial evidence. On failure it writes:

- `00_source/source_status.md`;
- `artifact_manifest.json`;
- `evidence_map.json`;
- a final JSON result on stdout with `success: false` and a structured `failed_stage`.

Known failure stages:

- `extractor_import_failed`;
- `parse_failed`;
- `download_failed`;
- `ffprobe_failed`;
- `transcript_failed`;
- `keyframe_failed`;
- `gemini_failed`;
- `synthesis_failed`.

If Xiaolvfang parsing returns a server error, the run should record the API failure and suggest `--local-video` fallback.

## Testing Strategy

Use test-first implementation after this design is approved. Tests should not call live APIs.

Focused tests should cover:

- skill folder exists and is independent from root `skill.md` and `capsules/`;
- `distill_video.py --local-video <fixture>` creates the required run layout;
- media info and keyframe extraction work on a generated tiny mp4 fixture;
- partial failure writes manifest and evidence map;
- copy logic schema includes hook, promise, script structure, CTA, rewrite template, and confidence;
- beat timeline includes full-video logic fields, not just opening fields;
- production logic schema includes AI video, digital human, TTS, screen recording, motion graphics, subtitles, BGM, SFX, manual editing, cheapest route, high-fidelity route, and recommended route;
- generated recipe seed excludes source URL, source account identity, copied script, signed media URLs, and local private token values;
- `account-distillation/` documentation points selected winner-video completion to `video-distillation/` without importing its code directly.

Manual verification should run one local fixture and one real URL when API availability allows.

## Acceptance Criteria

- A standalone `video-distillation/` skill exists with `SKILL.md`, `agents/openai.yaml`, references, and scripts.
- The skill can be invoked directly for a URL/share text or local video path.
- The runner writes the required output layout under `output/video_distillation/`.
- The deep report includes copy logic, whole-video logic, visual style, motion style, audio logic, and production-route classification.
- All major claims are tied to timestamps, transcript snippets, frame paths, media info, or marked inference.
- No raw run evidence is stored inside `video-distillation/`.
- No active capsule is modified.
- Tests pass without live API calls.
