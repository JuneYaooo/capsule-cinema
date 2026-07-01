# Capsule Cinema Architecture

The repo is one unified skill with two layers: the executable runtime (`scripts/`, `lib/`, `index.js`) and the production playbook (`references/production-guide.md` and its companion references). Runtime behavior should be implemented in code; reusable craft rules and channel policy belong in the references.

## Runtime Layers

| Layer | Path | Responsibility |
|------|------|----------------|
| Plugin adapter | `index.js` | OpenClaw inputs, env allowlist, subprocess execution, progress snapshots |
| CLI wrappers | `scripts/` | Stable command entry points for full video, scene rerun, concat, QA, tool calls |
| Flow orchestration | `lib/video_workflows/general_video/flow.py` | End-to-end pipeline ordering and state handoff |
| Planning agents | `lib/video_workflows/general_video/tasks.py` | Creative planning prompts and structured JSON generation |
| Runtime generators | `lib/src/runtime/general_video_crew/` | Audio, image, video, subtitle, concat, BGM, and copywriting execution used by the video workflow |
| Scene regeneration runtime | `lib/src/runtime/general_video_crew/scene_regenerator.py` | Reusable feedback workflow logic for rerunning one scene and updating `storyboard.json` |
| Shared runtime config | `lib/src/video_generation_config.py` | Canonical defaults shared by planning and runtime modules |
| Runtime contracts | `lib/src/contracts/` | Pydantic schemas and normalization for storyboard and continuity artifacts |
| Active capsule packages | `capsules/*.capsule/`, `references/capsule-package-format.md` | Stage-readable recipe packages, runtime contracts, assets, QA gates, and share format |
| Capability matching | `lib/config/tool_capabilities.yaml`, `lib/src/capsule_resolver.py`, `lib/src/capsule_preflight.py`, `lib/src/capsule_adapter.py` | Tool capability declarations, local env fit, role resolution, preflight status, and output contract compatibility |
| Tool registry | `lib/config/tool_registry.yaml` | Tool metadata and module lookup |
| Tools | `lib/custom_tools/` | Provider calls, TTS, image/video generation, subtitle, concat, QA |
| Release artifacts | `scripts/build_edit_plan.py`, `scripts/validate_edit_plan.py`, `scripts/plan_repairs.py`, `scripts/release_checkpoint.py` | Deterministic timeline, timeline contract validation, repair plan, and release checkpoint generation |

## Contract First

Core artifacts must be normalized through code contracts, not only prompt instructions.

Current contracts:

- `StoryboardDocument`
- `SceneContract`
- `ConsistencyContract`
- `CharacterContract`
- `StyleContract`

The runtime saves `storyboard.json` with a `consistency_contract` that records:

- `style_anchor_id`
- fixed and allowed style traits
- character identity anchors and fixed traits
- chapters
- continuity groups

Use `scripts/validate_storyboard.py` to check or normalize a storyboard:

```bash
cd "$(git rev-parse --show-toplevel)"
PYTHONPATH=lib python3.12 scripts/validate_storyboard.py \
  --storyboard output/<run_id>/storyboard.json \
  --write-normalized
```

## Long-Chain Generation

Default single-run delivery remains short-video oriented, with `target_duration <= 180s`. Long-chain support means the runtime can preserve continuity across many scenes, chapters, reruns, or series episodes.

Required long-chain fields:

- `chapter_id`
- `continuity_group`
- `character_ids`
- `reference_ids`
- `style_anchor`
- `continuity_notes`

Character and style consistency should be enforced in this order:

1. Lock reference design.
2. Normalize storyboard contract.
3. Run consistency QA.
4. Generate scene images.
5. Inspect/regenerate drifted scene images.
6. Generate scene videos.
7. Assemble and run final QA.

## QA Gates

Minimum gates:

- `validate_storyboard.py`: schema and contract normalization.
- `run_consistency_qa.py`: storyboard-level character/style continuity checks.
- `local_video_qa.py`: final media file, duration, audio, aspect-ratio checks.
- `build_edit_plan.py`: timeline-level source, timing, caption, and audio map for audit and rerendering.
- `validate_edit_plan.py`: local timeline contract checks for source paths, clip timing, scene coverage, and probed media duration.
- `plan_repairs.py`: non-destructive repair suggestions from QA blockers.
- `release_checkpoint.py`: final release package status, artifact list, blockers, warnings, and readiness.

Future visual gates should compare generated scene images against locked character/style references with a multimodal model before video generation.

## Tool Registry

Do not add new tool names directly to `scripts/run_tool.py`. Add metadata to `lib/config/tool_registry.yaml`; the script loads module paths from that registry.

Tool entries should include:

- `module`
- `category`
- `provider`
- relevant `limits`
- strengths and failure modes when known

## Design Rule

Prompt text may guide creative decisions, but hard runtime requirements belong in contracts, validators, registries, and QA scripts. If a rule must be reliable across model upgrades, implement it outside the prompt.

`EditPlan` follows the same rule. It is a checkable timeline contract, not a best-effort summary: release tooling should treat a failed `qa/edit_plan_validation.json` as a delivery blocker until the timeline is rebuilt or the missing media is repaired.
