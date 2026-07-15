# Production Guide

This is the production methodology layer of Capsule Cinema, sitting on top of the runtime in this repo (`scripts/`, `lib/`). For current video creation, use only channels approved by the active channel policy, and treat active capsules as stage-readable packages under `capsules/<name>.capsule/`. For maintaining the runtime itself (scripts, tool registry, tests, env plumbing), see the「运行时维护」section in the root `skill.md`.

## Design

This guide is organized into four layers:

1. **Route**: decide post-production, reference remake, new AI video, action transfer, lip sync, or code-rendered graphics.
2. **Policy**: choose only tools approved by the active channel registry; keep channels editable.
3. **Craft**: storyboard, prompt, timing, continuity, and reusable production patterns.
4. **State**: reference materials, active capsule packages, artifact manifest, review gates, and pitfalls.

## Iron Laws

```text
NO FINAL VIDEO DELIVERY WITHOUT A RELEASE CHECKPOINT
NO SERIOUS GENERATION WITHOUT A DELIVERY PROMISE
NO SILENT DOWNGRADE FROM THE APPROVED PROMISE
NO UNAPPROVED CHANNEL FALLBACK
NO REFERENCE REMAKE WITHOUT SOURCE ANALYSIS
NO SOURCE-LED EDIT WITHOUT SOURCE MEDIA REVIEW
NO CAPSULE PLANNING WITHOUT CONTRACT INSPECTION
NO CAPSULE GENERATION WITHOUT IN-CAPSULE TOOL CONFIRMATION
```

- A final delivery needs `release/release_checkpoint.json`; if the checkpoint is blocked, repair or report the blocker.
- Before generation, define what kind of result is promised: motion-led, source-led, narrated explainer, reference remake, capsule preset, or specialized route.
- If a fallback changes that promise, pause for approval or mark the run blocked. Do not quietly replace a motion-led, source-led, action-transfer, lip-sync, or music-led request with a generic image-to-video result.
- Use only tools approved by the active channel policy. Use `lib/config/tool_capabilities.yaml` for capability fit and provider requirements; use `lib/config/tool_registry.yaml` only as the direct invocation/module registry.
- Reference remakes must analyze the source video, image, link, or provided material before planning the new video.
- Source-led edits must inspect local media before planning: probe duration/resolution/audio, sample frames when useful, transcribe audio when relevant, and carry quality risks into the plan.
- Capsule work must load the active package from `capsules/<name>.capsule/` before planning.
- Capsule generation must pause after planning and before media generation to confirm the final tools inside the selected capsule route.

Route scope: the OpenClaw `full-video` workflow is the generic image-to-video chain only. Action transfer, digital human/lip sync, music MV, super-resolution, and code-rendered graphics are specialized/manual routes that must run through registered single tools, a capsule `local_script`, or a future dedicated workflow. Do not present a generic `run_video.py` result as the final output for those specialized routes.

## Route Gate

Before planning, classify the task. If none of these routes can satisfy the request with approved tools and accessible local assets, report a blocker instead of forcing a generic run:

1. Existing video/audio only -> post-production: trim, concat, subtitle, BGM, QA; super-resolution only if a registered wrapper exists.
2. Reference video/link -> analyze the reference first; do not guess its hook or shot structure.
3. Explicit capsule or repeated format -> load the active capsule package before planning.
4. New AI video -> plan storyboard, generate one representative scene, inspect, then scale out.
5. Action/dance transfer -> specialized RunningHub action tools via `run_tool.py` or a local-script capsule; require a real reference video.
6. Digital human/lip sync -> TTS first, mute source video, then registered RunningHub lip-sync tools via `run_tool.py` or a local-script capsule.

Default format is vertical `9:16` unless the user explicitly asks for horizontal.

## Delivery Promise Gate

After route classification and before writing prompts, set a delivery promise. Keep it short enough to repeat back to the user.

| Promise | Use when | Must be true at delivery |
|---|---|---|
| `motion_led` | The user expects real motion, cinematic clips, action, avatar movement, or high-motion generated scenes. | Most key beats use real generated/source motion, not only still images with pan/zoom. Still-led fallback needs explicit approval. |
| `source_led` | The user supplied footage/audio/images to edit, remix, subtitle, dub, or repurpose. | The source media was inspected and materially used. The plan must not invent source content that was not probed, sampled, or transcribed. |
| `tts_led_explainer` | Narration drives timing and comprehension. | TTS duration is the timing master; final video does not accidentally freeze after audio or run silent after narration. |
| `reference_remake` | The user wants something like a reference video or link. | The output preserves approved reference traits while changing topic/treatment enough to avoid carbon-copy imitation. |
| `capsule_preset` | An active capsule package is selected as the recipe. | Capsule contract, input schema, assets, quality rules, and approved channels were inspected and applied. |
| `specialized_route` | Action transfer, digital human/lip sync, music MV, super-resolution, or other non-generic route. | A registered specialized tool or capsule `local_script` produced the result. Generic `run_video.py` may only be a storyboard/preview unless the user approves fallback. |

Record the promise in planning notes, `qa/session_memory.json`, or `work/decision_log.json` when a run root exists. Final QA and release checkpoint review must judge the video against this promise, not just file playability.

## Proposal Gate

For serious generation, paid/batch generation, reference remakes, and capsule runs, present a concise proposal before scaling out. The proposal should help the user approve the direction without reading implementation details:

1. Viewer experience: hook, audience, platform, duration, aspect ratio, audio strategy.
2. Delivery promise: which promise applies and what would count as a downgrade.
3. Tool route: approved image/video/TTS/BGM tools, selected capsule or specialized route, and any policy limits.
4. Risks and blockers: missing inputs, unavailable providers, style/character continuity risk, source quality risk, moderation/channel risk.
5. First-scene/sample gate: which representative hard scene or short preview will be generated first.
6. Release bar: QA checks that must pass before delivery.

If the user explicitly asks to skip proposal review, keep a terse internal proposal in `work/decision_log.json` or `qa/run_notes.md` before running. Do not spend paid/batch generation effort from a vague plan.

The automatic `work/production_proposal.json` written by `scripts/run_video.py` is an audit artifact once a workspace exists; it is not a substitute for pre-run user approval. Agents still need a visible proposal before serious paid/batch generation unless the user explicitly skips review.

## Capsule Tool Confirmation Gate

Capsule tool confirmation is required before generation. Confirm tools inside the selected capsule, not replacement capsules.

After the capsule is selected and inspected, but before any image/video/audio generation starts, present the final in-capsule tool chain to the user and wait for approval. This gate is about the concrete tools that will be used inside the chosen capsule route, not about recommending a different capsule.

The confirmation should include:

1. Capsule route: selected capsule name, execution mode (`preset` or `local_script`), delivery promise, target platform/aspect/duration, and any required user inputs still missing.
2. Final tool chain by role: image/style-reference generation, video/motion generation, action transfer or lip-sync when applicable, TTS provider and voice, BGM/music generation or licensed search, SFX, subtitles, compositing/editing, QA, and the local-script entrypoint when used.
3. Selection reason: why each role chose that tool/channel, grounded in the capsule contract, active channel policy, local registry, available credentials, assets, tags, capabilities, and quality rules.
4. Same-role alternatives: approved/local alternatives for each role from the selected capsule route or local toolset, including why they are not selected for this run.
5. Missing or blocked alternatives: unavailable tools, missing env vars, absent assets, unsupported aspect/duration, or policy-disabled providers.
6. Substitutions and downgrades: any replacement, degraded quality mode, generic fallback, or promise-changing risk that requires explicit approval.
7. Approval state: do not start generation until the user confirms the listed tool chain, except `storyboard_only` planning that does not spend media generation.

If the tool chain changes after approval because a provider fails or a required asset is unavailable, stop again unless the change is a same-role retry already approved in the confirmation. Record approved substitutions in `work/decision_log.json` when a run root exists.

## Fallback and Downgrade Rules

Fallbacks are allowed only when they stay inside the active channel policy and do not falsify the delivery promise.

- **Same-promise fallback**: switching from one approved image-to-video provider to another approved provider is acceptable when recorded.
- **Quality downgrade**: switching from cinematic/high-quality engine to faster/lower-quality engine should be user-visible when the user asked for quality or paid work.
- **Promise downgrade**: replacing real motion with still-led fallback, source-led edit with generated filler, specialized route with generic image-to-video, or lip-sync/action transfer with ordinary scenes requires explicit approval or a blocker.
- **Unapproved fallback**: using a disabled channel is always blocked unless the active user/project policy is changed first.

For serious runs, append each meaningful fallback to `work/decision_log.json` with: attempted option, failure or reason, selected fallback, whether the user approved it, and expected QA impact.

## Capsule Route

For capsule work, load [capsule-package-format.md](capsule-package-format.md). Active capsules are `video.okf.capsule.v1` packages under `capsules/<name>.capsule/`. Do not look for or create `capsules/*.md` as the source of truth.

1. Load `capsule.yaml`, `index.md`, `CARD.md`, `contracts/input_schema.yaml`, and `contracts/content_scope.yaml` for routing and intake.
2. Read only the stage files named in `capsule.yaml.read_order` for planning, generation, QA, or learning.
3. Confirm status, execution mode, approved tools, required inputs, assets, quality rules, tags, capabilities, and local-script entrypoints.
4. Apply the Capsule Tool Confirmation Gate before generation, listing final in-capsule tools and same-role local alternatives for the selected route.
5. Use `tags`, `capabilities`, and `primary_workflow` for local fallback matching when the exact route or tool is unavailable.
6. `local_script`: run Preflight first, review `resolved_tools`, and require explicit acceptance for substitutions; inject the accepted tools into script params, then check the manifest, compliance, and final media.
7. `preset`: keep the agent in the loop. Use package contracts, recipes, assets, and quality rules as constraints while planning, generating, and reviewing.
8. After a stable improvement, promote generalized lessons back into the active package, not raw run notes.

Capsules should stay focused on reusable video knowledge, machine-readable contracts, packaged assets, quality gates, generalized learning, and optional local-script routing. Do not add broad skill files, raw run evidence, cloud storage, market/multi-user fields, multi-state factory lifecycle, or executor-only paths into active capsules.

Always run conflict review before updating an active capsule. If proposed metadata, capabilities, tags, runtime contract, recipes, QA rules, or promoted lessons contradict existing capsule content, list the conflict points and wait for the user's confirmed resolution before writing. Package validation and rollback protect structure; they do not replace semantic conflict review.

Create new active packages with `scripts/capsule_package_create.py`; do not hand-build the directory tree. Update active package metadata, capabilities, tags, or promoted generalized lessons with `scripts/capsule_package_update.py`; the command checks for update conflicts, validates the package, and rolls back invalid updates. Share active capsules with `scripts/capsule_package_pack.py` and `scripts/capsule_package_install.py` as `.video-capsule.zip` packages.

Before create, update, or video-to-capsule materialization, classify proposed content using `contracts/content_scope.yaml`: preserve series-fixed assets and mechanisms, but keep episode-variable names, projects, facts, figures, titles, narration, and diagram copy in current-run inputs. The validator blocks declared episode-specific literals from returning to reusable capsule surfaces; current-run evidence is not scanned as a reusable package surface.

## Channel Policy

Load [channel-policy.md](channel-policy.md) before choosing tools.
For adding, removing, or replacing approved channels, load [channel-customization.md](channel-customization.md).
For environment variables and secret handling, load [env-secrets.md](env-secrets.md).
Read `lib/config/tool_capabilities.yaml` first for the current capability schema, required env, and limits. Use `lib/config/tool_registry.yaml` only when calling a specific registered tool through `scripts/run_tool.py`. Filter both through the active channel policy.

Default rule:

- Full-video image/video generation: use `VolcengineImageGeneratorTool` and `Seedance20VideoGeneratorTool` through the official Volcengine Ark API. Local-only alternatives must come from the ignored overlay and must not appear in public capsules.
- Action and lip-sync: registered RunningHub tools only (`ActionImitateTool`, `WanMultiPersonActionImitateTool`, `LTX23LipSyncTool`, `InfiniteTalkV2VTool`, `Wan22LipSyncTool`), and only through specialized/manual routes.
- Super-resolution: do not auto-select unless an equivalent wrapper is registered in `lib/config/tool_registry.yaml`.
- TTS: use `UniversalTTSTool` / `UniversalTTSBatchTool` with `provider=minimax` or `provider=doubao`; direct `DoubaoTTSTool` is implementation-level and not the default `run_tool.py` contract.
- Music/BGM: use an explicit local user file or a capsule-packaged public asset.
- Do not fall back to any unregistered or non-public channel. A local-only adapter is selectable only from the effective ignored overlay.

These are defaults, not permanent hard-coding. If the user edits the channel policy or provides an explicit project/user channel policy, treat that policy as authoritative for future work. Removed channels must not be used even if old examples mention them; newly added channels must include tool name, channel owner, required inputs, env vars, strengths, failure modes, and QA requirements.

When an approved generation channel fails, either retry within the same channel, use another channel that is explicitly approved in the current policy, use a non-generative editing fallback such as Ken Burns/real material, or report the blocker. Unapproved channel fallback is a blocker; do not silently switch to an unapproved channel.

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
- Final delivery should cite the standard run package paths.

## Production Loop

1. **Plan the viewer experience**: propagation assets, hook, target audience, platform, total duration, audio strategy.
2. **Lock the delivery promise**: record the promised route and what would count as a downgrade.
3. **Present or record the proposal**: tool route, risks, first-scene/sample gate, QA bar, and user approval when needed.
4. **Storyboard**: merge continuous action into fewer scenes; split only on real subject/place/viewpoint changes.
5. **Choose tools and confirm capsule tools when applicable**: select from the approved channel policy, record meaningful decisions, and pause for in-capsule tool-chain approval before capsule generation.
6. **Prototype one scene/sample**: generate the first hard scene or short preview and inspect it before batch generation.
7. **Generate remaining scenes**: preserve character anchors, scene state, duration, and prompt style.
8. **Assemble**: TTS -> trim to measured audio -> concat -> BGM -> subtitles -> copywriting.
9. **Build and validate EditPlan**: write `work/edit_plan.json`, then `qa/edit_plan_validation.json`, so scene timing, source clips, captions, audio, and local media paths are auditable.
10. **Quality gate**: run technical, visual, subtitle, audio, timeline, promise, and artifact checks.
11. **Repair/release gate**: when QA fails, write `qa/repair_plan.json`; before handoff, write `release/release_checkpoint.json`.

## Stage Review Focus

Use these focus items during planning, prototype review, batch review, and release:

| Stage | Review focus |
|---|---|
| Route/proposal | Promise is explicit; route can satisfy it; selected tools are approved; costs/risks/fallbacks are clear. |
| Reference/source analysis | Reference traits are grounded in actual analysis; source media has probe/frame/transcript evidence where relevant. |
| Storyboard | Scenes cover the promise, avoid generic repetition, preserve character/style anchors, and fit narration duration. |
| Reference design | Character/style references are locked before batch generation when continuity matters. |
| First hard scene/sample | Representative hard scene proves style, subject, motion, orientation, and trimming feasibility. |
| Batch assets | Failures are not repeated blindly; fallbacks are recorded; generated text/watermarks/deformation are caught early. |
| Assembly | TTS timing, subtitle strategy, BGM balance, clean concat base, and EditPlan coverage are correct. |
| Release | Final QA and release checkpoint prove file quality, artifact completeness, channel compliance, and delivery-promise preservation. |

For storyboard and shot-craft rules, load [storyboard-craft.md](storyboard-craft.md).
For reusable video type patterns, load [production-patterns.md](production-patterns.md).
For concrete commands and plan snippets, load [tool-recipes.md](tool-recipes.md).
For reference materials, session memory, capsules, workspace state, and artifact manifest rules, load [workflow-state-artifacts.md](workflow-state-artifacts.md).
For active package capsules, load [capsule-package-format.md](capsule-package-format.md).
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
- Language review: manual playback or an explicitly configured local-overlay analyzer.
- EditPlan timeline: `scripts/build_edit_plan.py`
- EditPlan validation: `scripts/validate_edit_plan.py`
- QA repair plan: `scripts/plan_repairs.py`
- Release checkpoint: `scripts/release_checkpoint.py`
- Active capsule packages: `scripts/capsule_package_create.py`, `scripts/capsule_package_update.py`, `scripts/capsule_package_pack.py`, `scripts/capsule_package_install.py`, `scripts/capsule_package_validate.py`
- Local final-video QA: `scripts/local_video_qa.py`
- Tool registry: `lib/config/tool_registry.yaml`

If `SESSION_OUTPUT_DIR` is set by a wrapper, keep manually generated intermediate files inside that directory. Outside a managed session, use absolute output paths under `RUN_ROOT`.
