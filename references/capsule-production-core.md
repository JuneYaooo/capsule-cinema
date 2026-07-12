# Capsule Production Core

The project uses a **thin Core, thick capsules** architecture. Core provides generic,
versioned lifecycle contracts; each capsule continues to own its domain knowledge,
production method, and effect criteria.

## Progressive reading

Existing `capsule.yaml.read_order` remains authoritative and is normalized into five
ordered stages:

1. `routing`
2. `planning`
3. `generation`
4. `qa`
5. `learning`

Use `load_stage_resources(definition, stage)` to read only the requested stage. It
preserves author order and returns each resource's logical path, SHA-256 digest, and
UTF-8 content. Absolute paths, traversal, symlinks, missing files, and non-UTF-8
resources fail closed. A capsule without `read_order` gets five empty stages.

This is progressive disclosure, not content reduction: source packages are not
rewritten, and later-stage material remains available when that stage is requested.

## Lossless evolution

`snapshot_package()` and `inventory_sections()` inventory the original package.
`build_preservation_manifest()` requires the migration caller to provide its own
classification policy. `validate_preservation_manifest()` then detects missing,
duplicate, or silently deleted authored sections. Core does not contain rules for a
specific capsule type.

## Runtime lifecycle

- `CapsuleInstance` binds validated request inputs and immutable implementation
  digests to one capsule definition.
- `ProductionPlan` describes objectives, evidence, quality requirements, ordered
  steps, fallbacks, and approval points. Capsule-specific data stays inside
  `domain_payload`.
- `EffectReport` links checks to artifact evidence and derives the release result.
  A failed blocker or rejected review is `blocked`; a pending required review is
  `review_required`; otherwise it is `ready`.

Callers cannot override the derived effect recommendation by directly constructing
an inconsistent report.

## Boundary

Core deliberately has no GitHub, repository, scene, shot, subtitle, BGM, or other
domain-specific production fields. Those belong in capsule-owned resources,
`domain_payload`, and capsule-owned effect checks. Existing v1 capsules remain
loadable without byte mutation, so richer authored content is preserved while the
framework gains standard lifecycle controls.
