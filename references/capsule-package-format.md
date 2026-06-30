# Capsule Package Format

Capsule packages are the current checked-in recipe format for Capsule Cinema. Active packages live at:

```text
capsules/<name>.capsule/
```

Legacy `.capsule.zip` exports are retained for audit and migration under:

```text
archive/legacy_capsule_zips/
```

SQLite remains supported as a local evidence store and explicit fallback. Raw evidence from SQLite, runs, feedback, QA reports, prompt snapshots, and final artifact paths must not be copied into active recipe files.

## Layout

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

## Stage Reading

The loader reads only the files named for the requested stage:

```text
routing    -> capsule.yaml + CARD.md
planning   -> recipes/structure.md + recipes/visual.md + recipes/audio.md + recipes/copy.md
generation -> contracts/runtime.yaml + recipes/motion.md + assets/index.yaml
qa         -> quality/rules.yaml + quality/release_gates.yaml
learning   -> learning/promoted_lessons.yaml
```

Every active `recipes/*.md` file must be listed in `capsule.yaml.read_order`. Hidden recipe files are rejected because they create stale, contradictory surfaces.

## Commands

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

Run package tests:

```bash
PYTHONPATH=lib python3.12 -m unittest discover -s tests/python -p 'test_capsule_package_*.py'
```

## Learning Boundary

Raw evidence is not recipe. Evidence can produce lesson candidates, and promoted lessons may be written into `learning/promoted_lessons.yaml`, `recipes/`, or `quality/rules.yaml` only after being generalized and stripped of run-specific material.
