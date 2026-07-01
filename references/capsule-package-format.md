# Video OKF Capsule Package Format

Capsule packages are the current checked-in recipe format for Capsule Cinema. They use the `video.okf.capsule.v1` profile: an OKF-inspired knowledge bundle with skills-like progressive disclosure, plus video-specific runtime contracts, assets, QA gates, and learning surfaces.

Active packages live at:

```text
capsules/<name>.capsule/
```

Legacy `.capsule.zip` exports are retained for audit and migration under:

```text
archive/legacy_capsule_zips/
```

SQLite remains supported as a local evidence store, migration source, and explicit fallback. Raw evidence from SQLite, runs, feedback, QA reports, prompt snapshots, and final artifact paths must not be copied into active package files.

Shareable active packages use the newer `.video-capsule.zip` extension. Do not use the legacy SQLite `.capsule.zip` export/import commands for active OKF capsule sharing.

## Design Model

This profile combines three ideas:

- **OKF-style knowledge**: Markdown surfaces are concept documents with YAML frontmatter. The root `index.md` is the bundle map for human and agent traversal.
- **Skills-style loading**: `capsule.yaml` and `CARD.md` stay small. Detailed recipes, assets, scripts, QA, examples, and learning are read only when the stage needs them.
- **Video runtime contracts**: deterministic execution details stay in YAML contracts instead of prose. This keeps tool routing, input requirements, assets, QA, and release gates machine-readable.

Do not multiply directories by video type. Generic AI video, action imitation, digital human, AI music MV, source-media editing, and generated/source hybrid video are represented through `primary_workflow`, `capabilities`, `contracts/runtime.yaml`, asset roles, and QA gates.

## Layout

```text
capsules/<name>.capsule/
  index.md
  capsule.yaml
  CARD.md
  contracts/
    runtime.yaml
    input_schema.yaml
  recipes/
    structure.md
    visual.md
    audio.md
    copy.md
    motion.md
  quality/
    rules.yaml
    release_gates.yaml
  learning/
    promoted_lessons.yaml
  examples/
    illustrative.yaml
  assets/
    index.yaml
  scripts/
    ... only for execution_mode=local_script
```

Asset `path` values in `assets/index.yaml` are relative to the package's `assets/` directory. For example, `path: style.png` points to `capsules/<name>.capsule/assets/style.png`. The validator rejects paths that escape `assets/` or point at missing files.

## Manifest

`capsule.yaml` is the machine manifest. It must declare the package schema, the video profile, routing metadata, workflow capabilities, stage read order, and entrypoints:

```yaml
schema_version: capsule.package.v1
profile: video.okf.capsule.v1
name: life_sim
display_name: Douyin Life-Sim Anime Voiceover
status: active
execution_mode: local_script
category: douyin_story_voiceover
primary_workflow: douyin_life_sim_voiceover
capabilities:
  - image_generation
  - micro_cut_editing
  - tts
  - bgm
  - sfx
  - local_script
tags:
  - douyin
  - life-sim
  - anime
  - voiceover
read_order:
  routing:
    - index.md
    - CARD.md
    - contracts/input_schema.yaml
  planning:
    - contracts/input_schema.yaml
    - recipes/structure.md
    - recipes/copy.md
    - recipes/visual.md
    - recipes/audio.md
  generation:
    - contracts/runtime.yaml
    - recipes/motion.md
    - assets/index.yaml
  qa:
    - quality/rules.yaml
    - quality/release_gates.yaml
  learning:
    - learning/promoted_lessons.yaml
entrypoints:
  preset: general_video
  local_script: scripts/life_sim_executor.py
```

`capabilities` are intentionally extensible. They describe required video abilities; runtime preflight decides whether the current tool registry can satisfy them. If a capsule needs `action_transfer`, `lip_sync`, `beat_sync`, `source_media_editing`, or `hybrid_compositing`, declare the capability instead of creating a new directory family.

`tags` are required routing and substitution keys for the whole capsule. They are not merely display labels: local selection can use them to find a nearby replacement capsule when the exact workflow or tool channel is unavailable. Keep tags short, stable, and reusable across capsules, such as `digital-human`, `lip-sync`, `source-media-editing`, `wechat-channels`, `ai-video`, or `bgm`. `when_to_use` may still contain human-readable usage hints, but fallback matching should prefer `tags`, `capabilities`, and `primary_workflow`.

## Markdown Concepts

The root `index.md`, `CARD.md`, and every `recipes/*.md` file are OKF-style Markdown concepts with YAML frontmatter.

Root `index.md` is the progressive bundle map:

```markdown
---
okf_version: "0.1"
type: Video Capsule Bundle Index
title: Douyin Life-Sim Anime Voiceover
description: Short routing summary.
profile: video.okf.capsule.v1
primary_workflow: douyin_life_sim_voiceover
tags: [douyin, life-sim, voiceover]
---

# Entry

* [Capsule Card](CARD.md) - Routing summary, purpose, and usage boundary.
```

`CARD.md` is the small routing surface:

```markdown
---
type: Video Capsule Card
title: Douyin Life-Sim Anime Voiceover
description: Short routing summary.
stage: routing
profile: video.okf.capsule.v1
primary_workflow: douyin_life_sim_voiceover
tags: [douyin, life-sim, voiceover]
---
```

Each recipe declares its domain and stage:

```markdown
---
type: Video Recipe
title: Visual Recipe
description: Visual style, references, characters, scenes, composition, and continuity.
stage: planning
domain: visual
profile: video.okf.capsule.v1
tags: [visual]
---
```

The canonical recipe domains are:

```text
structure -> planning   -> story structure, pacing, beats, and scene architecture
copy      -> planning   -> voiceover, subtitles, titles, cover copy, lyrics, and CTA rules
visual    -> planning   -> visual style, references, characters, scenes, and continuity
audio     -> planning   -> TTS, original audio, BGM, SFX, mix, timing, and sync
motion    -> generation -> camera motion, action, transitions, dynamic generation, and edit rhythm
```

## Stage Reading

The loader reads only the files named for the requested stage:

```text
routing    -> capsule.yaml + index.md + CARD.md + contracts/input_schema.yaml
planning   -> contracts/input_schema.yaml + recipes/structure.md + recipes/copy.md + recipes/visual.md + recipes/audio.md
generation -> contracts/runtime.yaml + recipes/motion.md + assets/index.yaml
qa         -> quality/rules.yaml + quality/release_gates.yaml
learning   -> learning/promoted_lessons.yaml
```

Every active `recipes/*.md` file must be listed in `capsule.yaml.read_order`. Hidden recipe files are rejected because they create stale, contradictory surfaces. Do not add `legacy_notes.md`, `repair_playbook.md`, `subtitle.md`, or other side-channel recipe files. Subtitle rules belong in `recipes/copy.md` and `quality/rules.yaml`; repair lessons belong in `learning/promoted_lessons.yaml` until promoted into a recipe or QA rule.

## Video Coverage

Video type differences are modeled as capabilities and contracts:

| Video family | Typical capabilities | Main recipe/contract surfaces |
| --- | --- | --- |
| Generic AI video | `image_to_video`, `tts`, `subtitles`, `bgm` | `structure`, `visual`, `motion`, `audio`, runtime roles |
| Action imitation | `source_video`, `action_transfer`, `pose_reference`, `identity_preservation` | `motion`, `visual`, assets, QA rules |
| Digital human | `avatar_reference`, `tts`, `lip_sync`, `talking_head`, `voice_consistency` | `copy`, `audio`, `visual`, `motion`, runtime roles |
| AI music MV | `source_music`, `beat_sync`, `lyric_sync`, `montage_editing`, `audio_mastering` | `audio`, `structure`, `motion`, `visual` |
| Source-media editing | `source_media_editing`, `transcription`, `edit_plan`, `risk_mute`, `subtitle` | `structure`, `copy`, `motion`, `audio`, assets |
| Hybrid generated/source video | `source_media`, `generated_media`, `style_matching`, `compositing`, `provenance_tracking` | assets, runtime roles, `visual`, `motion`, QA rules |

The format can describe a capability even when the current runtime cannot execute it. The runtime must preflight and block unsupported capabilities instead of silently downgrading to a generic path.

## Surface Boundaries

- `CARD.md`: routing, purpose, when-to-use, when-not-to-use, and stage reading only.
- `recipes/*.md`: reusable craft rules for the recipe domain. No local paths, run history, raw feedback, migration notes, or final artifact paths.
- `contracts/*.yaml`: machine-readable input and runtime contracts. Keep long craft explanation in recipes.
- `assets/index.yaml`: reusable packaged assets and references. Asset files are not loaded into context unless needed.
- `quality/*.yaml`: machine-readable failure rules and release gates.
- `learning/promoted_lessons.yaml`: generalized lessons only. Raw evidence remains local, archived, or in legacy SQLite.
- `examples/illustrative.yaml`: examples for orientation only; never copy examples as final content.

## Commands

Create a new active package:

```bash
python3.12 scripts/capsule_package_create.py \
  --name demo_capsule \
  --display-name "Demo Capsule" \
  --summary "Reusable demo AI video workflow." \
  --category demo \
  --primary-workflow generic_ai_video \
  --capability image_to_video \
  --capability tts \
  --capability bgm \
  --tag demo \
  --tag ai-video
```

This writes a complete `video.okf.capsule.v1` scaffold and validates it before returning. Use this command instead of hand-creating package directories.

Safely update an active package:

```bash
python3.12 scripts/capsule_package_update.py capsules/demo_capsule.capsule \
  --add-capability lip_sync \
  --add-tag digital-human \
  --lesson-id lip_sync_audio_is_timing_authority \
  --lesson-scope audio \
  --lesson-rule "Lip-sync generation must use final mixed speech audio as the timing authority." \
  --applies-when lip_sync \
  --applies-when digital_human \
  --promote-to recipes/audio.md \
  --promote-to quality/rules.yaml
```

The update command rewrites only controlled surfaces (`capsule.yaml`, `index.md`, `CARD.md`, and `learning/promoted_lessons.yaml`) and validates the package after writing. If validation fails, it restores the previous package state. Use `--dry-run` to verify a proposed update without keeping the changes.

Before writing, the update command runs a deterministic conflict review against existing capsule surfaces. If a proposed metadata, capability, tag, workflow, or promoted-lesson change contradicts current capsule boundaries, the command stops before writing and reports stable conflict IDs. Review those conflict points with the user, decide how each conflict should be resolved, then pass a confirmation JSON with `--conflict-resolution`:

```json
{
  "resolved_conflicts": [
    {
      "id": "capsule_update_conflict_1",
      "resolution": "User confirmed this update should override the previous boundary."
    }
  ]
}
```

Use `--conflict-report-json` to print blocked conflict details as JSON for agent review. A structural validation pass is not proof that the update has no semantic conflict.

Convert legacy SQLite/zip capsules into active package directories:

```bash
python3.12 scripts/capsule_package_convert.py \
  --from-db ~/.codex/video-production/capsules.sqlite \
  --from-zip-dir archive/legacy_capsule_zips \
  --names repo_showcase,life_sim,felt_asmr,guofeng_history,ecommerce_product_showcase,art_motion \
  --out capsules \
  --overwrite
```

Validate one package:

```bash
python3.12 scripts/capsule_package_validate.py capsules/felt_asmr.capsule
```

Pack an active capsule for sharing:

```bash
python3.12 scripts/capsule_package_pack.py \
  capsules/felt_asmr.capsule \
  --out dist/capsules
```

This validates the capsule, refuses runtime/cache files such as `output/`, hidden transient files, local paths, secrets, remote URLs, and stale evidence tokens, then writes:

```text
dist/capsules/felt_asmr.video-capsule.zip
```

Install a shared active capsule:

```bash
python3.12 scripts/capsule_package_install.py \
  dist/capsules/felt_asmr.video-capsule.zip \
  --out capsules
```

Install verifies `manifest.json`, checks every file's SHA-256 and size, rejects unsafe archive paths, validates the unpacked capsule, and refuses to overwrite an existing `capsules/<name>.capsule/` unless `--force` is passed.

Share package layout:

```text
<name>.video-capsule.zip
  manifest.json
  <name>.capsule/
    index.md
    capsule.yaml
    CARD.md
    contracts/
    recipes/
    quality/
    learning/
    examples/
    assets/
    scripts/
```

Share manifest fields:

| Field | Meaning |
| --- | --- |
| `package_format` | Must be `video.okf.capsule.share.v1`. |
| `profile` | Must be `video.okf.capsule.v1`. |
| `name` | Capsule name. |
| `primary_workflow` | Main workflow key for routing. |
| `capabilities` | Machine-readable required video abilities. |
| `tags` | Whole-capsule routing and fallback substitution tags. |
| `capsule_dir` | Root directory inside the zip, usually `<name>.capsule`. |
| `files` | `{path, sha256, size}` for every packaged file. |

Validate a capsule package before publishing:

```bash
python3.12 scripts/capsule_package_validate.py capsules/<name>.capsule --warnings-ok
```

## Learning Boundary

Raw evidence is not recipe. Evidence can produce lesson candidates, and promoted lessons may be written into `learning/promoted_lessons.yaml`, `recipes/`, or `quality/rules.yaml` only after being generalized and stripped of run-specific material.
