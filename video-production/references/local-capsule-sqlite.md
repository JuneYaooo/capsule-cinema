# Local SQLite Capsules

This is a single-user, single-project capsule store. Capsules are local SQLite records, not Markdown files and not cloud assets. A capsule is a reusable local recipe: defaults, method notes, quality gates, local assets, optional local script path, feedback, changelog, and run evidence.

Default DB:

```text
~/.codex/video-production/capsules.sqlite
```

Override:

```bash
export VIDEO_PRODUCTION_CAPSULE_DB=/absolute/path/capsules.sqlite
```

Never store API keys, cookies, signed URLs, bearer tokens, private endpoints, cloud object URLs, or remote package references. Use env var names and local file paths only.

## Data Shape

Keep the store deliberately small:

| Field | Meaning |
|---|---|
| `config` | stable defaults: engines, voice, aspect ratio, duration, subtitle/BGM switches |
| `method` | concise method notes: structure, prompt rules, style rules, pitfalls worth applying |
| `input_schema` | required or overridable inputs; usually `topic`, `aspect_ratio`, `target_duration` |
| `quality_rules` | checks the agent should enforce during planning and final QA |
| `local_assets` | local paths for BGM, fonts, references, templates, or source media |
| `local_script_path` | optional local script/directory for mature deterministic workflows |
| `run_history` | recent local runs and final artifact paths |
| `feedback` | pitfalls, user notes, fixes |
| `changelog` | version notes for meaningful edits |

Do not split out market, owner, visibility, stars, collaborators, subscriptions, remote script packages, or cloud storage. This is one person's local project.

## Execution Modes

| mode | Use |
|---|---|
| `preset` | Agent remains in the loop. Capsule provides defaults, assets, method notes, and QA gates. |
| `local_script` | A local script or folder owns the pipeline. Agent still validates inputs, runs it, checks manifest/compliance, and reports diagnostics. |

`script_package` is accepted only as a legacy alias and is normalized to `local_script`.
For the required local-script input/output contract, read [local-script-protocol.md](local-script-protocol.md).

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
python "$VIDEO_AGENT_ROOT/scripts/capsule_store.py" init
```

Create a preset capsule:

```bash
python "$VIDEO_AGENT_ROOT/scripts/capsule_store.py" upsert \
  --name "voiceover_realistic_v1" \
  --display-name "Realistic voiceover" \
  --status draft \
  --execution-mode preset \
  --description "Vertical narrated realistic short video" \
  --tags "voiceover,realistic,9:16" \
  --config-json '{"aspect_ratio":"9:16","tts_provider":"minimax","tts_voice":"female-chengshu-jingpin","image_engine":"GptImage2Tool","video_engine":"GrokVideoGeneratorTool","bgm_volume":0.08}' \
  --method-json '{"structure":["hook","context","turn","payoff"],"prompt_rules":["no rendered Chinese text","one clear subject per scene"]}'
```

Create a local-script capsule:

```bash
python "$VIDEO_AGENT_ROOT/scripts/capsule_store.py" upsert \
  --name "tech_news_flash_local" \
  --status active \
  --execution-mode local_script \
  --local-script-path "/abs/project/capsules/tech_news_flash/main.py" \
  --input-schema-json '{"topic":{"type":"string","required":true},"article_path":{"type":"string","required":false}}' \
  --quality-rules-json '[{"id":"final_video_required","type":"artifact_required","category":"final_video"},{"id":"manifest_required","type":"manifest_required"}]'
```

Local assets:

```bash
python "$VIDEO_AGENT_ROOT/scripts/capsule_store.py" upsert \
  --name "voiceover_realistic_v1" \
  --local-assets-json '[{"key":"warm_bgm","role":"bgm","path":"/abs/project/assets/music/warm.mp3"},{"key":"subtitle_font","role":"font","path":"/abs/project/assets/fonts/NotoSansCJK.ttf"}]'
```

Inspect before using:

```bash
python "$VIDEO_AGENT_ROOT/scripts/capsule_store.py" list --status active
python "$VIDEO_AGENT_ROOT/scripts/capsule_store.py" show voiceover_realistic_v1 --contract
python "$VIDEO_AGENT_ROOT/scripts/capsule_store.py" doctor voiceover_realistic_v1
```

Record run evidence:

```bash
python "$VIDEO_AGENT_ROOT/scripts/capsule_store.py" record-run \
  --name "voiceover_realistic_v1" \
  --topic "sample topic" \
  --status success \
  --input-params-json '{"target_duration":30}' \
  --workspace-dir "/abs/run" \
  --final-video "/abs/run/final/video.mp4" \
  --manifest-path "/abs/run/artifact_manifest.json" \
  --compliance-report-json '{"ok":true}' \
  --metrics-json '{"duration":29.8,"aspect_ratio":"9:16"}' \
  --notes "Subtitles synced; BGM below narration"
```

Record run evidence from a run directory after local QA:

```bash
python "$VIDEO_AGENT_ROOT/scripts/local_video_qa.py" \
  --run-dir "/abs/run" \
  --aspect-ratio "9:16" \
  --expect-audio \
  --output "/abs/run/reports/local_video_qa.json"

python "$VIDEO_AGENT_ROOT/scripts/capsule_store.py" record-run-dir \
  --name "voiceover_realistic_v1" \
  --run-dir "/abs/run" \
  --topic "sample topic" \
  --qa-report "/abs/run/reports/local_video_qa.json"
```

Add a pitfall or user feedback:

```bash
python "$VIDEO_AGENT_ROOT/scripts/capsule_store.py" add-feedback \
  --name "voiceover_realistic_v1" \
  --type pitfall \
  --severity blocker \
  --summary "BGM covered narration" \
  --evidence "final mix" \
  --fix "Keep bgm_volume <= 0.08 and verify voice loudness after mix"
```

Version a meaningful recipe change:

```bash
python "$VIDEO_AGENT_ROOT/scripts/capsule_store.py" upsert \
  --name "voiceover_realistic_v1" \
  --bump-version \
  --change-source "run_feedback" \
  --changelog "Lowered default BGM volume after mix failures" \
  --config-json '{"bgm_volume":0.06}'
```

## Bundled starter capsules

The repository ships starter capsules as standard packages in `capsules/*.capsule.zip`. Install them into the local user DB once:

```bash
python "$VIDEO_AGENT_ROOT/scripts/capsule_store.py" install-defaults [--dir DIR] [--force]
```

Already-existing capsule names are skipped unless `--force`. The user DB stays local and is never committed; only packaged capsules live in the repo.

## Sharing (export / import)

Capsules can be packaged into a shareable `<name>.capsule.zip` and imported on another machine:

```bash
python "$VIDEO_AGENT_ROOT/scripts/capsule_store.py" export voiceover_realistic_v1 --out ./
python "$VIDEO_AGENT_ROOT/scripts/capsule_store.py" import voiceover_realistic_v1.capsule.zip
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
python "$VIDEO_AGENT_ROOT/scripts/capsule_store.py" doctor <capsule_name>
```

Doctor checks status/mode, local script path, local assets, input schema, quality rules, secret-looking values, remote/cloud-looking values, and run evidence warnings. It is a local consistency check; final delivery still requires video review and artifact QA.
