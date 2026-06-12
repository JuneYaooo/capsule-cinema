# Capsule Cinema Architecture

The repo is one unified skill with two layers: the executable runtime (`scripts/`, `lib/`, `index.js`) and the production playbook (`references/production-guide.md` and its companion references). Runtime behavior should be implemented in code; reusable craft rules and channel policy belong in the references.

## Runtime Layers

| Layer | Path | Responsibility |
|------|------|----------------|
| Plugin adapter | `index.js` | OpenClaw inputs, env allowlist, subprocess execution, progress snapshots |
| CLI wrappers | `scripts/` | Stable command entry points for full video, scene rerun, concat, QA, tool calls |
| Flow orchestration | `lib/agno_agents/general_video_crew/flow.py` | End-to-end pipeline ordering and state handoff |
| Planning agents | `lib/agno_agents/general_video_crew/tasks.py` | Creative planning prompts and structured JSON generation |
| Runtime contracts | `lib/src/contracts/` | Pydantic schemas and normalization for storyboard and continuity artifacts |
| Tool registry | `lib/config/tool_registry.yaml` | Tool metadata and module lookup |
| Tools | `lib/custom_tools/` | Provider calls, TTS, image/video generation, subtitle, concat, QA |

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
  --storyboard /path/to/workspace/storyboard.json \
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
