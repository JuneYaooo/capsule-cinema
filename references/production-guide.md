# Production Guide

This is the production methodology layer of Capsule Cinema, sitting on top of the runtime in this repo (`scripts/`, `lib/`). For current video creation, use only channels approved by the active channel policy, and treat capsules as structured local SQLite records rather than Markdown skill files. For maintaining the runtime itself (scripts, tool registry, tests, env plumbing), see the「运行时维护」section in the root `skill.md`.

## Design

This guide is organized into four layers:

1. **Route**: decide post-production, reference remake, new AI video, action transfer, lip sync, or code-rendered graphics.
2. **Policy**: choose only tools approved by the active channel registry; keep channels editable.
3. **Craft**: storyboard, prompt, timing, continuity, and reusable production patterns.
4. **State**: reference materials, local SQLite capsules, artifact manifest, review gates, and pitfalls.

Route scope: the OpenClaw `full-video` workflow is the generic image-to-video chain only. Action transfer, digital human/lip sync, music MV, super-resolution, and code-rendered graphics are specialized/manual routes that must run through registered single tools, a capsule `local_script`, or a future dedicated workflow. Do not present a generic `run_video.py` result as the final output for those specialized routes.

## First Decision

Before planning, classify the task:

1. Existing video/audio only -> post-production: trim, concat, subtitle, BGM, QA; super-resolution only if a registered wrapper exists.
2. Reference video/link -> analyze the reference first; do not guess its hook or shot structure.
3. Explicit capsule or repeated format -> inspect the local SQLite capsule before planning.
4. New AI video -> plan storyboard, generate one representative scene, inspect, then scale out.
5. Action/dance transfer -> specialized RunningHub action tools via `run_tool.py` or a local-script capsule; require a real reference video.
6. Digital human/lip sync -> TTS first, mute source video, then registered RunningHub lip-sync tools via `run_tool.py` or a local-script capsule.

Default format is vertical `9:16` unless the user explicitly asks for horizontal.

## Capsule Route

For capsule work, load [local-capsule-sqlite.md](local-capsule-sqlite.md). Do not look for or create `capsules/*.md` as the source of truth.

1. Query `"scripts/capsule_store.py" list` / `show <name> --contract`.
2. Confirm status, execution mode, approved tools, required inputs, local assets, quality rules, feedback, and recent run evidence.
3. `local_script`: run the local script path recorded in the capsule, then check manifest, compliance, and final media.
4. `preset`: keep the agent in the loop. Use `config`, `local_assets`, `method`, and `quality_rules` as constraints while planning, generating, and reviewing.
5. After a useful run, record `record-run`; after a failure or discovery, record `add-feedback`; after a stable improvement, bump the capsule version.

Take the useful parts of legacy `video_workflow` capsules: structured config, local assets, run evidence, quality gates, and optional local-script routing. Do not copy its broad skill files, long Markdown capsules, cloud storage, market/multi-user fields, multi-state factory lifecycle, or executor-only paths into this skill.

## Channel Policy

Load [channel-policy.md](channel-policy.md) before choosing tools.
For adding, removing, or replacing approved channels, load [channel-customization.md](channel-customization.md).
For environment variables and secret handling, load [env-secrets.md](env-secrets.md).
Read `lib/config/tool_registry.yaml` for the current tool schema and original `engine_decision` / `tool_chain_patterns`, then filter it through the active channel policy.

Default rule:

- Full-video image/video generation: registered Juling/Veo wrappers only. The default planner uses `Seedream5ImageGeneratorTool` for scene images and `SeedanceFastVideoGeneratorTool` for ordinary image-to-video scenes; approved alternatives include `GptImage2Tool`, `SeedanceVideoGeneratorTool`, `Jimeng35ProVideoGeneratorTool`, and `Veo3VideoGeneratorTool` when the task or project policy calls for them.
- Action and lip-sync: registered RunningHub tools only (`ActionImitateTool`, `WanMultiPersonActionImitateTool`, `LTX23LipSyncTool`, `InfiniteTalkV2VTool`, `Wan22LipSyncTool`), and only through specialized/manual routes.
- Super-resolution: do not auto-select unless an equivalent wrapper is registered in `lib/config/tool_registry.yaml`.
- TTS: use `UniversalTTSTool` / `UniversalTTSBatchTool` with `provider=minimax` or `provider=doubao`; direct `DoubaoTTSTool` is implementation-level and not the default `run_tool.py` contract.
- Music/BGM: explicit licensed audio URL, Jamendo, or Internet Archive search download first; **Suno via `UniversalMusicGenerationTool`** when generated music is needed or search is unavailable.
- Do not fall back to ZeakAI, Gemini image generation, Midjourney, XGAPI/Sdance2, Hailuo, Kling, Sora, Grok, Veo 3.1, or any other unregistered/unapproved channel.

These are defaults, not permanent hard-coding. If the user edits the channel policy or provides an explicit project/user channel policy, treat that policy as authoritative for future work. Removed channels must not be used even if old examples mention them; newly added channels must include tool name, channel owner, required inputs, env vars, strengths, failure modes, and QA requirements.

When an approved generation channel fails, either retry within the same channel, use another channel that is explicitly approved in the current policy, use a non-generative editing fallback such as Ken Burns/real material, or report the blocker. Do not silently switch to an unapproved channel.

## Self-Media Hook Extraction

For repo, tool, product, venue, and creator-account short videos, do not treat hook selection as a summary task. Before storyboard or TTS, run a propagation-asset audit:

1. Trust/click proof: stars, forks, screenshots, cost, speed, version, real-user proof, or other high-signal numbers.
2. Memory anchor: project/person/product name, IP, metaphor, slogan, visual symbol, ritual, or phrase the audience can repeat.
3. Core transformation: what concrete thing becomes what new usable result.
4. Audience recall sentence: one sentence a viewer could tell a friend after watching.
5. Non-replaceable test: if the hook still works after replacing the project/name with another one, it is too generic.

Strong proof numbers may be fronted when they are genuinely high-signal; do not bury them at the end. Pair them with the memory anchor and core transformation so the number earns attention without replacing the promise. Treat names, IP metaphors, and visual symbols as first-class story assets, not metadata.

Keep this audit language internal. Viewer-facing titles, voiceover, subtitles, cards, and platform copy must not say planning terms such as "front the proof", "trust hook", "memory anchor", "propagation asset", or "strategy". Translate the decision into natural audience language, for example "this repo already has 23.5k stars; click in and the stronger thing is..." rather than explaining why the number is being used.

Before delivery, run `scripts/visible_copy_lint.py` on viewer-facing scripts/storyboards/publishing copy that will be rendered or pasted publicly. A hit is a blocker unless the line is explicitly an internal rule/reminder, not public copy.

For rendered videos, create or extract a viewer-facing text file that contains only text visible to the audience: frame titles, badges, captions, subtitles, cover text, and platform copy. Lint that file before final assembly. Do not rely only on scanning full JSON profiles because local paths and release metadata can hide what is actually on screen or create false positives.

Viewer-facing video text must not contain production handoff language such as `v1`, `v2`, `v3`, "真实版", "真实截图版", "修正", "这次", "按你的反馈", "source:", "real asset", "README real", "draft", or "revision". Those belong in `technical/`, `internal/`, `release_manifest.json`, or QA notes, never in frames, subtitles, covers, or publishing copy.

## Audience Pull Audit

For self-media repo/tool/product videos, explicitly answer why a real user would care before finalizing the hook:

1. Primary audience: name the 1-3 user groups most likely to stop scrolling.
2. Stop reason: what makes them pause in the first 3 seconds: proof, name/IP, pain, result, or identity signal.
3. Care reason: what job, anxiety, aspiration, or workflow problem makes the topic worth saving.
4. User takeaway: one sentence describing what the viewer can do or understand after watching.
5. Non-target users: who should not be attracted, especially users expecting roleplay, guaranteed results, or high-risk decisions.

For serious runs, write an `audience_pull_card` under `qa/` or `work/`. The final hook should serve the primary audience, not a vague "everyone".

## User-First Framing Gate

Do not write from the producer's or tool-builder's point of view. Before writing titles, voiceover, cover text, or platform copy, create a user-first brief:

- `primary_user`: the concrete user segment this video is for.
- `user_language`: how that user would describe the problem or desired outcome in their own words.
- `current_alternative`: what they do today without this tool/skill/project.
- `attention_trigger`: what makes them stop in the feed.
- `use_reason`: why they would actually try, save, comment, or share.
- `actionable_takeaway`: what they can do after watching.
- `wrong_audience`: who should not be pulled in.

Every public-facing line should be defensible from that primary user's perspective. If a line only explains what the project is, what the producer found interesting, or why the agent chose a hook, rewrite it as a user benefit, user tension, proof, or boundary. Avoid broad "AI users" targeting unless the video names the real subset and their job-to-be-done.

## Artifact Landing Standard

Every serious video run must land artifacts like a release package, not a loose dump. The runtime-owned layout is the source of truth. Runs live under `output/<run_id>/` (run_id = `<workflow>_<timestamp>[_<project>]` or `general_video_<timestamp>`), with this standard shape:

```text
output/<run_id>/
  storyboard.json
  artifact_manifest.json
  release/           # final video, cover, platform-ready copy, optional release_manifest.json
  work/              # intermediates: images/audios/videos/reference_images/temp
  qa/                # QA report, lint report, review frames
  logs/              # run logs
```

Rules:

- `release/` is the only folder meant for publishing or handoff. It must not contain internal strategy notes, draft hooks, secrets, signed URLs, or failed versions.
- Planning and strategy artifacts belong in `work/` or `qa/` unless a local-script capsule explicitly creates a richer package under the run root.
- `artifact_manifest.json` at the run root is mandatory for completed runs and must identify final video and copywriting when available.
- `release/release_manifest.json` is optional but recommended when a run has platform copy, cover, QA report, or release notes.
- If a local-script capsule needs versioned packages, nest them under `release/<version_slug>/` and still keep/update the root `artifact_manifest.json`.
- Keep root-level legacy artifacts if they already exist, but final delivery should cite the standard run package paths.

## Production Loop

1. **Plan the viewer experience**: propagation assets, hook, target audience, platform, total duration, audio strategy.
2. **Storyboard**: merge continuous action into fewer scenes; split only on real subject/place/viewpoint changes.
3. **Choose tools** from the approved channel policy.
4. **Prototype one scene**: generate the first hard scene and inspect it before batch generation.
5. **Generate remaining scenes**: preserve character anchors, scene state, duration, and prompt style.
6. **Assemble**: TTS -> trim to measured audio -> concat -> BGM -> subtitles -> copywriting.
7. **Build EditPlan**: write `work/edit_plan.json` so scene timing, source clips, captions, and audio are auditable.
8. **Quality gate**: run technical, visual, subtitle, audio, and artifact checks.
9. **Repair/release gate**: when QA fails, write `qa/repair_plan.json`; before handoff, write `release/release_checkpoint.json`.

For storyboard and shot-craft rules, load [storyboard-craft.md](storyboard-craft.md).
For reusable video type patterns, load [production-patterns.md](production-patterns.md).
For concrete commands and plan snippets, load [tool-recipes.md](tool-recipes.md).
For reference materials, session memory, capsules, workspace state, and artifact manifest rules, load [workflow-state-artifacts.md](workflow-state-artifacts.md).
For persistent local SQLite capsules, load [local-capsule-sqlite.md](local-capsule-sqlite.md).
For local-script capsules, load [local-script-protocol.md](local-script-protocol.md).
For assembly, subtitles, BGM, and QA, load [assembly-qc-pitfalls.md](assembly-qc-pitfalls.md).
For video review gates and low-quality issue triage, load [video-review-gate.md](video-review-gate.md).
For changing the approved channel/tool set, load [channel-customization.md](channel-customization.md).
For adding new provider credentials or env vars, load [env-secrets.md](env-secrets.md).

## Non-Negotiables

- Do not create image prompts that ask the image model to render Chinese titles, captions, or UI text. Add text in post.
- For narrated videos, TTS duration is truth. Measure with `ffprobe`; final video duration should match narration duration within a small tolerance unless the user explicitly requests silent intro/outro/end-card time.
- Do not let narrated final video be shorter than audio and freeze/stutter on the last frame. Do not let narrated final video run longer than audio and leave an empty or silent visual tail.
- For Chinese subtitles, use ffmpeg drawtext through the project subtitle path. Do not use English-only subtitle tools.
- Preserve `assembly/01_concat.mp4`; it is the clean base for replacing subtitles or BGM.
- Do not double-burn subtitles.
- Do not hard-code API keys, tokens, cookies, signed URLs, private endpoints, or cloud object URLs in scripts, plans, capsules, docs, logs, or manifests. Use env vars and local paths.
- Do not deliver a final video with review blockers: unreadable subtitles, broken audio, major visual deformation, black frames, wrong aspect ratio, inaccessible artifact, or failed compliance report.
- Final artifacts are local project files. Summarize the deliverables and include local paths only when useful.
- Write or verify `artifact_manifest.json` for final video and copywriting.
- Run or produce a local QA report before recording a run as successful.

## Project Entry Points

The runtime lives in this repo. Run commands from the repo root:

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
cd "$PROJECT_ROOT"
RUN_ROOT="${RUN_ROOT:-${OPENCLAW_OUTPUT_DIR:-$PROJECT_ROOT/output}/manual_$(date +%Y%m%d_%H%M%S)_topic}"
```

`OPENCLAW_OUTPUT_DIR` and `RUN_ROOT` must resolve inside this repository's `output/` directory. Do not write final videos, covers, QA reports, release copy, or manual tool outputs to `/tmp`, the repo root, parent directories, or arbitrary external folders.

Common wrappers (all under `scripts/`, run with `PYTHONPATH=lib python3.12`):

- Single tool: `scripts/run_tool.py`
- Full video / storyboard only: `scripts/run_video.py`
- One-scene rerun: `scripts/run_scene.py`
- Reassembly: `scripts/run_concat.py`
- Language check: `scripts/run_language_check.py`
- EditPlan timeline: `scripts/build_edit_plan.py`
- QA repair plan: `scripts/plan_repairs.py`
- Release checkpoint: `scripts/release_checkpoint.py`
- Local capsule store: `scripts/capsule_store.py` (supports `export`/`import` for sharing capsules as `.capsule.zip`)
- Local final-video QA: `scripts/local_video_qa.py`
- Tool registry: `lib/config/tool_registry.yaml`

If `SESSION_OUTPUT_DIR` is set by a wrapper, keep manually generated intermediate files inside that directory. Outside a managed session, use absolute output paths under `RUN_ROOT`.
