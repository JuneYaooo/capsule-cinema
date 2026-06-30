# Local SQLite Capsules

This is a single-user, single-project capsule store. Capsules are local SQLite records, not Markdown files and not cloud assets. A capsule is a reusable local recipe: defaults, method notes, quality gates, local assets, optional local script path, feedback, changelog, and run evidence.

Default DB:

```text
~/.codex/video-production/capsules.sqlite
```

Override:

```bash
export VIDEO_CAPSULE_DB=/absolute/path/capsules.sqlite
```

## Capsule v3 Trial

SQLite remains the legacy local store and evidence source while Capsule v3 is evaluated. New stage-readable recipe packages live under `capsules_v3/<name>.capsule/`; see [capsule-v3-format.md](capsule-v3-format.md). Do not copy raw `run_history` or `feedback` into v3 recipe files.

Never store API keys, cookies, signed URLs, bearer tokens, private endpoints, cloud object URLs, or remote package references. Use env var names and local file paths only.

## What a capsule holds

A capsule stores the **invariant recipe**, never the output of any single run:

- **Invariants** — fixed defaults and reusable rules: `config`, `method` (structure, opening/hook pattern, visual/audio/subtitle rules), `quality_rules`, and genuinely fixed media in `local_assets`.
- **Variables** — what changes every run, declared in `input_schema` (e.g. `topic`, plus any per-run slots the agent fills from the user request).
- **Examples** — illustrative only, in `examples`; the agent must regenerate per topic and never copy them as final content.
- **Evidence** — `run_history` / `feedback` / `changelog`; local provenance only, never injected into generation and never shipped in an exported package.

Never bake one-off run content into `method` or `local_assets`: a specific finished video, that run's character/scene images, this episode's exact wording, or absolute run paths belong to a single run, not the reusable recipe. The runtime injects the recipe verbatim into the generation prompt, so anything one-off here gets reproduced every run.

## Data Shape

Keep the store deliberately small:

| Field | Meaning |
|---|---|
| `config` | stable defaults: engines/roles, voice, aspect ratio, duration, subtitle/BGM switches |
| `method` | reusable recipe: structure, opening/hook pattern, visual/audio/subtitle rules, pitfalls — flat sections, no one-off content |
| `input_schema` | per-run variables the agent fills; usually `topic`, `aspect_ratio`, `target_duration` |
| `quality_rules` | checks the agent enforces during planning and final QA |
| `local_assets` | fixed reusable media only (see roles + `reuse` below) |
| `examples` | illustrative samples; regenerate per topic, never copied as content |
| `local_script_path` | optional local script/directory for mature deterministic workflows |
| `run_history` | local run evidence and final artifact paths (never injected or exported) |
| `feedback` | pitfalls, user notes, fixes (never injected or exported) |
| `changelog` | version notes for meaningful edits |

Do not split out market, owner, visibility, stars, collaborators, subscriptions, remote script packages, or cloud storage. This is one person's local project.

## Execution Modes

| mode | Use |
|---|---|
| `preset` | Agent remains in the loop. Capsule provides defaults, assets, method notes, and QA gates. |
| `local_script` | A local script or folder owns the pipeline. Agent still validates inputs, runs it, checks manifest/compliance, and reports diagnostics. |

For the required local-script input/output contract, read [local-script-protocol.md](local-script-protocol.md).

## Naming

Use one short canonical `name` per capsule. The repository's bundled default capsules use `life_sim`, `felt_asmr`, `guofeng_history`, `repo_showcase`, and `art_motion`. Do not add versioned public names, long descriptive names, or alias maps; put human-facing wording in `display_name` and recipe maturity in `version`/`changelog`.

## Status

| status | Meaning |
|---|---|
| `draft` | promising but exploratory |
| `active` | usable when tools are approved and local assets are accessible |
| `archived` | keep for history; do not auto-select |
| `disabled` | do not use until repaired |

## Commands

Initialize:

```bash
python "scripts/capsule_store.py" init
```

Create a preset capsule:

```bash
python "scripts/capsule_store.py" upsert \
  --name "voiceover" \
  --display-name "Realistic voiceover" \
  --status draft \
  --execution-mode preset \
  --description "Vertical narrated realistic short video" \
  --tags "voiceover,realistic,9:16" \
  --config-json '{"aspect_ratio":"9:16","tts_provider":"minimax","tts_voice":"female-chengshu-jingpin","image_engine":"GptImage2Tool","video_engine":"SeedanceFastVideoGeneratorTool","bgm_volume":0.08}' \
  --method-json '{"structure":["hook","context","turn","payoff"],"prompt_rules":["no rendered Chinese text","one clear subject per scene"]}'
```

Create a local-script capsule:

```bash
python "scripts/capsule_store.py" upsert \
  --name "news_flash" \
  --status active \
  --execution-mode local_script \
  --local-script-path "/abs/project/capsules/tech_news_flash/main.py" \
  --input-schema-json '{"topic":{"type":"string","required":true},"article_path":{"type":"string","required":false}}' \
  --quality-rules-json '[{"id":"final_video_required","type":"artifact_required","category":"final_video"},{"id":"manifest_required","type":"manifest_required"}]'
```

Local assets:

```bash
python "scripts/capsule_store.py" upsert \
  --name "voiceover" \
  --local-assets-json '[{"key":"warm_bgm","role":"bgm","reuse":"always","path":"/abs/project/assets/music/warm.mp3"},{"key":"subtitle_font","role":"font","reuse":"always","path":"/abs/project/assets/fonts/NotoSansCJK.ttf"}]'
```

Examples (illustrative samples, regenerated per topic, never copied as content):

```bash
python "scripts/capsule_store.py" upsert \
  --name "voiceover" \
  --examples-json '[{"kind":"opening_terms","note":"illustration_only_regenerate_per_topic","value":["示例词A","示例词B"]}]'
```

Asset rules:

- `local_assets` holds reusable media only. Allowed `role`: `bgm`, `sfx`, `font`, `intro_template`, `style_reference`, `character_reference`, `source_media`, `template`. `doctor` rejects any other role — run outputs and evidence must not live here.
- Every asset declares a `reuse` mode:
  - `always` — a fixed signature asset used in every run (default BGM, subtitle font, brand intro, a fixed opening SFX). The runtime tells the agent it must be used as-is.
  - `reference_only` — a style/quality reference; the runtime tells the agent to regenerate per topic and never copy it as final content. This is the default when `reuse` is omitted.
- Asset paths must be stable. `doctor` rejects paths under a run `output/` directory; package import lands assets in `~/.codex/video-production/capsule_assets/<name>/` and rewrites paths.
- Keep `config` for names, keys, defaults, volume, and selection policy; absolute media paths belong in `local_assets`, not `config`.
- When a capsule has one default BGM, give it `{"role":"bgm","reuse":"always","tags":["default"]}` or point `config.default_bgm_asset` / `config.bgm_asset_filename` at it.
- Local-script capsules should prefer `local_assets` or same-package `assets/` files before online search or generated placeholders.

Inspect before using:

```bash
python "scripts/capsule_store.py" list --status active
python "scripts/capsule_store.py" show voiceover --contract
python "scripts/capsule_store.py" doctor voiceover
```

Record run evidence:

```bash
python "scripts/capsule_store.py" record-run \
  --name "voiceover" \
  --topic "sample topic" \
  --status success \
  --input-params-json '{"target_duration":30}' \
  --workspace-dir "/abs/project/output/<run_id>" \
  --final-video "/abs/project/output/<run_id>/release/video.mp4" \
  --manifest-path "/abs/project/output/<run_id>/artifact_manifest.json" \
  --compliance-report-json '{"ok":true}' \
  --metrics-json '{"duration":29.8,"aspect_ratio":"9:16"}' \
  --notes "Subtitles synced; BGM below narration"
```

Record run evidence from a run directory after local QA:

```bash
python "scripts/local_video_qa.py" \
  --run-dir "/abs/project/output/<run_id>" \
  --aspect-ratio "9:16" \
  --expect-audio \
  --require-prompts \
  --output "/abs/project/output/<run_id>/qa/local_video_qa.json"

python "scripts/capsule_store.py" record-run-dir \
  --name "voiceover" \
  --run-dir "/abs/project/output/<run_id>" \
  --topic "sample topic" \
  --qa-report "/abs/project/output/<run_id>/qa/local_video_qa.json"
```

Add a pitfall or user feedback:

```bash
python "scripts/capsule_store.py" add-feedback \
  --name "voiceover" \
  --type pitfall \
  --severity blocker \
  --summary "BGM covered narration" \
  --evidence "final mix" \
  --fix "Keep bgm_volume <= 0.08 and verify voice loudness after mix"
```

Version a meaningful recipe change:

```bash
python "scripts/capsule_store.py" upsert \
  --name "voiceover" \
  --bump-version \
  --change-source "run_feedback" \
  --changelog "Lowered default BGM volume after mix failures" \
  --config-json '{"bgm_volume":0.06}'
```

## Bundled starter capsules

The repository ships starter capsules as standard packages in `capsules/*.capsule.zip`. Install them into the local user DB once:

```bash
python "scripts/capsule_store.py" install-defaults [--dir DIR] [--force]
```

Already-existing capsule names are skipped unless `--force`. The user DB stays local and is never committed; only packaged capsules live in the repo.

## Sharing (export / import)

Capsules can be packaged into a shareable `<name>.capsule.zip` and imported on another machine:

```bash
python "scripts/capsule_store.py" export voiceover --out ./
python "scripts/capsule_store.py" import voiceover.capsule.zip
```

Package layout: `manifest.json` + `assets/<key>__<basename>` + `script/<basename>`.

Manifest fields:

| Field | Meaning |
|-------|---------|
| `capsule_package_version` | package format version (currently `1`) |
| `schema_version` | capsule schema version |
| `capsule` | full capsule payload with paths rewritten to package-relative |
| `files` | `{package_path, sha256, size, original_path, asset_key}` per packaged file |
| `missing_assets` | assets skipped via `--allow-missing-assets` |

Rules:

- Export refuses capsules containing secret-looking values or remote/cloud URLs; run `doctor` first.
- Export omits `run_history` and `feedback` (local evidence is not part of a shareable recipe).
- Export fails on missing asset files unless `--allow-missing-assets` is given.
- Import verifies the package version and per-file sha256 checksums, lands assets in `~/.codex/video-production/capsule_assets/<name>/` (override with `--assets-dir`), rewrites capsule paths to the landed absolute paths, refuses name conflicts without `--force`, appends an `import` changelog entry, and runs `doctor` automatically.
- Use `--name <new>` to import under a different capsule name.

## Selection Rules

Before using a capsule:

1. `show --contract` and inspect mode, config, local assets, quality rules, feedback, and recent runs.
2. Confirm every configured tool/channel is approved by the active channel policy.
3. Confirm every asset or script path is local and accessible.
4. Confirm there are no secret-looking values or remote/cloud URLs.
5. Prefer `active` capsules with successful recent run evidence.
6. Treat `draft` as guidance only; do not batch from it.
7. Do not use `archived`, `disabled`, or inconsistent capsules.

For `preset` capsules, use `config` as defaults while keeping the agent in the loop. For `local_script` capsules, run the local script but still inspect outputs and compliance.

## Experience Loop

After every serious run:

1. Run `local_video_qa.py` or verify an equivalent QA report exists.
2. Use `record-run-dir` for successful or needs-review runs.
3. Use `add-feedback` for blocker causes and fixes.
4. Use `upsert --bump-version` only when a stable recipe change should affect future runs.

Do not mark a capsule `active` just because files exist. It should have at least one useful run and no unresolved blocker feedback for the same route.

## Doctor

```bash
python "scripts/capsule_store.py" doctor <capsule_name>
```

Doctor checks status/mode, local script path, input schema, quality rules, secret-looking values, and remote/cloud-looking values. It also enforces the recipe boundary: asset `role` must be in the allowed set, each asset needs a `reuse` mode, asset paths must not live under a run `output/` directory, and `method`/`config` must not contain baked absolute or `output/` paths. It is a local consistency check; final delivery still requires video review and artifact QA.
