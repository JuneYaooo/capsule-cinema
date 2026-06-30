# Capsule V3 Format

Capsule v3 is a skill-like package format for Capsule Cinema recipes. It keeps route selection, runtime contracts, stage-specific recipes, quality rules, assets, and promoted learning in separate files so the runtime can read only the files needed for each stage.

## Layout

```text
capsules_v3/<name>.capsule/
  capsule.yaml
  CARD.md
  contracts/
    runtime.yaml
    input_schema.yaml
  recipes/
  quality/
  learning/
  examples/
  assets/
  scripts/
```

## SQLite Status

SQLite remains supported as a legacy capsule source and local evidence store. New v3 recipe packages should not embed raw `run_history`, `feedback`, QA reports, prompt snapshots, or final artifact paths.

## Commands

Convert the first-slice default capsules:

```bash
python3.12 scripts/capsule_v3_convert.py \
  --from-db ~/.codex/video-production/capsules.sqlite \
  --from-zip-dir capsules \
  --names repo_showcase,life_sim,felt_asmr,guofeng_history,ecommerce_product_showcase,art_motion \
  --out capsules_v3 \
  --overwrite
```

Validate one capsule:

```bash
python3.12 scripts/capsule_v3_validate.py capsules_v3/felt_asmr.capsule
```

Run v3 loader tests:

```bash
PYTHONPATH=lib python3.12 -m unittest discover -s tests/python -p 'test_capsule_v3_*.py'
```

## Learning Boundary

Raw evidence is not recipe. Evidence can produce lesson candidates, and promoted lessons may be written into `learning/promoted_lessons.yaml`, `recipes/`, or `quality/rules.yaml` only after being generalized and stripped of run-specific material.
