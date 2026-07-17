---
name: capsule-cinema
description: Plan, generate, revise, assemble, and quality-check local AI short videos with reusable Capsule Cinema recipes. Use when the user asks to make a video, design a storyboard, generate scenes, voiceover, subtitles or BGM, reproduce a reference-video workflow, repair a failed scene, review a release, or create, update, package, install, and reuse a video capsule.
---

# Capsule Cinema

Use Capsule Cinema as a recipe-driven local video studio. Keep planning, generation, targeted rework, assembly, QA, and reusable production knowledge auditable in one workspace.

## Resolve the runtime

Resolve the runtime before reading references or running commands:

1. If `{baseDir}/scripts/capsule.py` exists, use `{baseDir}` as `CAPSULE_CINEMA_ROOT`. This is a standalone Codex, Claude Code, or OpenClaw installation.
2. Otherwise, if `{baseDir}/../../scripts/capsule.py` exists, normalize `{baseDir}/../..` and use it as `CAPSULE_CINEMA_ROOT`. This is an OpenClaw plugin or source checkout.
3. Otherwise run `bash {baseDir}/scripts/bootstrap-runtime.sh`. Use the absolute path printed on stdout as `CAPSULE_CINEMA_ROOT`. The bootstrap clones the public runtime into the installed skill without reading or moving credentials.
4. Change to `CAPSULE_CINEMA_ROOT` before using relative paths in this skill.

If the runtime was just cloned, verify the prerequisites and install Python dependencies before production:

```bash
python3.12 --version
python3.12 -m pip install -r lib/requirements.txt
PYTHONPATH=lib python3.12 scripts/capsule.py list
```

FFmpeg is optional for recipe browsing and storyboard-only work, but required before rendering, audio mixing, subtitle burn-in, or final assembly.

## Route the request

Read `references/production-guide.md` before planning or generating media. Use it to route to the narrower references for storyboard craft, production patterns, channel policy, tool recipes, capsule packages, assembly pitfalls, review gates, and workflow artifacts.

Classify the request before choosing tools:

- New AI video or storyboard
- Post-production or assembly from local media
- Reference-video analysis or remake
- Existing capsule production
- Targeted scene, voice, subtitle, BGM, or assembly repair
- Action transfer, digital human, lip sync, or music-video workflow
- Capsule creation, update, validation, packaging, or installation
- Release QA or blocker diagnosis

Use only workflows and providers registered in the runtime. Do not invent an unsupported route or silently replace the promised production method.

## Follow the production contract

- Load `capsules/<name>.capsule/` before planning whenever a capsule is selected. Treat archived or legacy single-file recipes as non-active sources.
- Read `lib/config/tool_capabilities.yaml` and `lib/config/tool_registry.yaml` before choosing or invoking providers.
- Confirm the final image, video or motion, TTS or voice, BGM or music, SFX, subtitle, compositing, and local-script tool chain before paid or batch generation. Explain relevant alternatives, missing capabilities, and any downgrade.
- Define the delivery promise before generation: motion-led, source-led, TTS-led explainer, reference remake, capsule preset, or specialized route.
- Generate and inspect one representative hard scene before batching a new AI-video direction.
- Never silently downgrade after a provider or tool failure. Retry within the approved policy, or stop for approval when a substitution changes the promised result.
- Read `contracts/content_scope.yaml` before creating, updating, or materializing a capsule. Keep episode-specific facts, people, projects, accounts, metrics, prices, narration, and temporary assets out of reusable capsule defaults. Preserve only repeatable structure, identity, method, and QA knowledge.
- Review semantic conflicts before updating an existing capsule. Run `scripts/capsule_package_validate.py` after each create or update.
- Keep a capsule in `preset` mode unless a mature deterministic local renderer has successful-run evidence, cross-topic verification, parameterized inputs, and explicit deterministic steps.
- Treat lifecycle `blocked` as blocked and `review_required` as pending. Do not report either state as complete.
- Keep final deliverables under `output/`. A release must include its artifact manifest, applicable QA reports, repair plan when needed, and `release/release_checkpoint.json`.

## Protect credentials and local state

- Read credentials only from agent-managed secrets, system environment variables, or a user-created root `.env` for standalone local execution.
- Never ask the user to paste complete secret values into chat. Never print, commit, migrate, or place secrets in prompts, capsules, manifests, logs, or generated copy.
- Never create `lib/.env`. Keep `lib/.env.example` free of secrets.
- Preserve user-owned `.env`, `local-channels/`, capsules, generated output, and private provider adapters during upgrades.

## Use the command entry points

Run commands from `CAPSULE_CINEMA_ROOT` with `PYTHONPATH=lib` where shown.

| Task | Entry point |
| --- | --- |
| List and inspect capsules | `python3.12 scripts/capsule.py list` |
| Generate a full video | `PYTHONPATH=lib python3.12 scripts/run_video.py` |
| Generate only a storyboard | `PYTHONPATH=lib python3.12 scripts/run_video.py --storyboard_only` |
| Regenerate selected scenes | `PYTHONPATH=lib python3.12 scripts/run_scene.py` |
| Reassemble a workspace | `PYTHONPATH=lib python3.12 scripts/run_concat.py` |
| Analyze a video into a capsule draft | `PYTHONPATH=lib python3.12 scripts/analyze_video_to_capsule.py` |
| Validate a storyboard | `PYTHONPATH=lib python3.12 scripts/validate_storyboard.py` |
| Check visual consistency | `PYTHONPATH=lib python3.12 scripts/run_consistency_qa.py` |
| Run local technical QA | `PYTHONPATH=lib python3.12 scripts/local_video_qa.py` |
| Score video quality | `PYTHONPATH=lib python3.12 scripts/score_video_quality.py` |
| Build and validate an edit plan | `scripts/build_edit_plan.py`, then `scripts/validate_edit_plan.py` |
| Plan repairs | `PYTHONPATH=lib python3.12 scripts/plan_repairs.py` |
| Create a release checkpoint | `PYTHONPATH=lib python3.12 scripts/release_checkpoint.py` |
| Invoke a registered low-level tool | `PYTHONPATH=lib python3.12 scripts/run_tool.py` |
| Manage capsule packages | `scripts/capsule_package_create.py`, `capsule_package_update.py`, `capsule_package_pack.py`, `capsule_package_install.py` |

Inspect each command's `--help` before constructing an unfamiliar invocation. Prefer the high-level runners over calling provider classes directly.

## Work in reviewable stages

For serious generation, use this sequence unless the user explicitly requests a narrower stage:

1. Summarize the viewer experience, route, tool chain, expected limitations, representative-scene gate, and release QA bar.
2. Produce and validate the storyboard.
3. Wait for direction approval before paid or batch media generation.
4. Produce one representative hard scene and inspect it.
5. Generate the remaining media after the sample passes.
6. Build and validate `work/edit_plan.json`.
7. Assemble narration, video, subtitles, BGM, and SFX.
8. Run technical QA, visual checks, quality scoring, and visible-copy checks required by the route.
9. Repair blockers or report them honestly.
10. Create the release checkpoint and return only verified deliverables.

For targeted feedback, regenerate only the affected scene or layer and then rebuild dependent artifacts. Do not restart the entire production unless the change invalidates the whole plan.

## Manage capsules safely

Active capsules live at `capsules/<name>.capsule/`. Read `references/capsule-package-format.md` before creating or changing their structure.

Package and install a capsule with:

```bash
python3.12 scripts/capsule_package_pack.py capsules/<name>.capsule --out /path/to/packages
python3.12 scripts/capsule_package_install.py /path/to/packages/<name>.video-capsule.zip --out capsules
```

Before writing reusable lessons, distinguish stable production knowledge from one episode's literal content. Show conflict points to the user before overwriting an established capsule rule.

## Diagnose honestly

When a workflow cannot continue, identify the exact layer:

- Missing prerequisite or dependency
- Missing provider credential or entitlement
- Unsupported capability or unregistered provider
- Invalid storyboard, capsule, media path, or edit plan
- Failed representative scene or quality gate
- User approval still required
- Release checkpoint blocked

Return the smallest safe next action. Do not describe partial media, an unvalidated timeline, or a blocked lifecycle as a finished video.
