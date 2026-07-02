# Style Consistency Contract Design

## Context

The rejected `life_sim` preview failed for architectural reasons, not because one scene prompt was weak. The run used an ad-hoc script outside the capsule package, hard-coded a vertical aspect ratio, injected an unrequested platform tone, disabled the reference edit path, and changed prompt language/template during the batch. The system then assembled output without a machine-readable style consistency report.

The repository already has a storyboard-level `ConsistencyContract`, but it does not yet protect the generation boundary where prompt fallbacks, reference failures, and provider downgrades happen. Style stability must therefore be enforced after planning and before release, not only described in capsule prose.

## Root Cause

The root issue is a missing runtime contract between three layers:

1. Capsule contracts describe style and character rules.
2. Image generation mutates prompts and reference paths at runtime.
3. QA/release gates do not inspect the actual final prompts and reference downgrade state.

Because that boundary is missing, a batch can start with detailed Chinese style prompts, continue with short English fallback prompts, lose reference images, and still look like a normal completed run.

## Architecture Choice

The right next layer is a cross-capsule visual consistency contract:

- A shared prompt compiler creates a stable style/character block and a scene-specific action block.
- A stable `prompt_style_hash` is computed from the style, character, aspect, and negative drift rules only, not from scene action.
- Prompt-index validation checks the actual prompts used by the generation runtime, including fallback attempts.
- Strict character consistency is a declared mode. If reference support fails and the run downgrades to text-only soft lock, the run is blocked unless the user explicitly accepted a soft preview.
- QA and release tooling consume `qa/style_consistency_report.json` and block failed reports.

This is the best architecture for the current repo maturity. Jumping directly to LoRA, provider-specific reference edits, or longer prompt prose would not fix silent fallback, unrecorded actual prompts, or release gates. Provider reference support still matters for strict identity, but the framework must first stop pretending strict identity succeeded when it did not.

## Scope

In scope:

- Add a reusable helper in `lib/src`, available to all capsules.
- Add a CLI validator that reads a prompt index and writes a style consistency report.
- Add tests for prompt hash stability, mid-batch drift, missing actual prompts, and strict-reference downgrade blocking.
- Add release and score blockers for failed style consistency reports.
- Add `life_sim` runtime contract flags so the capsule requires this framework-level contract.

Out of scope:

- Regenerate the rejected `首富千金` preview.
- Call image APIs or store credentials.
- Build provider-specific reference-image probes.
- Train or fine-tune a model.
- Move `life_sim` back to generic one-off scripts.

## Contract Model

The shared helper accepts:

- `aspect_ratio`
- `style_contract`
- `character_bible`
- `negative_style_rules`
- scene fields such as `scene_id`, `action`, `continuity_anchor`, and `actor_state`
- reference status such as `required`, `available`, `failed`, and `soft_consistency_ack`

It produces:

- `compiled_prompt`
- `prompt_style_hash`
- `consistency_mode`
- `checks`
- `blockers`
- `warnings`

Valid consistency modes:

- `strict_reference_lock`: style/character prompt blocks are stable and required references are available.
- `text_only_soft_lock`: no reference image is active, but a stable text-only style/character anchor exists.
- `inconsistent_or_unknown`: prompts or reference records are missing, drifting, or unverified.

## Prompt Index Requirements

For final image attempts, the prompt index must record:

- `scene_id`
- `final_prompt_used`
- `prompt_style_hash`
- `consistency_mode`
- `reference_image_paths`
- `attempts`, including prompt, status, reference paths, and fallback reason when fallback occurred

The validator blocks:

- missing `final_prompt_used`
- missing or changing `prompt_style_hash`
- reference failure when strict character consistency is required
- fallback attempts with no fallback reason
- final prompts that omit style/character anchors
- unaccepted text-only soft consistency on a capsule that requires strict consistency

## QA And Release

`scripts/validate_visual_consistency.py` writes `qa/style_consistency_report.json`.

`scripts/score_video_quality.py` and `scripts/release_checkpoint.py` treat a failed report as a blocker. This keeps style drift from becoming a subjective after-the-fact review issue.

If no report exists, existing generic runs remain compatible. Capsules that require the report should declare that requirement in their runtime contract and release gates.

## life_sim Requirements

`life_sim` must declare:

- `style_consistency_contract_required: true`
- `prompt_compiler_required: true`
- `prompt_style_hash_stable_required: true`
- `reference_failure_policy: fail_closed`
- `soft_consistency_preview_requires_user_ack: true`

This prevents the exact failure mode from repeating: reference edits may fail, but the system cannot silently continue and label the result final.

## Testing

The test suite must prove:

- stable style hash across different scene actions
- drift detection when fallback prompts change style/template/language
- blocker on missing actual final prompt
- blocker on strict reference requirement downgraded to text-only without explicit acceptance
- score and release gates block failed style consistency reports
- `life_sim` dry-run contract validates the new consistency flags

## Success Criteria

- A reusable, provider-agnostic style consistency module exists under `lib/src`.
- The validator can be run without image API calls.
- Failed style reports block score and release.
- `life_sim` declares and validates the new framework contract.
- Full Python and npm verification pass.
