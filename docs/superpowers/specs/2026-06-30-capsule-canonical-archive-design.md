# Capsule Canonical Archive Design

## Goal

Make directory-style capsules the canonical active capsule format and move older SQLite/zip-era packages to archive-only status. The active path should be easy to understand, stage-readable, and free of version-name baggage such as "v3".

## Current Problem

The repository currently has two visible capsule truths:

- `capsules/` contains legacy `.capsule.zip` packages.
- `capsules_v3/` contains the new stage-readable directory packages.

The runtime and docs still mainly describe SQLite or "v3", while the new packages are only partially wired in. Some generated packages also contain migration residue such as `source.type: sqlite`, `legacy_version`, `converted_at`, and unreferenced files like `recipes/legacy_notes.md`. This makes it too easy for the system to forget which source is current, read stale lessons, or preserve old contradictions.

## Decision

Use `capsules/<name>.capsule/` as the only active checked-in capsule path.

Move legacy zip packages to:

```text
archive/legacy_capsule_zips/
```

Keep SQLite support as legacy/local evidence storage and explicit fallback, not as the default active capsule source. SQLite is not deleted in this slice.

Rename code and docs from `capsule_v3_*` to neutral package names so the current format does not immediately become another legacy label.

## Canonical Active Layout

Each active capsule uses this layout:

```text
capsules/<name>.capsule/
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

No active capsule should include hidden active recipe files. Every `recipes/*.md` file must be referenced by `capsule.yaml.read_order`, or validation fails.

## Stage Reading Contract

The canonical read stages are:

```text
routing    -> capsule.yaml + CARD.md
planning   -> recipes/structure.md + recipes/visual.md + recipes/audio.md + recipes/copy.md
generation -> contracts/runtime.yaml + recipes/motion.md + assets/index.yaml
qa         -> quality/rules.yaml + quality/release_gates.yaml
learning   -> learning/promoted_lessons.yaml
```

The loader must read only files declared for the requested stage. It must not implicitly include `CARD.md` or legacy notes in later stages.

## Learning Boundary

Raw evidence is not recipe. Active capsules must not contain run-specific evidence, final artifact paths, prompt snapshots, or raw feedback. Past experience can enter active capsules only after it is generalized into:

- `learning/promoted_lessons.yaml`
- relevant `recipes/*.md`
- relevant `quality/rules.yaml`

Legacy zip packages and SQLite rows remain available for audit and future promotion, but are not injected into normal generation.

## Runtime Behavior

`scripts/run_video.py --capsule <name>` should prefer the canonical directory package:

```text
capsules/<name>.capsule/
```

If no directory package exists, SQLite can still be used as a legacy fallback unless the user passes an explicit package path. This keeps older local workflows available while making the new format the default.

## Naming

Public/current names should avoid versioned format labels:

- Use `capsule_package_loader.py`, not `capsule_v3_loader.py`.
- Use `capsule_package_validate.py`, not `capsule_v3_validate.py`.
- Use `capsule_package_convert.py`, not `capsule_v3_convert.py`.
- Use `references/capsule-package-format.md`, not `references/capsule-v3-format.md`.

Legacy compatibility wrappers may remain briefly if tests or external calls still import old names.

## Validation Rules

Validation must reject:

- missing canonical files
- undeclared or missing read-order files
- non-canonical read-order stages
- `recipes/*.md` not referenced in read order
- local absolute paths, output paths, `.codex`, `capsules.sqlite`, secrets, remote URLs, raw `feedback`, `run_history`, or `artifact_manifest.json` on active package surfaces
- local-script entrypoints that escape the capsule directory
- asset paths that are absolute or escape the capsule directory
- migration metadata on active packages, including `source`, `legacy_version`, and `converted_at`

Validation should still allow executable scripts to contain normal implementation words and paths, because scripts are not injected as recipe text.

## Test Strategy

Use TDD for behavior changes:

- Loader tests prove default resolution points to `capsules/` and stage reads stay narrow.
- Validator tests prove unreferenced recipe files and migration metadata fail.
- Runtime tests prove `--capsule` prefers directory packages and only falls back to SQLite when no package exists.
- Real package tests validate all six active capsules and scan package surfaces for stale/evidence tokens.
- Existing SQLite/export/import tests keep passing to preserve legacy fallback.

## Success Criteria

- `capsules/` contains only active directory-style packages.
- legacy zip packages live under `archive/legacy_capsule_zips/`.
- code/docs no longer present "v3" as the user-facing current format.
- all six migrated capsules validate as active packages.
- no active capsule contains unreferenced recipe files or migration metadata.
- `run_video.py --capsule <name>` can load the canonical package first.
- SQLite remains available for legacy/local evidence workflows.
