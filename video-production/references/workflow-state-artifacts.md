# Workflow State and Artifacts

This captures the production mechanics that make video work repeatable: reference materials, session memory, capsules, workspace state, and artifact manifests.

## Planning Context Order

Before planning, inspect:

1. Current user instruction.
2. Session reference materials / attachments.
3. Matching local SQLite capsule and its execution mode.
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
if [ -f "$VIDEO_WRAPPER_ROOT/manage_attachments.py" ]; then
  python "$VIDEO_WRAPPER_ROOT/manage_attachments.py" add \
    --filename "reference.jpg" \
    --local-path "/absolute/path/reference.jpg" \
    --source "web_search" \
    --usage "reference"
fi
```

After analysis, mark semantics:

```bash
if [ -f "$VIDEO_WRAPPER_ROOT/manage_attachments.py" ]; then
  python "$VIDEO_WRAPPER_ROOT/manage_attachments.py" update \
    <attachment_id> \
    --usage "content" --strategy "use_original" --parsed 1
fi
```

If that wrapper is missing, keep the same fields in `inputs/reference_assets.json` under the run root and include the file in `artifact_manifest.json`.

If a reference image exists, prefer passing it through `reference_image_paths` when the approved image tool supports it. If a reference video exists, analyze hook, pacing, shot distribution, and emotional trigger before generating a remake plan.

## Session Memory

Use session memory to avoid losing decisions across turns. If a managed runtime provides `session_memory.py`, use it; otherwise keep `reports/session_memory.json` or `reports/run_notes.md` under the run root.

Track:

- `lock`: approved/planned scene, cover, character, visual direction, or final artifact.
- `reject`: directions the user or QA rejected.
- `pitfall`: concrete issue and where it appeared.
- `anchor`: topic, core metaphor, style direction, character identity, or format.

Examples:

```bash
if [ -f "$VIDEO_WRAPPER_ROOT/session_memory.py" ]; then
  python "$VIDEO_WRAPPER_ROOT/session_memory.py" lock scene_0 planned
  python "$VIDEO_WRAPPER_ROOT/session_memory.py" reject "3D style" "user wants documentary realism"
  python "$VIDEO_WRAPPER_ROOT/session_memory.py" pitfall "BGM too loud" "final mix"
  python "$VIDEO_WRAPPER_ROOT/session_memory.py" anchor style_direction "warm realistic documentary"
fi
```

After planning, lock planned scenes and anchors. After each meaningful turn, review what was locked, rejected, or newly learned; update memory only when it changed.

## Local Capsules

Capsules store local production recipes in SQLite, not local Markdown files. Treat capsule config, local assets, input schema, method notes, and quality rules as usable only when they still use approved channels and local paths.

For persistent local storage, use [local-capsule-sqlite.md](local-capsule-sqlite.md). Prefer the local SQLite store for reusable recipes and run evidence; use session memory for short-lived turn/session state.

Execution modes:

| mode | Behavior |
|---|---|
| `local_script` | local script or folder owns the pipeline; agent validates inputs, runs it, then checks manifest, compliance, and QA |
| `preset` | config, local assets, method hints, and quality gates; agent stays in the loop and inspects outputs |

Rules:

- Inspect the contract with `python "$VIDEO_AGENT_ROOT/scripts/capsule_store.py" show <name> --contract` before use.
- If `config` specifies image/video/TTS/BGM/volume and the channel is approved, use it as the starting point.
- If `input_schema` marks a field required and the user did not provide it, derive it from context only when safe; otherwise ask.
- Apply `quality_rules` during planning and final QA. They are not decorative notes.
- If a capsule references a disabled channel, migrate it or report a blocker.
- If `local_script_path` is present, do not decompile it into a loose workflow. Run the local script and inspect diagnostics.
- If a new free-exploration path works repeatedly, graduate it into a local capsule with config, input schema, quality rules, local assets, method notes, feedback, and run evidence.

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
2. `VIDEO_ARTIFACT_ROOT`
3. `SESSION_OUTPUT_DIR`
4. `<project_root>/artifacts/video_runs`

Do not hard-code a runtime repository name or the skill source path as the artifact root.

Root pattern:

```text
<video_artifact_root>/
```

Run directory naming:

```text
<video_artifact_root>/<kind>/<YYYYMMDD_HHMMSS>_<topic_slug>/
```

Use `kind` to keep production work separate from tests:

| kind | Use |
|---|---|
| `production` | user-facing videos |
| `regression` | external/API regression runs |
| `experiment` | exploratory trials not yet deliverable |

Put the timestamp before the topic so runs sort chronologically. Keep `topic_slug` short, ASCII when possible, and stable enough to recognize the subject.

Recommended layout:

```text
<video_artifact_root>/<kind>/<YYYYMMDD_HHMMSS>_<topic_slug>/
  inputs/                 source files copied or derived for this run
  intermediates/          downloaded provider results, scene trials, temp clips
    images/
    videos/
    audios/
    action_transfer/
    superres/
    lipsync/
  videos/                 named route outputs or scene clips
  audios/                 TTS, narration, VO
  music/                  BGM/music
  final/                  final delivery artifacts only
  reports/                QA reports, compliance, run notes
  prompts/                versioned prompts and parameter snapshots
  artifact_manifest.json
```

When calling a tool with `output_path`, set `output_dir` to a subdirectory inside the same run root when the tool downloads multiple intermediate files. If the wrapper can infer this, let it; otherwise pass it explicitly. After a run, move any known run-owned files from legacy defaults into `intermediates/` and update the manifest.

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

Minimum final artifacts:

```json
{
  "artifacts": [
    {"path": "/abs/final/video.mp4", "category": "final_video", "title": "Final video"},
    {"path": "/abs/final/copy.txt", "category": "copywriting", "title": "Copywriting"}
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
