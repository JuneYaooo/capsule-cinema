# Workflow State and Artifacts

This captures the production mechanics that make video work repeatable: reference materials, session memory, capsules, workspace state, and artifact manifests.

## Planning Context Order

Before planning, inspect:

1. Current user instruction.
2. Session reference materials / attachments.
3. Matching active capsule package and its execution mode.
4. Active session memory: locks, rejected ideas, anchors, pitfalls.
5. Current tool registry and active channel policy.

Do not copy an old run just because it once worked. Tool availability, channel policy, API behavior, and capsule contracts can change.

## Reference Materials

Reference materials are session-level content assets. If the session includes attachments, use them before inventing new visual anchors.

Common sources:

| source | Typical usage |
|---|---|
| `user_upload` | character anchor, style reference, cover, direct source media |
| `social_media` | reference video analysis: hook, pacing, shot structure, copy style |
| `web_extract` | article/webpage material for narration |
| `web_search` | reference image/material found during production |
| `ai_generated` | generated character/scene references reused across scenes |

Usage values:

| usage | Meaning |
|---|---|
| `reference` | guide generation/analysis |
| `content` | use directly in the final video |
| `cover` | cover image candidate |
| `ending` | ending/card material |
| `discard` | low-quality or irrelevant material |

Strategy values:

| strategy | Meaning |
|---|---|
| `use_original` | use as-is |
| `text_on_photo` | add text in post |
| `collage` | combine with other assets |
| `ai_generated` | regenerate from this reference |

If a managed runtime provides `manage_attachments.py`, register downloaded/searched/generated reference material through it:

```bash
if [ -f "scripts/manage_attachments.py" ]; then
  python "scripts/manage_attachments.py" add \
    --filename "reference.jpg" \
    --local-path "/absolute/path/reference.jpg" \
    --source "web_search" \
    --usage "reference"
fi
```

After analysis, mark semantics:

```bash
if [ -f "scripts/manage_attachments.py" ]; then
  python "scripts/manage_attachments.py" update \
    <attachment_id> \
    --usage "content" --strategy "use_original" --parsed 1
fi
```

If that wrapper is missing, keep the same fields in `work/inputs/reference_assets.json` under the run root and include the file in `artifact_manifest.json`.

If a reference image exists, prefer passing it through `reference_image_paths` when the approved image tool supports it. If a reference video exists, analyze hook, pacing, shot distribution, and emotional trigger before generating a remake plan.

## Session Memory

Use session memory to avoid losing decisions across turns. If a managed runtime provides `session_memory.py`, use it; otherwise keep `qa/session_memory.json` or `qa/run_notes.md` under the run root.

Track:

- `lock`: approved/planned scene, cover, character, visual direction, or final artifact.
- `reject`: directions the user or QA rejected.
- `pitfall`: concrete issue and where it appeared.
- `anchor`: topic, core metaphor, style direction, character identity, or format.

Examples:

```bash
if [ -f "scripts/session_memory.py" ]; then
  python "scripts/session_memory.py" lock scene_0 planned
  python "scripts/session_memory.py" reject "3D style" "user wants documentary realism"
  python "scripts/session_memory.py" pitfall "BGM too loud" "final mix"
  python "scripts/session_memory.py" anchor style_direction "warm realistic documentary"
fi
```

After planning, lock planned scenes and anchors. After each meaningful turn, review what was locked, rejected, or newly learned; update memory only when it changed.

## Local Capsules

Active reusable recipes live as stage-readable packages under `capsules/<name>.capsule/`.

For active package structure, use [capsule-package-format.md](capsule-package-format.md). Use session memory for short-lived turn/session state.

Execution modes:

| mode | Behavior |
|---|---|
| `local_script` | local script or folder owns the pipeline; agent validates inputs, runs it, then checks manifest, compliance, and QA |
| `preset` | config, local assets, method hints, and quality gates; agent stays in the loop and inspects outputs |

Rules:

- Inspect `capsule.yaml`, `CARD.md`, `contracts/input_schema.yaml`, and `contracts/runtime.yaml` before use.
- Read only the stage files named in `capsule.yaml.read_order` for planning, generation, QA, or learning.
- If runtime defaults specify image/video/TTS/BGM/volume and the channel is approved, use them as the starting point.
- If `contracts/input_schema.yaml` marks a field required and the user did not provide it, derive it from context only when safe; otherwise ask.
- Apply package `quality/` rules during planning and final QA. They are not decorative notes.
- If a capsule references a disabled channel, migrate it or report a blocker.
- If `entrypoints.local_script` is present, do not decompile it into a loose workflow. Run the local script and inspect diagnostics.
- If a new free-exploration path works repeatedly, graduate it into an active package with `scripts/capsule_package_create.py` or `scripts/capsule_package_update.py`.

## Free Exploration Loop

Use this when there is no mature capsule.

```text
call tool -> inspect output -> continue, retry with changed params, switch strategy, or stop
```

Minimum pass bar:

| Stage | Minimum standard |
|---|---|
| Image | composition correct, subject clear, style matches |
| Video | motion coherent, no obvious stutter, usable duration |
| TTS | speed/emotion natural, no abnormal pauses |
| Assembly | no black frames, no AV desync, duration aligned |

Retry budget:

- adjust prompt/params up to two times for one tool
- if first hard scene still fails after several attempts, revisit concept/tool/storyboard instead of batching
- record effective prompts and pitfalls for capsule graduation

## Artifact Manifest

Every production mode must write or verify `artifact_manifest.json` at the run root. The manifest is the delivery source of truth; do not rely on filename guessing.

Use one run root per production or regression run. Do not let tools scatter outputs into default folders such as `output/videos`, `superres_videos`, or ad hoc temp directories when a run root exists.

Artifact roots are project/runtime configuration, not skill-package configuration. Pick the root in this order:

1. explicit user/project run root
2. `OPENCLAW_OUTPUT_DIR`
3. `SESSION_OUTPUT_DIR`
4. `<project_root>/output`

Do not hard-code a runtime repository name or the skill source path as the artifact root.

Root pattern:

```text
<video_artifact_root>/
```

Run directory naming:

```text
<video_artifact_root>/<workflow>_<YYYYMMDD_HHMMSS>[_<topic_slug>]/
```

Runtime-created runs normally use names such as `general_video_<timestamp>` or `<workflow>_<timestamp>[_<project>]`. Manual experiments may include `manual_<timestamp>_<topic_slug>`, but should still use the same internal layout.

Recommended layout:

```text
<video_artifact_root>/<run_id>/
  storyboard.json
  artifact_manifest.json
  release/                final delivery artifacts only
    release_checkpoint.json
  work/                   run-owned intermediate files
    edit_plan.json
    inputs/               source files copied or derived for this run
    images/
    videos/
    audios/
    reference_images/
    temp/
      action_transfer/
      superres/
      lipsync/
  qa/                     QA reports, compliance, run notes
    edit_plan_validation.json
    repair_plan.json
  prompts/                versioned prompts and parameter snapshots
  logs/
```

When calling a tool with `output_path`, set `output_dir` to a subdirectory inside `work/temp/` when the tool downloads multiple intermediate files. If the wrapper can infer this, let it; otherwise pass it explicitly. Runtime-owned files should stay under `work/` and be recorded in the manifest.

## EditPlan, Repair Plan, and Checkpoint

Use `scripts/build_edit_plan.py` after assembly or before a careful rerender. It turns `storyboard.json` plus local scene media into `work/edit_plan.json`, with video, audio, and caption tracks. Treat this as the audit layer between creative storyboard and rendered media.

Use `scripts/validate_edit_plan.py` immediately after building the plan. It writes `qa/edit_plan_validation.json` and checks that source paths are local under `output/`, clips have positive and monotonic timing, scene coverage matches timeline duration, and probed media durations do not drift from recorded source durations beyond tolerance. A failed validation is a release blocker.

Use `scripts/plan_repairs.py` after `scripts/score_video_quality.py` writes `qa/video_quality_score.json`. The public scorer is provider-free; an optional video-analysis tool may be supplied only through the local overlay. The repair planner does not edit files. It maps blockers and required manual-review checks to a `qa/repair_plan.json` with command hints such as scene rerun, subtitle rerender, audio remix, or route replanning.

Use `scripts/release_checkpoint.py` before final handoff. It writes `release/release_checkpoint.json` with readiness status, score, blockers, warnings, and artifact paths. A checkpoint can be `blocked`, `needs_review`, or `pass`; only `pass` with `release_ready=true` is clean for delivery.

## Decision Log

For serious runs, keep `work/decision_log.json` as the audit trail for business-relevant choices. This is not viewer-facing copy and should not be pasted into subtitles, covers, or platform captions.

Create or append the log when any of these happen:

- delivery promise is selected or changed
- image/video/TTS/music provider or engine is selected
- capsule defaults override model planning
- source/reference analysis changes the route
- a provider fails and fallback is attempted
- a fallback changes cost, speed, quality, or promised output character
- the user approves, rejects, or revises a proposal/sample
- QA forces repair, rerender, or route replanning

Minimal schema:

```json
{
  "schema": "capsule_cinema.decision_log.v1",
  "run_id": "general_video_YYYYMMDD_HHMMSS",
  "decisions": [
    {
      "id": "d001",
      "created_at": "2026-06-23T12:00:00Z",
      "category": "delivery_promise",
      "selected": "tts_led_explainer",
      "options_considered": ["motion_led", "tts_led_explainer", "capsule_preset"],
      "reason": "User asked for a narrated explainer; no source footage was provided.",
      "user_visible": true,
      "user_approved": true,
      "confidence": 0.8,
      "qa_impact": "Final duration must track measured TTS duration."
    }
  ]
}
```

Decision categories:

| category | Use |
|---|---|
| `delivery_promise` | What kind of result the run promises. |
| `route_selection` | Generic video, reference remake, source edit, capsule, action transfer, lip sync, music MV, or blocker. |
| `capsule_contract` | Capsule loaded, defaults applied, stale channel migrated, or local script selected. |
| `provider_selection` | Image/video/TTS/music provider or engine choice. |
| `fallback` | Retry, provider switch, still fallback, generated filler, or blocked downgrade. |
| `sample_approval` | First hard scene or preview accepted/rejected. |
| `qa_repair` | QA blocker, repair plan, scene rerun, subtitle rerender, audio remix, or release block. |

Quality rules:

- `options_considered` should include real alternatives when there were alternatives; do not log only the selected option unless the route was genuinely constrained.
- `reason` must be specific enough to audit later. Avoid "best option" or "default".
- `confidence` should be realistic. Provider/channel choices rarely deserve `1.0`.
- `user_visible=true` only for decisions that affect user expectation, cost, delivery character, or final quality.
- Do not store API keys, upload URLs, signed URLs, cookies, or private endpoints.
- Add the decision log to `artifact_manifest.json` with a category such as `decision_log` when present.

## Prompt Retention

Keep prompts and important tool parameters as first-class artifacts. Store them under:

```text
prompts/<category>/<route-or-scene>/v001.json
prompts/<category>/<route-or-scene>/v002.json
prompts/prompt_index.json
```

Categories should be stable and coarse:

| category | Use |
|---|---|
| `storyboard` | planning, scene beats, narration drafts |
| `image` | image-generation prompts and reference notes |
| `video` | text-to-video/image-to-video prompts |
| `tts` | narration text, voice, speed, volume |
| `music` | BGM/music prompts, tags, instrumental flags |
| `runninghub` | workflow params for lip-sync, action transfer, super-res |
| `assembly` | ffmpeg/assembly settings, subtitle style, BGM mix |

Version rules:

- Use `v001`, `v002`, ... for prompt or parameter revisions that were actually attempted.
- Do not overwrite a previous version after the tool has run.
- Record `status` (`pass`, `failed`, `blocked_external`, `qa_blocked`) and linked output paths.
- Exclude API keys, tokens, cookies, signed URLs, provider upload URLs, private endpoints, and cloud object URLs.
- Add every prompt file and `prompt_index.json` to `artifact_manifest.json` with category `storyboard_prompt`.
- Before delivery, run `local_video_qa.py --require-prompts` for generated runs so missing prompt snapshots block QA instead of becoming a handoff surprise.

Minimum final artifacts:

```json
{
  "artifacts": [
    {"path": "/abs/project/output/<run_id>/release/video.mp4", "category": "final_video", "title": "Final video"},
    {"path": "/abs/project/output/<run_id>/release/copy.txt", "category": "copywriting", "title": "Copywriting"}
  ]
}
```

Use these categories:

| category | Typical files |
|---|---|
| `final_video` | final `.mp4` |
| `copywriting` | `.txt`, `.md`, `.json` copy |
| `storyboard_prompt` | storyboard or prompt files |
| `storyboard_image` | scene images |
| `scene_video` | intermediate scene clips |
| `voiceover` | TTS audio |
| `bgm` | background music |
| `sound_effect` | sound effects |
| `character_ref` | character references |
| `subtitle` | `.srt`, `.ass`, subtitle text |
| `cover` | cover image |
| `other` | only when none of the above fit |

Do not mark images or videos as `copywriting`. Do not omit intermediate scene images/videos/audio when they are useful for revision.

## Delivery Language

This is a local project. Final response should summarize:

- title/topic
- duration and aspect ratio
- major scenes/style
- audio/subtitle status
- copywriting availability
- delivery artifact status and useful local paths
