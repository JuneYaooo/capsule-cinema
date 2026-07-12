# Capsule Production Core Design

## Goal

Upgrade the project-wide capsule framework without making any one capsule type the center of the Core. Existing Skills/OKF-style progressive reading remains intact; the Core makes it first-class, adds lossless/configured capsule primitives, and introduces generic production and effect-review contracts.

## Principles

- Thin Core, thick capsules: the Core owns lifecycle and contracts; each capsule owns its domain knowledge and production details.
- Existing v1 capsules remain read-only compatible.
- Progressive reading is not reinvented. Existing `read_order` and resource `stage` declarations become normalized Core data.
- No GitHub, repository, scene, shot, BGM, subtitle, or other video-specific vocabulary enters generic Core models.
- Simplification must not silently delete authored capsule knowledge.
- Human effect approval remains explicit when a plan requires it.
- The open-source Core contains no future commercial/hosted product design.

## Architecture

### 1. First-class progressive reading

`CapsuleDefinition` gains a normalized `read_order` containing the stable stages:

```text
routing → planning → generation → qa → learning
```

The v1 adapter preserves `capsule.yaml.read_order`. A generic stage-resource resolver:

- returns resources in author-declared order;
- rejects absolute paths and traversal outside the package;
- rejects missing files with stable structured issues;
- never reads later-stage resources automatically;
- preserves an empty stage as an empty ordered list.

This standardizes the existing OKF behavior without requiring compilation artifacts for normal use.

### 2. Generic preservation primitive

The Core provides read-only package snapshots and authored-section inventories for YAML, Markdown, Python, and binary files. A caller supplies disposition policy; Core contains no package-name-specific classifier.

Validation requires exact inventory/disposition equality and reports coverage, unclassified sections, duplicates, and silent deletion. Source packages are never rewritten.

### 3. Generic configured Instance

`CapsuleInstance` binds a normalized Definition to one request:

- explicit inputs and defaults;
- strict types, bounds, and options;
- definition/candidate/implementation digests;
- fallback policy and approvals;
- deterministic, bounded JSON serialization.

It contains no repo-showcase-specific input inference.

### 4. Generic ProductionPlan

The Core adds a versioned plan contract containing only cross-domain concepts:

- objectives;
- evidence requirements;
- ordered production steps and their stages;
- declared input/output/rule references;
- quality requirements;
- fallback policy;
- required human approval points;
- a namespaced `domain_payload` owned and validated by the capsule.

The Core validates structural completeness, stable stage ordering, unique identifiers, known references, and deterministic digesting. It does not interpret domain payloads.

### 5. Generic EffectReport

The Core adds a versioned effect-report contract containing:

- blocker, warning, and informational checks;
- artifact evidence references;
- production-plan digest;
- human-review status;
- release recommendation.

Release recommendation is derived fail-closed:

- any failed blocker → `blocked`;
- required human approval still pending → `review_required`;
- otherwise → `ready`.

Domain capsules supply their own checks. For example, a video capsule may check visual readability, while a non-video capsule may check schema or execution quality.

## Public boundaries

Generic modules live under `lib/src/capsules/`. Package-specific migration/build orchestration does not. In particular, `repo_showcase_shadow.py` is not merged into Core.

Public DTOs expose logical capsule identity and stable issue codes, not internal runner paths, commands, environment values, or secrets.

## Compatibility

- Missing `read_order` adapts to empty stages.
- Existing tracked v1 packages must load without byte mutation.
- Existing catalog, doctor, dispatch, and CLI behavior remains compatible.
- Existing package-authored `read_order` remains authoritative.
- No generated candidate is activated or added to catalog discovery.

## Testing

Focused tests cover:

- v1 `read_order` preservation and stage ordering;
- traversal, symlink, missing-resource, and duplicate-resource handling;
- preservation completeness and source immutability;
- strict Instance binding and serialization;
- ProductionPlan reference integrity and deterministic digest;
- EffectReport fail-closed release decisions and human-review gates;
- at least two structurally different tracked capsules;
- all existing Capsule Core regressions and `npm test`.

## Delivery

Implementation occurs on `feature/capsule-production-core`, receives an independent whole-branch review, then is merged into local `main`. After merged-state verification, `main` is pushed to `origin/main`. Main-worktree uncommitted changes are not staged or modified.

## Non-goals

- No universal video shot/copy/motion schema in Core.
- No repo-showcase-specific collector, renderer, migration, or shadow candidate in Core.
- No mandatory stage-context compilation for ordinary capsule use.
- No marketplace, accounts, billing, cloud sync, remote runner, or commercial “solution three” functionality.
