# Skill Lifecycle Consumption Design

## Goal

Make the existing OpenClaw Skill entry consume the capsule lifecycle and derive release decisions from real QA evidence, while preserving non-capsule video behavior.

## Architecture

Keep `index.js -> run_video.py` as the Skill entry. For preset capsules, `run_video.py` prepares lifecycle context before planning, injects the planning and generation resources into the capsule prompt, materializes lifecycle artifacts under the resulting workspace, and finalizes the EffectReport from the structured run result.

For local-script capsules, `run_video.py` delegates to the existing Core dispatch path instead of refusing the route. Core dispatch selects `run_capsule.py`, forwards lifecycle paths, and returns its structured result. `run_capsule.py` also adds the lifecycle contract to the merged params document so a local capsule receives it through its existing input surface.

## Input binding

Add an optional `capsule_params_json` Skill and CLI input. It must be a JSON object. These values bind declared capsule inputs but are not converted into unrelated preset command flags. `user_requirements` remains the deterministic topic fallback. Ambiguous missing required inputs block before paid generation.

## Context consumption

The lifecycle context supplied to planning contains only routing, planning, and generation stage resources in author order. QA and learning content are not inserted into the planning prompt. The prompt includes logical paths, digests, and authored content, plus the configured Instance and ProductionPlan digest.

When Core dispatch already supplied `CAPSULE_*_PATH`, the runner consumes those files and does not prepare a duplicate lifecycle. Direct OpenClaw execution prepares an equivalent lifecycle in a temporary control directory and copies it into the created workspace before finalization.

## Effect decision

Dispatch extracts the final structured JSON object from runner stdout without publishing it in the public envelope. EffectReport creates blocker checks for evidence that exists:

- process return code;
- `deliverable`;
- `run_status`;
- `qa_blockers`;
- EditPlan validation;
- local video QA;
- release checkpoint status;
- capsule release-gate result.

Any explicit negative value or blocker yields `blocked`. A zero exit code is only a fallback when no richer evidence exists. Pending required human review yields `review_required`; otherwise the recommendation is `ready`.

## Compatibility

- Non-capsule `run_video.py` behavior is unchanged.
- Existing preset and local-script commands remain valid.
- Existing OpenClaw output fields remain; lifecycle paths and recommendation are additive.
- No capsule source files are rewritten.
- Learning is never loaded automatically.
- Standard Codex Skill packaging remains a separate adapter and is not mixed into OpenClaw `skill.md`.

## Tests

Tests prove preset prompt consumption, local-script delegation, explicit capsule input binding, no duplicate lifecycle preparation, real-QA blocking despite exit code zero, safe structured-output extraction, OpenClaw argument routing, source immutability, and all existing Core/runtime regressions.
