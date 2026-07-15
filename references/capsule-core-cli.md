# Capsule Core CLI

`scripts/capsule.py` is the local creator surface for all repository-tracked v1 capsule packages. It discovers, explains, diagnoses, plans, and runs a capsule without asking whether the package uses a preset or a local runner.

## Discover and inspect

```bash
PYTHONPATH=lib:scripts python3.12 scripts/capsule.py list
PYTHONPATH=lib:scripts python3.12 scripts/capsule.py show ecommerce_product_showcase
PYTHONPATH=lib:scripts python3.12 scripts/capsule.py doctor ecommerce_product_showcase
```

After argument parsing succeeds, each requested operation writes exactly one JSON result envelope to stdout with `ok`, `status`, `data`, and `issues`. An issue contains a stable `code`, human message, subject, remediation, severity, and optional details.

The process uses exit code `0` for a successful operation and exit code `1` for an operational or validation failure represented by that JSON envelope. An argparse syntax error or missing required CLI argument instead prints usage diagnostics to stderr, exits with exit code `2`, and stdout remains empty.

## Plan through one interface

```bash
PYTHONPATH=lib:scripts python3.12 scripts/capsule.py plan ecommerce_product_showcase \
  --topic "Ink flowers opening into a summer landscape" \
  --params-json '{"aspect_ratio":"9:16"}' \
  --output-dir output/art-motion-plan
```

`plan` validates and prepares dispatch but does not claim that a deliverable video exists. The same command works for every runner family. It also writes the configured Instance, routing and planning contexts, and deterministic ProductionPlan under `<output-dir>/lifecycle/`.

## Run through one interface

```bash
PYTHONPATH=lib:scripts python3.12 scripts/capsule.py run ecommerce_product_showcase \
  --topic "A wool-felt strawberry mille-feuille" \
  --params-json '{"target_duration":20,"aspect_ratio":"9:16"}' \
  --output-dir output/felt-asmr-run
```

The command delegates to the existing production runner. The unified CLI forwards legacy runner logs to stderr and reserves stdout for the final JSON envelope; produced artifacts retain their current contracts.

Before runner start, `run` additionally enters the `generation` read stage and passes the lifecycle artifact paths through `CAPSULE_*_PATH` environment variables. After every runner attempt it enters `qa` and writes `lifecycle/capsule.effect-report.json`. A failed or unavailable runner produces a Core-derived `blocked` recommendation. The `learning` stage is never loaded automatically.

Declared capsule inputs may be supplied through `--params-json` even when they are not legacy preset flags. They are bound into `capsule.instance.json` and are not incorrectly forwarded as runner command-line flags. `--topic` fills an explicit `topic` input or the only unresolved required string input; ambiguous required inputs return `needs_input` instead of being guessed.

## Foundation boundary

This compatibility layer does not rewrite v1 packages or replace their existing runners. Core now owns configured Instances, progressive stage contexts, ProductionPlans, and EffectReports at the dispatch boundary. Capsule-specific production logic, quality checks, and learning promotion remain capsule-owned.
